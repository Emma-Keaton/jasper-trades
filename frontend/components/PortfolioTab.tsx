'use client';

import React, { useState, useEffect } from 'react';
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
  ArrowUpRight,
  TrendingUp
} from 'lucide-react';
import ReactFrappeChart from 'react-frappe-charts';
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
  portfolioInitialized?: boolean;
}

export default function PortfolioTab({
  cash,
  setCash,
  holdings,
  setHoldings,
  tradeHistory,
  triggerToast,
  portfolioInitialized = false
}: PortfolioTabProps) {
  const [allocationStyle, setAllocationStyle] = useState<'donut' | 'treemap'>('donut');
  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [isExportingCSV, setIsExportingCSV] = useState<boolean>(false);
  const [isSyncingBroker, setIsSyncingBroker] = useState<boolean>(false);
  const [showWithdrawModal, setShowWithdrawModal] = useState<boolean>(false);

  const [allocationData, setAllocationData] = useState<{ labels: string[]; datasets: { values: number[] }[] }>({ labels: [], datasets: [] });
  const [totalNetValue, setTotalNetValue] = useState<number>(0);
  const [holdingsValue, setHoldingsValue] = useState<number>(0);

  useEffect(() => {
    const fetchPortfolioData = async () => {
      try {
        const portfolioId = 1;
        const [holdingsRes, cashRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/portfolio/${portfolioId}/holdings`),
          fetch(`${API_URL}/api/v1/portfolio/${portfolioId}/cash`),
        ]);

        let holdingsData: Holding[] = [];
        let cashData = cash;

        if (holdingsRes.ok) {
          const hData = await holdingsRes.json();
          // Backend returns { holdings: [...] } not direct array
          holdingsData = Array.isArray(hData) ? hData : (hData?.holdings || []);
          setHoldings(holdingsData);
        }

        if (cashRes.ok) {
          const cData = await cashRes.json();
          cashData = cData.amount || cash;
          setCash(cashData);
        }

        const hValue = holdingsData.reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
        const total = hValue + cashData;
        setHoldingsValue(hValue);
        setTotalNetValue(total);

        const stocksVal = holdingsData.filter(h => h.type === 'Stock').reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
        const cryptoVal = holdingsData.filter(h => h.type === 'Crypto').reduce((sum, h) => sum + (h.shares * h.currentPrice), 0);
        const cashVal = cashData;

        const labels: string[] = [];
        const values: number[] = [];

        if (stocksVal > 0) { labels.push('Stocks'); values.push(parseFloat((stocksVal / total * 100).toFixed(1))); }
        if (cryptoVal > 0) { labels.push('Crypto'); values.push(parseFloat((cryptoVal / total * 100).toFixed(1))); }
        if (cashVal > 0) { labels.push('Cash'); values.push(parseFloat((cashVal / total * 100).toFixed(1))); }

        if (labels.length === 0) {
          labels.push('No Holdings');
          values.push(100);
        }

        setAllocationData({ labels, datasets: [{ values }] });

      } catch (error) {
        console.error('Failed to fetch portfolio:', error);
        triggerToast('error', 'Load Failed', 'Could not load portfolio data from backend.');
      }
    };

    fetchPortfolioData();
    const interval = setInterval(fetchPortfolioData, 30000);
    return () => clearInterval(interval);
  }, [cash, setCash, setHoldings, triggerToast]);

  const handleSyncBroker = async () => {
    setIsSyncingBroker(true);
    try {
      const portfolioId = 1;
      const response = await fetch(`${API_URL}/api/v1/portfolio/${portfolioId}/sync-broker`, { method: 'POST' });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Sync failed');
      }

      const result = await response.json();
      if (result.status === 'paper_trading') {
        triggerToast('info', 'Paper Trading', 'Portfolio is in paper trading mode. No broker sync needed.');
      } else if (result.status === 'success') {
        setCash(result.new_cash);
        triggerToast('success', 'Broker Synced', `Synced $${result.new_cash.toLocaleString()} from ${result.broker}.`);
      }
    } catch (error: any) {
      triggerToast('error', 'Sync Failed', error.message || 'Could not sync with broker.');
    } finally {
      setIsSyncingBroker(false);
    }
  };

  const handleExportCSV = () => {
    if (tradeHistory.length === 0) {
      triggerToast('warning', 'No Data Available', 'There is no trade history to export.');
      return;
    }

    setIsExportingCSV(true);

    try {
      const escapeCSV = (val: any) => {
        if (val === undefined || val === null) return '';
        let str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
          str = '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
      };

      const headers = ['Timestamp', 'Operation Type', 'Asset Symbol', 'Broker Side', 'Shares Filled', 'Execution Price', 'Dispatched Cost', 'Origin Agent'];
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

      const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
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
      triggerToast('error', 'CSV Export Failed', 'An error occurred while generating the CSV file.');
    } finally {
      setIsExportingCSV(false);
    }
  };

  const toggleSelectPosition = (symbol: string) => {
    setSelectedPositions(prev => prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol]);
  };

  const toggleSelectAll = () => {
    setSelectedPositions(selectedPositions.length === holdings.length ? [] : holdings.map(h => h.symbol));
  };

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

    setHoldings(remainingHoldings);
    setCash(prev => prev + creditAmount);
    triggerToast('success', 'Positions Liquidated', `Closed ${selectedPositions.length} positions, credited $${creditAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })} to cash.`);
    setSelectedPositions([]);
  };

  const stocksCount = holdings.filter(h => h.type === 'Stock').length;
  const cryptoCount = holdings.filter(h => h.type === 'Crypto').length;
  const totalPositions = holdings.length;

  return (
    <div 
      data-onboarding="portfolio-tour"
      className="flex flex-col gap-6 w-full"
    >

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight font-sans">Portfolio Management Desk</h1>
          <p className="text-sm text-[#94A3B8]">Monitor allocation indices, synchronise broker positions, and execute withdrawals.</p>
        </div>
        <span className="bg-[#3B82F6]/15 border border-[#3B82F6]/30 text-[#3B82F6] px-3 py-1 rounded-full text-xs font-bold font-mono">
          {totalPositions} Positions | ${totalNetValue.toLocaleString(undefined, { minimumFractionDigits: 2 })} AUM
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Net Valuation</span>
            <span className="text-2xl font-black font-mono text-white">${totalNetValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">Holdings + Liquid Cash</span>
          </div>
          <div className="p-3 bg-[#3B82F6]/10 text-[#3B82F6] rounded-xl">
            <Briefcase className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold" data-onboarding="cash-balance">Liquid Cash</span>
            <span className="text-2xl font-black font-mono text-white">${cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">Available for deployment</span>
          </div>
          <div className="p-3 bg-[#10B981]/10 text-[#10B981] rounded-xl">
            <DollarSign className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Equity Holdings</span>
            <span className="text-2xl font-black font-mono text-white">${holdingsValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">{stocksCount} Stocks, {cryptoCount} Crypto</span>
          </div>
          <div className="p-3 bg-[#F59E0B]/10 text-[#F59E0B] rounded-xl">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Actions Available</span>
            <span className="text-2xl font-black font-mono text-white">3</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">Sync, Export, Withdraw</span>
          </div>
          <div className="p-3 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-xl">
            <Layers className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Allocation Chart & Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Frappe Charts Pie Chart */}
        <div 
          data-onboarding="allocation-chart"
          className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl lg:col-span-2"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-[#F8FAFC] text-sm">Portfolio Allocation Breakdown</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setAllocationStyle('donut')}
                className={`text-[10px] px-2 py-1 rounded font-mono font-bold ${allocationStyle === 'donut' ? 'bg-[#3B82F6] text-white' : 'text-[#94A3B8] hover:bg-[#334155]'}`}
              >
                DONUT
              </button>
              <button
                onClick={() => setAllocationStyle('treemap')}
                className={`text-[10px] px-2 py-1 rounded font-mono font-bold ${allocationStyle === 'treemap' ? 'bg-[#3B82F6] text-white' : 'text-[#94A3B8] hover:bg-[#334155]'}`}
              >
                TREEMAP
              </button>
            </div>
          </div>

          <div className="w-full h-[250px] flex items-center justify-center">
            {!portfolioInitialized ? (
              <div className="text-center">
                <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Briefcase className="w-8 h-8 text-gray-500" />
                </div>
                <h4 className="text-lg font-bold text-white mb-2">Portfolio Not Initialized</h4>
                <p className="text-sm text-gray-400 mb-4">Complete your first trade to see allocation breakdown</p>
                <button
                  onClick={() => triggerToast('info', 'Get Started', 'Navigate to Signals tab to execute your first trade')}
                  className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
                >
                  View Trading Signals
                </button>
              </div>
            ) : (
              <ReactFrappeChart
                type={'pie' as any}
                height={250}
                colors={['#3B82F6', '#14F195', '#10B981', '#F59E0B', '#EF4444']}
                data={allocationData}
              />
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col gap-4">
          <h3 className="font-bold text-[#F8FAFC] text-sm">Portfolio Actions</h3>

          <button
            onClick={handleSyncBroker}
            disabled={isSyncingBroker}
            data-onboarding="sync-broker"
            className="w-full bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-white text-xs font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2"
          >
            <RotateCw className={`w-4 h-4 ${isSyncingBroker ? 'animate-spin' : ''}`} />
            {isSyncingBroker ? 'SYNCING...' : 'SYNC WITH BROKER'}
          </button>

          <button
            onClick={handleExportCSV}
            disabled={isExportingCSV}
            data-onboarding="export-csv"
            className="w-full bg-[#10B981] hover:bg-[#059669] disabled:opacity-50 text-white text-xs font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            {isExportingCSV ? 'EXPORTING...' : 'EXPORT CSV'}
          </button>

          <button
            onClick={() => setShowWithdrawModal(true)}
            data-onboarding="withdraw-button"
            className="w-full bg-[#F59E0B] hover:bg-[#D97706] text-white text-xs font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2"
          >
            <ArrowUpRight className="w-4 h-4" />
            WITHDRAW PROFITS
          </button>

          <button
            onClick={toggleSelectAll}
            className="w-full border border-[#475569] hover:bg-[#334155] text-[#94A3B8] text-xs font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2"
          >
            <Check className="w-4 h-4" />
            {selectedPositions.length > 0 ? 'DESELECT ALL' : 'SELECT ALL'}
          </button>

          {selectedPositions.length > 0 && (
            <button
              onClick={handleCloseSelected}
              className="w-full bg-[#EF4444] hover:bg-[#DC2626] text-white text-xs font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2"
            >
              <Trash2 className="w-4 h-4" />
              LIQUIDATE {selectedPositions.length} POSITIONS
            </button>
          )}
        </div>
      </div>

      {/* Holdings Table */}
      <div 
        data-onboarding="position-cards"
        className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl"
      >
        <div className="flex items-center justify-between mb-4 border-b border-[#475569] pb-3">
          <div className="flex flex-col">
            <h3 className="font-bold text-md text-[#F8FAFC]">Current Holdings</h3>
            <span className="text-xs font-mono text-[#94A3B8]">Your portfolio positions</span>
          </div>
          <span className="text-[10px] font-mono text-[#94A3B8]">Total: ${holdingsValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>

        {holdings.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
              <Briefcase className="w-8 h-8 text-gray-500" />
            </div>
            <h4 className="text-lg font-bold text-white mb-2">No Holdings Yet</h4>
            <p className="text-sm text-gray-400 mb-4">Start trading to see your positions appear here</p>
            <button
              onClick={() => triggerToast('info', 'Get Started', 'Navigate to Signals tab to see trading opportunities')}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
            >
              View Trading Signals
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#94A3B8] font-mono min-w-[600px]">
              <thead>
                <tr className="border-b border-[#475569] text-[#94A3B8] font-bold uppercase tracking-wide text-[10px] select-none h-8">
                  <th className="pb-2">Select</th>
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
                  const isSelected = selectedPositions.includes(h.symbol);
                  const isPositive = h.pnlPercent >= 0;
                  const positionValue = h.shares * h.currentPrice;
                  return (
                    <tr key={h.symbol} className={`h-12 hover:bg-[#334155]/20 group transition ease-out ${isSelected ? 'bg-[#3B82F6]/10' : ''}`}>
                      <td className="text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectPosition(h.symbol)}
                          className="w-4 h-4 rounded border-[#475569] bg-[#0F172A] text-[#3B82F6] focus:ring-[#3B82F6]"
                        />
                      </td>
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
                      <td className="text-right text-[#F8FAFC]">${h.avgPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td className="text-right text-[#F8FAFC]">${h.currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td className="text-right font-bold text-white">${positionValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
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

      {/* Withdraw Modal */}
      {showWithdrawModal && (
        <WithdrawModal
          portfolioId={1}
          availableBalance={cash}
          onClose={() => setShowWithdrawModal(false)}
          triggerToast={triggerToast}
        />
      )}

    </div>
  );
}