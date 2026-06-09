'use client';

import React, { useState } from 'react';
import { 
  Users, 
  TrendingUp, 
  ExternalLink, 
  UserPlus, 
  UserPlus2, 
  Check, 
  X, 
  ChevronLeft, 
  ChevronRight,
  TrendingDown,
  Info
} from 'lucide-react';
import { Toast } from '@/app/page';

interface CopyTradeTabProps {
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

interface Trader {
  id: string;
  rank: string;
  user: string;
  color: string;
  ret: string;
  winRate: string;
  aum: string;
  trades: number;
  copiers: string;
  following: boolean;
  avatarInitails: string;
}

export default function CopyTradeTab({ triggerToast }: CopyTradeTabProps) {
  // Leaderboard list - empty initially, would fetch from backend
  const [traders, setTraders] = useState<Trader[]>([]);

  // Active copied holdings - empty initially
  const [copiedPositions, setCopiedPositions] = useState<Array<{ id: string; trader: string; symbol: string; entry: number; current: number; pnl: string }>>([]);

  // Detail user profile states
  const [selectedTraderProfile, setSelectedTraderProfile] = useState<Trader | null>(null);

  // Toggle Following status of trader
  const toggleFollowTrader = (id: string, name: string) => {
    setTraders(prev => prev.map(t => {
      if (t.id === id) {
        const nextState = !t.following;
        triggerToast(
          nextState ? 'success' : 'warning', 
          nextState ? 'Copy Connection Online' : 'Copy Connection Dispatched', 
          nextState ? `Commenced passive order synthesis for ${name}.` : `Terminated copy allocations from ${name}.`
        );
        return { ...t, following: nextState };
      }
      return t;
    }));
  };

  // Close direct copied allocation element
  const unfollowCopiedPosition = (id: string, symbol: string, traderName: string) => {
    setCopiedPositions(prev => prev.filter(p => p.id !== id));
    triggerToast('warning', 'Position Extinguished', `Successfully liquidated copied allocation of ${symbol} from ${traderName}.`);
  };

  // Active follow metric counters
  const activeFollowsCount = traders.filter(t => t.following).length;

  return (
    <div className="flex flex-col gap-6 w-full">
      
      {/* Visual Title */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight font-sans">Copy Trading Desk</h1>
        <p className="text-sm text-[#94A3B8]">Bridge direct allocation models with audited top performers in real-time.</p>
      </div>

      {/* SUMMARY BOX CARDS ROW */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Connections Active</span>
            <span className="text-2xl font-black font-mono text-white">{activeFollowsCount} Traders</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">Rebalancing live allocations</span>
          </div>
          <div className="p-3 bg-[#3B82F6]/10 text-[#3B82F6] rounded-xl">
            <Users className="w-5 h-5" />
          </div>
        </div>

        {/* Card 2: Total Copy P&L */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Total Copy P&L</span>
            <span className="text-2xl font-black font-mono text-[#94A3B8]">$0.00</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">No copied trades yet</span>
          </div>
          <div className="p-3 bg-[#94A3B8]/10 text-[#94A3B8] rounded-xl">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        {/* Card 3: Top Producer */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Alpha Top Producer</span>
            <span className="text-xl font-black font-mono text-[#94A3B8]">N/A</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">Enable copy trading</span>
          </div>
          <div className="p-3 bg-[#94A3B8]/10 text-[#94A3B8] rounded-xl">
            👑
          </div>
        </div>

        {/* Card 4 */}
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold text-slate-400">Copied Holdings</span>
            <span className="text-2xl font-black font-mono text-white">{copiedPositions.length} Items</span>
            <span className="text-[11px] text-[#94A3B8] font-mono">Hedged across 3 desks</span>
          </div>
          <div className="p-3 bg-[#EC4899]/10 text-[#EC4899] rounded-xl">
            🔥
          </div>
        </div>
      </div>

      {/* LEADERBOARD TABLE GRID */}
      <div className="bg-[#1E293B] border border-[#475569] rounded-xl p-4">
        <div className="flex items-center justify-between mb-4 border-b border-[#475569] pb-3 select-none">
          <div className="flex flex-col">
            <h3 className="font-bold text-md text-[#F8FAFC]">Verified Traders Leaderboard</h3>
            <span className="text-xs font-mono text-[#94A3B8]">Audit-proven capital managers sorting live ROI indices</span>
          </div>
          <button 
            onClick={() => triggerToast('info', 'Leaderboard Scanned', 'Synchronized audited return streams.')}
            className="text-xs text-[#3B82F6] hover:underline font-mono"
          >
            Refresh index
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono text-[#94A3B8] min-w-[700px]">
            <thead>
              <tr className="border-b border-[#475569] text-slate-400 font-bold uppercase tracking-wide text-[10px] h-8 select-none">
                <th className="pb-2 text-center w-12">Rank</th>
                <th className="pb-2">Trader Account</th>
                <th className="pb-2 text-right">Trailing ROI</th>
                <th className="pb-2 text-right">Win Frequency</th>
                <th className="pb-2 text-right">Audited AUM</th>
                <th className="pb-2 text-right">Copiers Count</th>
                <th className="pb-2 text-right w-40">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#475569]/30">
              {traders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12">
                    <div className="flex flex-col items-center justify-center gap-3">
                      <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center">
                        <Users className="w-8 h-8 text-gray-500" />
                      </div>
                      <div className="text-center">
                        <h4 className="text-lg font-bold text-white mb-1">No Traders Yet</h4>
                        <p className="text-sm text-gray-400">Leaderboard will appear when copy trading is enabled</p>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                traders.map((trader) => (
                <tr key={trader.id} className="h-14 hover:bg-[#334155]/20 transition ease-out">
                  <td className="text-center font-bold text-[#F8FAFC] text-sm">{trader.rank}</td>
                  <td>
                    <div 
                      onClick={() => setSelectedTraderProfile(trader)}
                      className="flex items-center gap-2.5 cursor-pointer group"
                    >
                      <div className="w-8 h-8 rounded-full bg-[#0F172A] flex items-center justify-center font-bold text-xs text-white border border-[#475569]/50 group-hover:border-[#3B82F6]">
                        {trader.avatarInitails}
                      </div>
                      <div className="flex flex-col">
                        <span className="font-bold text-[#3B82F6] group-hover:underline">{trader.user}</span>
                        <span className="text-[10px] text-[#94A3B8]">{trader.trades} completed trades</span>
                      </div>
                    </div>
                  </td>
                  <td className="text-right font-bold text-[#10B981]">{trader.ret}</td>
                  <td className="text-right font-bold text-white">{trader.winRate}</td>
                  <td className="text-right text-[#F8FAFC]">{trader.aum}</td>
                  <td className="text-right">{trader.copiers} copiers</td>
                  <td className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setSelectedTraderProfile(trader)}
                        className="p-1 px-2 border border-[#475569] hover:bg-[#334155] rounded text-[10px] font-bold text-white transition outline-none"
                      >
                        PROFILE
                      </button>
                      
                      <button
                        onClick={() => toggleFollowTrader(trader.id, trader.user)}
                        className={`py-1 px-3 rounded text-[10px] font-bold flex items-center gap-1.5 transition outline-none ${
                          trader.following
                            ? 'bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 hover:bg-[#10B981]/25'
                            : 'bg-[#3B82F6] hover:bg-[#2563EB] text-white'
                        }`}
                      >
                        {trader.following ? (
                          <>
                            <Check className="w-3 h-3" /> COPIED ✓
                          </>
                        ) : (
                          <>
                            <UserPlus className="w-3 h-3" /> COPY TRADER
                          </>
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ACTIVE COPY POSITION TABLES LISTINGS */}
      <div className="bg-[#1E293B] border border-[#475569] rounded-xl p-4">
        <div className="flex flex-col gap-1 mb-4 border-b border-[#475569] pb-3">
          <h3 className="font-bold text-md text-[#F8FAFC]">Active Synthesized Holdings</h3>
          <span className="text-xs font-mono text-[#94A3B8]">Secondary order payloads currently linked with follower allocations</span>
        </div>

        <div className="overflow-x-auto">
          {copiedPositions.length > 0 ? (
            <table className="w-full text-left text-xs font-mono text-[#94A3B8]">
              <thead>
                <tr className="border-b border-[#475569] text-slate-400 font-bold uppercase tracking-wide text-[10px] h-8 select-none">
                  <th className="pb-2">Source Trader</th>
                  <th className="pb-2">Asset Symbol</th>
                  <th className="pb-2 text-right">Entry Point</th>
                  <th className="pb-2 text-right">Market Valuation</th>
                  <th className="pb-2 text-right">Total Net Return</th>
                  <th className="pb-2 text-right w-36">Command Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#475569]/30">
                {copiedPositions.map(pos => (
                  <tr key={pos.id} className="h-11 hover:bg-[#334155]/20 transition ease-out">
                    <td className="font-bold text-[#3B82F6]">{pos.trader}</td>
                    <td className="font-bold text-white">{pos.symbol}</td>
                    <td className="text-right">${pos.entry.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                    <td className="text-right">${pos.current.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                    <td className="text-right font-bold text-[#10B981]">{pos.pnl}</td>
                    <td className="text-right">
                      <button
                        onClick={() => unfollowCopiedPosition(pos.id, pos.symbol, pos.trader)}
                        className="py-1 px-2.5 border border-[#475569] hover:bg-red-500/10 hover:border-red-400 hover:text-red-400 rounded text-[10px] font-bold font-mono uppercase tracking-wider transition outline-none"
                      >
                        LIQUIDATE
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-8 text-[#94A3B8] font-mono text-xs">
              No active copy allocations. Select a top performer above to initiate order synthesis.
            </div>
          )}
        </div>
      </div>

      {/* TRADER OVERLAY METRICS MODAL */}
      {selectedTraderProfile && (
        <div className="fixed inset-0 bg-[#0F172A]/80 flex items-center justify-center p-4 z-50 animate-fade-in" onClick={() => setSelectedTraderProfile(null)}>
          <div className="bg-[#1E293B] border border-[#475569] rounded-xl max-w-lg w-full p-6 flex flex-col gap-4 shadow-2xl animate-scale-up" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-[#475569] pb-3">
              <div className="flex items-center gap-3">
                <span className="text-xl">{selectedTraderProfile.rank}</span>
                <span className="font-black text-white text-md font-mono">{selectedTraderProfile.user} Profile</span>
              </div>
              <button onClick={() => setSelectedTraderProfile(null)}>
                <X className="w-5 h-5 text-[#94A3B8] hover:text-white" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 font-mono text-xs text-[#94A3B8] py-2 border-b border-[#475569]/30">
              <div className="flex flex-col gap-1 leading-normal">
                <span>Trailing Return (ROI)</span>
                <strong className="text-[#10B981] text-lg">{selectedTraderProfile.ret}</strong>
              </div>
              <div className="flex flex-col gap-1 leading-normal">
                <span>Operational Win rate</span>
                <strong className="text-white text-lg">{selectedTraderProfile.winRate}</strong>
              </div>
              <div className="flex flex-col gap-1 leading-normal">
                <span>Managed Assets (AUM)</span>
                <strong className="text-[#3B82F6] text-lg">{selectedTraderProfile.aum}</strong>
              </div>
              <div className="flex flex-col gap-1 leading-normal">
                <span>Audited Copiers Followers</span>
                <strong className="text-white text-lg">{selectedTraderProfile.copiers} users</strong>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="font-mono text-[10px] text-[#94A3B8] font-bold uppercase flex items-center gap-1">
                <Info className="w-3.5 h-3.5" /> Performance Summary
              </span>
              <p className="text-xs text-[#94A3B8] leading-relaxed">
                This account operates on continuous automated algorithms scanning mid-cap sectors. Maintains a maximum risk-per-trade boundary of 1.5% and utilizes multi-layer volatility hedgers. Fully audited on-chain profile.
              </p>
            </div>

            <button
              onClick={() => {
                toggleFollowTrader(selectedTraderProfile.id, selectedTraderProfile.user);
                setSelectedTraderProfile(null);
              }}
              className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white text-xs font-bold py-2.5 rounded-lg transition"
            >
              {selectedTraderProfile.following ? 'DISCONNECT COPY SYNERGY' : 'SYNCHRONIZE COPY ACTIONS'}
            </button>
          </div>
        </div>
      )}

      {/* Styled keyframes for overlay modals imports */}
      <style jsx global>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUp {
          from { transform: scale(0.95); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        .animate-fade-in {
          animation: fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .animate-scale-up {
          animation: scaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}</style>

    </div>
  );
}
