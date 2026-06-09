'use client';

import React, { useState, useEffect } from 'react';
import {
  Radio,
  Filter,
  Check,
  X,
  Star,
  Info,
  Trash2
} from 'lucide-react';
import { Toast } from '@/app/page';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Signal {
  id: string;
  type: 'BUY' | 'SELL' | 'HOLD';
  symbol: string;
  name: string;
  agent: string;
  confidence: number;
  price: number;
  target_price: number;
  stop_price: number;
  reason: string;
  created_at: string;
  time?: string;
  thesis?: string;
  shares?: number;
  expectedUpside?: string;
  stopVal?: number;
  targetVal?: number;
}

interface SignalsTabProps {
  executeTrade: (symbol: string, type: 'BUY' | 'SELL', shares: number, price: number, total: number, agentName: string) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

export default function SignalsTab({
  executeTrade,
  triggerToast
}: SignalsTabProps) {
  // Available filters states
  const [selectedAgent, setSelectedAgent] = useState<string>('all');
  const [selectedAsset, setSelectedAsset] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [minConfidence, setMinConfidence] = useState<number>(0);

  // Watchlist list state
  const [watchlist, setWatchlist] = useState<string[]>([]);

  // Real signals from backend
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | undefined>();

  // Fetch signals from backend
  useEffect(() => {
    const fetchSignals = async () => {
      setLoading(true);
      setError(undefined);

      try {
        const response = await fetch(`${API_URL}/api/v1/signals?limit=50`);
        const data = await response.json();

        if (response.ok && Array.isArray(data)) {
          setSignals(data);
        } else {
          setError(data.detail || 'Failed to fetch signals');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Network error');
      } finally {
        setLoading(false);
      }
    };

    fetchSignals();
    const interval = setInterval(fetchSignals, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const toggleWatchlist = (symbol: string) => {
    setWatchlist(prev => {
      const isAlready = prev.includes(symbol);
      if (isAlready) {
        triggerToast('info', 'Watchlist Updated', `Removed ${symbol} from active tracking lists.`);
        return prev.filter(s => s !== symbol);
      } else {
        triggerToast('success', 'Watchlist Updated', `Added ${symbol} into active tracking lists.`);
        return [...prev, symbol];
      }
    });
  };

  const handleExecuteTradeAction = (sig: Signal) => {
    if (sig.type === 'HOLD') {
      triggerToast('info', 'Trade Aborted', 'HOLD signals do not translate to order executions.');
      return;
    }
    const totalCost = sig.price * 1; // 1 share default
    executeTrade(sig.symbol, sig.type, 1, sig.price, totalCost, sig.agent);
  };

  // Perform multi-parameters filtering on signals array
  const filteredSignals = signals.filter(sig => {
    const matchesAgent = selectedAgent === 'all' || sig.agent.toLowerCase() === selectedAgent.toLowerCase();
    const matchesAsset = selectedAsset === 'all' || sig.symbol.toLowerCase() === selectedAsset.toLowerCase();
    const matchesType = selectedType === 'all' || sig.type.toLowerCase() === selectedType.toLowerCase();
    const matchesConf = sig.confidence >= minConfidence;
    return matchesAgent && matchesAsset && matchesType && matchesConf;
  });

  const clearAllFilters = () => {
    setSelectedAgent('all');
    setSelectedAsset('all');
    setSelectedType('all');
    setMinConfidence(0);
    triggerToast('info', 'Filters Cleared', 'Restoring all signal listings.');
  };

  const dismissSignal = (id: string, symbol: string) => {
    setSignals(prev => prev.filter(s => s.id !== id));
    triggerToast('info', 'Signal Dismissed', `Removed ${symbol} from active feed.`);
  };

  const getSignalTypeClass = (type: string) => {
    switch(type) {
      case 'BUY': return 'text-[#10B981] bg-[#10B981]/10 border-[#10B981]/35';
      case 'SELL': return 'text-[#EF4444] bg-[#EF4444]/10 border-[#EF4444]/35';
      case 'HOLD': default: return 'text-[#3B82F6] bg-[#3B82F6]/10 border-[#3B82F6]/35';
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full">
      
      {/* Title Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight font-sans">Signals Feed Terminal</h1>
          <p className="text-sm text-[#94A3B8]">Deploy active models and intercept trade directives as they occur.</p>
        </div>
        <span className="bg-[#EF4444]/15 border border-[#EF4444]/30 text-[#EF4444] px-3 py-1 rounded-full text-xs font-bold font-mono uppercase tracking-wider animate-pulse self-start">
          🔴 Live Signals Network
        </span>
      </div>

      {/* FILTER BAR ROW SPECIFICATION */}
      <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-[#475569]/30 pb-2">
          <Filter className="w-4 h-4 text-[#3B82F6]" />
          <span className="font-mono text-[10px] font-bold uppercase text-[#94A3B8]">Live Feed Parameters Range</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {/* Filter Agent */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Scanning Agent</label>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="h-9 bg-[#0F172A] border border-[#475569] rounded-lg px-2.5 text-xs text-[#F8FAFC] font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">All Active Agents</option>
              <option value="director">Director Agent</option>
              <option value="quant">Quant Agent</option>
              <option value="risk">Risk Agent</option>
            </select>
          </div>

          {/* Filter Asset */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Specific Asset Symbol</label>
            <select
              value={selectedAsset}
              onChange={(e) => setSelectedAsset(e.target.value)}
              className="h-9 bg-[#0F172A] border border-[#475569] rounded-lg px-2.5 text-xs text-[#F8FAFC] font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">Full Market Index</option>
              <option value="nvda">NVIDIA Corp (NVDA)</option>
              <option value="aapl">Apple Inc (AAPL)</option>
              <option value="tsla">Tesla Inc (TSLA)</option>
            </select>
          </div>

          {/* Filter Type */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-[#94A3B8] font-mono leading-none">Signal Type</label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="h-9 bg-[#0F172A] border border-[#475569] rounded-lg px-2.5 text-xs text-[#F8FAFC] font-mono focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="all">All Signals</option>
              <option value="buy">BUY Operations</option>
              <option value="sell">SELL Operations</option>
              <option value="hold">HOLD Operations</option>
            </select>
          </div>

          {/* Score rating sliders selectors */}
          <div className="flex flex-col gap-1.5">
            <span className="text-xs text-[#94A3B8] font-mono leading-none">Minimum Confidence Score</span>
            <div className="flex items-center gap-1.5 h-9 bg-[#0F172A] border border-[#475569] rounded-lg px-2 text-xs">
              {[50, 60, 70, 80].map(score => (
                <button
                  key={score}
                  onClick={() => setMinConfidence(minConfidence === score ? 0 : score)}
                  className={`flex-1 py-1 rounded text-[10px] font-mono font-bold transition outline-none ${
                    minConfidence === score ? 'bg-[#3B82F6] text-white' : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#334155]'
                  }`}
                >
                  {score}%+
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Clear Actions Pill lists */}
        {(selectedAgent !== 'all' || selectedAsset !== 'all' || selectedType !== 'all' || minConfidence > 0) && (
          <div className="flex items-center justify-between border-t border-[#475569]/20 pt-2.5">
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span className="text-[#94A3B8]">Applied:</span>
              {selectedType !== 'all' && (
                <span className="bg-[#3B82F6]/10 text-[#3B82F6] px-2.5 py-0.5 rounded border border-[#3B82F6]/20 font-mono text-[10px] uppercase font-bold">
                  Type: {selectedType}
                </span>
              )}
              {selectedAgent !== 'all' && (
                <span className="bg-[#6366F1]/10 text-[#6366F1] px-2.5 py-0.5 rounded border border-[#6366F1]/20 font-mono text-[10px] uppercase font-bold">
                  Model: {selectedAgent}
                </span>
              )}
              {selectedAsset !== 'all' && (
                <span className="bg-purple-500/10 text-purple-400 px-2.5 py-0.5 rounded border border-purple-500/20 font-mono text-[10px] uppercase font-bold">
                  Target: {selectedAsset}
                </span>
              )}
              {minConfidence > 0 && (
                <span className="bg-[#F59E0B]/10 text-[#F59E0B] px-2.5 py-0.5 rounded border border-[#F59E0B]/20 font-mono text-[10px] uppercase font-bold">
                  Score: {minConfidence}%
                </span>
              )}
            </div>
            <button onClick={clearAllFilters} className="text-xs text-[#EF4444] hover:underline font-mono">
              Clear All Filtering Range
            </button>
          </div>
        )}
      </div>

      {/* SIGNALS CARDS STACK */}
      <div className="flex flex-col gap-4">
        {filteredSignals.length > 0 ? (
          filteredSignals.map(sig => {
            const isBUY = sig.type === 'BUY';
            const isSELL = sig.type === 'SELL';
            const isHOLD = sig.type === 'HOLD';
            const watchlisted = watchlist.includes(sig.symbol);

            return (
              <div 
                key={sig.id}
                className="bg-[#1E293B] border border-[#475569] rounded-xl overflow-hidden shadow-lg flex flex-col md:flex-row relative"
              >
                {/* Visual type side pillar */}
                <div className={`w-full md:w-1.5 self-stretch ${
                  isBUY ? 'bg-[#10B981]' : isSELL ? 'bg-[#EF4444]' : 'bg-[#3B82F6]'
                }`} />

                {/* Main Card Content */}
                <div className="flex-1 p-5 flex flex-col gap-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#475569]/30 pb-3">
                    <div className="flex items-center gap-3">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-black tracking-widest border uppercase font-mono ${getSignalTypeClass(sig.type)}`}>
                        {sig.type}
                      </span>
                      <div className="flex flex-col">
                        <span className="font-black text-white text-md tracking-tight font-sans">{sig.symbol}</span>
                        <span className="text-xs text-[#94A3B8]">{sig.name}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 font-mono text-xs text-[#94A3B8]">
                      <span>Dispatcher: <strong className="text-[#3B82F6]">AI {sig.agent}</strong></span>
                      <span className="text-[#475569]">|</span>
                      <span>Confidence: <strong className="text-white">{sig.confidence}%</strong></span>
                      <span className="text-[#475569]">|</span>
                      <span>{sig.time}</span>
                    </div>
                  </div>

                  {/* Thesis description */}
                  <div className="flex flex-col gap-2">
                    <span className="font-mono text-[10px] text-[#94A3B8] uppercase font-bold flex items-center gap-1">
                      <Info className="w-3.5 h-3.5" /> Analytical Hypothesis Thesis
                    </span>
                    <p className="text-sm text-[#F8FAFC] leading-relaxed select-text">{sig.thesis}</p>
                  </div>

                  {/* Expected upside stats container */}
                  <div className="bg-[#0F172A] border border-[#475569]/50 p-3 rounded-lg grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs select-none">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[#94A3B8] text-[10px] uppercase">Transaction Target</span>
                      <span className="font-bold text-white uppercase">{sig.type} {sig.shares} Shares @ ${sig.price.toLocaleString()}</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[#94A3B8] text-[10px] uppercase">Upside Outlook</span>
                      <span className="font-bold text-[#10B981]">{sig.expectedUpside}</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[#94A3B8] text-[10px] uppercase">Margin Safety parameters</span>
                      <span className="font-bold text-white">Stop: ${sig.stopVal} | Tgt: ${sig.targetVal}</span>
                    </div>
                  </div>

                  {/* Actions buttons shelf */}
                  <div className="flex items-center gap-2 flex-wrap border-t border-[#475569]/30 pt-3 mt-1">
                    {!isHOLD && (
                      <button
                        onClick={() => handleExecuteTradeAction(sig)}
                        className="bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-black py-2 px-4 rounded-lg flex items-center gap-1.5 outline-none transition"
                      >
                        <Check className="w-4 h-4" /> EXECUTE TRANSACTION
                      </button>
                    )}
                    <button
                      onClick={() => toggleWatchlist(sig.symbol)}
                      className={`text-xs font-bold py-2 px-4 rounded-lg flex items-center gap-1.5 outline-none border transition ${
                        watchlisted 
                          ? 'bg-[#10B981]/15 border-[#10B981] text-[#10B981]' 
                          : 'border-[#475569] text-[#94A3B8] hover:bg-[#334155] hover:text-[#F8FAFC]'
                      }`}
                    >
                      <Star className={`w-4 h-4 ${watchlisted ? 'fill-current' : ''}`} /> 
                      {watchlisted ? 'TRACKING ON WATCHLIST' : 'ADD TO WATCHLIST'}
                    </button>
                    <button
                      onClick={() => dismissSignal(sig.id, sig.symbol)}
                      className="border border-[#475569] text-[#94A3B8] hover:bg-red-500/10 hover:border-red-400 hover:text-red-400 text-xs font-bold py-2 px-3 rounded-lg flex items-center gap-1.5 outline-none transition ml-auto"
                    >
                      <Trash2 className="w-4 h-4" /> DISMISS
                    </button>
                  </div>

                </div>

              </div>
            );
          })
        ) : (
          <div className="bg-[#1E293B] border border-[#475569] p-8 text-center rounded-xl flex flex-col items-center justify-center gap-3">
            <Radio className="w-8 h-8 text-[#94A3B8] opacity-50 animate-pulse" />
            <span className="text-sm font-mono text-[#94A3B8]">No signal alerts found matching specified filters constraints.</span>
            <button onClick={clearAllFilters} className="bg-[#3B82F6] text-white text-xs font-bold py-2 px-3 rounded-lg outline-none transition">
              Refresh Index
            </button>
          </div>
        )}
      </div>

    </div>
  );
}
