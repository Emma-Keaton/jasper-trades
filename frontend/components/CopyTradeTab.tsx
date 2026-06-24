'use client';

import React, { useState, useEffect } from 'react';
import { Users, TrendingUp, ExternalLink, Award } from 'lucide-react';
import { Toast } from '@/app/page';
import { useCurrencyFormatter } from '@/lib/currencyContext';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface CopyTradeTabProps {
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

interface Trader {
  trader_id: string;
  trader_name: string;
  total_return: number;
  win_rate: number;
  total_followers: number;
  total_aum: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  trades_count: number;
  is_verified: boolean;
}

interface CopyTradeStats {
  following_count: number;
  total_copied_trades: number;
  total_pnl: number;
  avg_pnl: number;
  win_rate: number;
  total_signals_copied: number;
}

interface CopyTrade {
  id: number;
  follow_id: number;
  source_signal_id: number;
  symbol: string;
  action: string;
  quantity: number;
  copied_at: string;
  copy_percentage: number;
  pnl: number;
  pnl_percent: number;
  closed_at: string | null;
}

export default function CopyTradeTab({ triggerToast }: CopyTradeTabProps) {
  const { formatMoney } = useCurrencyFormatter();
  const [traders, setTraders] = useState<Trader[]>([]);
  const [stats, setStats] = useState<CopyTradeStats | null>(null);
  const [copyTrades, setCopyTrades] = useState<CopyTrade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [followingMap, setFollowingMap] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchLeaderboard();
    fetchStats();
    fetchCopyTrades();
  }, []);

  const fetchLeaderboard = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/traders/leaderboard?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setTraders(data);
      }
    } catch (err) {
      console.error('Failed to fetch leaderboard:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/copytrade/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const fetchCopyTrades = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/copytrade/history?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setCopyTrades(data.copy_trades || []);
      }
    } catch (err) {
      console.error('Failed to fetch copy trades:', err);
    }
  };

  const toggleFollowTrader = async (traderId: string, traderName: string) => {
    try {
      const isFollowing = followingMap[traderId];
      const endpoint = isFollowing ? '/unfollow' : '/follow';
      const method = isFollowing ? 'POST' : 'POST';

      const res = await fetch(`${API_URL}/api/v1/traders/${traderId}${endpoint}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: isFollowing ? undefined : JSON.stringify({
          trader_id: traderId,
          copy_percentage: 100,
          max_position_size: 10000,
          auto_copy: true,
        }),
      });

      if (res.ok) {
        setFollowingMap(prev => ({ ...prev, [traderId]: !isFollowing }));
        triggerToast(
          isFollowing ? 'warning' : 'success',
          isFollowing ? 'Unfollowed Trader' : 'Following Trader',
          isFollowing ? `Stopped copying ${traderName}` : `Now copying ${traderName}'s trades`
        );
        fetchStats();
      } else {
        const error = await res.json();
        triggerToast('error', 'Error', error.detail || 'Failed to update follow status');
      }
    } catch (err: any) {
      triggerToast('error', 'Error', err.message || 'Failed to update follow status');
    }
  };

  const totalPnl = stats?.total_pnl || 0;
  const winRate = stats?.win_rate || 0;

  return (
    <div className="flex flex-col gap-6 w-full">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight font-sans">Copy Trading Desk</h1>
        <p className="text-sm text-[#94A3B8]">Follow top performers and auto-copy their trades in real-time.</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Following</span>
            <span className="text-2xl font-black font-mono text-white">{stats?.following_count || 0} Traders</span>
          </div>
          <div className="p-3 bg-[#3B82F6]/10 text-[#3B82F6] rounded-xl">
            <Users className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Total Copy P&L</span>
            <span className={`text-2xl font-black font-mono ${totalPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              {totalPnl >= 0 ? '+' : ''}{formatMoney(Math.abs(totalPnl), 'USD')}
            </span>
          </div>
          <div className="p-3 bg-[#10B981]/10 text-[#10B981] rounded-xl">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Win Rate</span>
            <span className="text-2xl font-black font-mono text-white">{winRate.toFixed(1)}%</span>
          </div>
          <div className="p-3 bg-[#F59E0B]/10 text-[#F59E0B] rounded-xl">
            <Award className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase font-mono text-[#94A3B8] font-bold">Copied Trades</span>
            <span className="text-2xl font-black font-mono text-white">{stats?.total_copied_trades || 0}</span>
          </div>
          <div className="p-3 bg-[#8B5CF6]/10 text-[#8B5CF6] rounded-xl">
            <ExternalLink className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Leaderboard Table */}
      <div className="bg-[#1E293B] border border-[#475569] rounded-xl overflow-hidden">
        <div className="p-4 border-b border-[#475569]">
          <h2 className="text-lg font-bold text-white font-sans">Top Traders Leaderboard</h2>
          <p className="text-sm text-[#94A3B8]">Ranked by total returns</p>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400">Loading leaderboard...</div>
        ) : traders.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No traders available yet</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#0F172A]">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-mono text-[#94A3B8] uppercase">Rank</th>
                  <th className="px-4 py-3 text-left text-xs font-mono text-[#94A3B8] uppercase">Trader</th>
                  <th className="px-4 py-3 text-right text-xs font-mono text-[#94A3B8] uppercase">Return</th>
                  <th className="px-4 py-3 text-right text-xs font-mono text-[#94A3B8] uppercase">Win Rate</th>
                  <th className="px-4 py-3 text-right text-xs font-mono text-[#94A3B8] uppercase">Followers</th>
                  <th className="px-4 py-3 text-right text-xs font-mono text-[#94A3B8] uppercase">Trades</th>
                  <th className="px-4 py-3 text-center text-xs font-mono text-[#94A3B8] uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#475569]">
                {traders.map((trader, index) => (
                  <tr key={trader.trader_id} className="hover:bg-[#334155]/50 transition-colors">
                    <td className="px-4 py-3 text-sm font-mono text-white">#{index + 1}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-xs">
                          {trader.trader_name.substring(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-white">{trader.trader_name}</div>
                          {trader.is_verified && (
                            <div className="text-xs text-[#10B981] flex items-center gap-1">
                              <Award className="w-3 h-3" /> Verified
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className={`px-4 py-3 text-right text-sm font-mono ${trader.total_return >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {trader.total_return >= 0 ? '+' : ''}{trader.total_return.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-mono text-white">{trader.win_rate.toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right text-sm font-mono text-white">{trader.total_followers}</td>
                    <td className="px-4 py-3 text-right text-sm font-mono text-white">{trader.trades_count}</td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => toggleFollowTrader(trader.trader_id, trader.trader_name)}
                        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                          followingMap[trader.trader_id]
                            ? 'bg-[#EF4444]/10 text-[#EF4444] hover:bg-[#EF4444]/20'
                            : 'bg-[#3B82F6]/10 text-[#3B82F6] hover:bg-[#3B82F6]/20'
                        }`}
                      >
                        {followingMap[trader.trader_id] ? 'Unfollow' : 'Follow'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Copy Trades */}
      {copyTrades.length > 0 && (
        <div className="bg-[#1E293B] border border-[#475569] rounded-xl overflow-hidden">
          <div className="p-4 border-b border-[#475569]">
            <h2 className="text-lg font-bold text-white font-sans">Recent Copied Trades</h2>
          </div>
          <div className="divide-y divide-[#475569]">
            {copyTrades.map((trade) => (
              <div key={trade.id} className="p-4 flex items-center justify-between">
                <div>
                  <div className="text-white font-medium">{trade.symbol}</div>
                  <div className="text-xs text-[#94A3B8]">
                    {new Date(trade.copied_at).toLocaleDateString()} • {trade.copy_percentage}% copy
                  </div>
                </div>
                <div className={`text-right font-mono ${trade.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                  <div>{trade.pnl >= 0 ? '+' : ''}{formatMoney(Math.abs(trade.pnl), 'USD')}</div>
                  <div className="text-xs">{trade.pnl_percent.toFixed(2)}%</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}