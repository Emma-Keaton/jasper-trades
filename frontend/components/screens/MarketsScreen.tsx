'use client';

import React, { useState, useEffect } from 'react';
import { TrendingUp, ArrowUpRight, ArrowDownRight, Compass, Microscope } from 'lucide-react';
import { Card, Badge, RowLink } from '@/components/ui';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Action = 'BUY' | 'HOLD' | 'SELL';
interface Recommend { symbol: string; name: string; action: Action; reason: string; confidence: number; }
interface TrendingCoin { symbol: string; name: string; change: number; }

const actionCopy: Record<Action, { label: string; tone: 'up' | 'down' | 'warning'; explain: string }> = {
  BUY: { label: 'Buy', tone: 'up', explain: 'AI thinks this will go up.' },
  HOLD: { label: 'Hold', tone: 'warning', explain: 'AI sees no clear direction.' },
  SELL: { label: 'Sell', tone: 'down', explain: 'AI thinks this will fall.' },
};

interface MarketsScreenProps {
  onNavigate: (tab: string) => void;
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
}

export default function MarketsScreen({ onNavigate }: MarketsScreenProps) {
  const [recs, setRecs] = useState<Recommend[]>([]);
  const [trending, setTrending] = useState<TrendingCoin[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [mRes, tRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/market-data/trending`).catch(() => null),
          fetch(`${API_URL}/api/v1/memecoin/discover?limit=8`).catch(() => null),
        ]);
        if (tRes && tRes.ok) {
          const data = await tRes.json();
          const coins = Array.isArray(data) ? data : data?.coins || data?.data || [];
          setTrending(coins.slice(0, 8).map((c: any) => ({
            symbol: (c.symbol || c.ticker || '').toUpperCase(),
            name: c.name || c.symbol || '',
            change: Number(c.change || c.price_change_percent || c.change_24h || 0),
          })).filter((c: any) => c.symbol));
        }
        if (mRes && mRes.ok) {
          const data = await mRes.json();
          const items = Array.isArray(data) ? data : data?.recommendations || data?.recs || data?.trending || [];
          if (Array.isArray(items) && items.length) {
            setRecs(items.slice(0, 5).map((r: any) => ({
              symbol: (r.symbol || r.ticker || '').toUpperCase(),
              name: r.name || r.symbol || '',
              action: (r.action || r.rating || r.signal || 'HOLD').toUpperCase() as Action,
              reason: r.reason || r.summary || '',
              confidence: Number(r.confidence || r.score || 0),
            })).filter((r: any) => r.symbol && actionCopy[(r.action || 'HOLD') as Action]));
          }
        }
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Markets</p>
        <h1 className="page-title mt-1">What is worth buying today</h1>
        <p className="mt-2 max-w-xl muted-caption">Plain-English ideas from the AI, plus what is trending right now.</p>
      </div>

      {/* AI Recommendations */}
      <section>
        <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50" data-onboarding="markets-recs">AI recommendations</h2>
        {loading ? (
          <div className="mt-4 grid gap-3">{[0,1,2].map(i => <div key={i} className="skeleton h-24 w-full" />)}</div>
        ) : recs.length === 0 ? (
          <div className="mt-4 flex items-center gap-3 rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-8 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
            <Compass className="h-5 w-5 text-brand-500" /> No recommendations yet. Check back soon.
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            {recs.map(r => {
              const a = actionCopy[r.action] || actionCopy.HOLD;
              return (
                <Card key={r.symbol} hover className="flex flex-col p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-display text-lg font-bold text-slate-900 dark:text-slate-50">{r.symbol}</p>
                      <p className="text-sm text-slate-500 dark:text-slate-400">{r.name}</p>
                    </div>
                    <Badge tone={a.tone} className="uppercase">{a.label}</Badge>
                  </div>
                  <p className="mt-3 flex-1 text-sm text-slate-600 dark:text-slate-300">{r.reason || a.explain}</p>
                  <div className="mt-4 flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
                    <span>Confidence</span>
                    <span className="tnum font-semibold text-slate-700 dark:text-slate-200">{r.confidence ? `${r.confidence}%` : 'n/a'}</span>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Trending */}
      <section>
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-brand-500" />
          <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">Trending right now</h2>
        </div>
        {trending.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Nothing trending yet.</p>
        ) : (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {trending.map(t => (
              <Card key={t.symbol} hover className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-slate-900 dark:text-slate-50">{t.symbol}</p>
                  {t.change >= 0 ? <ArrowUpRight className="h-4 w-4 text-emerald-500" /> : <ArrowDownRight className="h-4 w-4 text-rose-500" />}
                </div>
                <p className={`tnum mt-1 text-sm font-semibold ${t.change >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                  {t.change >= 0 ? '+' : ''}{t.change}%
                </p>
              </Card>
            ))}
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
        <RowLink onClick={() => onNavigate('backtest')}>Open research</RowLink>
      </Card>
    </div>
  );
}
