'use client';

import React, { useState } from 'react';
import { Play, RotateCcw, TrendingUp, Activity, Gauge, BarChart } from 'lucide-react';
import { Card, Button, Badge, Spinner } from '@/components/ui';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface BacktestScreenProps {
  selectedAlphaFactors: string[];
  removeAlphaFactor: (factorName: string) => void;
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
  onNavigate: (tab: string) => void;
}

interface Result { performance?: { sharpe_ratio?: number; max_drawdown?: number }; capital?: { total_return?: number; final_value?: number }; }

export default function BacktestScreen({ selectedAlphaFactors, removeAlphaFactor, triggerToast, onNavigate }: BacktestScreenProps) {
  const [stratName, setStratName] = useState('My first strategy');
  const [engine, setEngine] = useState('vibetrader');
  const [feed, setFeed] = useState('dailyohlc');
  const [capital, setCapital] = useState<number>(100000);
  const [assetScope, setAssetScope] = useState('NVDA, AAPL, MSFT, BTC, ETH');
  const [dateFrom, setDateFrom] = useState('2024-01-01');
  const [dateTo, setDateTo] = useState('2025-04-01');
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<Result | null>(null);

  const run = async () => {
    setRunning(true); setProgress(0); setResult(null);
    const tick = setInterval(() => setProgress(p => (p >= 90 ? p : p + 12)), 120);
    try {
      const res = await fetch(`${API_URL}/api/v1/backtest/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: stratName,
          factor_ids: selectedAlphaFactors.map((n, i) => `f-${i + 1}`),
          start_date: dateFrom, end_date: dateTo, initial_capital: capital,
          asset_scope: assetScope.split(',').map(s => s.trim()).filter(Boolean),
          engine, feed,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error('Backtest failed');
      setResult(data);
      setProgress(100);
      triggerToast('success', 'Backtest finished', 'Check the results below.');
    } catch {
      triggerToast('error', 'Could not run backtest', 'Check the inputs and try again.');
    } finally {
      clearInterval(tick);
      setRunning(false);
    }
  };

  const ret = Number(result?.capital?.total_return ?? 0);
  const sharpe = Number(result?.performance?.sharpe_ratio ?? 0);
  const dd = Number(result?.performance?.max_drawdown ?? 0);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Research</p>
        <h1 className="page-title mt-1">Backtesting</h1>
        <p className="mt-2 max-w-xl muted-caption">Test a strategy against past market data to see how it might have performed. Ideal for curious users.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Config */}
        <Card className="p-6 lg:col-span-5">
          <h2 className="text-base font-display font-bold text-slate-900 dark:text-slate-50">Configuration</h2>
          <div className="mt-4 space-y-4">
            <div><label htmlFor="backtest-strategy-name" className="field-label">Strategy name</label><input id="backtest-strategy-name" className="input" value={stratName} onChange={e => setStratName(e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label htmlFor="backtest-engine" className="field-label">Engine</label><select id="backtest-engine" className="input" value={engine} onChange={e => setEngine(e.target.value)}><option>vibetrader</option><option>backtrader</option></select></div>
              <div><label htmlFor="backtest-feed" className="field-label">Feed</label><select id="backtest-feed" className="input" value={feed} onChange={e => setFeed(e.target.value)}><option>dailyohlc</option><option>intraday</option></select></div>
            </div>
            <div><label htmlFor="backtest-capital" className="field-label">Starting capital</label><input id="backtest-capital" type="number" className="input" value={capital} onChange={e => setCapital(Number(e.target.value))} /></div>
            <div><label htmlFor="backtest-assets" className="field-label">Assets (comma separated)</label><input id="backtest-assets" className="input" value={assetScope} onChange={e => setAssetScope(e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label htmlFor="backtest-from" className="field-label">From</label><input id="backtest-from" type="date" className="input" value={dateFrom} onChange={e => setDateFrom(e.target.value)} /></div>
              <div><label htmlFor="backtest-to" className="field-label">To</label><input id="backtest-to" type="date" className="input" value={dateTo} onChange={e => setDateTo(e.target.value)} /></div>
            </div>

            <div className="rounded-control border border-slate-200 p-3 dark:border-slate-700">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Alpha factors</p>
                <button onClick={() => onNavigate('alphazoo')} className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-400">Add from Alpha Zoo</button>
              </div>
              {selectedAlphaFactors.length === 0 ? (
                <p className="mt-2 text-xs text-slate-400">No factors selected yet.</p>
              ) : (
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedAlphaFactors.map(f => (
                    <Badge key={f} tone="accent">{f}<button onClick={() => removeAlphaFactor(f)} className="ml-1 font-bold hover:opacity-70">×</button></Badge>
                  ))}
                </div>
              )}
            </div>

            <Button className="w-full" onClick={run} disabled={running}><Play className="h-4 w-4 fill-current" />{running ? 'Running...' : 'Run backtest'}</Button>
          </div>
        </Card>

        {/* Results */}
        <Card className="p-6 lg:col-span-7">
          <div className="flex items-center gap-2"><BarChart className="h-5 w-5 text-brand-500" /><h2 className="text-base font-display font-bold text-slate-900 dark:text-slate-50">Results</h2></div>

          {running ? (
            <div className="mt-8 flex flex-col items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
              <Spinner />
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${progress}%` }} /></div>
              <span>Testing your strategy over historical data...</span>
            </div>
          ) : result ? (
            <div className="mt-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
                  <p className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400"><TrendingUp className="h-3.5 w-3.5" /> Total return</p>
                  <p className={`mt-1 text-2xl font-display font-bold tnum ${ret >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{ret >= 0 ? '+' : ''}{ret.toFixed(2)}%</p>
                </div>
                <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
                  <p className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400"><Activity className="h-3.5 w-3.5" /> Sharpe ratio</p>
                  <p className="tnum mt-1 text-2xl font-display font-bold text-slate-900 dark:text-slate-50">{sharpe.toFixed(2)}</p>
                </div>
                <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
                  <p className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400"><Gauge className="h-3.5 w-3.5" /> Max drawdown</p>
                  <p className="tnum mt-1 text-2xl font-display font-bold text-rose-600 dark:text-rose-400">{dd.toFixed(2)}%</p>
                </div>
                <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Final value</p>
                  <p className="tnum mt-1 text-2xl font-display font-bold text-slate-900 dark:text-slate-50">{result.capital?.final_value ? result.capital.final_value.toLocaleString() : '-'}</p>
                </div>
              </div>
              <Button variant="secondary" size="sm" onClick={() => { setResult(null); triggerToast('info', 'Cleared', 'Results cleared.'); }}><RotateCcw className="h-4 w-4" /> Run again</Button>
            </div>
          ) : (
            <div className="mt-8 rounded-control border border-dashed border-slate-300 bg-slate-50/50 px-6 py-12 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
              Configure the strategy on the left and press Run backtest. Results will show here.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
