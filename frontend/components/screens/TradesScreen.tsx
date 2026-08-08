'use client';

import React, { useMemo } from 'react';
import { Briefcase, ArrowUpRight, ArrowDownRight, Play } from 'lucide-react';
import { Holding, TradeHistoryItem } from '@/app/types';
import { Card, Badge, EmptyState, Button, Stat } from '@/components/ui';
import { useCurrencyFormatter } from '@/lib/currencyContext';

interface TradesScreenProps {
  cash: number;
  holdings: Holding[];
  tradeHistory: TradeHistoryItem[];
  loading?: boolean;
  portfolioInitialized?: boolean;
  onNavigate: (tab: string) => void;
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
}

function trendLine(pnl: number): string {
  if (pnl > 0) return 'This has been going up recently.';
  if (pnl < 0) return 'This has been going down recently.';
  return 'No clear trend right now.';
}

export default function TradesScreen({
  cash, holdings, tradeHistory, loading = false, onNavigate, triggerToast,
}: TradesScreenProps) {
  const { formatMoney } = useCurrencyFormatter();

  const holdingsValue = useMemo(
    () => holdings.reduce((s, h) => s + h.shares * h.currentPrice, 0),
    [holdings]
  );

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Trades</p>
        <h1 className="page-title mt-1">What Jasper has done</h1>
        <p className="mt-2 max-w-xl muted-caption">Everything you own and every trade the AI has placed, explained in plain English.</p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="p-5"><Stat label="Cash available" value={formatMoney(cash)} caption="practice money ready to use" /></Card>
        <Card className="p-5"><Stat label="What I own" value={formatMoney(holdingsValue)} caption="current value of holdings" /></Card>
        <Card className="p-5"><Stat label="Open positions" value={String(holdings.length)} caption="assets the AI is holding" /></Card>
      </div>

      {/* Holdings */}
      <section>
        <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50" data-onboarding="trades-holdings">Holdings</h2>
        {loading ? (
          <div className="mt-4 grid gap-3">{[0,1,2].map(i => <div key={i} className="skeleton h-20 w-full" />)}</div>
        ) : holdings.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              icon={<Briefcase className="h-6 w-6" />}
              title="Nothing owned yet"
              description="The AI hasn't bought anything yet. Press START to let it begin trading with practice money."
              action={<Button onClick={() => onNavigate('home')}><Play className="h-4 w-4 fill-current" /> Go to Home</Button>}
            />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {holdings.map(h => {
              const value = h.shares * h.currentPrice;
              const up = h.pnlPercent >= 0;
              return (
                <Card key={h.symbol} className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 font-display font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-200">{h.symbol[0]}</span>
                      <div>
                        <p className="font-semibold text-slate-900 dark:text-slate-50">{h.symbol}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{h.name}</p>
                      </div>
                    </div>
                    {up ? <Badge tone="up"><ArrowUpRight className="h-3 w-3" />{h.pnlPercent}%</Badge> : <Badge tone="down"><ArrowDownRight className="h-3 w-3" />{h.pnlPercent}%</Badge>}
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    <div><dt className="text-slate-400 dark:text-slate-500">Amount</dt><dd className="tnum font-semibold text-slate-900 dark:text-slate-100">{h.shares.toLocaleString()}</dd></div>
                    <div><dt className="text-slate-400 dark:text-slate-500">Worth now</dt><dd className="tnum font-semibold text-slate-900 dark:text-slate-100">{formatMoney(value)}</dd></div>
                  </dl>
                  <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{trendLine(h.pnlPercent)}</p>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Trade history */}
      <section>
        <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">Trade history</h2>
        {loading ? (
          <div className="mt-4 grid gap-3">{[0,1,2,3].map(i => <div key={i} className="skeleton h-14 w-full" />)}</div>
        ) : tradeHistory.length === 0 ? (
          <p className="mt-4 rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
            No trades yet. Trades the AI places will appear here with a plain-English reason.
          </p>
        ) : (
          <div className="mt-4 divide-y divide-slate-100 rounded-card border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
            {tradeHistory.map(t => (
              <div key={t.id} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <span className={t.type === 'BUY' ? 'flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' : 'flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300'}>{t.type}</span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{t.type === 'BUY' ? 'Bought' : 'Sold'} <span className="tnum">{t.symbol}</span></p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{formatMoney(t.price)} each · {t.date}</p>
                  </div>
                </div>
                <p className="tnum text-sm font-semibold text-slate-700 dark:text-slate-200">{formatMoney(t.total)}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
