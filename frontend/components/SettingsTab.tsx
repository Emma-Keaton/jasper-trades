'use client';

import { useState, useEffect } from 'react';
import { Save, Key, Shield, Server, Check, X, RefreshCw, MessageCircle, DollarSign, TrendingUp, Plane, Bell, Send } from 'lucide-react';
import { Toast } from '@/app/page';
import { SkeletonCard, SkeletonText } from './Skeleton';
import TradingCapsSection from './TradingCapsSection';
import PayoutSection from './PayoutSection';
import MarketDataSection from './settings/MarketDataSection';
import CTraderConnection from './settings/CTraderConnection';
import TroveSettings from './settings/TroveSettings';
import AKShareSettings from './settings/AKShareSettings';
import CurrencyToggle from './settings/CurrencyToggle';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { useOnboarding } from '@/components/onboarding/OnboardingProvider';
import { CollapsibleSection } from '@/components/ui/CollapsibleSection';
import { SystemStatusPanel } from '@/components/panels/SystemStatusPanel';

interface ApiSettings {
  nvidia_api_key: string;
  binance_api_key: string;
  binance_api_secret: string;
  colab_kronos_url: string;
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
  onNavigate?: (tab: string) => void;
}

export default function SettingsTab({ triggerToast, initialTab = 'api', onNavigate }: SettingsTabProps) { 
  const { resetTours } = useOnboarding();
  const [formData, setFormData] = useState<ApiSettings>({
    nvidia_api_key: '',
    binance_api_key: '',
    binance_api_secret: '',
    colab_kronos_url: '',
  });

  const [telegram, setTelegram] = useState<TelegramSettings>({
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
    payout_destination: 'crypto_wallet' as 'crypto_wallet' | 'naira_bank' | 'forex_account' | 'split',
    split_ratio: 50,
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
  const [activeSection, setActiveSection] = useState<string>(initialTab);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { valid: boolean; message: string }>>({});
  const [telegramTestStatus, setTelegramTestStatus] = useState<{testing: boolean; success?: boolean; message?: string}>({ testing: false });
  const [telegramRequestStatus, setTelegramRequestStatus] = useState<{
    requesting: boolean;
    verifying: boolean;
    codeSent: boolean;
    success?: boolean;
    message?: string;
  }>({ requesting: false, verifying: false, codeSent: false });
  const [verificationCode, setVerificationCode] = useState('');
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

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const fetchSettings = async () => {
    setLoading(true);
    try {
      // Generate or get device ID
      let deviceId = getOrCreateDeviceId();
      console.log('Using persistent device ID:', deviceId);

      const res = await fetch(`${API_URL}/api/v1/settings`, {
        headers: {
          'X-Device-ID': deviceId,
        },
      });

      if (!res.ok) throw new Error(`Failed to load settings`);

      const data = await res.json();
      
      // Always load form data (even if not configured)
      setFormData({
        nvidia_api_key: data.nvidia_api_key || '',
        binance_api_key: data.binance_api_key || '',
        binance_api_secret: data.binance_api_secret || '',
        colab_kronos_url: data.colab_kronos_url || '',
      });
      
      setDeviceInfo(`Device ID: ${deviceId}`);

      // Get portfolio ID for trading caps
      const portfolioRes = await fetch(`${API_URL}/api/v1/portfolio`);
      const portfolios = await portfolioRes.json();
      if (portfolios.data && portfolios.data.length > 0) {
        setPortfolioId(portfolios.data[0].id);
      }

      // Load notification settings from unified settings endpoint
      if (data.telegram_config) {
        setTelegram({ 
          chat_id: data.telegram_config.chat_id || '',
          bot_token: data.telegram_config.bot_token || '',
          enabled: data.telegram_config.enabled || false,
          chat_enabled: data.telegram_config.chat_enabled || true,
          configured: !!data.telegram_config.chat_id 
        });
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
      const res = await fetch(`${API_URL}/api/v1/settings/validate-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service,
          key: service === 'nvidia' ? formData.nvidia_api_key :
               
               formData.binance_api_key
        }),
      });
      const result = await res.json();
      setTestResults(prev => ({
        ...prev,
        [service]: { valid: result.valid, message: result.message }
      }));
    } catch (error) {
      setTestResults(prev => ({
        [service]: { valid: false, message: 'Connection failed' }
      }));
    } finally {
      setTesting(null);
    }
  };

  const saveApiSettings = async () => {
    try {
      const deviceId = localStorage.getItem('device_id') || 'unknown';
      const res = await fetch(`${API_URL}/api/v1/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        triggerToast('success', 'Settings Saved', 'Your API configuration has been saved.');
      }
    } catch (error) {
      triggerToast('error', 'Save Failed', 'Could not save settings.');
    }
  };

  const savePaymentGateways = async () => {
    try {
      const deviceId = localStorage.getItem('device_id') || 'unknown';
      await fetch(`${API_URL}/api/v1/settings/payment-gateways`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(paymentGateways),
      });
      triggerToast('success', 'Payment Gateways Saved', 'Nigerian bank payout configuration saved.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not save payment gateway settings.');
    }
  };

  const saveTelegram = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/settings/telegram/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify({
          chat_id: telegram.chat_id,
          bot_token: telegram.bot_token,
          enabled: telegram.enabled,
          chat_enabled: telegram.chat_enabled,
        }),
      });
      setTelegram({ ...telegram, configured: true });
      triggerToast('success', 'Telegram Configured', 'Telegram notifications enabled.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not configure Telegram.');
    }
  };

  const testTelegram = async () => {
    setTelegramTestStatus({ testing: true });
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/test`, {
        method: 'POST',
        headers: { 'X-Device-ID': localStorage.getItem('device_id')! },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTelegramTestStatus({ testing: false, success: true, message: 'Test message sent! Check your Telegram.' });
        setTimeout(() => setTelegramTestStatus({ testing: false }), 3000);
      } else {
        setTelegramTestStatus({ testing: false, success: false, message: data.detail || 'Failed to send test' });
      }
    } catch (error) {
      setTelegramTestStatus({ testing: false, success: false, message: 'Connection failed' });
    }
  };

  const requestVerification = async () => {
    if (!telegram.chat_id) {
      setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: false, success: false, message: 'Please enter your chat ID' });
      return;
    }

    setTelegramRequestStatus({ requesting: true, verifying: false, codeSent: false });
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/verify/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': localStorage.getItem('device_id')! },
        body: JSON.stringify({ chat_id: telegram.chat_id }),
      });
      const data = await res.json();
      
      if (res.ok && data.success) {
        setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: true, success: true, message: `Verification code sent to ${telegram.chat_id.slice(0, 5)}***` });
      } else {
        setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: false, success: false, message: data.detail || 'Failed to send code' });
      }
    } catch (error) {
      setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: false, success: false, message: 'Failed to send verification code' });
    }
  };

  const confirmVerification = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      setTelegramRequestStatus(prev => ({ ...prev, verifying: false, success: false, message: 'Please enter a 6-digit code' }));
      return;
    }

    setTelegramRequestStatus(prev => ({ ...prev, verifying: true }));
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/verify/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': localStorage.getItem('device_id')! },
        body: JSON.stringify({ chat_id: telegram.chat_id, verification_code: verificationCode }),
      });
      const data = await res.json();
      
      if (res.ok && data.success) {
        setTelegram({ ...telegram, is_verified: true });
        setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: false, success: true, message: 'Telegram verified successfully!' });
        setVerificationCode('');
        loadTelegramPreferences();
        triggerToast('success', 'Verified', 'Telegram number verified successfully');
      } else {
        setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: true, success: false, message: data.detail || 'Invalid or expired code' });
      }
    } catch (error) {
      setTelegramRequestStatus({ requesting: false, verifying: false, codeSent: true, success: false, message: 'Verification failed' });
    }
  };

  const saveTelegramPreferences = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': localStorage.getItem('device_id')! },
        body: JSON.stringify({
          trade_notifications_enabled: telegram.trade_notifications_enabled,
          daily_summary_enabled: telegram.daily_summary_enabled,
          summary_time_wat: telegram.summary_time_wat || '20:00',
          chat_enabled: telegram.chat_enabled,
          ai_explanations_enabled: telegram.ai_explanations_enabled,
        }),
      });
      const data = await res.json();
      
      if (res.ok && data.success) {
        triggerToast('success', 'Preferences Saved', 'Telegram notification preferences updated');
        await saveTelegramLegacy();
      } else {
        triggerToast('error', 'Failed', data.detail || 'Could not save preferences');
      }
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not save Telegram preferences');
    }
  };

  const saveTelegramLegacy = async () => {
    try {
      await fetch(`${API_URL}/api/v1/settings/telegram/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': localStorage.getItem('device_id')! },
        body: JSON.stringify({
          chat_id: telegram.chat_id,
          bot_token: telegram.bot_token,
          enabled: telegram.trade_notifications_enabled,
          chat_enabled: telegram.chat_enabled,
        }),
      });
    } catch (error) {
      // Ignore legacy errors
    }
  };

  const loadTelegramPreferences = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/status`, {
        headers: { 'X-Device-ID': localStorage.getItem('device_id')! },
      });
      const data = await res.json();
      
      if (data.is_configured && data.is_verified) {
        setTelegram(prev => ({
          ...prev,
          is_verified: true,
          trade_notifications_enabled: data.preferences?.trade_notifications_enabled ?? true,
          daily_summary_enabled: data.preferences?.daily_summary_enabled ?? true,
          summary_time_wat: data.preferences?.summary_time_wat ?? '20:00',
          chat_enabled: data.preferences?.chat_enabled ?? true,
          ai_explanations_enabled: data.preferences?.ai_explanations_enabled ?? true,
        }));
      }
    } catch (error) {
      // Ignore errors
    }
  };

  // ============ Polymarket Functions ============

  const checkPolymarketConnection = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/connection/status`, {
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
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/connection/configure`, {
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
    } catch (error) {
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
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/connection`, {
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
    } catch (error) {
      setPolymarket(prev => ({
        ...prev,
        message: 'Failed to disconnect',
        success: false,
      }));
    }
  };

  const refreshBalance = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/account/balance`, {
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

  const loadLeaders = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/leaders?limit=10`, {
        headers: { 'X-Device-ID': deviceId! },
      });

      if (res.ok) {
        const data = await res.json();
        setPolymarket(prev => ({ ...prev, leaders: data.leaders || [] }));
        setShowLeaders(true);
      }
    } catch (error) {
      console.error('Failed to load leaders:', error);
    }
  };

  const followLeader = async (leaderId: string, leaderName: string) => {
    try {
      const deviceId = localStorage.getItem('device_id');
      const res = await fetch(`${API_URL}/api/v1/polymarket/leader/${leaderId}/follow`, {
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
    } catch (error) {
      setPolymarket(prev => ({
        ...prev,
        message: 'Failed to follow leader',
        success: false,
      }));
    }
  };

  const savePayoutSettings = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/withdrawal/payout/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify({
          crypto_wallet: payoutSettings.crypto_wallet,
          payout_enabled: payoutSettings.payout_enabled,
          payout_percentage: payoutSettings.payout_percentage,
          payout_schedule_hour: payoutSettings.payout_schedule_hour,
        }),
      });
      setPayoutSettings({ ...payoutSettings, configured: true });
      triggerToast('success', 'Auto-Payout Configured', 'Daily profit auto-payout settings saved.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not save payout settings.');
    }
  };

  const validateWallet = async () => {
    if (!payoutSettings.crypto_wallet) {
      triggerToast('warning', 'Enter Wallet', 'Please enter a wallet address to validate');
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/v1/withdrawal/payout/validate-wallet`, {
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
    } catch (error) {
      triggerToast('error', 'Validation Failed', 'Could not validate wallet address');
    }
  };

  const testNotification = async (channel: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/notify/test`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        triggerToast('success', 'Test Sent', `Test notification sent to ${channel}`);
      }
    } catch (error) {
      triggerToast('error', 'Test Failed', `Could not send test to ${channel}`);
    }
  };

  useEffect(() => {
    fetchSettings();
    checkPolymarketConnection();
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
    <div className="max-w-4xl mx-auto p-6 sm:p-8 md:p-10 lg:p-12">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">Settings & Configuration</h1>
        <p className="text-gray-400 text-sm">{deviceInfo} • All keys encrypted before storage</p>
      </div>

      {saved && (
        <div className="mb-6 p-3 bg-green-500/10 border border-green-500/50 rounded-lg flex items-center gap-2">
          <Check className="w-5 h-5 text-green-500" />
          <span className="text-green-500 text-sm font-medium">Settings saved!</span>
        </div>
      )}

      <div className="space-y-6">
        {/* Notification Channels - Telegram */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="w-5 h-5 text-[#F59E0B]" />
            <h2 className="text-lg font-semibold text-white">Telegram Notifications</h2>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            Receive trade alerts, daily summaries, and 2-way chat via Telegram.
            Verify your chat ID and configure your notification preferences below.
          </p>

          {/* Telegram */}
          <div className="border-t border-[#475569] pt-4 mt-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-[#25D366]" />
                <h3 className="text-md font-semibold text-white">Telegram Notifications</h3>
              </div>
              {telegram.is_verified && (
                <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Verified
                </span>
              )}
            </div>

            {/* Setup Instructions */}
            <div className="mb-4 p-3 bg-[#0F172A] rounded-lg border border-[#25D366]/30">
              <h4 className="text-sm font-semibold text-white mb-2">📱 Setup in 3 Steps:</h4>
              <ol className="text-xs text-gray-400 space-y-2">
                <li className="flex items-start gap-2">
                  <span className="text-[#25D366] font-bold">1.</span>
                  <span>Click "Open on Telegram" below to start @jasper_trades_bot</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#25D366] font-bold">2.</span>
                  <span>The bot will send you a Chat ID - copy it and paste in the field above, then click "Send Code"</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#25D366] font-bold">3.</span>
                  <span>The bot will send a 6-digit verification code - enter it below to complete setup</span>
                </li>
              </ol>
              <p className="text-xs text-gray-500 mt-3 italic">
                💡 Your Chat ID links your Telegram account to this device's trading portfolio. You'll only receive notifications for YOUR trades.
              </p>
            </div>

            {/* Open on Telegram Button */}
            <div className="mb-4 p-3 bg-gradient-to-r from-[#25D366]/10 to-[#25D366]/5 rounded-lg border border-[#25D366]/30">
              <div className="flex items-start gap-3">
                <div className="flex-1">
                  <h4 className="text-sm font-semibold text-white mb-1">🤖 Start Jasper Trades Bot</h4>
                  <p className="text-xs text-gray-400 mb-2">
                    Click below to open Telegram and start the bot. You'll receive a verification code there.
                  </p>
                  <a
                    href="https://t.me/jasper_trades_bot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-[#25D366] hover:bg-[#20BD5A] text-white rounded-md text-sm transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Open on Telegram
                  </a>
                </div>
              </div>
            </div>

            {/* Chat ID Verification */}
            <div className="mb-4 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
              <label className="text-xs text-gray-400 mb-2 block">Step 1: Enter Your Telegram Chat ID</label>
              <div className="mb-2 p-2 bg-[#1E293B] rounded border border-[#25D366]/30">
                <p className="text-xs text-gray-300">
                  <strong>What is a Chat ID?</strong> Your unique Telegram identifier (starts with <code className="bg-[#0F172A] px-1 py-0.5 rounded">@username</code> or <code className="bg-[#0F172A] px-1 py-0.5 rounded">123456789</code>).
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  <strong>How to find it:</strong> After clicking "Open on Telegram" below, the bot will tell you your Chat ID in the first message.
                </p>
              </div>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={telegram.chat_id}
                  onChange={(e) => setTelegram({...telegram, chat_id: e.target.value})}
                  placeholder="@username or 123456789"
                  className="flex-1 bg-[#1E293B] border border-[#475569] rounded-md px-3 py-2 text-white text-sm font-mono"
                />
                <button
                  onClick={requestVerification}
                  disabled={telegramRequestStatus.requesting || telegram.is_verified}
                  className="px-4 py-2 bg-[#25D366] hover:bg-[#20BD5A] text-white rounded-md text-sm disabled:opacity-50 whitespace-nowrap"
                >
                  {telegramRequestStatus.requesting ? 'Sending...' : telegram.is_verified ? 'Verified ✓' : 'Send Code'}
                </button>
              </div>
              
              {/* Verification Code Input */}
              {!telegram.is_verified && telegramRequestStatus.codeSent && (
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="Enter 6-digit code"
                    maxLength={6}
                    className="flex-1 bg-[#1E293B] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
                  />
                  <button
                    onClick={confirmVerification}
                    disabled={telegramRequestStatus.verifying}
                    className="px-4 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm disabled:opacity-50"
                  >
                    {telegramRequestStatus.verifying ? 'Verifying...' : 'Verify'}
                  </button>
                </div>
              )}
              {telegramRequestStatus.message && (
                <p className={`text-xs mt-2 ${telegramRequestStatus.success ? 'text-green-400' : 'text-red-400'}`}>
                  {telegramRequestStatus.message}
                </p>
              )}
            </div>

            {/* Notification Preferences */}
            {telegram.is_verified && (
              <>
                <div className="mb-4 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
                  <label className="text-xs text-gray-400 mb-3 block">Step 2: Notification Preferences</label>
                  
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={telegram.trade_notifications_enabled}
                        onChange={(e) => setTelegram({...telegram, trade_notifications_enabled: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-gray-300">📈 Trade executions (real-time)</span>
                    </label>
                    
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={telegram.daily_summary_enabled}
                        onChange={(e) => setTelegram({...telegram, daily_summary_enabled: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-gray-300">📊 Daily summary at 8:00 PM WAT</span>
                    </label>
                    
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={telegram.chat_enabled}
                        onChange={(e) => setTelegram({...telegram, chat_enabled: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-gray-300">💬 2-way chat (ask about portfolio)</span>
                    </label>
                    
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={telegram.ai_explanations_enabled}
                        onChange={(e) => setTelegram({...telegram, ai_explanations_enabled: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-gray-300">🤖 AI trade explanations</span>
                    </label>
                  </div>
                </div>

                {/* Daily Summary Schedule */}
                <div className="mb-4 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
                  <label className="text-xs text-gray-400 mb-2 block">Daily Summary Schedule</label>
                  <div className="flex items-center gap-3">
                    <input
                      type="time"
                      value={telegram.summary_time_wat || '20:00'}
                      onChange={(e) => setTelegram({...telegram, summary_time_wat: e.target.value})}
                      className="bg-[#1E293B] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
                    />
                    <span className="text-xs text-gray-400">WAT (West Africa Time)</span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2">
                  <button onClick={saveTelegramPreferences} className="flex-1 py-2 bg-[#25D366] hover:bg-[#20BD5A] text-white rounded-md text-sm">
                    Save Preferences
                  </button>
                  <button onClick={testTelegram} className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm">
                    Test Connection
                  </button>
                </div>
                {telegramTestStatus.message && (
                  <p className={`text-xs mt-2 ${telegramTestStatus.success ? 'text-green-400' : 'text-red-400'}`}>
                    {telegramTestStatus.message}
                  </p>
                )}
              </>
            )}

            {!telegram.is_verified && (
              <div className="text-xs text-gray-400 mt-3">
                💡 <strong>How it works:</strong> Enter your chat ID, receive a verification code via Telegram, then configure your notification preferences. All messages are sent from "Jasper Trades".
              </div>
            )}
          </div>

          {/* Polymarket Account Connection */}
          <div className="mt-6 p-4 bg-[#1E293B] rounded-lg border border-[#475569]">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-semibold text-white">Polymarket (Prediction Markets)</h2>
            </div>

            {!polymarket.connected ? (
              <>
                <p className="text-sm text-gray-300 mb-3">
                  Connect your Polymarket account for AI-powered prediction market trading and copytrading.
                </p>
                
                <div className="space-y-3 mb-3">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">API Key</label>
                    <input
                      type="password"
                      value={polymarket.api_key}
                      onChange={(e) => setPolymarket({...polymarket, api_key: e.target.value})}
                      placeholder="Enter your Polymarket API key"
                      className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
                    />
                  </div>
                  
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">API Secret</label>
                    <input
                      type="password"
                      value={polymarket.api_secret}
                      onChange={(e) => setPolymarket({...polymarket, api_secret: e.target.value})}
                      placeholder="Enter your API secret"
                      className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
                    />
                  </div>
                </div>

                <div className="mb-3 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
                  <p className="text-xs text-gray-400 mb-2">🔐 Security Features:</p>
                  <ul className="text-xs text-gray-400 space-y-1">
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
                <div className="mb-3 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-green-400 flex items-center gap-2">
                      <Check className="w-4 h-4" />
                      Connected
                    </span>
                    <span className="text-xs text-gray-400">
                      Wallet: {polymarket.wallet_address?.slice(0, 6)}...{polymarket.wallet_address?.slice(-4)}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-400">Balance:</span>
                      <p className="text-white font-medium">${polymarket.balance?.toLocaleString() || '0.00'}</p>
                    </div>
                    <div>
                      <span className="text-gray-400">Equity:</span>
                      <p className="text-white font-medium">${polymarket.equity?.toLocaleString() || '0.00'}</p>
                    </div>
                  </div>

                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => setShowLeaders(!showLeaders)}
                      className="flex-1 py-1.5 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-xs"
                    >
                      {showLeaders ? 'Hide Leaders' : 'Browse Leaders'} ({polymarket.leaders?.length || 0})
                    </button>
                    <button
                      onClick={refreshBalance}
                      className="px-3 py-1.5 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-xs"
                    >
                      Refresh
                    </button>
                  </div>
                </div>

                {/* Copytrading Leaders Section */}
                {showLeaders && polymarket.leaders && polymarket.leaders.length > 0 && (
                  <div className="mb-3">
                    <h3 className="text-sm font-medium text-white mb-2">Top Polymarket Leaders</h3>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {polymarket.leaders.map((leader: any) => (
                        <div key={leader.leader_id} className="p-2 bg-[#0F172A] rounded border border-[#475569]">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm text-white">{leader.leader_name}</p>
                              <p className="text-xs text-gray-400">
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
                    <span className="text-sm text-gray-300">🤖 Enable AI trading</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={polymarket.copytrading_enabled}
                      onChange={(e) => setPolymarket({...polymarket, copytrading_enabled: e.target.checked})}
                      className="w-4 h-4"
                    />
                    <span className="text-sm text-gray-300">📊 Enable copytrading leaders</span>
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

        {/* API Keys Section */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]" data-tour="api-keys-section">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Key className="w-5 h-5 text-[#3B82F6]" />
              <h2 className="text-lg font-semibold text-white">NVIDIA NIM API</h2>
            </div>
            <button onClick={() => testConnection('nvidia')} disabled={!formData.nvidia_api_key} className="text-xs px-3 py-1.5 rounded-md bg-[#3B82F6]/20 text-[#3B82F6] disabled:opacity-50">Test</button>
          </div>
          <input type="password" value={formData.nvidia_api_key} onChange={(e) => setFormData({...formData, nvidia_api_key: e.target.value})} placeholder="nvapi-..." className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
          {testResults.nvidia && <p className={`text-xs mt-2 ${testResults.nvidia.valid ? 'text-green-500' : 'text-red-500'}`}>{testResults.nvidia.message}</p>}
        </section>

        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Key className="w-5 h-5 text-[#F7931A]" />
              <h2 className="text-lg font-semibold text-white">Binance</h2>
            </div>
            <button onClick={() => testConnection('binance')} disabled={!formData.binance_api_key} className="text-xs px-3 py-1.5 rounded-md bg-[#F7931A]/20 text-[#F7931A] disabled:opacity-50">Test</button>
          </div>
          <input type="password" value={formData.binance_api_key} onChange={(e) => setFormData({...formData, binance_api_key: e.target.value})} placeholder="API Key" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm mb-2" />
          <input type="password" value={formData.binance_api_secret} onChange={(e) => setFormData({...formData, binance_api_secret: e.target.value})} placeholder="API Secret" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
        </section>

        {/* cTrader OAuth Connection (Multi-Tenant Copy Trading) */}
        <div data-tour="ctrader-section">
          <CTraderConnection
            onConnected={(accountId) => {
              triggerToast('success', 'cTrader Connected', 'Your account is now connected for auto-trading!');
            }}
          />
        </div>

        {/* Trove API - US & Nigerian Stocks */}
        <div data-tour="trove-section">
          <TroveSettings triggerToast={triggerToast} />
        </div>

        {/* AKShare - Chinese Stocks */}
        <div data-tour="akshare-section">
          <AKShareSettings triggerToast={triggerToast} />
        </div>

        {/* Currency Toggle - USD/NGN */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[#10B981]" />
              <h2 className="text-lg font-semibold text-white">Currency Display</h2>
            </div>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            Toggle between US Dollar (USD) and Nigerian Naira (NGN) for all monetary values.
            Exchange rates update every 60 seconds.
          </p>
          <CurrencyToggle />
        </section>

        {/* Kronos Colab */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
          <div className="flex items-center gap-2 mb-3">
            <Server className="w-5 h-5 text-[#8B5CF6]" />
            <h2 className="text-lg font-semibold text-white">Kronos on Google Colab</h2>
          </div>
          <input
            type="url"
            value={formData.colab_kronos_url}
            onChange={(e) => setFormData({...formData, colab_kronos_url: e.target.value})}
            placeholder="https://<your-colab-url>/proxy/8080"
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-[#8B5CF6]"
          />
          <p className="text-xs text-gray-500 mt-2">
            Google Colab URL from kronos_colab.ipynb notebook for GPU-accelerated predictions
          </p>
          <div className="mt-3 p-3 bg-[#8B5CF6]/10 border border-[#8B5CF6]/30 rounded-md">
            <p className="text-xs text-[#8B5CF6]">
              📝 Run the kronos_colab.ipynb notebook, copy the public URL (with /proxy/8080), and paste it here.
            </p>
          </div>
        </section>

        {/* Trading Caps & Risk Limits */}
        <div data-tour="trading-caps-section">
          <TradingCapsSection portfolioId={portfolioId} triggerToast={triggerToast} />
        </div>

        {/* Market Data Providers */}
        <div data-tour="market-data-section">
          <MarketDataSection marketData={marketData} setMarketData={setMarketData} triggerToast={triggerToast} />
        </div>

        {/* Auto-Payout Settings */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className="w-5 h-5 text-[#10B981]" />
            <h2 className="text-lg font-semibold text-white">Auto-Payout (50% Daily Profit)</h2>
          </div>
          
          <p className="text-xs text-gray-400 mb-3">
            Automatically send 50% of your daily trading profits to your crypto wallet. 
            Executes at your scheduled time (ET) each day.
          </p>

          {/* Crypto Wallet */}
          <div className="mb-3">
            <label className="block text-sm text-gray-300 mb-2">Crypto Wallet Address (USDC/USDT)</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={payoutSettings.crypto_wallet}
                onChange={(e) => setPayoutSettings({...payoutSettings, crypto_wallet: e.target.value})}
                placeholder="0x... (Ethereum USDT/USDC) or Solana USDT/USDC"
                className="flex-1 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white font-mono text-sm"
              />
              <button
                onClick={validateWallet}
                className="px-3 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white text-sm rounded-md"
              >
                Validate
              </button>
            </div>
            <p className="text-xs text-amber-500 mt-1.5 flex items-center gap-1">
              ⚠️ <strong>USDT or USDC only</strong> - All profits (forex, stocks, crypto) are converted to USDT before payout
            </p>
          </div>

          {/* Enable Auto-Payout */}
          <div className="mb-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={payoutSettings.payout_enabled}
                onChange={(e) => setPayoutSettings({...payoutSettings, payout_enabled: e.target.checked})}
                className="w-4 h-4"
              />
              <span className="text-sm text-gray-300">Enable Auto-Payout</span>
            </label>
          </div>

          {/* Payout Percentage */}
          <div className="mb-3">
            <label className="block text-sm text-gray-300 mb-2">Payout Percentage</label>
            <input
              type="range"
              min="0"
              max="100"
              value={payoutSettings.payout_percentage}
              onChange={(e) => setPayoutSettings({...payoutSettings, payout_percentage: parseInt(e.target.value)})}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>0%</span>
              <span className="text-[#10B981] font-semibold">{payoutSettings.payout_percentage}%</span>
              <span>100%</span>
            </div>
            <p className="text-xs text-gray-500 mt-1.5">
             Percentage of daily profit to auto-withdraw
            </p>
          </div>

          {/* Payout Schedule Time */}
          <div className="mb-3">
            <label className="block text-sm text-gray-300 mb-2">Payout Time (ET)</label>
            <select
              value={payoutSettings.payout_schedule_hour}
              onChange={(e) => setPayoutSettings({...payoutSettings, payout_schedule_hour: parseInt(e.target.value)})}
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm"
            >
              {[...Array(24)].map((_, i) => {
                const hour = i % 12 || 12;
                const ampm = i < 12 ? 'AM' : 'PM';
                return (
                  <option key={i} value={i}>
                    {hour}:00 {ampm} ET
                  </option>
                );
              })}
            </select>
            <p className="text-xs text-amber-500 mt-1.5 flex items-center gap-1">
              ⏰ Time is in <strong>Eastern Time (ET)</strong> - US Eastern timezone
            </p>
          </div>

          {/* Info Box */}
          <div className="bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg p-3 mb-3">
            <p className="text-xs text-[#10B981]">
              💡 Auto-payout runs once per day at your scheduled time. It calculates your total realized 
              profit for the day and sends {payoutSettings.payout_percentage}% to your wallet. 
              No profit = no payout.
            </p>
          </div>

          {/* Save Button */}
          <button
            onClick={savePayoutSettings}
            className="w-full py-2.5 bg-[#10B981] hover:bg-[#059669] text-white font-medium rounded-lg transition-colors"
          >
            Save Auto-Payout Settings
          </button>
        </section>

        {/* Payment Gateways - Nigerian Banks */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]" data-tour="payment-gateways">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-[#10B981]" />
              <h2 className="text-lg font-semibold text-white">Payment Gateways (Nigerian Banks)</h2>
            </div>
          </div>

          <p className="text-xs text-gray-400 mb-4">
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
                <span className="text-sm text-gray-300 font-medium">Paystack</span>
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
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
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
                <span className="text-sm text-gray-300 font-medium">Flutterwave</span>
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
              className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#F59E0B]"
            />
            <p className="text-xs text-gray-500 mt-1">
              Secret key for account validation and bank list fetching
            </p>
          </div>

          <div className="mt-4 p-3 bg-[#3B82F6]/10 border border-[#3B82F6]/30 rounded-md">
            <p className="text-xs text-[#3B82F6]">
              <strong>💡 Why configure this?</strong> Nigerian regulations (CBN NIP) require account validation 
              before transfers. Your users will see verified account holder names before payouts, preventing fraud.
            </p>
          </div>
        </section>

        {/* Save Button */}
        <div
          data-onboarding="save-reset"
          className="flex items-center justify-between gap-3 pt-6 border-t border-[#475569]"
        >
          <button
            onClick={() => { resetTours(); triggerToast('success', 'Tours Reset', 'Onboarding tours will show again on next page navigation'); }}
            className="px-4 py-2 border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm flex items-center gap-2"
          >
            <Plane className="w-4 h-4" /> Reset Onboarding Tours
          </button>
          <button
            onClick={async () => {
              await saveApiSettings();
              if (paymentGateways.paystack_api_key || paymentGateways.flutterwave_api_key) {
                await savePaymentGateways();
              }
            }}
            className="px-6 py-3 bg-[#3B82F6] hover:bg-[#2563EB] text-white font-semibold rounded-lg flex items-center justify-center gap-2"
          >
            <Save className="w-5 h-5" /> Save All Settings
          </button>
        </div>
      </section>
    </div>

      {/* System Status Panel */}
      <CollapsibleSection
        title="System Status"
        subtitle="Real-time monitoring of backend services"
        storageKey="settings-system-open"
      >
        <SystemStatusPanel />
      </CollapsibleSection>

    </div>
  );
}