'use client';

import React, { useState, useMemo } from 'react';
import { Bot, Play, Pause, Sparkles, ArrowRight, Activity } from 'lucide-react';
import { Holding, TradeHistoryItem } from '@/app/types';
import { EquityDataPoint } from '@/hooks/usePortfolioHistory';
import { Card, Stat, Button, Badge, EmptyState, RowLink } from '@/components/ui';
import { useCurrencyFormatter } from '@/lib/currencyContext';
import { StepId } from '@/components/screens/SettingsScreen';
import { fetchPreferences, fetchTradingMode, savePreferences } from '@/lib/preferences';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const DEFAULT_WATCHING = ['BTC', 'ETH', 'EURUSD', 'AAPL', 'SOL'];

interface HomeScreenProps {
  cash: number;
  holdings: Holding[];
  tradeHistory: TradeHistoryItem[];
  equityData?: EquityDataPoint[];
  portfolioInitialized?: boolean;
  loading?: boolean;
  backendConnected?: boolean;
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
  onNavigate: (tab: string, opts?: { defaultOpen?: StepId }) => void;
}

const actionText: Record<string, string> = { BUY: 'Bought', SELL: 'Sold' };

// Shared helper: run-state read persisted in the DB (per device).
export async function isAiRunning(): Promise<boolean> {
  const prefs = await fetchPreferences();
  return prefs.ai_running === true;
}

export default function HomeScreen({
  cash, holdings, tradeHistory, equityData = [],
  loading = false, backendConnected = false, triggerToast, onNavigate,
}: HomeScreenProps) {
  const { formatMoney } = useCurrencyFormatter();
  const [running, setRunning] = useState<boolean>(false);
  const [starting, setStarting] = useState(false);
  const [tradingMode, setTradingMode] = useState<'practice' | 'live' | null>(null);

  React.useEffect(() => {
    isAiRunning().then(setRunning);
    fetchTradingMode().then((m) => setTradingMode(m));
  }, []);

  const watching = useMemo(() => {
    const owned = holdings.map(h => h.symbol);
    return Array.from(new Set([...owned, ...DEFAULT_WATCHING])).slice(0, 6).join(', ');
  }, [holdings]);

  const totalValue = useMemo(
    () => holdings.reduce((s, h) => s + h.shares * h.currentPrice, 0) + cash,
    [holdings, cash]
  );

  const todayPnl = useMemo(() => {
    if (equityData.length > 0 && equityData[0].y > 0) {
      const change = totalValue - equityData[0].y;
      return { value: change, pct: (change / equityData[0].y) * 100 };
    }
    return { value: 0, pct: 0 };
  }, [equityData, totalValue]);

  const recentTrades = useMemo(() => tradeHistory.slice(0, 3), [tradeHistory]);

  const setRunState = (next: boolean) => {
    setRunning(next);
    savePreferences({ ai_running: next });
  };

  const handleStartStop = async () => {
    // Stopping is always allowed.
    if (running) {
      setStarting(true);
      try {
        for (const name of ['director', 'quant', 'risk', 'execution']) {
          await fetch(`${API_URL}/api/v1/agents/${name}/stop`, { method: 'POST' }).catch(() => null);
        }
        setRunState(false);
      } finally {
        setStarting(false);
      }
      return;
    }

    // First-run guard: a trading mode must be chosen before starting.
    const mode = tradingMode;
    if (!mode) {
      triggerToast('info', 'Pick a mode first', 'Choose Paper or Live trading before starting.');
      onNavigate('settings', { defaultOpen: 'mode' });
      return;
    }

    // Live-mode guard: confirm before trading with real money.
    if (mode === 'live') {
      const ok = window.confirm(
        'Live trading uses REAL money with your connected wallets and brokers.\n\nAre you sure you want to start?'
      );
      if (!ok) return;
    }

    setStarting(true);
    try {
      for (const name of ['director', 'quant', 'risk', 'execution']) {
        await fetch(`${API_URL}/api/v1/agents/${name}/start`, { method: 'POST' }).catch(() => null);
      }
      setRunState(true);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="eyebrow">Home</p>
        <h1 className="page-title mt-1">Your AI Trader</h1>
        <p className="mt-2 max-w-xl muted-caption">Jasper watches markets and trades for you with practice money. Nothing real unless you say so.</p>
      </div>

      {/* AI TRADER STATUS CARD */}
      <Card className="relative overflow-hidden p-6 md:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-brand-100/70 blur-2xl dark:bg-brand-500/10" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-lg">
            <div className="flex items-center gap-2">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white"><Bot className="h-5 w-5" /></span>
              <span className="font-display text-lg font-bold text-slate-900 dark:text-slate-50">The AI Trader</span>
              <Badge tone={running ? 'up' : 'neutral'}>
                <span className={`h-1.5 w-1.5 rounded-full ${running ? 'bg-emerald-500' : 'bg-slate-400'}`} />{running ? 'Trading' : 'Paused'}
              </Badge>
            </div>
            <p className="mt-4 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              <Activity className="h-4 w-4 text-brand-500" />
              <span className="tnum">Watching {watching}</span>
            </p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {running
                ? 'Jasper is monitoring the markets and placing practice trades for you. Check Trades to see what it is doing.'
                : 'Press START and Jasper will begin watching and trading with practice money.'}
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button size="lg" onClick={handleStartStop} disabled={starting || !backendConnected} className="min-w-44" data-onboarding="home-start">
                {starting ? (<Sparkles className="h-5 w-5 animate-spin" />) : running ? (<Pause className="h-5 w-5" />) : (<Play className="h-5 w-5 fill-current" />)}
                {running ? 'Pause' : 'Start'}
              </Button>
              <p className="text-xs text-slate-400 dark:text-slate-500">Start with practice money. You can switch to real trading later in Settings.</p>
            </div>
          </div>

          <div className="grid w-full max-w-sm grid-cols-1 gap-6 rounded-card border border-slate-100 bg-white/60 p-5 dark:border-slate-800 dark:bg-slate-900/50 sm:grid-cols-2 lg:w-80" data-onboarding="home-stats">
            <Stat label="Balance" value={formatMoney(cash)} caption="practice money" tone="accent" />
            <Stat label="Today's P&L" value={
              <span className={todayPnl.value >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                {formatMoney(Math.abs(todayPnl.value))}{' '}
                <span className="text-base font-medium">({todayPnl.value >= 0 ? '+' : '-'}{Math.abs(todayPnl.pct).toFixed(1)}%)</span>
              </span>
            } caption="what I earned today" />
            <div className="sm:col-span-2"><Stat label="Total portfolio" value={formatMoney(totalValue)} caption="cash + what I own" /></div>
          </div>
        </div>
      </Card>

      {/* RECENT AI TRADES */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50" data-onboarding="recent-trades">Recent AI trades</h2>
          {tradeHistory.length > 0 && <RowLink onClick={() => onNavigate('trades')}>See all in Trades</RowLink>}
        </div>
        {loading ? (
          <div className="mt-4 grid gap-3">{[0,1,2].map(i => <div key={i} className="skeleton h-16 w-full" />)}</div>
        ) : recentTrades.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              icon={<Bot className="h-6 w-6" />}
              title="No trades yet"
              description="Press START and Jasper will begin watching the markets. Recent trades will show up here."
              action={<Button onClick={handleStartStop} disabled={!backendConnected}><Play className="h-4 w-4 fill-current" /> Start now</Button>}
            />
          </div>
        ) : (
          <div className="mt-4 divide-y divide-slate-100 rounded-card border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
            {recentTrades.map(t => (
              <div key={t.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className={t.type === 'BUY' ? 'flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' : 'flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300'}>{t.type}</span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{actionText[t.type] || t.type} <span className="tnum">{t.symbol}</span></p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{formatMoney(t.price)} each · {t.shares} · {t.date}</p>
                  </div>
                </div>
                <p className="text-sm font-semibold tnum text-slate-700 dark:text-slate-200">{formatMoney(t.total)}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {!running && (
        <Card className="flex items-start gap-3 p-4">
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
          <p className="text-sm text-slate-600 dark:text-slate-300">
            <span className="font-semibold">Next step:</span> connect signal sources in{' '}
            <button onClick={() => onNavigate('signals')} className="font-semibold text-brand-600 underline-offset-2 hover:underline dark:text-brand-400">Signals</button>{' '}
            so Jasper has places to look for ideas. This is optional.
          </p>
        </Card>
      )}
    </div>
  );
}
