'use client';

import { useState, useEffect } from 'react';
import { Shield, Check, DollarSign, Percent, AlertTriangle } from 'lucide-react';
import { Toast } from '@/app/types';

interface TradingCaps {
  configured: boolean;
  portfolio_id: number;
  max_position_amount?: number;
  max_position_percentage?: number;
  daily_loss_limit?: number;
  daily_loss_percentage?: number;
  hard_limit: boolean;
  soft_limit_enabled: boolean;
  enabled: boolean;
}

interface TradingCapsSectionProps {
  portfolioId: number | null;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function TradingCapsSection({ portfolioId, triggerToast }: TradingCapsSectionProps) {
  const [caps, setCaps] = useState<TradingCaps>({
    configured: false,
    portfolio_id: portfolioId || 1,
    max_position_amount: undefined,
    max_position_percentage: undefined,
    daily_loss_limit: undefined,
    daily_loss_percentage: undefined,
    hard_limit: true,
    soft_limit_enabled: false,
    enabled: false,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCaps();
  }, [portfolioId]);

  const fetchCaps = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/trading-caps?portfolio_id=${portfolioId || 1}`);
      const data = await res.json();

      if (data.configured) {
        setCaps({
          configured: true,
          portfolio_id: portfolioId || 1,
          max_position_amount: data.max_position_amount,
          max_position_percentage: data.max_position_percentage,
          daily_loss_limit: data.daily_loss_limit,
          daily_loss_percentage: data.daily_loss_percentage,
          hard_limit: data.hard_limit ?? true,
          soft_limit_enabled: data.soft_limit_enabled ?? false,
          enabled: data.enabled ?? true,
        });
      }
    } catch (error) {
      console.error('Failed to load trading caps:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveCaps = async () => {
    if (!caps.max_position_amount && !caps.max_position_percentage && 
        !caps.daily_loss_limit && !caps.daily_loss_percentage) {
      triggerToast('warning', 'No Limits Set', 'Please set at least one risk limit');
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/trading-caps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_id: portfolioId || 1,
          max_position_amount: caps.max_position_amount,
          max_position_percentage: caps.max_position_percentage,
          daily_loss_limit: caps.daily_loss_limit,
          daily_loss_percentage: caps.daily_loss_percentage,
          hard_limit: caps.hard_limit,
          soft_limit_enabled: caps.soft_limit_enabled,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setCaps({ ...caps, configured: true, enabled: true });
        triggerToast('success', 'Trading Caps Saved', 'Your risk limits have been configured');
      } else {
        triggerToast('error', 'Save Failed', data.detail || 'Could not save trading caps');
      }
    } catch (error) {
      triggerToast('error', 'Save Failed', 'Could not save trading caps');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
        <div className="h-6 w-48 bg-gray-700 rounded animate-pulse mb-2" />
        <div className="h-4 w-80 bg-gray-700 rounded animate-pulse" />
      </section>
    );
  }

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-[#3B82F6]" />
          <h2 className="text-lg font-semibold text-white">Trading Caps & Risk Limits</h2>
        </div>
        {caps.configured && caps.enabled && (
          <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">
            Active
          </span>
        )}
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Protect your portfolio by limiting position sizes and daily losses.
        Prevents over-trading and excessive risk exposure.
      </p>

      {caps.configured && caps.enabled && (
        <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <div className="grid grid-cols-2 gap-4 text-sm">
            {caps.max_position_amount && (
              <div>
                <span className="text-gray-400">Max Position:</span>
                <span className="text-white font-mono ml-2">${caps.max_position_amount.toLocaleString()}</span>
              </div>
            )}
            {caps.max_position_percentage && (
              <div>
                <span className="text-gray-400">Max %:</span>
                <span className="text-white font-mono ml-2">{caps.max_position_percentage}%</span>
              </div>
            )}
            {caps.daily_loss_limit && (
              <div>
                <span className="text-gray-400">Daily Loss Limit:</span>
                <span className="text-white font-mono ml-2">${caps.daily_loss_limit.toLocaleString()}</span>
              </div>
            )}
            {caps.daily_loss_percentage && (
              <div>
                <span className="text-gray-400">Daily Loss %:</span>
                <span className="text-white font-mono ml-2">{caps.daily_loss_percentage}%</span>
              </div>
            )}
          </div>
          <div className="mt-2 pt-2 border-t border-blue-500/30 flex items-center gap-2">
            <span className={`text-xs px-2 py-1 rounded ${caps.hard_limit ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
              {caps.hard_limit ? 'Hard Limit (Block Trades)' : 'Soft Limit (Warn Only)'}
            </span>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {/* Position Limits */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-300 mb-2 flex items-center gap-2">
              <DollarSign className="w-4 h-4" />
              Max Position Amount ($)
            </label>
            <input
              type="number"
              value={caps.max_position_amount ?? ''}
              onChange={(e) => setCaps({ ...caps, max_position_amount: parseFloat(e.target.value) || undefined })}
              placeholder="e.g., 5000"
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#3B82F6]"
            />
            <p className="text-xs text-gray-500 mt-1">
              Maximum dollars per trade
            </p>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-2 flex items-center gap-2">
              <Percent className="w-4 h-4" />
              Max Position (%)
            </label>
            <input
              type="number"
              value={caps.max_position_percentage ?? ''}
              onChange={(e) => setCaps({ ...caps, max_position_percentage: parseFloat(e.target.value) || undefined })}
              placeholder="e.g., 20"
              min="0"
              max="100"
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#3B82F6]"
            />
            <p className="text-xs text-gray-500 mt-1">
              Percentage of portfolio per trade
            </p>
          </div>
        </div>

        {/* Daily Loss Limits */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-300 mb-2">Daily Loss Limit ($)</label>
            <input
              type="number"
              value={caps.daily_loss_limit ?? ''}
              onChange={(e) => setCaps({ ...caps, daily_loss_limit: parseFloat(e.target.value) || undefined })}
              placeholder="e.g., 2000"
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#3B82F6]"
            />
            <p className="text-xs text-gray-500 mt-1">
              Stop trading after this loss
            </p>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-2">Daily Loss Limit (%)</label>
            <input
              type="number"
              value={caps.daily_loss_percentage ?? ''}
              onChange={(e) => setCaps({ ...caps, daily_loss_percentage: parseFloat(e.target.value) || undefined })}
              placeholder="e.g., 5"
              min="0"
              max="100"
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#3B82F6]"
            />
            <p className="text-xs text-gray-500 mt-1">
              Stop trading after % loss
            </p>
          </div>
        </div>

        {/* Enforcement */}
        <div className="border-t border-[#475569] pt-4">
          <label className="block text-sm text-gray-300 mb-3">Enforcement Mode</label>
          <div className="space-y-2">
            <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-[#475569] hover:bg-[#334155]">
              <input
                type="radio"
                name="enforcement"
                checked={caps.hard_limit}
                onChange={() => setCaps({ ...caps, hard_limit: true })}
                className="w-4 h-4"
              />
              <div>
                <span className="text-sm font-medium text-white">Hard Limit</span>
                <p className="text-xs text-gray-500">Block any trade that exceeds caps</p>
              </div>
            </label>
            <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-[#475569] hover:bg-[#334155]">
              <input
                type="radio"
                name="enforcement"
                checked={!caps.hard_limit}
                onChange={() => setCaps({ ...caps, hard_limit: false })}
                className="w-4 h-4"
              />
              <div>
                <span className="text-sm font-medium text-white">Soft Limit</span>
                <p className="text-xs text-gray-500">Warn but allow trades (for testing)</p>
              </div>
            </label>
          </div>
        </div>

        {/* Enable/Disable */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={caps.enabled}
              onChange={(e) => setCaps({ ...caps, enabled: e.target.checked })}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-300">Enable trading caps</span>
          </label>
        </div>

        <button
          onClick={saveCaps}
          disabled={saving}
          className="w-full py-2.5 bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <AlertTriangle className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              {caps.configured ? 'Update Trading Caps' : 'Save Trading Caps'}
            </>
          )}
        </button>

        <div className="mt-3 p-3 bg-[#3B82F6]/10 border border-[#3B82F6]/30 rounded-lg">
          <p className="text-xs text-[#3B82F6]">
            💡 <strong>Recommended:</strong> Set max position to 10-20% of portfolio and daily loss limit to 5%.
            This prevents catastrophic losses while allowing room for growth.
          </p>
        </div>
      </div>
    </section>
  );
}