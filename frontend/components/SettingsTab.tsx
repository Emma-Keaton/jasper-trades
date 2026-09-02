'use client';

import { useState, useEffect } from 'react';
import { Save, Key, Shield, Check, DollarSign, TrendingUp, Plane, Cpu, Briefcase, Lock, Brain } from 'lucide-react';
import { Toast } from '@/app/types';
import { SkeletonCard } from './Skeleton';
import { API_URL } from '@/lib/constants';
import TradingCapsSection from './TradingCapsSection';
import MarketDataSection from './settings/MarketDataSection';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { apiFetch } from '@/lib/api-client';
import { useOnboarding } from '@/components/onboarding/OnboardingProvider';
import { CollapsibleSection } from '@/components/ui/CollapsibleSection';
import { SystemStatusPanel } from '@/components/panels/SystemStatusPanel';

interface ApiSettings {
  nvidia_api_key: string;
  binance_api_key: string;
  binance_api_secret: string;
  trove_api_key?: string;
  akshare_token?: string;
}

interface TelegramSettings {
  chat_id: string;
  enabled: boolean;
  bot_token: string;
  configured: boolean;
  chat_enabled?: boolean;
  // New fields for verification and preferences
  is_verified?: boolean;
  trade_notifications_enabled?: boolean;
  daily_summary_enabled?: boolean;
  summary_time_wat?: string;  // Format: "20:00"
  ai_explanations_enabled?: boolean;
}

interface SettingsTabProps {
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  initialTab?: string;
}

// Helper functions to compute completion status
const getApiConfiguredCount = (formData: ApiSettings) => {
  let count = 0;
  if (formData.nvidia_api_key) count++;
  if (formData.binance_api_key && formData.binance_api_secret) count++;
  return count;
};

export default function SettingsTab({ triggerToast }: SettingsTabProps) { 
  const { resetTours } = useOnboarding();
  const [formData, setFormData] = useState<ApiSettings>({
    nvidia_api_key: '',
    binance_api_key: '',
    binance_api_secret: '',
    trove_api_key: '',
    akshare_token: '',
  });

  const [, setTelegram] = useState<TelegramSettings>({
    bot_token: '',
    chat_id: '',
    enabled: true,
    configured: false,
    chat_enabled: true,
    is_verified: false,
    trade_notifications_enabled: true,
    daily_summary_enabled: true,
    summary_time_wat: '20:00',
    ai_explanations_enabled: true,
  });

  const [payoutSettings, setPayoutSettings] = useState({
    crypto_wallet: '',
    crypto_chain: 'ethereum' as 'ethereum' | 'solana' | 'bsc',
    payout_enabled: false,
    payout_percentage: 50,
    payout_schedule_hour: 20,
    payout_schedule_minute: 0,
    payout_frequency: 'custom_time' as 'custom_time' | 'end_of_trade',
    min_payout_threshold: 10,
    configured: false,
  });

  const [paymentGateways, setPaymentGateways] = useState({
    paystack_api_key: '',
    flutterwave_api_key: '',
    paystack_enabled: false,
    flutterwave_enabled: false,
  });

  const [marketData, setMarketData] = useState({
    alphavantage_key: '',
    finnhub_key: '',
    twelvedata_key: '',
    polygon_key: '',
    fred_key: '',
    coingecko_enabled: true,
  });

  const [deviceInfo, setDeviceInfo] = useState('');
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { valid: boolean; message: string }>>({});
  const [portfolioId, setPortfolioId] = useState<number | null>(null);

  // Polymarket state
  const [polymarket, setPolymarket] = useState({
    connected: false,
    api_key: '',
    api_secret: '',
    wallet_address: '',
    balance: 0,
    equity: 0,
    ai_trading_enabled: false,
    copytrading_enabled: false,
    loading: false,
    message: '',
    success: false,
    leaders: [] as any[],
  });
  const [showLeaders, setShowLeaders] = useState(false);

  // Environment variable status from backend
  const [envStatus, setEnvStatus] = useState<{
    environment_variables: Record<string, {
      configured: boolean;
      env_var: string;
      description: string;
      required_for: string;
    }>;
    summary: {
      total: number;
      configured: number;
      missing: number;
    };
  } | null>(null);

  const fetchEnvStatus = async () => {
    try {
      const envRes = await apiFetch(`${API_URL}/api/v1/settings/env-status`);
      const envData = await envRes.json();
      setEnvStatus(envData);
    } catch (error) {
      console.error('Failed to load env status:', error);
    }
  };

  const fetchSettings = async () => {
    setLoading(true);
    try {
      // Generate or get device ID
      let deviceId = getOrCreateDeviceId();
      console.log('Using persistent device ID:', deviceId);

      const res = await apiFetch(`${API_URL}/api/v1/settings`, {
        headers: {
          'X-Device-ID': deviceId,
        },
      });

      if (!res.ok) throw new Error(`Failed to load settings`);

      const data = await res.json();
      const s = data.settings || data;
      
      // Always load form data (even if not configured)
      setFormData({
        nvidia_api_key: s.nvidia_api_key || '',
        binance_api_key: s.binance_api_key || '',
        binance_api_secret: s.binance_api_secret || '',
        trove_api_key: s.trove_api_key || '',
        akshare_token: s.akshare_token || '',
      });
      
      setDeviceInfo(`Device ID: ${deviceId}`);

      // Get portfolio ID for trading caps
      const portfolioRes = await apiFetch(`${API_URL}/api/v1/portfolio`, {
        headers: { 'X-Device-ID': deviceId },
      });
      const portfolioData = await portfolioRes.json();
      if (portfolioData && portfolioData.id) {
        setPortfolioId(portfolioData.id);
      }

      // Load notification settings from unified settings endpoint
      if (s.telegram_config) {
        setTelegram({ 
          chat_id: s.telegram_config.chat_id || '',
          bot_token: s.telegram_config.bot_token || '',
          enabled: s.telegram_config.enabled || false,
          chat_enabled: s.telegram_config.chat_enabled || true,
          configured: !!s.telegram_config.chat_id 
        });
      }

      // Load broker connection status for completion counting
      // Load environment variable status
      await fetchEnvStatus();

      // Load auto-payout settings
      const payoutRes = await apiFetch(`${API_URL}/api/v1/withdrawal/payout/settings`, {
        headers: { 'X-Device-ID': deviceId },
      });
      if (payoutRes.ok) {
        const pd = await payoutRes.json();
        if (pd.crypto_wallet || pd.payout_enabled !== undefined) {
          setPayoutSettings(prev => ({
            ...prev,
            crypto_wallet: pd.crypto_wallet || '',
            payout_enabled: pd.payout_enabled || false,
            payout_percentage: pd.payout_percentage ?? 50,
            payout_schedule_hour: pd.payout_schedule_hour ?? 20,
            payout_schedule_minute: pd.payout_schedule_minute ?? 0,
            payout_frequency: pd.payout_frequency || 'custom_time',
            min_payout_threshold: pd.min_payout_threshold ?? 10,
            configured: !!pd.configured,
          }));
        }
      }

    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async (service: string) => {
    setTesting(service);
    try {
      const res = await apiFetch(`${API_URL}/api/v1/settings/validate-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service,
          key: service === 'nvidia' ? formData.nvidia_api_key : formData.binance_api_key
        }),
      });
      const result = await res.json();
      setTestResults(prev => ({
        ...prev,
        [service]: { valid: result.valid, message: result.message }
      }));
    } catch {
      setTestResults(prev => ({
        ...prev,
        [service]: { valid: false, message: 'Connection failed' }
      }));
    } finally {
      setTesting(null);
    }
  };

  const handleSave = async () => {
    try {
      // Save all form data
      const payload = {
        nvidia_api_key: formData.nvidia_api_key,
        binance_api_key: formData.binance_api_key,
        binance_api_secret: formData.binance_api_secret,
        trove_api_key: formData.trove_api_key,
        akshare_token: formData.akshare_token,
      };

      const response = await apiFetch(`${API_URL}/api/v1/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': getOrCreateDeviceId(),
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        triggerToast('success', 'Settings Saved', 'All settings and broker modes have been updated.');
        // Also refresh env status
        await fetchEnvStatus();
      } else {
        throw new Error('Failed to save');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      triggerToast('error', 'Save Failed', 'Could not save settings.');
    }
  };

  const savePaymentGateways = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      await apiFetch(`${API_URL}/api/v1/settings/payment-gateways`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(paymentGateways),
      });
      triggerToast('success', 'Payment Gateways Saved', 'Nigerian bank payout configuration saved.');
    } catch {
      triggerToast('error', 'Failed', 'Could not save payment gateway settings.');
    }
  };

  // ============ Polymarket Functions ============

  const checkPolymarketConnection = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/polymarket/connection/status`, {
        headers: { 'X-Device-ID': deviceId! },
      });
      const data = await res.json();

      if (data.connected) {
        setPolymarket(prev => ({
          ...prev,
          connected: true,
          wallet_address: data.wallet_address || '',
          balance: data.account_balance || 0,
          equity: data.account_equity || 0,
          ai_trading_enabled: data.ai_trading_enabled || false,
          copytrading_enabled: data.copytrading_enabled || false,
        }));
      } else {
        setPolymarket(prev => ({ ...prev, connected: false }));
      }
    } catch (error) {
      console.error('Failed to check Polymarket connection:', error);
    }
  };

  const connectPolymarket = async () => {
    if (!polymarket.api_key || !polymarket.api_secret) {
      setPolymarket(prev => ({ ...prev, message: 'Please enter both API key and secret', success: false }));
      return;
    }

    setPolymarket(prev => ({ ...prev, loading: true, message: '' }));

    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/polymarket/connection/configure`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId!,
        },
        body: JSON.stringify({
          api_key: polymarket.api_key,
          api_secret: polymarket.api_secret,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setPolymarket(prev => ({
          ...prev,
          connected: true,
          wallet_address: data.wallet_address || '',
          loading: false,
          message: 'Polymarket account connected successfully!',
          success: true,
        }));
        refreshBalance();
      } else {
        setPolymarket(prev => ({
          ...prev,
          loading: false,
          message: data.detail || 'Failed to connect',
          success: false,
        }));
      }
    } catch {
      setPolymarket(prev => ({
        ...prev,
        loading: false,
        message: 'Failed to connect Polymarket account',
        success: false,
      }));
    }
  };

  const disconnectPolymarket = async () => {
    if (!confirm('Are you sure you want to disconnect your Polymarket account?')) return;

    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/polymarket/connection`, {
        method: 'DELETE',
        headers: { 'X-Device-ID': deviceId! },
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setPolymarket(prev => ({
          ...prev,
          connected: false,
          api_key: '',
          api_secret: '',
          wallet_address: '',
          balance: 0,
          equity: 0,
          message: 'Account disconnected',
          success: true,
          leaders: [],
        }));
        setShowLeaders(false);
      } else {
        setPolymarket(prev => ({
          ...prev,
          message: data.detail || 'Failed to disconnect',
          success: false,
        }));
      }
    } catch {
      setPolymarket(prev => ({
        ...prev,
        message: 'Failed to disconnect',
        success: false,
      }));
    }
  };

  const refreshBalance = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/polymarket/account/balance`, {
        headers: { 'X-Device-ID': deviceId! },
      });

      if (res.ok) {
        const data = await res.json();
        setPolymarket(prev => ({
          ...prev,
          balance: data.balance || 0,
          equity: data.equity || 0,
        }));
      }
    } catch (error) {
      console.error('Failed to refresh balance:', error);
    }
  };

  const followLeader = async (leaderId: string, leaderName: string) => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/polymarket/leader/${leaderId}/follow`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId!,
        },
        body: JSON.stringify({
          leader_name: leaderName,
          allocation_weight: 0.5,
          min_confidence: 0.7,
          max_copy_amount: 50.0,
        }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setPolymarket(prev => ({
          ...prev,
          leaders: prev.leaders.map((l: any) =>
            l.leader_id === leaderId ? { ...l, is_following: true } : l
          ),
          message: `Now following ${leaderName}`,
          success: true,
        }));
      } else {
        setPolymarket(prev => ({
          ...prev,
          message: data.detail || 'Failed to follow leader',
          success: false,
        }));
      }
    } catch {
      setPolymarket(prev => ({
        ...prev,
        message: 'Failed to follow leader',
        success: false,
      }));
    }
  };

  const savePayoutSettings = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/withdrawal/payout/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify({
          crypto_wallet: payoutSettings.crypto_wallet,
          payout_enabled: payoutSettings.payout_enabled,
          payout_percentage: payoutSettings.payout_percentage,
          payout_schedule_hour: payoutSettings.payout_schedule_hour,
          payout_schedule_minute: payoutSettings.payout_schedule_minute,
          payout_frequency: payoutSettings.payout_frequency,
          min_payout_threshold: payoutSettings.min_payout_threshold,
        }),
      });
      if (res.ok) {
        const result = await res.json();
        if (result.success) {
          setPayoutSettings(prev => ({ ...prev, configured: true }));
          const modeLabel = payoutSettings.payout_frequency === 'end_of_trade' ? 'end-of-trade' : 'daily';
          triggerToast('success', 'Auto-Payout Saved', `Payouts will send ${payoutSettings.payout_percentage}% of profits via ${modeLabel}.`);
        }
      } else {
        triggerToast('error', 'Failed', 'Could not save payout settings.');
      }
    } catch {
      triggerToast('error', 'Failed', 'Could not save payout settings.');
    }
  };

  const validateWallet = async () => {
    if (!payoutSettings.crypto_wallet) {
      triggerToast('warning', 'Enter Wallet', 'Please enter a wallet address to validate');
      return;
    }
    try {
      const res = await apiFetch(`${API_URL}/api/v1/withdrawal/payout/validate-wallet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: payoutSettings.crypto_wallet, network: 'ethereum' }),
      });
      const data = await res.json();
      if (data.valid) {
        triggerToast('success', 'Valid Wallet', `Address: ${data.address}`);
      } else {
        triggerToast('error', 'Invalid Wallet', data.message);
      }
    } catch {
      triggerToast('error', 'Validation Failed', 'Could not validate wallet address');
    }
  };

  useEffect(() => {
    fetchSettings();
    checkPolymarketConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col gap-6 w-full">
        <div>
          <div className="h-8 w-48 bg-gray-700 rounded animate-pulse mb-2" />
          <div className="h-4 w-80 bg-gray-700 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (<SkeletonCard key={i} />))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto p-2 sm:p-3 md:p-4 overflow-x-hidden">
      <div className="mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2">Settings & Configuration</h1>
        <p className="text-slate-500 dark:text-slate-400 text-xs sm:text-sm">{deviceInfo} • All keys encrypted before storage</p>
      </div>

      {saved && (
        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/50 rounded-lg flex items-center gap-2">
          <Check className="w-5 h-5 text-green-500" />
          <span className="text-green-500 text-sm font-medium">Settings saved!</span>
        </div>
      )}

      <div className="space-y-4">
        {/* Group 1: AI & External Services */}
        <CollapsibleSection
          title="AI & External Services"
          subtitle="Gemini (primary), NVIDIA NIM (deprecated), Binance, and market data providers"
          icon={Key}
          defaultOpen={true}
          storageKey="settings-ai-services-open"
          completionStatus={
            envStatus?.environment_variables?.gemini_api_key?.configured
              ? 'Gemini ready'
              : `${getApiConfiguredCount(formData)} of 2 configured`
          }
        >
          <div className="space-y-4">
            {/* Gemini (primary LLM) */}
            <div data-tour="ai-keys-section" className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-[#8B5CF6]" />
                  <h3 className="text-md font-semibold text-slate-900 dark:text-slate-100">Gemini (Primary AI)</h3>
                </div>
                <div className="flex items-center gap-2">
                  {envStatus?.environment_variables?.gemini_api_key?.configured ? (
                    <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1">
                      <Lock className="w-3 h-3" /> ENV
                    </span>
                  ) : (
                    <span className="text-xs px-2 py-1 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                      Not configured
                    </span>
                  )}
                </div>
              </div>
              {envStatus?.environment_variables?.gemini_api_key?.configured ? (
                <div className="p-2 bg-green-500/10 border border-green-500/30 rounded">
                  <p className="text-xs text-green-400 flex items-center gap-1 font-medium">
                    <Lock className="w-3 h-3" />
                    <span>Managed via Render: GEMINI_API_KEY detected</span>
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Gemini 2.5 Flash is the primary engine for AI chat, trade analysis, and trade reasoning.
                  </p>
                </div>
              ) : (
                <div className="p-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded">
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Gemini is the primary AI model. Set <code className="text-[#8B5CF6]">GEMINI_API_KEY</code> (~3 keys, comma-separated) in the Render dashboard to enable AI chat, analysis, and trade reasoning.
                  </p>
                </div>
              )}
            </div>

            {/* NVIDIA NIM API (deprecated fallback) */}
            <div data-tour="api-keys-section" className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-[#3B82F6]" />
                  <h3 className="text-md font-semibold text-slate-900 dark:text-slate-100">NVIDIA NIM API</h3>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-600/40 text-slate-300 uppercase">Deprecated fallback</span>
                </div>
                <div className="flex items-center gap-2">
                  {envStatus?.environment_variables?.nvidia_api_key?.configured && (
                    <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1">
                      <Lock className="w-3 h-3" /> ENV
                    </span>
                  )}
                  {!envStatus?.environment_variables?.nvidia_api_key?.configured && (
                    <button
                      onClick={() => testConnection('nvidia')}
                      disabled={!formData.nvidia_api_key}
                      className="text-xs px-3 py-1.5 rounded-md bg-[#3B82F6]/20 text-[#3B82F6] disabled:opacity-50"
                    >
                      Test
                    </button>
                  )}
                </div>
              </div>
              <input
                type="password"
                value={formData.nvidia_api_key}
                onChange={(e) => envStatus?.environment_variables?.nvidia_api_key?.configured
                  ? undefined
                  : setFormData({...formData, nvidia_api_key: e.target.value})
                }
                disabled={envStatus?.environment_variables?.nvidia_api_key?.configured}
                placeholder="nvapi-..."
                className={`w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm ${
                  envStatus?.environment_variables?.nvidia_api_key?.configured
                    ? 'opacity-60 cursor-not-allowed'
                    : ''
                }`}
              />
              {envStatus?.environment_variables?.nvidia_api_key?.configured ? (
                <div className="mt-2 p-2 bg-green-500/10 border border-green-500/30 rounded">
                  <p className="text-xs text-green-400 flex items-center gap-1 font-medium">
                    <Lock className="w-3 h-3" />
                    <span>Managed via Render:</span>
                    <span className="ml-1 text-slate-600 dark:text-slate-300">NVIDIA_API_KEY environment variable detected</span>
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    This field is locked. Update Render Dashboard variables to edit this value.
                  </p>
                </div>
              ) : (
                testResults.nvidia && (
                  <p className={`text-xs mt-2 ${testResults.nvidia.valid ? 'text-green-500' : 'text-red-500'}`}>
                    {testResults.nvidia.message}
                  </p>
                )
              )}
            </div>

            {/* Binance API */}
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-[#F7931A]" />
                  <h3 className="text-md font-semibold text-slate-900 dark:text-slate-100">Binance</h3>
                </div>
                <div className="flex items-center gap-2">
                  {(envStatus?.environment_variables?.binance_api_key?.configured &&
                      envStatus?.environment_variables?.binance_api_secret?.configured) && (
                    <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1">
                      <Lock className="w-3 h-3" /> ENV
                    </span>
                  )}
                  {!envStatus?.environment_variables?.binance_api_key?.configured && (
                    <button
                      onClick={() => testConnection('binance')}
                      disabled={!formData.binance_api_key}
                      className="text-xs px-3 py-1.5 rounded-md bg-[#F7931A]/20 text-[#F7931A] disabled:opacity-50"
                    >
                      Test
                    </button>
                  )}
                </div>
              </div>
              <div className="space-y-3">
                <div>
                  <label htmlFor="binance-api-key" className="block text-xs text-slate-500 dark:text-slate-400 mb-1">API Key</label>
                  <input
                    id="binance-api-key"
                    type="password"
                    value={formData.binance_api_key}
                    onChange={(e) => envStatus?.environment_variables?.binance_api_key?.configured
                      ? undefined
                      : setFormData({...formData, binance_api_key: e.target.value})
                    }
                    disabled={envStatus?.environment_variables?.binance_api_key?.configured}
                    placeholder="Binance API Key"
                    className={`w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm ${
                      envStatus?.environment_variables?.binance_api_key?.configured
                        ? 'opacity-60 cursor-not-allowed'
                        : ''
                    }`}
                  />
                  {envStatus?.environment_variables?.binance_api_key?.configured && (
                    <p className="text-xs text-green-400 mt-1 flex items-center gap-1">
                      <Lock className="w-3 h-3" />
                      Managed via Render: BINANCE_API_KEY
                    </p>
                  )}
                </div>
                <div>
                  <label htmlFor="binance-api-secret" className="block text-xs text-slate-500 dark:text-slate-400 mb-1">API Secret</label>
                  <input
                    id="binance-api-secret"
                    type="password"
                    value={formData.binance_api_secret}
                    onChange={(e) => envStatus?.environment_variables?.binance_api_secret?.configured
                      ? undefined
                      : setFormData({...formData, binance_api_secret: e.target.value})
                    }
                    disabled={envStatus?.environment_variables?.binance_api_secret?.configured}
                    placeholder="Binance API Secret"
                    className={`w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm ${
                      envStatus?.environment_variables?.binance_api_secret?.configured
                        ? 'opacity-60 cursor-not-allowed'
                        : ''
                    }`}
                  />
                  {envStatus?.environment_variables?.binance_api_secret?.configured && (
                    <p className="text-xs text-green-400 mt-1 flex items-center gap-1">
                      <Lock className="w-3 h-3" />
                      Managed via Render: BINANCE_API_SECRET
                    </p>
                  )}
                </div>
              </div>
              {(envStatus?.environment_variables?.binance_api_key?.configured &&
                  envStatus?.environment_variables?.binance_api_secret?.configured) ? (
                <div className="mt-2 p-2 bg-green-500/10 border border-green-500/30 rounded">
                  <p className="text-xs text-green-400 flex items-center gap-1 font-medium">
                    <Lock className="w-3 h-3" />
                    <span>Credentials Locked:</span>
                    <span className="ml-1 text-slate-600 dark:text-slate-300">Set via system environment variables</span>
                  </p>
                </div>
              ) : (
                testResults.binance && (
                  <p className={`text-xs mt-2 ${testResults.binance.valid ? 'text-green-500' : 'text-red-500'}`}>
                    {testResults.binance.message}
                  </p>
                )
              )}
            </div>

            {/* Market Data Section */}
            <div data-tour="market-data-section">
              <MarketDataSection marketData={marketData} setMarketData={setMarketData} triggerToast={triggerToast} />
            </div>
          </div>
        </CollapsibleSection>

        {/* Group 2: Prediction Markets */}
        <CollapsibleSection
          title="Prediction Markets"
          subtitle="Polymarket account for AI-powered trading and copytrading"
          icon={Briefcase}
          storageKey="settings-polymarket-open"
          completionStatus={polymarket.connected ? '✓ Connected' : 'Not connected'}
        >
          <div className="space-y-4">
            {/* Polymarket (Prediction Markets) */}
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-5 h-5 text-purple-400" />
                <h3 className="text-md font-semibold text-slate-900 dark:text-slate-100">Polymarket (Prediction Markets)</h3>
              </div>

              {!polymarket.connected ? (
                <>
                  <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">
                    Connect your Polymarket account for AI-powered prediction market trading and copytrading.
                  </p>
                  
                  <div className="space-y-3 mb-3">
                    <div>
                      <label htmlFor="polymarket-api-key" className="text-xs text-slate-500 dark:text-slate-400 block mb-1">API Key</label>
                      <input
                        id="polymarket-api-key"
                        type="password"
                        value={polymarket.api_key}
                        onChange={(e) => setPolymarket({...polymarket, api_key: e.target.value})}
                        placeholder="Enter your Polymarket API key"
                        className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm"
                      />
                    </div>
                    
                    <div>
                      <label htmlFor="polymarket-api-secret" className="text-xs text-slate-500 dark:text-slate-400 block mb-1">API Secret</label>
                      <input
                        id="polymarket-api-secret"
                        type="password"
                        value={polymarket.api_secret}
                        onChange={(e) => setPolymarket({...polymarket, api_secret: e.target.value})}
                        placeholder="Enter your API secret"
                        className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm"
                      />
                    </div>
                  </div>

                  <div className="mb-3 p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">ðŸ” Security Features:</p>
                    <ul className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
                      <li>• Credentials encrypted with AES-128 before storage</li>
                      <li>• Only you can access your API keys</li>
                      <li>• AI can trade automatically (when enabled)</li>
                      <li>• Copytrade top Polymarket leaders</li>
                    </ul>
                  </div>

                  <button
                    onClick={connectPolymarket}
                    disabled={polymarket.loading || !polymarket.api_key || !polymarket.api_secret}
                    className="w-full py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium"
                  >
                    {polymarket.loading ? 'Connecting...' : 'Connect Polymarket Account'}
                  </button>
                </>
              ) : (
                <>
                  <div className="mb-3 p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-green-400 flex items-center gap-2">
                        <Check className="w-4 h-4" />
                        Connected
                      </span>
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        Wallet: {polymarket.wallet_address?.slice(0, 6)}...{polymarket.wallet_address?.slice(-4)}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-slate-500 dark:text-slate-400">Balance:</span>
                        <p className="text-slate-900 dark:text-slate-100 font-medium">${polymarket.balance?.toLocaleString() || '0.00'}</p>
                      </div>
                      <div>
                        <span className="text-slate-500 dark:text-slate-400">Equity:</span>
                        <p className="text-slate-900 dark:text-slate-100 font-medium">${polymarket.equity?.toLocaleString() || '0.00'}</p>
                      </div>
                    </div>

                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => setShowLeaders(!showLeaders)}
                        className="flex-1 py-1.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-900 dark:text-slate-100 rounded-md text-xs"
                      >
                        {showLeaders ? 'Hide Leaders' : 'Browse Leaders'} ({polymarket.leaders?.length || 0})
                      </button>
                      <button
                        onClick={refreshBalance}
                        className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-900 dark:text-slate-100 rounded-md text-xs"
                      >
                        Refresh
                      </button>
                    </div>
                  </div>

                  {/* Copytrading Leaders Section */}
                  {showLeaders && polymarket.leaders && polymarket.leaders.length > 0 && (
                    <div className="mb-3">
                      <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-2">Top Polymarket Leaders</h3>
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {polymarket.leaders.map((leader: any) => (
                          <div key={leader.leader_id} className="p-2 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-sm text-slate-900 dark:text-slate-100">{leader.leader_name}</p>
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  Win Rate: {(leader.win_rate * 100).toFixed(1)}% | PnL: ${leader.total_pnl.toLocaleString()}
                                </p>
                              </div>
                              <button
                                onClick={() => followLeader(leader.leader_id, leader.leader_name)}
                                disabled={leader.is_following}
                                className={`px-3 py-1 text-xs rounded-md ${
                                  leader.is_following
                                    ? 'bg-green-600/20 text-green-400 cursor-default'
                                    : 'bg-purple-600 hover:bg-purple-700 text-white'
                                }`}
                              >
                                {leader.is_following ? '✓ Following' : 'Follow'}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI Trading Settings */}
                  <div className="mb-3 space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={polymarket.ai_trading_enabled}
                        onChange={(e) => setPolymarket({...polymarket, ai_trading_enabled: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-slate-600 dark:text-slate-300">ðŸ¤– Enable AI trading</span>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={polymarket.copytrading_enabled}
                        onChange={(e) => setPolymarket({...polymarket, copytrading_enabled: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-slate-600 dark:text-slate-300">ðŸ“Š Enable copytrading leaders</span>
                    </label>
                  </div>

                  <button
                    onClick={disconnectPolymarket}
                    className="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm"
                  >
                    Disconnect Account
                  </button>
                </>
              )}

              {polymarket.message && (
                <p className={`text-xs mt-2 ${polymarket.success ? 'text-green-400' : 'text-red-400'}`}>
                  {polymarket.message}
                </p>
              )}
            </div>
          </div>
        </CollapsibleSection>

        {/* Group 4: Portfolio & Payouts */}
        <CollapsibleSection
          title="Portfolio & Payouts"
          subtitle="Auto-payout and Nigerian bank payment gateways"
          icon={DollarSign}
          storageKey="settings-payouts-open"
        >
          <div className="space-y-4">
            {/* Auto-Payout Settings */}
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center gap-2 mb-3">
                <DollarSign className="w-5 h-5 text-[#10B981]" />
                <h3 className="text-md font-semibold text-slate-900 dark:text-slate-100">Auto-Payout</h3>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                Payouts are sent to your configured USDT wallet.
              </p>

              {/* Enable toggle */}
              <div className="mb-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={payoutSettings.payout_enabled}
                    onChange={(e) => setPayoutSettings({...payoutSettings, payout_enabled: e.target.checked})}
                    className="w-4 h-4 accent-[#10B981]"
                  />
                  <span className="text-sm text-slate-700 dark:text-slate-200">Enable auto-payout</span>
                </label>
              </div>

              {/* Frequency toggle */}
              <div className="mb-4">
                <span className="block text-sm text-slate-600 dark:text-slate-300 mb-2">When to pay out</span>
                <div className="flex gap-2">
                  {(['custom_time', 'end_of_trade'] as const).map(freq => (
                    <button
                      key={freq}
                      onClick={() => setPayoutSettings(p => ({ ...p, payout_frequency: freq }))}
                      className={`flex-1 py-2 text-sm rounded-md border transition ${
                        payoutSettings.payout_frequency === freq
                          ? 'bg-[#10B981]/10 border-[#10B981] text-[#10B981] font-semibold'
                          : 'border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300'
                      }`}
                    >
                      {freq === 'custom_time' ? 'Custom daily time' : 'End of each trade'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom time picker */}
              {payoutSettings.payout_frequency === 'custom_time' && (
                <div className="mb-4 grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor="payout-hour" className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Hour (WAT)</label>
                    <select
                      id="payout-hour"
                      value={payoutSettings.payout_schedule_hour}
                      onChange={(e) => setPayoutSettings(p => ({ ...p, payout_schedule_hour: parseInt(e.target.value) }))}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-2 py-1.5 text-sm text-slate-900 dark:text-slate-100"
                    >
                      {Array.from({ length: 24 }, (_, i) => (
                        <option key={i} value={i}>{String(i).padStart(2, '0')}h</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="payout-minute" className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Minute (WAT)</label>
                    <select
                      id="payout-minute"
                      value={payoutSettings.payout_schedule_minute}
                      onChange={(e) => setPayoutSettings(p => ({ ...p, payout_schedule_minute: parseInt(e.target.value) }))}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-2 py-1.5 text-sm text-slate-900 dark:text-slate-100"
                    >
                      {[0, 15, 30, 45].map(m => (
                        <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* Percentage */}
              <div className="mb-4">
                <label htmlFor="payout-percentage" className="block text-sm text-slate-600 dark:text-slate-300 mb-2">Payout % of profits</label>
                <input
                  id="payout-percentage"
                  type="range"
                  min="1"
                  max="100"
                  value={payoutSettings.payout_percentage}
                  onChange={(e) => setPayoutSettings(p => ({ ...p, payout_percentage: parseInt(e.target.value) }))}
                  className="w-full accent-[#10B981]"
                />
                <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400 mt-1">
                  <span>1%</span>
                  <span className="text-[#10B981] font-semibold">{payoutSettings.payout_percentage}%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* Min threshold */}
              <div className="mb-4">
                <label htmlFor="payout-threshold" className="block text-sm text-slate-600 dark:text-slate-300 mb-2">Min profit before payout ($)</label>
                <input
                  id="payout-threshold"
                  type="number"
                  min="0"
                  step="1"
                  value={payoutSettings.min_payout_threshold}
                  onChange={(e) => setPayoutSettings(p => ({ ...p, min_payout_threshold: parseFloat(e.target.value) || 0 }))}
                  className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm"
                />
              </div>

              {/* Crypto wallet */}
              <div className="mb-4">
                <label htmlFor="crypto-wallet" className="block text-sm text-slate-600 dark:text-slate-300 mb-2">USDT Wallet Address</label>
                <div className="flex gap-2">
                  <input
                    id="crypto-wallet"
                    type="text"
                    value={payoutSettings.crypto_wallet}
                    onChange={(e) => setPayoutSettings(p => ({ ...p, crypto_wallet: e.target.value }))}
                    placeholder="0x... (ERC20) or Solana address"
                    className="flex-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 font-mono text-sm"
                  />
                  <button
                    onClick={validateWallet}
                    className="px-3 py-2 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-900 dark:text-slate-100 text-sm rounded-md"
                  >
                    Validate
                  </button>
                </div>
                <p className="text-xs text-amber-500 mt-1.5 flex items-center gap-1">
                  ⚠️ <strong>USDT only</strong> — profits are sent as USDT to this wallet.
                </p>
              </div>

              {/* Save */}
              <button
                onClick={savePayoutSettings}
                className="w-full py-2.5 bg-[#10B981] hover:bg-[#059669] text-white font-medium rounded-lg transition-colors"
              >
                Save Auto-Payout Settings
              </button>
            </div>
            {/* Payment Gateways - Nigerian Banks */}
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700" data-tour="payment-gateways">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-5 h-5 text-[#10B981]" />
                  <h3 className="text-md font-semibold text-slate-900 dark:text-slate-100">Payment Gateways (Nigerian Banks)</h3>
                </div>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                Configure Paystack or Flutterwave to enable dynamic Nigerian bank list fetching and 
                CBN-mandated account validation for Naira payouts.
              </p>

              {/* Paystack */}
              <div className="mb-4 p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={paymentGateways.paystack_enabled}
                      onChange={(e) => setPaymentGateways({...paymentGateways, paystack_enabled: e.target.checked})}
                      className="w-4 h-4 rounded border-gray-600 text-[#10B981] focus:ring-[#10B981]"
                    />
                    <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Paystack</span>
                  </label>
                  <a
                    href="https://dashboard.paystack.com/settings/api"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-[#10B981] hover:underline"
                  >
                    Get API Key →
                  </a>
                </div>
                <input
                  type="password"
                  value={paymentGateways.paystack_api_key}
                  onChange={(e) => setPaymentGateways({...paymentGateways, paystack_api_key: e.target.value})}
                  placeholder="sk_live_xxx or sk_test_xxx"
                  className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm focus:outline-none focus:border-[#10B981]"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Secret key for account validation and bank list fetching
                </p>
              </div>

              {/* Flutterwave */}
              <div className="p-3 bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={paymentGateways.flutterwave_enabled}
                      onChange={(e) => setPaymentGateways({...paymentGateways, flutterwave_enabled: e.target.checked})}
                      className="w-4 h-4 rounded border-gray-600 text-[#F59E0B] focus:ring-[#F59E0B]"
                    />
                    <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Flutterwave</span>
                  </label>
                  <a
                    href="https://dashboard.flutterwave.com/settings/api"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-[#F59E0B] hover:underline"
                  >
                    Get API Key →
                  </a>
                </div>
                <input
                  type="password"
                  value={paymentGateways.flutterwave_api_key}
                  onChange={(e) => setPaymentGateways({...paymentGateways, flutterwave_api_key: e.target.value})}
                  placeholder="FLWSECK_xxx"
                  className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md px-3 py-2 text-slate-900 dark:text-slate-100 text-sm focus:outline-none focus:border-[#F59E0B]"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Secret key for account validation and bank list fetching
                </p>
              </div>

              <div className="mt-4 p-3 bg-[#3B82F6]/10 border border-[#3B82F6]/30 rounded-md">
                <p className="text-xs text-[#3B82F6]">
                  <strong>ðŸ’¡ Why configure this?</strong> Nigerian regulations (CBN NIP) require account validation 
                  before transfers. Your users will see verified account holder names before payouts, preventing fraud.
                </p>
              </div>
            </div>
          </div>
        </CollapsibleSection>

        {/* Group 6: Risk Controls */}
        <CollapsibleSection
          title="Risk Controls"
          subtitle="Trading caps and position limits"
          icon={Shield}
          storageKey="settings-risk-open"
        >
          <div data-tour="trading-caps-section">
            <TradingCapsSection portfolioId={portfolioId} triggerToast={triggerToast} />
          </div>
        </CollapsibleSection>

        {/* Group 7: System Status */}
        <CollapsibleSection
          title="System Status"
          subtitle="Real-time monitoring of backend services"
          icon={Shield}
          storageKey="settings-system-open"
          defaultOpen={false}
        >
          <SystemStatusPanel />
        </CollapsibleSection>

        {/* Global Save and Onboarding controllers */}
        <div
          data-onboarding="save-reset"
          className="flex items-center justify-between gap-3 pt-6 border-t border-slate-200 dark:border-slate-700"
        >
          <button
            onClick={() => { resetTours(); triggerToast('success', 'Tours Reset', 'Onboarding tours will show again on next page navigation'); }}
            className="px-4 py-2 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-900 dark:text-slate-100 rounded-md text-sm flex items-center gap-2"
          >
            <Plane className="w-4 h-4" /> Reset Onboarding Tours
          </button>
          <button
            onClick={async () => {
              await handleSave();
              if (paymentGateways.paystack_api_key || paymentGateways.flutterwave_api_key) {
                await savePaymentGateways();
              }
            }}
            className="px-6 py-3 bg-[#3B82F6] hover:bg-[#2563EB] text-white font-semibold rounded-lg flex items-center justify-center gap-2"
          >
            <Save className="w-5 h-5" /> Save All Settings
          </button>
        </div>
      </div>
    </div>
  );
}
