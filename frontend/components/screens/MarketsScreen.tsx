'use client';

import React, { useCallback, useEffect, useState, useRef } from 'react';
import { TrendingUp, Compass, Microscope, Star, Sparkles, Search, X } from 'lucide-react';
import { Card } from '@/components/ui';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { DEFAULT_DEVICE_ID } from '@/lib/constants';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface MarketItem {
  symbol: string;
  name: string;
  change?: number;
  price_usd?: number | null;
  source?: string;
  asset_class: 'crypto' | 'stocks' | 'cn';
  inWatchlist?: boolean;
}

function deviceHeaders(): Record<string, string> {
  let deviceId: string;
  try {
    deviceId = getOrCreateDeviceId();
  } catch {
    deviceId = DEFAULT_DEVICE_ID;
  }
  return { 'X-Device-ID': deviceId };
}

function normalizeCrypto(items: any[]): MarketItem[] {
  return (items || [])
    .map((c: any) => ({
      symbol: (c.symbol || c.base_symbol || c.ticker || '').toUpperCase(),
      name: c.name || c.base_name || c.symbol || '',
      change: Number(c.change || c.price_change_24h || c.change_24h || 0),
      price_usd: c.price_usd ?? null,
      source: c.source || undefined,
      asset_class: 'crypto' as const,
    }))
    .filter((i: MarketItem) => i.symbol);
}

function normalizeStocks(items: any[]): MarketItem[] {
  return (items || [])
    .map((s: any) => {
      const rawType = (s.type || s.asset_class || '').toLowerCase();
      let asset_class: MarketItem['asset_class'] = 'stocks';
      if (rawType === 'cn' || rawType === 'a_share' || rawType === 'a-share') {
        asset_class = 'cn';
      }
      return {
        symbol: (s.symbol || s.ticker || '').toUpperCase(),
        name: s.name || s.company || s.symbol || '',
        price_usd: s.price ?? s.price_usd ?? null,
        source: s.exchange || s.source || undefined,
        asset_class,
        change: undefined,
      };
    })
    .filter((i: MarketItem) => i.symbol);
}

type Filter = 'all' | 'crypto' | 'stocks';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'crypto', label: 'Crypto' },
  { key: 'stocks', label: 'Stocks' },
];

function assetBadge(ac: MarketItem['asset_class']) {
  if (ac === 'crypto') return <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">Crypto</span>;
  if (ac === 'cn') return <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">CN</span>;
  return <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">Stock</span>;
}

export default function MarketsScreen({ onNavigate }: { onNavigate: (tab: string) => void; triggerToast?: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void }) {
  const [newTokens, setNewTokens] = useState<MarketItem[]>([]);
  const [trending, setTrending] = useState<MarketItem[]>([]);
  const [watchlist, setWatchlist] = useState<MarketItem[]>([]);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MarketItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshWatchlist = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/watchlist`, { headers: deviceHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      const items: MarketItem[] = (data.watchlist || []).map((w: any) => ({
        symbol: (w.symbol || '').toUpperCase(),
        name: w.name || w.symbol || '',
        price_usd: w.price_usd ?? null,
        asset_class: (w.asset_class === 'stocks' || w.asset_class === 'cn' ? w.asset_class : 'crypto') as MarketItem['asset_class'],
        change: 0,
      }));
      setWatchlist(items);
    } catch {
      /* ignore */
    }
  }, []);

  const toggleWatch = useCallback(
    async (item: MarketItem) => {
      const symbol = item.symbol;
      const current = watchlist.some((w) => w.symbol === symbol);
      try {
        if (current) {
          await fetch(`${API_URL}/api/v1/watchlist/${symbol}`, { method: 'DELETE', headers: deviceHeaders() });
        } else {
          await fetch(`${API_URL}/api/v1/watchlist`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...deviceHeaders() },
            body: JSON.stringify({ symbol, name: item.name, asset_class: item.asset_class, source: item.source }),
          });
        }
      } catch {
        return;
      }
      await refreshWatchlist();
    },
    [watchlist, refreshWatchlist],
  );

  useEffect(() => {
    mounted.current = true;
    (async () => {
      const [disco, trend, watchRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/memecoin/discover?limit=8`).catch(() => null),
        fetch(`${API_URL}/api/v1/memecoin/trending?limit=8`).catch(() => null),
        fetch(`${API_URL}/api/v1/watchlist`, { headers: deviceHeaders() }).catch(() => null),
      ]);
      if (mounted.current) {
        if (disco && disco.ok) {
          const data = await disco.json();
          setNewTokens(normalizeCrypto(data.results || data.coins || data.data || []));
        }
        if (trend && trend.ok) {
          const data = await trend.json();
          setTrending(normalizeCrypto(data.results || data.coins || data.data || []));
        }
        if (watchRes && watchRes.ok) {
          const data = await watchRes.json();
          const items: MarketItem[] = (data.watchlist || []).map((w: any) => ({
            symbol: (w.symbol || '').toUpperCase(),
            name: w.name || w.symbol || '',
            price_usd: w.price_usd ?? null,
            asset_class: (w.asset_class === 'stocks' || w.asset_class === 'cn' ? w.asset_class : 'crypto') as MarketItem['asset_class'],
            change: 0,
          }));
          setWatchlist(items);
        }
        setLoading(false);
      }
    })();
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      setSearching(false);
      return;
    }

    setSearching(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      try {
        const [cryptoRes, stockRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/memecoin/search?q=${encodeURIComponent(q)}&limit=15`).catch(() => null),
          fetch(`${API_URL}/api/v1/symbols?search=${encodeURIComponent(q)}`).catch(() => null),
        ]);

        const cryptoItems = cryptoRes && cryptoRes.ok
          ? normalizeCrypto((await cryptoRes.json()).results || (await cryptoRes.json()).coins || [])
          : [];
        const stockItems = stockRes && stockRes.ok
          ? normalizeStocks((await stockRes.json()).symbols || (await stockRes.json()).results || [])
          : [];

        const bySymbol = new Map<string, MarketItem>();
        for (const item of cryptoItems) bySymbol.set(item.symbol, item);
        for (const item of stockItems) {
          if (!bySymbol.has(item.symbol)) bySymbol.set(item.symbol, item);
        }

        setSearchResults(Array.from(bySymbol.values()));
      } catch {
        setSearchResults([]);
      } finally {
        if (mounted.current) setSearching(false);
      }
    }, 350);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchQuery]);

  const watched = (m: MarketItem) => watchlist.some((w) => w.symbol === m.symbol);

  const filteredSearch = searchResults.filter((item) => {
    if (filter === 'all') return true;
    if (filter === 'crypto') return item.asset_class === 'crypto';
    return item.asset_class === 'stocks' || item.asset_class === 'cn';
  });

  const renderCard = (item: MarketItem) => (
    <Card key={item.symbol} hover className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate font-semibold text-slate-900 dark:text-slate-50">{item.symbol}</p>
            {assetBadge(item.asset_class)}
          </div>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{item.name || item.symbol}</p>
          {item.source && item.asset_class !== 'crypto' && (
            <p className="truncate text-[10px] text-slate-400 dark:text-slate-500">{item.source}</p>
          )}
        </div>
        <span
          role="button"
          tabIndex={0}
          aria-label={watched(item) ? `Remove ${item.symbol} from watchlist` : `Add ${item.symbol} to watchlist`}
          data-onboarding="watchlist-star"
          onClick={() => toggleWatch(item)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleWatch(item); } }}
          className={
            watched(item)
              ? 'shrink-0 cursor-pointer text-amber-400 transition hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
              : 'shrink-0 cursor-pointer text-slate-300 transition hover:scale-110 hover:text-amber-400 dark:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
          }
        >
          <Star className="h-4 w-4 fill-current" />
        </span>
      </div>
      {typeof item.change === 'number' && item.asset_class === 'crypto' && (
        <p className={`tnum mt-1 text-sm font-semibold ${item.change >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
          {item.change >= 0 ? '+' : ''}{item.change}%
        </p>
      )}
      {typeof item.price_usd === 'number' && item.price_usd > 0 && (
        <p className="tnum mt-1 text-xs text-slate-400 dark:text-slate-500">${Number(item.price_usd).toLocaleString(undefined, { maximumFractionDigits: 8 })}</p>
      )}
    </Card>
  );

  const isSearching = searchQuery.trim().length > 0;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Markets</p>
        <h1 className="page-title mt-1">What is worth buying today</h1>
        <p className="mt-2 max-w-xl muted-caption">New launches, what is trending right now, and the symbols you are watching.</p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Search stocks, crypto, tokens..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-card border border-slate-200 bg-white py-2.5 pl-10 pr-10 text-sm text-slate-900 placeholder-slate-400 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-50 dark:placeholder-slate-500"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Filter chips */}
      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              filter === f.key
                ? 'bg-brand-500 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Search results */}
      {isSearching && (
        <section>
          <div className="flex items-center gap-2">
            <Search className="h-5 w-5 text-brand-500" />
            <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">
              {searching ? 'Searching...' : `Results for "${searchQuery.trim()}"`}
            </h2>
          </div>
          {searching ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="skeleton h-24 w-full" />
              ))}
            </div>
          ) : filteredSearch.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">No results found.</p>
          ) : (
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {filteredSearch.map(renderCard)}
            </div>
          )}
        </section>
      )}

      {/* Default sections (hidden during search) */}
      {!isSearching && (
        <>
          {/* My watchlist */}
          <section>
            <div className="flex items-center gap-2">
              <Star className="h-5 w-5 text-amber-400" />
              <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">My watchlist</h2>
            </div>
            {loading ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="skeleton h-24 w-full" />
                ))}
              </div>
            ) : watchlist.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
                Nothing pinned yet. Tap the star on a coin below to watch it here.
              </p>
            ) : (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {watchlist.map(renderCard)}
              </div>
            )}
          </section>

          {/* Trending right now */}
          <section>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-brand-500" />
              <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">Trending right now</h2>
            </div>
            {loading ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="skeleton h-24 w-full" />
                ))}
              </div>
            ) : trending.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Nothing trending yet. Check back soon.</p>
            ) : (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {trending.map(renderCard)}
              </div>
            )}
          </section>

          {/* New tokens (discover) */}
          <section>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-violet-500" />
              <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">New tokens</h2>
            </div>
            {loading ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="skeleton h-24 w-full" />
                ))}
              </div>
            ) : newTokens.length === 0 ? (
              <p className="mt-4 flex items-center gap-3 rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-8 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
                <Compass className="h-5 w-5 text-brand-500" /> No new launches right now. Check back soon.
              </p>
            ) : (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {newTokens.map(renderCard)}
              </div>
            )}
          </section>
        </>
      )}

      {/* Advanced research (hidden from beginners, optional) */}
      <Card className="flex flex-col gap-2 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <Microscope className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Advanced research tools</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Backtesting and factor research, for curious users.</p>
          </div>
        </div>
        <button type="button" onClick={() => onNavigate('backtest')} className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
          Open research
        </button>
      </Card>
    </div>
  );
}
