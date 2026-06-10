'use client';

import React, { useState } from 'react';
import {
  TrendingUp,
  Play,
  RotateCcw,
  Plus,
  X,
  Calendar,
  BarChart,
  Award,
  Sparkles,
  Info
} from 'lucide-react';
import { Toast } from '@/app/page';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface BacktestTabProps {
  selectedAlphaFactors: string[];
  removeAlphaFactor: (factorName: string) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  setActiveTab: (tab: string) => void;
}

export default function BacktestTab({
  selectedAlphaFactors,
  removeAlphaFactor,
  triggerToast,
  setActiveTab
}: BacktestTabProps) {
  const [stratName, setStratName] = useState<string>('My Alpha Combo Strategy');
  const [selectedEngine, setSelectedEngine] = useState<string>('vibetrader');
  const [selectedFeed, setSelectedFeed] = useState<string>('dailyohlc');
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [assetScope, setAssetScope] = useState<string>('NVDA, AAPL, MSFT, BTC, ETH');
  const [dateFrom, setDateFrom] = useState<string>('2024-01-01');
  const [dateTo, setDateTo] = useState<string>('2025-04-01');
  const [runningBacktest, setRunningBacktest] = useState<boolean>(false);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [backtestCompleted, setBacktestCompleted] = useState<boolean>(false);
  const [selectedHeatBlock, setSelectedHeatBlock] = useState<{ year: number; month: string; value: string } | null>(null);

  // Backend data state
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [heatmapData, setHeatmapData] = useState<any>({});

  const handleTriggerBacktest = async () => {
    setRunningBacktest(true);
    setProgressPercent(0);
    setBacktestCompleted(false);

    try {
      const response = await fetch(`${API_URL}/api/v1/backtest/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: stratName,
          factor_ids: selectedAlphaFactors.map((name: string) => `f-${selectedAlphaFactors.indexOf(name) + 1}`),
          start_date: dateFrom,
          end_date: dateTo,
          initial_capital: initialCapital,
          asset_scope: assetScope.split(',').map((s: string) => s.trim()).filter((s: string) => s.length > 0),
          engine: selectedEngine,
          feed: selectedFeed,
        }),
      });

      if (!response.ok) {
        throw new Error('Backtest failed');
      }

      const result = await response.json();
      setBacktestResults(result);

      const progressInterval = setInterval(() => {
        setProgressPercent(prev => {
          if (prev >= 100) {
            clearInterval(progressInterval);
            return 100;
          }
          return prev + 10;
        });
      }, 100);

      setTimeout(() => {
        clearInterval(progressInterval);
        setProgressPercent(100);
        setRunningBacktest(false);
        setBacktestCompleted(true);
        triggerToast('success', 'Backtest Completed', `Sharpe: ${result.performance?.sharpe_ratio || 'N/A'} | Return: ${result.capital?.total_return || '0'}%`);
      }, 1500);

    } catch (error) {
      console.error('Backtest error:', error);
      setRunningBacktest(false);
      triggerToast('error', 'Backtest Failed', 'Could not run backtest simulation.');
    }
  };

  const getHeatmapColor = (p: number, label: string) => {
    if (label === '-') return 'bg-[#334155]';
    if (p >= 8.0) return 'bg-[#065F46] text-emerald-100 hover:ring-2 hover:ring-emerald-300';
    if (p >= 4.0) return 'bg-[#10B981] text-emerald-50 hover:ring-2 hover:ring-emerald-200';
    if (p >= 0.1) return 'bg-[#34D399] text-emerald-950 hover:ring-2 hover:ring-emerald-100';
    if (p === 0) return 'bg-[#64748B] text-slate-100';
    if (p >= -2.0) return 'bg-[#F87171] text-red-950 hover:ring-2 hover:ring-red-200';
    return 'bg-[#EF4444] text-red-50 hover:ring-2 hover:ring-red-350';
  };

  const defaultHeatmapData = {
    2024: [
      { month: 'Jan', val: '+5.2%', p: 5.2 },
      { month: 'Feb', val: '+3.1%', p: 3.1 },
      { month: 'Mar', val: '-1.4%', p: -1.4 },
      { month: 'Apr', val: '+8.7%', p: 8.7 },
      { month: 'May', val: '+2.3%', p: 2.3 },
      { month: 'Jun', val: '+4.5%', p: 4.5 },
      { month: 'Jul', val: '+1.1%', p: 1.1 },
      { month: 'Aug', val: '-0.8%', p: -0.8 },
      { month: 'Sep', val: '+3.9%', p: 3.9 },
      { month: 'Oct', val: '-2.5%', p: -2.5 },
      { month: 'Nov', val: '+6.1%', p: 6.1 },
      { month: 'Dec', val: '+4.2%', p: 4.2 }
    ],
    2025: [
      { month: 'Jan', val: '+6.8%', p: 6.8 },
      { month: 'Feb', val: '-2.1%', p: -2.1 },
      { month: 'Mar', val: '+7.4%', p: 7.4 },
      { month: 'Apr', val: '+3.9%', p: 3.9 },
      { month: 'May', val: '-', p: 0 },
      { month: 'Jun', val: '-', p: 0 },
      { month: 'Jul', val: '-', p: 0 },
      { month: 'Aug', val: '-', p: 0 },
      { month: 'Sep', val: '-', p: 0 },
      { month: 'Oct', val: '-', p: 0 },
      { month: 'Nov', val: '-', p: 0 },
      { month: 'Dec', val: '-', p: 0 }
    ]
  };

  const displayHeatmap = backtestResults?.heatmap || defaultHeatmapData;

  return (
    <div 
      data-onboarding="backtest-tour"
      className="flex flex-col gap-6 w-full"
    >

      {/* Visual Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight font-sans">Historical Backtester</h1>
        <p className="text-sm text-[#94A3B8]">Benchmarking active alpha signals against historical market coordinates.</p>
      </div>

      {/* STRATEGY CONFIGURATION */}
      <div 
        data-onboarding="strategy-form"
        className="bg-[#1E293B] border border-[#475569] p-5 rounded-xl flex flex-col gap-5"
      >
        <div className="flex items-center gap-2 border-b border-[#475569]/30 pb-2 leading-none">
          <BarChart className="w-5 h-5 text-[#3B82F6]" />
          <span className="font-mono text-[10px] font-bold uppercase text-[#94A3B8]">Strategy Configurator Desk</span>
        </div>

        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Custom Strategy Profile Name</label>
            <input
              type="text"
              value={stratName}
              onChange={(e) => setStratName(e.target.value)}
              className="h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white uppercase font-mono focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Backtester Engine Engine</label>
            <select
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value)}
              className="h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="vibetrader">Vibe-Trading Multi-Factor Engine</option>
              <option value="singlefactor">Standard Single Factor Engine</option>
              <option value="vectorized">Vectorized Pandas DataFrame Engine</option>
              <option value="eventauthoritative">Event-driven authoritative engine</option>
            </select>
          </div>

          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Tick Data Resolution</label>
            <select
              value={selectedFeed}
              onChange={(e) => setSelectedFeed(e.target.value)}
              className="h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="dailyohlc">Daily OHLCV Candles</option>
              <option value="hourlyohlc">Hourly OHLCV Candles</option>
              <option value="millisecondtick">Millisecond Orderbook Trades</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pb-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Asset Index Scope</label>
            <input
              type="text"
              value={assetScope}
              onChange={(e) => setAssetScope(e.target.value)}
              placeholder="e.g., NVDA, AAPL, MSFT, BTC, ETH"
              className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Initial Investment Capital</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              placeholder="100000"
              className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Interval Start</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Interval Terminate</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
            />
          </div>
        </div>

        {/* Selected Alpha Factors */}
        <div className="border-t border-[#475569]/20 pt-4 flex flex-col gap-2.5">
          <label className="text-xs text-[#94A3B8] font-mono leading-none font-bold uppercase tracking-wider">Active Alpha Factors Under Test</label>
          <div 
            data-onboarding="alpha-factors"
            className="flex items-center gap-2 flex-wrap"
          >
            {selectedAlphaFactors.length > 0 ? (
              selectedAlphaFactors.map(factor => (
                <div key={factor} className="bg-[#3B82F6]/10 text-[#3B82F6] border border-[#3B82F6]/30 pl-3 pr-1.5 py-1 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5">
                  <span>{factor}</span>
                  <button onClick={() => removeAlphaFactor(factor)} className="p-0.5 hover:bg-[#3B82F6]/20 rounded text-[#3B82F6] hover:text-white transition">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            ) : (
              <span className="text-xs text-[#EF4444] font-semibold">No elements selected. Strategy will operate on neutral market parameters.</span>
            )}

            <button
              onClick={() => setActiveTab('alphazoo')}
              className="bg-[#0F172A] border border-[#475569] hover:border-[#3b82f6] hover:text-[#3B82F6] text-[#94A3B8] text-[10px] font-mono font-bold px-3 py-1.5 rounded-lg outline-none transition"
            >
              + BROWSE ALPHA ZOO (452 factors)
            </button>
          </div>
        </div>

        {/* Action Run Button */}
        <div className="border-t border-[#475569]/30 pt-4">
          <button
            onClick={handleTriggerBacktest}
            disabled={runningBacktest}
            data-onboarding="run-backtest"
            className="bg-[#10B981] hover:bg-[#059669] text-white py-3 px-8 rounded-lg text-xs font-black tracking-widest font-sans flex items-center justify-center gap-2 transition outline-none disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-current" /> RUN BACKTEST SIMULATOR
          </button>
        </div>

      </div>

      {/* Progress Bar */}
      {runningBacktest && (
        <div 
          data-onboarding="progress-bar"
          className="bg-[#1E293B] border border-[#3B82F6] p-6 rounded-xl flex flex-col gap-3 shadow-xl animate-pulse"
        >
          <div className="flex items-center justify-between font-mono text-xs text-[#94A3B8]">
            <span className="flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-[#3B82F6] animate-spin" />
              Simulating factor equations & fetching indices...
            </span>
            <span className="font-bold text-[#3B82F6]">{progressPercent}%</span>
          </div>
          <div className="w-full h-2 bg-[#0F172A] rounded-full overflow-hidden border border-[#475569]">
            <div
              className="h-full bg-gradient-to-r from-[#3B82F6] to-[#10B981] transition-all duration-150 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* RESULTS */}
      {backtestCompleted && (
        <div className="flex flex-col gap-6 animate-fade-in">

          <div className="flex items-center gap-2 border-b border-[#475569] pb-2 text-[#10B981] font-sans font-bold text-md select-none">
            <Award className="w-5 h-5 text-[#10B981]" /> SIMULATION SCORES RESULTS
          </div>

          {/* Performance Metrics */}
          <div 
            data-onboarding="performance-metrics"
            className="grid grid-cols-2 lg:grid-cols-6 gap-3.5 font-mono text-xs"
          >
            <div className="bg-[#1E293B] border border-[#475569] p-3.5 rounded-xl flex flex-col gap-1 justify-center relative group">
              <span className="text-[#94A3B8] text-[10px] uppercase">Simulation Yield</span>
              <span className="text-lg font-black text-[#10B981]">{backtestResults?.performance?.total_return || '+42.70%'}</span>
            </div>

            <div className="bg-[#1E293B] border border-[#475569] p-3.5 rounded-xl flex flex-col gap-1 justify-center relative group">
              <span className="text-[#94A3B8] text-[10px] uppercase">Annual Return</span>
              <span className="text-lg font-black text-white">{backtestResults?.performance?.annual_return || '+31.25%'}</span>
            </div>

            <div className="bg-[#1E293B] border border-[#475569] p-3.5 rounded-xl flex flex-col gap-1 justify-center relative group">
              <span className="text-[#94A3B8] text-[10px] uppercase">Max Drawdowns</span>
              <span className="text-lg font-black text-white">{backtestResults?.risk?.max_drawdown || '-12.42%'}</span>
            </div>

            <div className="bg-[#1E293B] border border-[#475569] p-3.5 rounded-xl flex flex-col gap-1 justify-center relative group">
              <span className="text-[#94A3B8] text-[10px] uppercase">Sharpe Ratio Score</span>
              <span className="text-lg font-black text-[#3B82F6]">{backtestResults?.performance?.sharpe_ratio || '2.14'}</span>
            </div>

            <div className="bg-[#1E293B] border border-[#475569] p-3.5 rounded-xl flex flex-col gap-1 justify-center relative group">
              <span className="text-[#94A3B8] text-[10px] uppercase">Win Frequency</span>
              <span className="text-lg font-black text-white">{backtestResults?.performance?.win_rate || '64.30%'}</span>
            </div>

            <div className="bg-[#1E293B] border border-[#475569] p-3.5 rounded-xl flex flex-col gap-1 justify-center relative group">
              <span className="text-[#94A3B8] text-[10px] uppercase">Executed Trades</span>
              <span className="text-lg font-black text-white">{backtestResults?.stats?.total_trades || '247'} orders</span>
            </div>
          </div>

          {/* Equity Curve Chart */}
          <div 
            data-onboarding="equity-curve"
            className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col gap-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#475569]/30 pb-3 h-auto sm:h-10">
              <span className="font-bold text-[#F8FAFC] text-sm">Strategy Yield Curve Plot VS Benchmark Index</span>

              <div className="flex items-center gap-4 font-mono text-[10px]">
                <div className="flex items-center gap-1.5 text-white">
                  <span className="w-3.5 h-1 border-t-2 border-[#3B82F6]" />
                  <span>My Strategy ({backtestResults?.performance?.total_return || '+42.7%'})</span>
                </div>
                <div className="flex items-center gap-1.5 text-[#10B981]">
                  <span className="w-3.5 h-1 border-t-2 border-dashed border-[#10B981]" />
                  <span>S&P 500 Index (+18.4%)</span>
                </div>
              </div>
            </div>

            <div className="relative w-full h-[220px] bg-[#0F172A] border border-[#475569] rounded-lg p-2">
              <div className="absolute inset-0 flex flex-col justify-between py-6 px-2 pointer-events-none opacity-20">
                <div className="border-b border-[#475569] w-full" />
                <div className="border-b border-[#475569] w-full" />
                <div className="border-b border-[#475569] w-full" />
                <div className="border-b border-[#475569] w-full" />
              </div>

              <svg viewBox="0 0 600 200" preserveAspectRatio="none" className="w-full h-full">
                <path
                  d="M 0 160 L 100 142 L 200 148 L 300 120 L 400 90 L 500 70 L 600 50"
                  fill="none"
                  stroke="#3B82F6"
                  strokeWidth="3"
                  strokeLinecap="round"
                />

                <path
                  d="M 0 160 L 100 152 L 200 135 L 300 145 L 400 125 L 500 115 L 600 100"
                  fill="none"
                  stroke="#10B981"
                  strokeWidth="2"
                  strokeDasharray="5,5"
                  strokeLinecap="round"
                />

                {[
                  { x: 0, label: "Jan 1" },
                  { x: 100, label: "Mar 1" },
                  { x: 200, label: "Jun 1" },
                  { x: 300, label: "Sep 1" },
                  { x: 400, label: "Nov 1" },
                  { x: 500, label: "Jan 15" },
                  { x: 600, label: "Apr 1" }
                ].map((pt, i) => (
                  <text key={i} x={pt.x} y="190" textAnchor="middle" fill="#94A3B8" fontSize="10" fontFamily="monospace">
                    {pt.label}
                  </text>
                ))}
              </svg>
            </div>
          </div>

          {/* Heatmap */}
          <div 
            data-onboarding="heatmap"
            className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col gap-4"
          >
            <div className="flex flex-col leading-none">
              <span className="font-bold text-[#F8FAFC] text-sm">Monthly Return Performance Heatmap Matrix</span>
              <span className="text-xs text-[#94A3B8] font-mono mt-0.5">Click cells to display quantitative parameters details</span>
            </div>

            <div className="flex flex-col gap-2 font-mono text-[11px] overflow-x-auto">
              <div className="min-w-[650px] flex flex-col gap-1.5">
                <div className="flex items-center select-none text-[#94A3B8] font-bold pb-1 text-center font-mono">
                  <span className="w-14 text-left">Year</span>
                  {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].map(m => (
                    <span key={m} className="flex-1">{m}</span>
                  ))}
                </div>

                <div className="flex items-center text-center font-mono py-1">
                  <span className="w-14 text-left text-white font-bold">2024</span>
                  {displayHeatmap[2024]?.map((item: any, idx: number) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedHeatBlock({ year: 2024, month: item.month, value: item.val })}
                      className={`flex-1 h-12 m-0.5 rounded flex items-center justify-center font-black transition cursor-pointer select-none outline-none ${getHeatmapColor(item.p, item.val)}`}
                    >
                      {item.val}
                    </button>
                  ))}
                </div>

                <div className="flex items-center text-center font-mono py-1">
                  <span className="w-14 text-left text-white font-bold">2025</span>
                  {displayHeatmap[2025]?.map((item: any, idx: number) => (
                    <button
                      key={idx}
                      onClick={() => {
                        if (item.val === '-') {
                          triggerToast('warning', 'Data Unreleased', 'Cannot extract performance metrics for prospective month.');
                          return;
                        }
                        setSelectedHeatBlock({ year: 2025, month: item.month, value: item.val });
                      }}
                      className={`flex-1 h-12 m-0.5 rounded flex items-center justify-center font-black transition cursor-pointer select-none outline-none ${getHeatmapColor(item.p, item.val)}`}
                    >
                      {item.val}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {selectedHeatBlock && (
              <div className="bg-[#0F172A] border border-[#475569] p-3 rounded-xl font-mono text-xs text-[#94A3B8] flex items-center justify-between animate-slide-in select-text">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                  <span>
                    Simulated Return Profile for <strong className="text-white">{selectedHeatBlock.month} {selectedHeatBlock.year}</strong>:
                    <strong className={selectedHeatBlock.value.startsWith('+') ? 'text-[#10B981]' : 'text-[#EF4444]'}> {selectedHeatBlock.value} ROI</strong>
                  </span>
                </div>
                <button
                  onClick={() => setSelectedHeatBlock(null)}
                  className="text-xs hover:text-white uppercase font-bold"
                >
                  DISMISS
                </button>
              </div>
            )}
          </div>

          {/* Save Strategy Button */}
          <div className="flex justify-end">
            <button
              onClick={() => {
                triggerToast('success', 'Strategy Saved', 'Backtest configuration saved to library.');
              }}
              data-onboarding="save-strategy"
              className="bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-bold py-2.5 px-6 rounded-lg transition flex items-center gap-2"
            >
              <Play className="w-4 h-4 rotate-90" /> SAVE STRATEGY
            </button>
          </div>

        </div>
      )}

    </div>
  );
}