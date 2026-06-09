'use client';

import { useState } from 'react';
import { Save, DollarSign, Wallet, Percent, Clock, Split, RefreshCw, Check, AlertCircle } from 'lucide-react';
import { Toast } from '@/app/page';

interface PayoutConfig {
  payout_enabled: boolean;
  payout_percentage: number;
  payout_schedule_hour: number;
  payout_destination: 'crypto_wallet' | 'forex_account' | 'split';
  crypto_wallet: string;
  crypto_chain: 'ethereum' | 'solana' | 'bsc';
  split_ratio: number;
  min_payout_threshold: number;
  configured: boolean;
}

interface PayoutSectionProps {
  payoutConfig: PayoutConfig;
  setPayoutConfig: (config: PayoutConfig) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Common hours for scheduling
const SCHEDULE_HOURS = Array.from({ length: 24 }, (_, i) => i);

// Payout destinations
const PAYOUT_DESTINATIONS = [
  { value: 'crypto_wallet', label: 'Crypto Wallet (USDT)', icon: Wallet },
  { value: 'forex_account', label: 'Forex Account (Reinvest)', icon: DollarSign },
  { value: 'split', label: 'Split (Crypto + Forex)', icon: Split },
] as const;

export default function PayoutSection({ payoutConfig, setPayoutConfig, triggerToast }: PayoutSectionProps) {
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const savePayoutConfig = async () => {
    // Validate configuration
    if (payoutConfig.payout_enabled) {
      if (payoutConfig.payout_destination === 'crypto_wallet' && !payoutConfig.crypto_wallet) {
        triggerToast('error', 'Missing Wallet', 'Please enter your USDT wallet address');
        return;
      }
      
      if (payoutConfig.payout_destination === 'crypto_wallet' && 
          !payoutConfig.crypto_wallet.startsWith('0x') && 
          !(payoutConfig.crypto_wallet.length >= 32)) {
        triggerToast('error', 'Invalid Wallet', 'Wallet must be ERC20 (0x...) or SOLANA address');
        return;
      }

      if (payoutConfig.payout_percentage <= 0 || payoutConfig.payout_percentage > 100) {
        triggerToast('error', 'Invalid Percentage', 'Payout percentage must be 1-100%');
        return;
      }
    }

    setSaving(true);
    try {
      const deviceId = localStorage.getItem('device_id') || 'unknown';
      
      // Encrypt config before sending
      const response = await fetch(`${API_URL}/api/v1/settings/payout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify({
          payout_config: payoutConfig,
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setPayoutConfig({ ...payoutConfig, configured: true });
        triggerToast(
          'success',
          'Auto-Payout Saved',
          `Payout ${payoutConfig.payout_enabled ? 'enabled' : 'disabled'} - ${payoutConfig.payout_percentage}% ${getPayoutDestinationLabel()}`
        );
      } else {
        triggerToast('error', 'Save Failed', data.detail || 'Could not save payout settings');
      }
    } catch (error) {
      triggerToast('error', 'Save Failed', 'Could not save payout settings');
    } finally {
      setSaving(false);
    }
  };

  const testPayout = async () => {
    if (!payoutConfig.configured) {
      triggerToast('error', 'Not Configured', 'Save payout settings first');
      return;
    }

    setTesting(true);
    try {
      const deviceId = localStorage.getItem('device_id') || 'unknown';
      
      // Get portfolio ID
      const portfolioRes = await fetch(`${API_URL}/api/v1/portfolio`);
      const portfolios = await portfolioRes.json();
      
      if (!portfolios.data || portfolios.data.length === 0) {
        triggerToast('error', 'No Portfolio', 'Please create a portfolio first');
        setTesting(false);
        return;
      }

      const portfolioId = portfolios.data[0].id;

      // Trigger immediate payout (small test amount)
      const res = await fetch(`${API_URL}/api/v1/payout/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify({
          portfolio_id: portfolioId,
        }),
      });

      const data = await res.json();

      if (res.ok && data.executed) {
        triggerToast(
          'success',
          'Test Payout Executed',
          `Amount: $${data.amount?.toFixed(2) || '0.00'}, Status: ${data.status}`
        );
      } else {
        triggerToast(
          'info',
          'Test Skipped',
          data.reason || 'No profit available for test'
        );
      }
    } catch (error) {
      triggerToast('error', 'Test Failed', 'Could not execute test payout');
    } finally {
      setTesting(false);
    }
  };

  const getPayoutDestinationLabel = () => {
    const dest = PAYOUT_DESTINATIONS.find(d => d.value === payoutConfig.payout_destination);
    return dest?.label || 'Unknown';
  };

  const formatHour = (hour: number) => {
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour} ${ampm} ET`;
  };

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Percent className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Auto-Payout Configuration</h2>
        </div>
        {payoutConfig.configured && payoutConfig.payout_enabled && (
          <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">
            Active
          </span>
        )}
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Automatically distribute {payoutConfig.payout_percentage}% of daily trading profits.
        Configure payout destination (crypto wallet, forex reinvestment, or split).
      </p>

      <div className="space-y-4">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-3 bg-[#0F172A] rounded-lg">
          <div className="flex items-center gap-2">
            <Check className={`w-5 h-5 ${payoutConfig.payout_enabled ? 'text-green-500' : 'text-gray-500'}`} />
            <span className="text-sm text-white font-medium">Enable Auto-Payout</span>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={payoutConfig.payout_enabled}
              onChange={(e) => setPayoutConfig({ ...payoutConfig, payout_enabled: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
          </label>
        </div>

        {/* Payout Percentage */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Payout Percentage (%)
          </label>
          <div className="relative">
            <input
              type="number"
              min="1"
              max="100"
              value={payoutConfig.payout_percentage}
              onChange={(e) => setPayoutConfig({ ...payoutConfig, payout_percentage: parseFloat(e.target.value) || 50 })}
              disabled={!payoutConfig.payout_enabled}
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981] pl-10"
            />
            <Percent className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Percentage of daily profit to payout (e.g., 50% = half of profits distributed)
          </p>
        </div>

        {/* Schedule Hour */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Payout Schedule (ET)
          </label>
          <div className="relative">
            <select
              value={payoutConfig.payout_schedule_hour}
              onChange={(e) => setPayoutConfig({ ...payoutConfig, payout_schedule_hour: parseInt(e.target.value) })}
              disabled={!payoutConfig.payout_enabled}
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981] pl-10 appearance-none"
            >
              {SCHEDULE_HOURS.map((hour) => (
                <option key={hour} value={hour}>
                  {formatHour(hour)}
                </option>
              ))}
            </select>
            <Clock className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Auto-payout executes daily at this time (ET timezone)
          </p>
        </div>

        {/* Payout Destination */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Payout Destination
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {PAYOUT_DESTINATIONS.map((dest) => {
              const Icon = dest.icon;
              return (
                <button
                  key={dest.value}
                  onClick={() => setPayoutConfig({ ...payoutConfig, payout_destination: dest.value })}
                  disabled={!payoutConfig.payout_enabled}
                  className={`p-3 rounded-lg border flex flex-col items-center gap-2 transition-all ${
                    payoutConfig.payout_destination === dest.value
                      ? 'border-green-500 bg-green-500/20 text-white'
                      : 'border-[#475569] bg-[#0F172A] text-gray-400 hover:border-gray-500'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-xs font-medium">{dest.label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Choose where to send profits: crypto wallet, forex reinvestment, or split
          </p>
        </div>

        {/* Crypto Wallet (conditional) */}
        {payoutConfig.payout_destination === 'crypto_wallet' && (
          <>
            <div>
              <label className="block text-sm text-gray-300 mb-2">
                USDT Wallet Address
              </label>
              <input
                type="text"
                value={payoutConfig.crypto_wallet}
                onChange={(e) => setPayoutConfig({ ...payoutConfig, crypto_wallet: e.target.value })}
                placeholder="0x... (ERC20) or SOLANA address"
                className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
              />
              <p className="text-xs text-gray-500 mt-1">
                Supports ERC20 (0x...), SOLANA, or BSC USDT addresses
              </p>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">
                Blockchain Network
              </label>
              <select
                value={payoutConfig.crypto_chain}
                onChange={(e) => setPayoutConfig({ ...payoutConfig, crypto_chain: e.target.value as any })}
                className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
              >
                <option value="ethereum">Ethereum (ERC20)</option>
                <option value="solana">Solana (SPL)</option>
                <option value="bsc">BNB Smart Chain (BEP20)</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Select the blockchain network for USDT transfers
              </p>
            </div>
          </>
        )}

        {/* Split Ratio (conditional) */}
        {payoutConfig.payout_destination === 'split' && (
          <div>
            <label className="block text-sm text-gray-300 mb-2">
              Split Ratio: Crypto (%)
            </label>
            <input
              type="number"
              min="0"
              max="100"
              value={payoutConfig.split_ratio}
              onChange={(e) => setPayoutConfig({ ...payoutConfig, split_ratio: parseFloat(e.target.value) || 50 })}
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
            />
            <p className="text-xs text-gray-500 mt-1">
              {payoutConfig.split_ratio}% to crypto wallet, {100 - payoutConfig.split_ratio}% to forex reinvestment
            </p>
            <div className="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden">
              <div 
                className="h-full bg-green-500 transition-all"
                style={{ width: `${payoutConfig.split_ratio}%` }}
              />
            </div>
          </div>
        )}

        {/* Minimum Threshold */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Minimum Payout Threshold ($)
          </label>
          <input
            type="number"
            min="0"
            value={payoutConfig.min_payout_threshold}
            onChange={(e) => setPayoutConfig({ ...payoutConfig, min_payout_threshold: parseFloat(e.target.value) || 0 })}
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
          />
          <p className="text-xs text-gray-500 mt-1">
            Only payout if daily profit exceeds this amount (prevents micro-transactions)
          </p>
        </div>
      </div>

      {/* Status Box */}
      {payoutConfig.configured && payoutConfig.payout_enabled && (
        <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
          <div className="flex items-start gap-2">
            <Check className="w-4 h-4 text-green-500 mt-0.5" />
            <div className="text-sm text-green-400">
              <p className="font-medium">Auto-Payout Active</p>
              <p className="text-green-500/80 mt-1">
                {getPayoutDestinationLabel()} at {formatHour(payoutConfig.payout_schedule_hour)} daily
              </p>
              <p className="text-green-500/80">
                Threshold: ${payoutConfig.min_payout_threshold.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Warning for no wallet */}
      {payoutConfig.payout_enabled && payoutConfig.payout_destination === 'crypto_wallet' && !payoutConfig.crypto_wallet && (
        <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5" />
            <div className="text-sm text-yellow-400">
              <p className="font-medium">Wallet Address Required</p>
              <p className="text-yellow-500/80 mt-1">
                Please enter your USDT wallet address to receive payouts
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 mt-4">
        <button
          onClick={savePayoutConfig}
          disabled={saving}
          className="flex-1 py-2 bg-[#10B981] hover:bg-[#059669] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              {payoutConfig.configured ? 'Update Settings' : 'Save Configuration'}
            </>
          )}
        </button>
        
        <button
          onClick={testPayout}
          disabled={!payoutConfig.configured || testing}
          className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium flex items-center justify-center gap-2"
        >
          {testing ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Testing...
            </>
          ) : (
            <>
              <DollarSign className="w-4 h-4" />
              Test Payout
            </>
          )}
        </button>
      </div>

      {/* Info Box */}
      <div className="mt-4 p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg">
        <p className="text-xs text-[#10B981]">
          💡 <strong>How it works:</strong> Daily profits are calculated from filled trades at {formatHour(payoutConfig.payout_schedule_hour)}. 
          If profit exceeds ${payoutConfig.min_payout_threshold.toFixed(2)}, auto-payout distributes {payoutConfig.payout_percentage}% 
          to your configured {getPayoutDestinationLabel().toLowerCase()}.
        </p>
      </div>
    </section>
  );
}