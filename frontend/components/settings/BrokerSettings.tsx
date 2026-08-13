'use client';

import { useState, useEffect } from 'react';
import { DollarSign, Activity, Info } from 'lucide-react';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface UniversalPaperTradingConfig {
  enabled: boolean;
  initial_capital: number;
  current_balance: number;
  total_pnl: number;
  currency: string;
}

interface BrokerSettingsProps {
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
  onSave?: () => void;
}

export default function BrokerSettings({ triggerToast, onSave }: BrokerSettingsProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<UniversalPaperTradingConfig>({
    enabled: true,
    initial_capital: 10000,
    current_balance: 10000,
    total_pnl: 0,
    currency: 'USD'
  });

  const deviceId = getOrCreateDeviceId();

  useEffect(() => {
    loadConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadConfig = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/settings/universal-paper-trading`, {
        headers: { 'X-Device-ID': deviceId }
      });
      
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Failed to load universal paper trading config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/settings/universal-paper-trading`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId
        },
        body: JSON.stringify({
          enabled: config.enabled,
          initial_capital: config.initial_capital,
          currency: config.currency
        })
      });

      if (response.ok) {
        triggerToast('success', 'Settings Saved', 'Universal paper trading configuration updated');
        onSave?.();
      } else {
        throw new Error('Failed to save');
      }
    } catch {
      triggerToast('error', 'Save Failed', 'Failed to save universal paper trading settings');
    } finally {
      setSaving(false);
    }
  };

  const formatCurrency = (amount: number) => {
    const symbol = config.currency === 'USD' ? '$' : 
                   config.currency === 'NGN' ? '₦' : '¥';
    return `${symbol}${Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  if (loading) {
    return <div className="text-center py-4 text-gray-400">Loading...</div>;
  }

  return (
    <div className="bg-[#1E293B] rounded-lg p-4 border border-[#475569] space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <Activity className="w-5 h-5 text-[#10B981]" />
        <h3 className="text-md font-semibold text-white">Universal Paper Trading</h3>
      </div>

      {/* Toggle */}
      <div className="flex items-center justify-between p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
        <div>
          <p className="text-sm font-semibold text-white">
            {config.enabled ? 'Paper Trading Active' : 'Live Trading Mode'}
          </p>
          <p className="text-xs text-gray-400">
            {config.enabled 
              ? 'AI simulates trades without risking real capital' 
              : '⚠️ Real trades will be executed with connected brokers'}
          </p>
        </div>
        <button
          onClick={() => setConfig({ ...config, enabled: !config.enabled })}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            config.enabled ? 'bg-[#10B981]' : 'bg-[#EF4444]'
          }`}
        >
          <span
            className={`${
              config.enabled ? 'translate-x-6' : 'translate-x-1'
            } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
          />
        </button>
      </div>

      {/* Capital Input (only when enabled) */}
      {config.enabled && (
        <div className="space-y-2">
          <label htmlFor="virtual-capital" className="text-sm text-gray-300 flex items-center gap-1">
            <DollarSign className="w-4 h-4" />
            Virtual Initial Capital
          </label>
          <input
            id="virtual-capital"
            type="number"
            value={config.initial_capital}
            onChange={(e) => setConfig({ ...config, initial_capital: parseFloat(e.target.value) || 0 })}
            className="w-full px-3 py-2 bg-[#0F172A] border border-[#475569] rounded-lg text-white focus:outline-none focus:border-[#10B981]"
          />
        </div>
      )}

      {/* Currency Selector */}
      <div className="space-y-2">
        <label htmlFor="broker-currency" className="text-sm text-gray-300">Currency</label>
        <select
          id="broker-currency"
          value={config.currency}
          onChange={(e) => setConfig({ ...config, currency: e.target.value })}
          className="w-full px-3 py-2 bg-[#0F172A] border border-[#475569] rounded-lg text-white focus:outline-none focus:border-[#10B981]"
        >
          <option value="USD">USD</option>
          <option value="NGN">NGN</option>
          <option value="CNY">CNY</option>
        </select>
      </div>

      {/* P&L Display */}
      {config.enabled && (
        <div className="grid grid-cols-2 gap-3 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
          <div>
            <p className="text-xs text-gray-400 mb-1">Current Balance</p>
            <p className="text-lg font-bold text-white">
              {formatCurrency(config.current_balance)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Total P&L</p>
            <p className={`text-lg font-bold ${config.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {config.total_pnl >= 0 ? '+' : ''}{formatCurrency(config.total_pnl)}
            </p>
          </div>
        </div>
      )}

      {/* Info */}
      <div className={`p-3 rounded border ${
        config.enabled 
          ? 'bg-blue-500/10 border-blue-500/30' 
          : 'bg-red-500/10 border-red-500/30'
      }`}>
        <p className="text-xs flex items-start gap-1" style={{ 
          color: config.enabled ? '#60A5FA' : '#F87171' 
        }}>
          <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
          <span>
            {config.enabled 
              ? 'AI will simulate trades and track performance without touching real broker accounts.'
              : 'Live mode enabled. All trades will use real broker accounts and real capital.'}
          </span>
        </p>
      </div>

      {/* Save Button */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full py-2 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {saving ? 'Saving...' : 'Save Configuration'}
      </button>
    </div>
  );
}