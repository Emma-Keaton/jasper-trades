'use client';

import React, { useCallback, useEffect, useState, useRef } from 'react';
import { TrendingUp, Compass, Microscope, Star, Sparkles } from 'lucide-react';
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

function normalize(items: any[]): MarketItem[] {
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

export default function MarketsScreen({ onNavigate }: { onNavigate: (tab: string) => void; triggerToast?: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void }) {
  const [newTokens, setNewTokens] = useState<MarketItem[]>([]);
  const [trending, setTrending] = useState<MarketItem[]>([]);
  const [watchlist, setWatchlist] = useState<MarketItem[]>([]);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

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
          setNewTokens(normalize(data.results || data.coins || data.data || []));
        }
        if (trend && trend.ok) {
          const data = await trend.json();
          setTrending(normalize(data.results || data.coins || data.data || []));
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

  const watched = (m: MarketItem) => watchlist.some((w) => w.symbol === m.symbol);

  const renderCard = (item: MarketItem) => (
    <Card key={item.symbol} hover className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-900 dark:text-slate-50">{item.symbol}</p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{item.name || item.symbol}</p>
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

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Markets</p>
        <h1 className="page-title mt-1">What is worth buying today</h1>
        <p className="mt-2 max-w-xl muted-caption">New launches, what is trending right now, and the symbols you are watching.</p>
      </div>

      {/* My watchlist */}
      <section>
        <div className="flex items-center gap-2">
          <Star className="h-5 w-5 text-amber-400" />
          <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">My watchlist</h2>
        </div>
        {loading ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24 w-full" />)}</div>
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
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24 w-full" />)}</div>
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
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24 w-full" />)}</div>
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

      {/* Advanced research (hidden from beginners, optional) */}
      <Card className="flex flex-col gap-2 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"><Microscope className="h-5 w-5" /></span>
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