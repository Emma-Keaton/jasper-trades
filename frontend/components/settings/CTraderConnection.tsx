'use client';

import { useState, useEffect } from 'react';
import { Shield, CheckCircle, AlertCircle, Loader2, ExternalLink, Trash2, RefreshCw, Zap, ToggleLeft, ToggleRight } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface CTraderAccount {
  id: number;
  broker_name: string;
  account_name: string;
  account_currency: string;
  account_balance: number;
  account_equity: number;
  is_active: boolean;
  is_connected: boolean;
  connection_status: string;
  token_status: string;
  created_at: string;
}

interface CTraderConnectionProps {
  onConnected?: (accountId: string) => void;
  paperTradingConfig?: { enabled: boolean; capital: number; currency: string };
  onUpdatePaperTrading?: (updates: Partial<{enabled: boolean; capital: number; currency: string}>) => void;
  onSave?: () => void;
}

export default function CTraderConnection({ onConnected, paperTradingConfig, onUpdatePaperTrading, onSave }: CTraderConnectionProps) {
  const [connecting, setConnecting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [accounts, setAccounts] = useState<CTraderAccount[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatingMode, setUpdatingMode] = useState(false);
  const [isLiveMode, setIsLiveMode] = useState(false);

  const getDeviceId = () => {
    let deviceId = localStorage.getItem('device_id');
    if (!deviceId) {
      deviceId = 'dev_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('device_id', deviceId);
    }
    return deviceId;
  };

  useEffect(() => {
    loadEnvironmentMode();
    fetchAccounts();
  }, []);

  const loadEnvironmentMode = () => {
    const stored = localStorage.getItem('environment_mode');
    if (stored) {
      setIsLiveMode(stored === 'live');
    }
  };

  const fetchAccounts = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/ctrader/accounts`);
      if (res.ok) {
        const data = await res.json();
        setAccounts(data.accounts || []);
      }
    } catch (err) {
      console.error('Failed to fetch accounts:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const mode = isLiveMode ? 'live' : 'sandbox';
      const res = await fetch(`${API_URL}/api/v1/ctrader/connect?mode=${mode}`);
      const data = await res.json();
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        setError(data.detail || 'Failed to get authorization URL');
      }
    } catch (err) {
      setError('Connection failed. Please try again.');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async (accountId: number) => {
    if (!confirm('Are you sure you want to disconnect this account? Auto-trading will stop.')) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/ctrader/disconnect/${accountId}`, { method: 'POST' });
      if (res.ok) {
        setAccounts(prev => prev.filter(acc => acc.id !== accountId));
        triggerToast('success', 'Account Disconnected', 'Auto-trading stopped for this account');
      }
    } catch (err) {
      setError('Failed to disconnect account');
    }
  };

  const toggleAccountActive = async (account: CTraderAccount) => {
    try {
      setAccounts(prev => prev.map(acc =>
        acc.id === account.id ? { ...acc, is_active: !acc.is_active } : acc
      ));
      triggerToast('success', account.is_active ? 'Auto-Trading Disabled' : 'Auto-Trading Enabled',
        `${account.account_name} ${account.is_active ? 'stopped' : 'started'}`);
    } catch (err) {
      setError('Failed to update account');
    }
  };

  const toggleEnvironmentMode = async () => {
    const newMode = isLiveMode ? 'sandbox' : 'live';
    if (!confirm(`Switch to ${newMode.toUpperCase()} mode?\n\nThis will affect all cTrader connections. ${newMode === 'live' ? 'Real money trades will be executed!' : ''}`)) return;

    setUpdatingMode(true);
    try {
      const deviceId = getDeviceId();
      const res = await fetch(`${API_URL}/api/v1/settings/environment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ environment_mode: newMode }),
      });
      if (res.ok) {
        setIsLiveMode(newMode === 'live');
        localStorage.setItem('environment_mode', newMode);
        triggerToast('success', 'Mode Switched', `Now in ${newMode.toUpperCase()} mode`);
      } else {
        const errorData = await res.json();
        setError(errorData.detail || 'Failed to update environment mode');
      }
    } catch (err) {
      setError('Failed to update environment mode');
    } finally {
      setUpdatingMode(false);
    }
  };

  const triggerToast = (type: string, title: string, message: string) => {
    console.log(`[${type}] ${title}: ${message}`);
  };

  const getStatusColor = (status: string) => {
    if (status.includes('Active')) return 'text-[#10B981]';
    if (status.includes('Expired')) return 'text-[#EF4444]';
    if (status.includes('Not Connected')) return 'text-[#EF4444]';
    return 'text-[#F59E0B]';
  };

  return (
    <div className="bg-[#1E293B] border border-[#475569] p-6 rounded-xl">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            cTrader Auto-Trading
            <span className={`text-xs px-2 py-0.5 rounded-full font-mono flex items-center gap-1 ${
              isLiveMode ? 'bg-[#EF4444]/20 text-[#EF4444] animate-pulse' : 'bg-[#10B981]/20 text-[#10B981]'
            }`}>
              {isLiveMode ? (
                <><span className="w-2 h-2 bg-[#EF4444] rounded-full animate-pulse"></span>LIVE MODE</>
              ) : (
                <><span className="w-2 h-2 bg-[#10B981] rounded-full"></span>SANDBOX</>
              )}
            </span>
          </h3>
          <p className="text-sm text-[#94A3B8] mt-1">
            {isLiveMode ? '⚠️ LIVE TRADING - Real money trades will be executed' : '🧪 Sandbox Mode - Demo trades only'}
          </p>
        </div>
        <Shield className="w-8 h-8 text-[#3B82F6]" />
      </div>

      <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isLiveMode ? 'bg-[#EF4444]/10' : 'bg-[#10B981]/10'}`}>
              {isLiveMode ? <Zap className="w-5 h-5 text-[#EF4444]" /> : <CheckCircle className="w-5 h-5 text-[#10B981]" />}
            </div>
            <div>
              <div className="text-white font-bold text-sm">{isLiveMode ? 'Live Trading Mode' : 'Sandbox Mode'}</div>
              <div className="text-xs text-[#94A3B8]">
                {isLiveMode ? 'Executing real trades with real money' : 'Testing with demo account - no real money'}
              </div>
            </div>
          </div>
          <button onClick={toggleEnvironmentMode} disabled={updatingMode}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold transition-colors ${
              isLiveMode ? 'bg-[#10B981] hover:bg-[#059669] text-white' : 'bg-[#EF4444] hover:bg-[#DC2626] text-white'
            } disabled:opacity-50`}>
            {updatingMode ? <><Loader2 className="w-4 h-4 animate-spin" />Switching...</> : (
              isLiveMode ? <><>Switch to Sandbox</><ToggleLeft className="w-5 h-5" /></> : <><>Switch to Live</><ToggleRight className="w-5 h-5" /></>
            )}
          </button>
        </div>
      </div>

      <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-3 mb-4">
        <div className="flex items-start gap-2">
          <CheckCircle className="w-4 h-4 text-[#10B981] mt-0.5" />
          <div className="text-xs text-[#94A3B8]">
            <p className="font-bold text-[#F8FAFC] mb-1">OAuth 2.0 Security</p>
            <ul className="space-y-1">
              <li>• OAuth 2.0 - login on cTrader's secure site</li>
              <li>• Zero password storage - tokens encrypted with Fernet (AES-128)</li>
              <li>• Auto token refresh every 30 days</li>
              <li>• Revoke access anytime from broker dashboard</li>
            </ul>
          </div>
        </div>
      </div>

      {!loading && accounts.length > 0 && (
        <div className="space-y-3 mb-4">
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#F59E0B]" />
            Connected Accounts ({accounts.length}) - {isLiveMode ? 'LIVE' : 'SANDBOX'}
          </h4>
          {accounts.map((account) => (
            <div key={account.id} className="bg-[#0F172A] border border-[#475569] rounded-lg p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-xs">
                      {account.broker_name.substring(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-white font-bold">{account.account_name}</div>
                      <div className="text-xs text-[#94A3B8]">{account.broker_name} • {account.account_currency}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                    <div><span className="text-[#64748B]">Balance:</span><span className="text-white font-mono ml-2">{account.account_currency} {account.account_balance?.toFixed(2)}</span></div>
                    <div><span className="text-[#64748B]">Equity:</span><span className="text-white font-mono ml-2">{account.account_currency} {account.account_equity?.toFixed(2)}</span></div>
                    <div><span className="text-[#64748B]">Status:</span><span className={`font-mono ml-2 ${getStatusColor(account.token_status)}`}>{account.token_status}</span></div>
                    <div><span className="text-[#64748B]">Auto-Trading:</span><span className={`font-mono ml-2 ${account.is_active ? 'text-[#10B981]' : 'text-[#94A3B8]'}`}>{account.is_active ? 'ON' : 'OFF'}</span></div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => toggleAccountActive(account)}
                      className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                        account.is_active ? 'bg-[#F59E0B]/10 text-[#F59E0B] hover:bg-[#F59E0B]/20' : 'bg-[#10B981]/10 text-[#10B981] hover:bg-[#10B981]/20'
                      }`}>
                      {account.is_active ? <><RefreshCw className="w-3 h-3 inline mr-1" /> Pause</> : <><Zap className="w-3 h-3 inline mr-1" /> Enable</>}
                    </button>
                    <button onClick={() => handleDisconnect(account.id)} className="px-3 py-1.5 rounded text-xs font-medium bg-[#EF4444]/10 text-[#EF4444] hover:bg-[#EF4444]/20 transition-colors">
                      <Trash2 className="w-3 h-3 inline mr-1" /> Disconnect
                    </button>
                  </div>
                </div>
                <div className="ml-4">{account.is_connected ? <CheckCircle className="w-6 h-6 text-[#10B981]" /> : <AlertCircle className="w-6 h-6 text-[#EF4444]" />}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-8 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading accounts...
        </div>
      )}

      {error && (
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg p-3 mb-4 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-[#EF4444]" /><span className="text-sm text-[#EF4444]">{error}</span>
        </div>
      )}

      {!loading || accounts.length === 0 ? (
        <button onClick={handleConnect} disabled={connecting}
          className={`w-full font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2 ${
            isLiveMode ? 'bg-[#EF4444] hover:bg-[#DC2626] text-white' : 'bg-[#10B981] hover:bg-[#059669] text-white'
          } disabled:opacity-50`}>
          {connecting ? <><Loader2 className="w-5 h-5 animate-spin" />Connecting...</> : (
            <>{isLiveMode ? '⚠️ Connect LIVE Account' : 'Connect Sandbox Account'}<ExternalLink className="w-4 h-4" /></>
          )}
        </button>
      ) : (
        <button onClick={handleConnect}
          className={`w-full font-bold py-3 px-4 rounded-lg transition flex items-center justify-center gap-2 ${
            isLiveMode ? 'bg-[#EF4444] hover:bg-[#DC2626] text-white' : 'bg-[#3B82F6] hover:bg-[#2563EB] text-white'
          }`}>
          Connect Another Account <ExternalLink className="w-4 h-4" />
        </button>
      )}

      <div className="mt-4 pt-4 border-t border-[#475569]">
        <p className="text-xs text-[#64748B] text-center">Supports: FxPro, IronFX, and all cTrader-enabled brokers</p>
      </div>
    </div>
  );
}