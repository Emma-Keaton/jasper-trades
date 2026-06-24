'use client';

import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  Bot,
  Terminal,
  DollarSign,
  Activity,
  Plus
} from 'lucide-react';
import { Holding, TradeHistoryItem, Toast } from '@/app/page';
import { EquityDataPoint } from '@/hooks/usePortfolioHistory';
import { SkeletonCard, SkeletonChart, SkeletonConsole, SkeletonTable } from './Skeleton';
import EquityChart from './charts/EquityChart';
import { useCurrencyFormatter } from '@/lib/currencyContext';

interface DashboardTabProps {
  cash: number;
  holdings: Holding[];
  agents: any[];
  tradeHistory: TradeHistoryItem[];
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  loading?: boolean;
  portfolioInitialized?: boolean;
  equityData?: EquityDataPoint[];
}

export default function DashboardTab({
  cash,
  holdings,
  agents,
  tradeHistory,
  triggerToast,
  loading = false,
  portfolioInitialized = false,
  equityData = []
}: DashboardTabProps) {
  const { formatMoney } = useCurrencyFormatter();
  const [timeframe, setTimeframe] = useState<string>('1M');

  // Portfolio calculation variables
  const totalHoldingsValue = holdings.reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
  const totalPortfolioValue = totalHoldingsValue + cash;

  // PnL is calculated and provided by backend via portfolio history
  // Frontend does NOT make assumptions about initial values
  // Display portfolio value as-is from backend data
  const portfolioChange = equityData && equityData.length > 0
    ? totalPortfolioValue - equityData[0].y  // Change from first data point
    : 0;  // No history data = no PnL to show
  const portfolioChangePercent = equityData && equityData.length > 0 && equityData[0].y > 0
    ? (portfolioChange / equityData[0].y) * 100
    : 0;

  // Chart data for equity curve - use actual backend data
  const chartData = useMemo(() => {
    // If we have actual equity data from backend, use it
    if (equityData && equityData.length > 0) {
      return equityData.map(point => ({ x: point.x, y: point.y }));
    }

    // Fallback: show flat line at current value if portfolio exists
    if (totalPortfolioValue > 0) {
      return [
        { x: 0, y: totalPortfolioValue },
        { x: 1, y: totalPortfolioValue }
      ];
    }

    // No portfolio data - empty chart
    return [];
  }, [equityData, totalPortfolioValue]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6 w-full">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="h-8 w-48 bg-gray-700 rounded animate-pulse" />
            <div className="h-4 w-80 bg-gray-700 rounded mt-2 animate-pulse" />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7">
            <SkeletonChart />
          </div>
          <div className="lg:col-span-5">
            <SkeletonConsole />
          </div>
        </div>

        <SkeletonTable />
      </div>
    );
  }

  return (
    <div
      data-onboarding="dashboard-tour"
      className="flex flex-col gap-6 w-full"
    >

      {/* Dynamic View Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-[#F8FAFC] tracking-tight font-sans">Active Trading Desk</h1>
          <p className="text-sm text-[#94A3B8]">Real-time portfolio monitoring and AI agent activity</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#94A3B8] font-mono select-none">Auto-refresh:</span>
          <span className="inline-flex items-center gap-1 bg-[#10B981]/15 text-[#10B981] px-2.5 py-1 rounded-full text-[11px] font-bold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-ping" />
            ON (30s sync)
          </span>
        </div>
      </div>

      {/* PORTFOLIO SUMMARY CARDS */}
      <div
        data-onboarding="portfolio-value"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        {/* Card 1: Total Value */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between relative overflow-hidden group hover:border-[#3B82F6] transition">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs uppercase font-mono text-[#94A3B8] tracking-wider font-bold">Total Net Value</span>
            <span className="text-2xl font-black font-mono text-white tracking-tight">
              {formatMoney(totalPortfolioValue, 'USD')}
            </span>
            <span className="text-xs text-[#94A3B8] font-mono">Cash + Asset value</span>
          </div>
          <div className="p-3 bg-[#3B82F6]/10 text-[#3B82F6] rounded-xl group-hover:scale-110 transition">
            <DollarSign className="w-6 h-6" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#3B82F6] to-transparent opacity-0 group-hover:opacity-100 transition" />
        </div>

        {/* Card 2: P&L */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between relative overflow-hidden group hover:border-[#10B981] transition">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs uppercase font-mono text-[#94A3B8] tracking-wider font-bold">Total P&L</span>
            <span className={`text-2xl font-black font-mono tracking-tight ${portfolioChange >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              {portfolioChange >= 0 ? '+' : ''}{formatMoney(Math.abs(portfolioChange), 'USD')}
            </span>
            <span className={`text-xs font-bold font-mono flex items-center gap-1 ${portfolioChange >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              <TrendingUp className="w-3.5 h-3.5" />
              {portfolioChangePercent >= 0 ? '+' : ''}{portfolioChangePercent.toFixed(2)}%
            </span>
          </div>
          <div className={`p-3 rounded-xl group-hover:scale-110 transition ${portfolioChange >= 0 ? 'bg-[#10B981]/10 text-[#10B981]' : 'bg-[#EF4444]/10 text-[#EF4444]'}`}>
            <TrendingUp className="w-6 h-6" />
          </div>
          <div className={`absolute bottom-0 left-0 right-0 h-[2px] opacity-0 group-hover:opacity-100 transition ${portfolioChange >= 0 ? 'bg-gradient-to-r from-[#10B981]' : 'bg-gradient-to-r from-[#EF4444]'}`} />
        </div>

        {/* Card 3: Today's Trades */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between relative overflow-hidden group hover:border-[#6366F1] transition">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs uppercase font-mono text-[#94A3B8] tracking-wider font-bold">Trades Executed</span>
            <span className="text-2xl font-black font-mono text-white tracking-tight">
              {tradeHistory.length}
            </span>
            <span className="text-xs text-[#94A3B8] font-mono">
              {tradeHistory.length > 0 ? 'All time trades' : 'No trades yet'}
            </span>
          </div>
          <div className="p-3 bg-[#6366F1]/10 text-[#6366F1] rounded-xl group-hover:scale-110 transition">
            <Terminal className="w-6 h-6" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#6366F1] to-transparent opacity-0 group-hover:opacity-100 transition" />
        </div>

        {/* Card 4: Active Agents */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between relative overflow-hidden group hover:border-[#F59E0B] transition">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs uppercase font-mono text-[#94A3B8] tracking-wider font-bold">Active Agents</span>
            <span className="text-2xl font-black font-mono text-[#F59E0B] tracking-tight">
              {agents.filter(a => a.status === 'Running').length} / {agents.length}
            </span>
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
              <span className="text-xs text-[#10B981] font-bold">Operational</span>
            </div>
          </div>
          <div className="p-3 bg-[#F59E0B]/10 text-[#F59E0B] rounded-xl group-hover:scale-110 transition">
            <Bot className="w-6 h-6" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#F59E0B] to-transparent opacity-0 group-hover:opacity-100 transition" />
        </div>
      </div>

      {/* EQUITY CURVE CHART & AGENT CONSOLE GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Equity Curve Chart with Recharts */}
        <div
          data-onboarding="pnl-chart"
          className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl lg:col-span-7 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="font-bold text-md text-[#F8FAFC]">Portfolio Equity Curve</span>
              <span className="text-xs font-mono text-[#94A3B8]">Performance since inception</span>
            </div>
          </div>

          {/* Equity Chart with fullscreen and timeframe */}
          <EquityChart
            data={chartData}
            timeframe={timeframe as any}
            onTimeframeChange={(tf) => {
              setTimeframe(tf);
              triggerToast('info', 'Timeframe Updated', `Chart view changed to ${tf}`);
            }}
          />

          {/* Chart stats */}
          <div className="flex items-center justify-between px-2 pt-1 font-mono text-[11px] text-[#94A3B8]">
            <div className="flex items-center gap-1.5">
              <span>Starting:</span>
              <span className="font-bold text-white leading-none">
                {equityData && equityData.length > 0 ? `$${equityData[0].y.toLocaleString()}` : '$0'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span>Current:</span>
              <span className="font-bold text-[#3B82F6] leading-none">${totalPortfolioValue.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span>Change:</span>
              <span className={`font-bold leading-none ${portfolioChange >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                {portfolioChange >= 0 ? '+' : ''}{portfolioChangePercent.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>

        {/* Agent Activity Console */}
        <div
          data-onboarding="trade-history"
          className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl lg:col-span-5 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <h3 className="font-bold text-md text-[#F8FAFC]">Agent Activity Log</h3>
              <span className="text-xs font-mono text-[#94A3B8]">Real-time AI agent decisions</span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => triggerToast('info', 'Agent Logs', 'Live agent streaming coming soon')}
                className="bg-[#0F172A] border border-[#475569] text-xs hover:text-[#3B82F6] hover:border-[#3B82F6] px-2 py-1 rounded transition flex items-center gap-1 font-mono outline-none"
              >
                <Plus className="w-3.5 h-3.5" />
                REFRESH
              </button>
              <button
                onClick={() => {
                  triggerToast('info', 'Logs Cleared', 'Agent log buffer cleared');
                }}
                className="bg-[#0F172A] border border-[#475569] text-xs hover:text-[#EF4444] hover:border-[#EF4444] px-2 py-1 rounded transition font-mono outline-none"
              >
                CLEAR
              </button>
            </div>
          </div>

          {/* Console container */}
          <div className="flex-1 bg-[#0F172A] border border-[#475569] rounded-lg p-3 min-h-[180px] max-h-[180px] overflow-y-auto flex flex-col gap-3 font-mono text-xs select-text">
            <div className="flex flex-col items-center justify-center h-full gap-2 text-[#94A3B8] text-center">
              <Activity className="w-5 h-5 opacity-40 animate-pulse text-[#3B82F6]" />
              <div>
                <p className="text-sm font-bold mb-1">No Agent Activity Yet</p>
                <p className="text-xs">Enable agents in the Agents tab to start seeing real-time trading decisions and market analysis.</p>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* HOLDINGS TABLE */}
      <div
        data-onboarding="holdings-table"
        className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl"
      >
        <div className="flex items-center justify-between mb-4 border-b border-[#475569] pb-3">
          <div className="flex flex-col">
            <h3 className="font-bold text-md text-[#F8FAFC]">Current Holdings</h3>
            <span className="text-xs font-mono text-[#94A3B8]">Your portfolio positions</span>
          </div>
          <span className="text-[10px] font-mono text-[#94A3B8]">Total: {formatMoney(totalHoldingsValue, 'USD')}</span>
        </div>

        {holdings.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
              <DollarSign className="w-8 h-8 text-gray-500" />
            </div>
            <h4 className="text-lg font-bold text-white mb-2">No Holdings Yet</h4>
            <p className="text-sm text-gray-400 mb-4">
              Start trading to see your positions appear here
            </p>
            <button
              onClick={() => triggerToast('info', 'Get Started', 'Navigate to Signals tab to see trading opportunities')}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
            >
              View Trading Signals
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#94A3B8] font-mono">
              <thead>
                <tr className="border-b border-[#475569] text-[#94A3B8] font-bold uppercase tracking-wide text-[10px] select-none h-8">
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2">Name</th>
                  <th className="pb-2">Type</th>
                  <th className="pb-2 text-right">Shares</th>
                  <th className="pb-2 text-right">Avg Price</th>
                  <th className="pb-2 text-right">Current</th>
                  <th className="pb-2 text-right">Value</th>
                  <th className="pb-2 text-right">P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#475569]/30">
                {holdings.map((h) => {
                  const isPositive = h.pnlPercent >= 0;
                  const positionValue = h.shares * h.currentPrice;
                  return (
                    <tr key={h.symbol} className="h-12 hover:bg-[#334155]/20 group transition ease-out">
                      <td className="font-bold text-[#3B82F6]">{h.symbol}</td>
                      <td className="text-[#F8FAFC]">{h.name}</td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          h.type === 'Crypto' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                          h.type === 'Cash' ? 'bg-emerald-500/10 text-[#10B981] border border-emerald-500/20' :
                          'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                        }`}>
                          {h.type}
                        </span>
                      </td>
                      <td className="text-right text-[#F8FAFC]">{h.shares.toLocaleString()}</td>
                      <td className="text-right text-[#F8FAFC]">{formatMoney(h.avgPrice, 'USD')}</td>
                      <td className="text-right text-[#F8FAFC]">{formatMoney(h.currentPrice, 'USD')}</td>
                      <td className="text-right font-bold text-white">{formatMoney(positionValue, 'USD')}</td>
                      <td className={`text-right font-bold ${isPositive ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {isPositive ? '▲' : '▼'} {isPositive ? '+' : ''}{h.pnlPercent}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}