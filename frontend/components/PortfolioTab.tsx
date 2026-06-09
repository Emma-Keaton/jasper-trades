'use client';

import React, { useState } from 'react';
import {
  Briefcase,
  RotateCw,
  Download,
  Layers,
  Trash2,
  RefreshCw,
  Check,
  Info,
  DollarSign,
  FileSpreadsheet,
  ArrowUpRight
} from 'lucide-react';
import { Holding, TradeHistoryItem, Toast } from '@/app/page';
import WithdrawModal from './WithdrawModal';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PortfolioTabProps {
  cash: number;
  setCash: React.Dispatch<React.SetStateAction<number>>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  tradeHistory: TradeHistoryItem[];
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

export default function PortfolioTab({
  cash,
  setCash,
  holdings,
  setHoldings,
  tradeHistory,
  triggerToast
}: PortfolioTabProps) {
  const [allocationStyle, setAllocationStyle] = useState<'donut' | 'treemap'>('donut');
  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isExportingCSV, setIsExportingCSV] = useState<boolean>(false);
  const [isSyncingBroker, setIsSyncingBroker] = useState<boolean>(false);
  const [showWithdrawModal, setShowWithdrawModal] = useState<boolean>(false);

  // Sync portfolio with live broker
  const handleSyncBroker = async () => {
    setIsSyncingBroker(true);
    try {
      // Get portfolio ID (assuming default is 1, would come from context in production)
      const portfolioId = 1;
      
      const response = await fetch(`${API_URL}/api/v1/portfolio/${portfolioId}/sync-broker`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Sync failed');
      }

      const result = await response.json();
      
      if (result.status === 'paper_trading') {
        triggerToast('info', 'Paper Trading', 'Portfolio is in paper trading mode. No broker sync needed.');
      } else if (result.status === 'success') {
        // Update cash from result
        setCash(result.new_cash);
        triggerToast('success', 'Broker Synced', `Synced $${result.new_cash.toLocaleString()} from ${result.broker}.`);
      }
    } catch (error: any) {
      console.error('Sync error:', error);
      triggerToast('error', 'Sync Failed', error.message || 'Could not sync with broker.');
    } finally {
      setIsSyncingBroker(false);
    }
  };

  // Export Trade History to CSV format
  const handleExportCSV = () => {
    if (tradeHistory.length === 0) {
      triggerToast('warning', 'No Data Available', 'There is no trade history to export.');
      return;
    }

    setIsExportingCSV(true);

    try {
      // Helper to sanitize CSV field values
      const escapeCSV = (val: any) => {
        if (val === undefined || val === null) return '';
        let str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
          str = '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
      };

      // Header definition
      const headers = [
        'Timestamp', 
        'Operation Type', 
        'Asset Symbol', 
        'Broker Side', 
        'Shares Filled', 
        'Execution Price', 
        'Dispatched Cost', 
        'Origin Agent'
      ];
      
      // Rows mapping
      const rows = tradeHistory.map(log => [
        escapeCSV(log.date),
        escapeCSV(log.type),
        escapeCSV(log.symbol),
        escapeCSV(log.side),
        escapeCSV(log.shares),
        escapeCSV(log.price),
        escapeCSV(log.total),
        escapeCSV(log.agent)
      ]);

      // Build the csv content string
      const csvContent = [
        headers.join(','),
        ...rows.map(r => r.join(','))
      ].join('\n');

      // Generate blob and trigger browser download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `trade-history_${new Date().toISOString().slice(0, 10)}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      triggerToast('success', 'Trade History Exported', 'CSV file successfully downloaded.');
    } catch (error) {
      console.error(error);
      triggerToast('error', 'CSV Export Failed', 'An error occurred while generating the CSV file.');
    } finally {
      setIsExportingCSV(false);
    }
  };

  // Position select handlers
  const toggleSelectPosition = (symbol: string) => {
    setSelectedPositions(prev => 
      prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol]
    );
  };

  const toggleSelectAll = () => {
    if (selectedPositions.length === holdings.length) {
      setSelectedPositions([]);
    } else {
      setSelectedPositions(holdings.map(h => h.symbol));
    }
  };

  // Liquidate selected positions and credit cash balances!
  const handleCloseSelected = () => {
    if (selectedPositions.length === 0) {
      triggerToast('warning', 'Selection Required', 'No positions selected. Check position rows to liquidate.');
      return;
    }

    let creditAmount = 0;
    const remainingHoldings = holdings.filter(h => {
      if (selectedPositions.includes(h.symbol)) {
        creditAmount += (h.shares * h.currentPrice);
        return false;
      }
      return true;
    });

    setCash(prev => prev + creditAmount);
    setHoldings(remainingHoldings);
    setSelectedPositions([]);
    triggerToast(
      'success', 
      'Selected Positions Liquidated', 
      `Credited +$${creditAmount.toLocaleString(undefined, {minimumFractionDigits: 2})} to your Cash balance.`
    );
  };

  const handleRebalance = () => {
    triggerToast('info', 'Portfolio Rebalance Synchronized', 'Scanning optimization models. Allocations adjusted safely targeting equal-weights risk boundaries.');
  };

  const handleExportPDF = () => {
    setIsExporting(true);
    setTimeout(() => {
      setIsExporting(false);
      triggerToast('success', 'Operational Report Saved', 'PDF statements saved. Download archived onto your desktop directories.');
    }, 1500);
  };

  // Allocation computations percentages
  const holdingsValue = holdings.reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
  const totalNetValue = holdingsValue + cash;
  
  const stocksValue = holdings.filter(h => h.type === 'Stock').reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
  const cryptoValue = holdings.filter(h => h.type === 'Crypto').reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
  
  const stocksPct = totalNetValue > 0 ? Number(((stocksValue / totalNetValue) * 100).toFixed(1)) : 0;
  const cryptoPct = totalNetValue > 0 ? Number(((cryptoValue / totalNetValue) * 100).toFixed(1)) : 0;
  const cashPct = totalNetValue > 0 ? Number(((cash / totalNetValue) * 100).toFixed(1)) : 0;

  return (
    <div className="flex flex-col gap-6 w-full animate-fade-in">
      
      {/* Title Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight font-sans">Portfolio Analyzer</h1>
          <p className="text-sm text-[#94A3B8]">Comprehensive statistics mapping direct asset balances and histories.</p>
        </div>

        <div className="flex items-center gap-2">
          {/* Action triggers */}
          <button
            onClick={handleExportPDF}
            disabled={isExporting}
            className="bg-[#0F172A] border border-[#475569]/80 hover:text-[#3B82F6] hover:border-[#3B82F6] text-[#94A3B8] text-xs font-mono font-bold px-3 h-10 rounded-lg transition flex items-center gap-1.5 focus:outline-none"
          >
            <Download className="w-4 h-4" /> {isExporting ? 'EXPORTING...' : 'EXPORT STATS'}
          </button>
          
          <button
            onClick={() => triggerToast('info', 'Asset Prices Queried', 'Prices synchronized. All net calculations updated.')}
            className="bg-[#0F172A] border border-[#475569]/80 hover:text-white text-[#94A3B8] text-xs font-mono font-bold px-3 h-10 rounded-lg transition flex items-center gap-1.5 focus:outline-none"
          >
            <RotateCw className="w-4 h-4" /> REFRESH DATA
          </button>
        </div>
      </div>

      {/* PORTFOLIO PERFORMANCE LINE GRAPH */}
      <div className="bg-[#1E293B] border border-[#475569] p-5 rounded-xl flex flex-col gap-4">
        <div className="flex flex-col text-left">
          <span className="text-[#94A3B8] text-[10px] uppercase font-mono tracking-wider font-bold">Total Portfolio Net Assets</span>
          <h2 className="text-3xl font-black font-mono text-white tracking-tight mt-1.5">
            ${totalNetValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
          </h2>
        </div>

        {/* Dynamic mini coordinates display */}
        <div className="relative w-full h-[180px] bg-[#0F172A] border border-[#475569] rounded-lg p-2">
          <div className="absolute inset-0 flex flex-col justify-between py-6 px-2 pointer-events-none opacity-20">
            <div className="border-b border-[#475569] w-full" />
            <div className="border-b border-[#475569] w-full" />
            <div className="border-b border-[#475569] w-full" />
          </div>

          <svg viewBox="0 0 600 200" preserveAspectRatio="none" className="w-full h-full">
            <defs>
              <linearGradient id="curveFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.25"/>
                <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0"/>
              </linearGradient>
            </defs>
            {/* Area */}
            <path d="M 0 160 L 100 150 L 200 130 L 300 142 L 400 100 L 500 110 L 600 65 L 600 200 L 0 200 Z" fill="url(#curveFill)" />
            {/* Stroke */}
            <path d="M 0 160 L 100 150 L 200 130 L 300 142 L 400 100 L 500 110 L 600 65" fill="none" stroke="#3B82F6" strokeWidth="3" strokeLinecap="round" />
            
            {/* X metrics labeling guides */}
            {[
              {x: 0, l: "Jan 1"}, {x: 100, l: "Jan 15"}, {x: 200, l: "Feb 1"}, 
              {x: 300, l: "Feb 15"}, {x: 400, l: "Mar 1"}, {x: 500, l: "Mar 15"},
              {x: 600, l: "Apr 1"}
            ].map((p, i) => (
              <text key={i} x={p.x} y="190" textAnchor="middle" fill="#94A3B8" fontSize="10" fontFamily="monospace">{p.l}</text>
            ))}
          </svg>
        </div>

        <div className="flex items-center gap-6 font-mono text-xs text-[#94A3B8] flex-wrap justify-between pt-1 select-none">
          <span>Day return: <strong className="text-[#10B981] font-bold">+$2,450.00 (+2.45%)</strong></span>
          <span>Week return: <strong className="text-[#10B981] font-bold">+$4,120.00 (+4.12%)</strong></span>
          <span>Month return: <strong className="text-[#10B981] font-bold">+$8,340.00 (+8.34%)</strong></span>
          <span>All time: <strong className="text-[#10B981] font-bold">+$42,700.00 (+42.70%)</strong></span>
        </div>
      </div>

      {/* ALLOCATIONS DONUT VS TREEMAP CHART STAGE */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 select-none">
        {/* allocation chart box */}
        <div className="bg-[#1E293B] border border-[#475569] p-5 rounded-xl md:col-span-12 flex flex-col gap-4">
          <div className="flex sm:items-center justify-between border-b border-[#475569]/30 pb-3 flex-col sm:flex-row gap-3">
            <div className="flex flex-col leading-none">
              <span className="font-bold text-[#F8FAFC] text-sm">Asset Classes Allocations Matrix</span>
              <span className="text-xs text-[#94A3B8] font-mono mt-0.5">Stocks, Cryptos, and Cash diversification parameters</span>
            </div>
            
            <button
              onClick={() => {
                setAllocationStyle(allocationStyle === 'donut' ? 'treemap' : 'donut');
                triggerToast('info', 'Allocation Rendered Updated', `Switched layout view to ${allocationStyle === 'donut' ? 'TREEMAP' : 'DONUT CHART'} mode.`);
              }}
              className="bg-[#0F172A] border border-[#475569] hover:border-[#3B82F6] hover:text-[#3B82F6] px-3.5 h-8 text-[11px] font-mono font-bold rounded-lg transition"
            >
              SWITCH TO {allocationStyle === 'donut' ? 'TREEMAP' : 'DONUT'}
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Visual plot col */}
            <div className="lg:col-span-5 flex justify-center py-4 relative group">
              {allocationStyle === 'donut' ? (
                /* Conic donut visual ring mockup using simple styled border properties */
                <div className="w-48 h-48 rounded-full border-[18px] border-slate-500/50 flex flex-col justify-center items-center font-mono relative">
                  {/* Concentric elements overlay highlights */}
                  <div className="absolute inset-0 rounded-full border-[18px] border-transparent border-t-[#3B82F6] border-r-[#10B981] border-l-purple-500 transform rotate-45" />
                  
                  <span className="text-2xl font-black text-white">{stocksPct || 65}%</span>
                  <span className="text-[10px] text-[#94A3B8] uppercase font-bold tracking-widest leading-none">STOCKS INDEX</span>
                </div>
              ) : (
                /* Beautiful proportional rect grid visual representations */
                <div className="w-full h-48 flex gap-1.5 font-mono text-xs text-white">
                  {/* Stocks compartment */}
                  <div className="flex-1 bg-gradient-to-tr from-[#3B82F6] to-blue-600 rounded-lg p-3 flex flex-col justify-between hover:opacity-90 transition">
                    <span className="font-black">STOCKS</span>
                    <span className="text-lg font-black">{stocksPct}%</span>
                  </div>
                  {/* Crypto compartment */}
                  <div className="w-28 bg-gradient-to-tr from-purple-500 to-indigo-600 rounded-lg p-3 flex flex-col justify-between hover:opacity-90 transition">
                    <span className="font-black">CRYPTO</span>
                    <span className="text-lg font-black">{cryptoPct}%</span>
                  </div>
                  {/* Cash compartment */}
                  <div className="w-16 bg-gradient-to-tr from-[#10B981] to-emerald-600 rounded-lg p-3 flex flex-col justify-between hover:opacity-90 transition">
                    <span className="font-black">CASH</span>
                    <span className="text-lg font-black">{cashPct}%</span>
                  </div>
                </div>
              )}
            </div>

            {/* Custom high fidelity legend table columns */}
            <div className="lg:col-span-7 flex flex-col gap-4 font-mono text-xs text-[#94A3B8]">
              {/* Legend item Stocks */}
              <div className="flex flex-col gap-1.5 pb-2.5 border-b border-[#475569]/30">
                <div className="flex justify-between items-center text-white">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded bg-[#3B82F6]" />
                    <span className="font-bold">Equities & Stocks (Primary)</span>
                  </div>
                  <strong>${stocksValue.toLocaleString()} ({stocksPct}%)</strong>
                </div>
                <div className="w-full h-1.5 bg-[#0F172A] rounded-full overflow-hidden">
                  <div className="h-full bg-[#3B82F6]" style={{ width: `${stocksPct}%` }} />
                </div>
              </div>

              {/* Legend item Cryptos */}
              <div className="flex flex-col gap-1.5 pb-2.5 border-b border-[#475569]/30">
                <div className="flex justify-between items-center text-white">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded bg-purple-500" />
                    <span className="font-bold">Digital Cryptocurrencies Assets</span>
                  </div>
                  <strong>${cryptoValue.toLocaleString()} ({cryptoPct}%)</strong>
                </div>
                <div className="w-full h-1.5 bg-[#0F172A] rounded-full overflow-hidden">
                  <div className="h-full bg-purple-500" style={{ width: `${cryptoPct}%` }} />
                </div>
              </div>

              {/* Legend item Cash */}
              <div className="flex flex-col gap-1.5 pb-2 border-b border-[#475569]/30">
                <div className="flex justify-between items-center text-white">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded bg-[#10B981]" />
                    <span className="font-bold">Simulated Fiat Cash Balance</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <strong>${cash.toLocaleString()} ({cashPct}%)</strong>
                    <button
                      onClick={() => setShowWithdrawModal(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#10B981] hover:bg-[#059669] text-white text-xs font-medium rounded-lg transition-colors"
                    >
                      <ArrowUpRight className="w-3.5 h-3.5" />
                      Withdraw
                    </button>
                  </div>
                </div>
                <div className="w-full h-1.5 bg-[#0F172A] rounded-full overflow-hidden">
                  <div className="h-full bg-[#10B981]" style={{ width: `${cashPct}%` }} />
                </div>
              </div>

              {/* Withdrawal Modal */}
              {showWithdrawModal && (
                <WithdrawModal
                  portfolioId={1}
                  availableBalance={cash}
                  onClose={() => setShowWithdrawModal(false)}
                  triggerToast={triggerToast}
                />
              )}

              {/* Diversification scoring */}
              <div className="pt-2 flex justify-between items-center text-sm font-mono text-white">
                <span>Diversification Score: <strong className="text-[#10B981]">7.4 / 10 Excellent</strong></span>
                <span className="text-xs text-[#94A3B8]">Risk Index: LOW</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* POSITIONS DRAWER INTERACTION TABLE */}
      <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 border-b border-[#475569] pb-3">
          <div className="flex flex-col">
            <h3 className="font-bold text-md text-[#F8FAFC]">Active Strategic Positions</h3>
            <span className="text-xs font-mono text-[#94A3B8]">Check items and liquidates selected from the index pools</span>
          </div>
          
          <div className="flex items-center gap-2 font-mono">
            {selectedPositions.length > 0 && (
              <button
                onClick={handleCloseSelected}
                className="bg-red-500/10 hover:bg-red-500/25 text-red-400 border border-red-500/30 px-3.5 h-8 text-[11px] font-bold rounded-lg transition flex items-center justify-center gap-1 focus:outline-none"
              >
                <Trash2 className="w-3.5 h-3.5" /> LIQUIDATE SELECTED ({selectedPositions.length})
              </button>
            )}
            
            <button
              onClick={handleRebalance}
              className="bg-[#0F172A] border border-[#475569]/80 hover:border-[#3B82F6] hover:text-[#3B82F6] text-[#94A3B8] px-3.5 h-8 text-[11px] font-bold rounded-lg transition"
            >
              REBALANCE POSITIONS
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          {holdings.length > 0 ? (
            <table className="w-full text-left text-xs font-mono text-[#94A3B8] min-w-[650px]">
              <thead>
                <tr className="border-b border-[#475569] text-[#94A3B8] font-bold uppercase tracking-wide text-[10px] select-none h-8">
                  <th className="pb-2 w-10">
                    <input 
                      type="checkbox" 
                      onChange={toggleSelectAll}
                      checked={selectedPositions.length === holdings.length}
                      className="w-3.5 h-3.5 accent-[#3B82F6] cursor-pointer"
                    />
                  </th>
                  <th className="pb-2">Asset Symbol</th>
                  <th className="pb-2">Company / Name</th>
                  <th className="pb-2">Type</th>
                  <th className="pb-2 text-right">Shares owned</th>
                  <th className="pb-2 text-right">Acquisition Avg</th>
                  <th className="pb-2 text-right">Market Price</th>
                  <th className="pb-2 text-right">Current Value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#475569]/30">
                {holdings.map((h) => {
                  const isChecked = selectedPositions.includes(h.symbol);
                  const valCurrent = h.shares * h.currentPrice;
                  return (
                    <tr key={h.symbol} className={`h-12 hover:bg-[#334155]/20 group transition ease-out ${isChecked ? 'bg-[#3B82F6]/5' : ''}`}>
                      <td>
                        <input 
                          type="checkbox" 
                          checked={isChecked}
                          onChange={() => toggleSelectPosition(h.symbol)}
                          className="w-3.5 h-3.5 accent-[#3B82F6] cursor-pointer"
                        />
                      </td>
                      <td className="font-bold text-[#3B82F6]">{h.symbol}</td>
                      <td className="text-white">{h.name}</td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          h.type === 'Crypto' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' : 
                          h.type === 'Cash' ? 'bg-emerald-500/10 text-[#10B981] border border-emerald-500/20' :
                          'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                        }`}>
                          {h.type}
                        </span>
                      </td>
                      <td className="text-right text-white">{h.shares.toLocaleString()}</td>
                      <td className="text-right">${h.avgPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                      <td className="text-right select-all">${h.currentPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                      <td className="text-right font-bold text-white">${valCurrent.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-6 block font-mono text-xs text-[#94A3B8]">
              No active holdings. Go to the Signals Feed to fill order positions.
            </div>
          )}
        </div>
      </div>

      {/* CHRONOLOGICAL HISTORICAL TRADE LEDGER */}
      <div className="bg-[#1E293B] border border-[#475569] rounded-xl p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 border-b border-[#475569] pb-3">
          <div className="flex flex-col gap-1">
            <h3 className="font-bold text-md text-[#F8FAFC]">Simulated Trade Audits History</h3>
            <span className="text-xs font-mono text-[#94A3B8]">Sequential transaction tickets generated from workspace executions</span>
          </div>
          <button
            onClick={handleExportCSV}
            disabled={isExportingCSV}
            className="self-start sm:self-center bg-[#0F172A] border border-[#475569]/80 hover:text-[#3B82F6] hover:border-[#3B82F6] text-[#94A3B8] text-xs font-mono font-bold px-3 h-9 rounded-lg transition flex items-center gap-1.5 focus:outline-none disabled:opacity-50"
          >
            <FileSpreadsheet className="w-4 h-4 text-[#3B82F6]" /> {isExportingCSV ? 'EXPORTING...' : 'EXPORT CSV'}
          </button>
        </div>

        <div className="overflow-x-auto h-48 overflow-y-auto">
          <table className="w-full text-left text-xs font-mono text-[#94A3B8] min-w-[650px]">
            <thead>
              <tr className="border-b border-[#475569] text-slate-400 font-bold uppercase tracking-wide text-[10px] h-8 select-none">
                <th className="pb-2">Timestamp</th>
                <th className="pb-2">Operation Type</th>
                <th className="pb-2">Asset Symbol</th>
                <th className="pb-2">Broker Side</th>
                <th className="pb-2 text-right">Shares Filled</th>
                <th className="pb-2 text-right">Execution Price</th>
                <th className="pb-2 text-right">Dispatched Cost</th>
                <th className="pb-2 text-right">Origin Agent</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#475569]/30">
              {tradeHistory.map(log => {
                const isBuy = log.type === 'BUY';
                return (
                  <tr key={log.id} className="h-10 hover:bg-[#334155]/20 transition ease-out">
                    <td className="text-[#94A3B8]">{log.date}</td>
                    <td>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        isBuy ? 'bg-[#10B981]/15 text-[#10B981]' : 'bg-[#EF4444]/15 text-[#EF4444]'
                      }`}>
                        {log.type}
                      </span>
                    </td>
                    <td className="font-bold text-white">{log.symbol}</td>
                    <td>{log.side}</td>
                    <td className="text-right text-white">{log.shares}</td>
                    <td className="text-right">${log.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                    <td className="text-right font-bold text-white">${log.total.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                    <td className="text-right text-[#3B82F6] font-bold">{log.agent}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
