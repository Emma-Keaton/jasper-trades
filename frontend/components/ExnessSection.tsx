'use client';

import { useState } from 'react';
import { Shield, Check, X, RefreshCw, Eye, EyeOff } from 'lucide-react';
import { Toast } from '@/app/page';

export interface ExnessSettings {
  login_id: string;
  server: string;
  password: string;
  investor_password: string;
  enabled: boolean;
  configured: boolean;
  is_connected?: boolean;
  balance?: number;
  last_sync_at?: string;
}

interface ExnessSectionProps {
  exness: ExnessSettings;
  setExness: (settings: ExnessSettings) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Common Exness MT5 servers
const EXNESS_SERVERS = [
  'Exness-MT5-Real6',
  'Exness-MT5-Real7',
  'Exness-MT5-Real8',
  'Exness-MT5-Real9',
  'Exness-MT5-Real10',
  'Exness-MT5-Trial10',
  'Exness-MT5-Trial11',
  'Exness-MT5-Demo01',
  'Exness-MT5-Demo02',
];

export default function ExnessSection({ exness, setExness, triggerToast }: ExnessSectionProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [showInvestorPassword, setShowInvestorPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const saveExnessAccount = async () => {
    if (!exness.login_id || !exness.server || !exness.password) {
      triggerToast('error', 'Missing Information', 'Please fill in all required fields');
      return;
    }

    // Validate login ID is numeric
    if (!/^\d+$/.test(exness.login_id)) {
      triggerToast('error', 'Invalid Login ID', 'MT5 Login ID should be numeric (e.g., 87291043)');
      return;
    }

    setSaving(true);
    try {
      const deviceId = localStorage.getItem('device_id') || 'unknown';
      
      // Get portfolio ID first
      const portfolioRes = await fetch(`${API_URL}/api/v1/portfolio`);
      const portfolios = await portfolioRes.json();
      
      if (!portfolios.data || portfolios.data.length === 0) {
        triggerToast('error', 'No Portfolio', 'Please create a portfolio first');
        setSaving(false);
        return;
      }

      const portfolioId = portfolios.data[0].id;

      const res = await fetch(`${API_URL}/api/v1/exness/account/link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify({
          portfolio_id: portfolioId,
          login_id: exness.login_id,
          server: exness.server,
          password: exness.password,
          investor_password: exness.investor_password || undefined,
          broker_name: 'Exness',
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setExness({ ...exness, configured: true, enabled: true });
        triggerToast('success', 'Exness Account Linked', `Account ${exness.login_id} connected to ${exness.server}`);
        
        // Sync account data
        await syncExnessAccount(portfolioId);
      } else {
        triggerToast('error', 'Link Failed', data.detail || 'Could not link Exness account');
      }
    } catch (error) {
      triggerToast('error', 'Link Failed', 'Could not link Exness account');
    } finally {
      setSaving(false);
    }
  };

  const syncExnessAccount = async (portfolioId?: number) => {
    if (!portfolioId) {
      // Get portfolio ID
      const portfolioRes = await fetch(`${API_URL}/api/v1/portfolio`);
      const portfolios = await portfolioRes.json();
      if (!portfolios.data || portfolios.data.length === 0) return;
      portfolioId = portfolios.data[0].id;
    }

    setSyncing(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/exness/account/sync?portfolio_id=${portfolioId}`, {
        method: 'POST',
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setExness({
          ...exness,
          is_connected: data.is_connected,
          balance: data.balance,
          last_sync_at: new Date().toISOString(),
        });
        
        const statusText = data.is_connected ? 'Connected' : 'Disconnected';
        triggerToast(
          data.is_connected ? 'success' : 'warning',
          'Account Synced',
          `Balance: $${data.balance?.toLocaleString() || '0.00'} (${statusText})`
        );
      } else {
        triggerToast('error', 'Sync Failed', data.detail || 'Could not sync account');
      }
    } catch (error) {
      triggerToast('error', 'Sync Failed', 'Could not sync Exness account');
    } finally {
      setSyncing(false);
    }
  };

  const testConnection = async () => {
    const deviceId = localStorage.getItem('device_id');
    
    try {
      const portfolioRes = await fetch(`${API_URL}/api/v1/portfolio`);
      const portfolios = await portfolioRes.json();
      if (!portfolios.data || portfolios.data.length === 0) return;
      
      const portfolioId = portfolios.data[0].id;
      await syncExnessAccount(portfolioId);
    } catch (error) {
      triggerToast('error', 'Test Failed', 'Could not test connection');
    }
  };

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Exness/MT5 Account</h2>
        </div>
        {exness.configured && (
          <span className={`text-xs px-2 py-1 rounded ${exness.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
            {exness.enabled ? 'Enabled' : 'Disabled'}
          </span>
        )}
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Link your Exness MetaTrader 5 account for live trading. Credentials are encrypted before storage.
        Supports both local (Windows + MT5) and cloud hosting (REST API).
      </p>

      {exness.configured && exness.is_connected && (
        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-green-500" />
              <span className="text-sm text-green-400 font-medium">Connected</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-gray-400">Balance:</span>
              <span className="text-white font-mono">${exness.balance?.toLocaleString() || '0.00'}</span>
            </div>
          </div>
          {exness.last_sync_at && (
            <p className="text-xs text-gray-500 mt-2">
              Last synced: {new Date(exness.last_sync_at).toLocaleString()}
            </p>
          )}
        </div>
      )}

      <div className="space-y-3">
        {/* MT5 Login ID */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">MT5 Login ID</label>
          <input
            type="text"
            value={exness.login_id}
            onChange={(e) => setExness({ ...exness, login_id: e.target.value })}
            placeholder="e.g., 87291043"
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
          />
          <p className="text-xs text-gray-500 mt-1">
            Your Exness MT5 account number (numeric only)
          </p>
        </div>

        {/* Server Selection */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">Exness Server</label>
          <select
            value={exness.server}
            onChange={(e) => setExness({ ...exness, server: e.target.value })}
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
            disabled={exness.configured}
          >
            <option value="">Select server...</option>
            {EXNESS_SERVERS.map((server) => (
              <option key={server} value={server}>
                {server}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Found in your Exness email or MT4/MT5 terminal
          </p>
        </div>

        {/* Trading Password */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">Trading Password</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={exness.password}
              onChange={(e) => setExness({ ...exness, password: e.target.value })}
              placeholder="Your MT5 trading password"
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981] pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Investor Password (Optional) */}
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Investor Password <span className="text-gray-500">(Optional)</span>
          </label>
          <div className="relative">
            <input
              type={showInvestorPassword ? 'text' : 'password'}
              value={exness.investor_password}
              onChange={(e) => setExness({ ...exness, investor_password: e.target.value })}
              placeholder="Read-only access password"
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981] pr-10"
            />
            <button
              type="button"
              onClick={() => setShowInvestorPassword(!showInvestorPassword)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
            >
              {showInvestorPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Optional read-only password for monitoring without trading
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-3">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={exness.enabled}
            onChange={(e) => setExness({ ...exness, enabled: e.target.checked })}
            className="w-4 h-4"
            disabled={!exness.configured}
          />
          <span className="text-sm text-gray-300">Enable Exness trading</span>
        </label>
      </div>

      <div className="flex gap-2 mt-4">
        <button
          onClick={saveExnessAccount}
          disabled={saving}
          className="flex-1 py-2 bg-[#10B981] hover:bg-[#059669] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Linking...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              {exness.configured ? 'Update Account' : 'Link Account'}
            </>
          )}
        </button>
        <button
          onClick={testConnection}
          disabled={!exness.configured || syncing}
          className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium flex items-center justify-center gap-2"
        >
          {syncing ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Syncing...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              Sync
            </>
          )}
        </button>
      </div>

      <div className="mt-4 p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg">
        <p className="text-xs text-[#10B981]">
          💡 <strong>Local vs Cloud:</strong> On Windows with MT5 installed, trades execute via MT5 terminal.
          On cloud hosting (Linux), trades use Exness REST API (requires additional API credentials).
        </p>
      </div>
    </section>
  );
}