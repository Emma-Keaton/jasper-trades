'use client';

import { useState, useEffect } from 'react';
import { Save, Key, Shield, Server, Check, X, RefreshCw, MessageCircle, Bell, Mail, Send, DollarSign, Hash, Smartphone, TrendingUp } from 'lucide-react';
import { Toast } from '@/app/page';
import { SkeletonCard, SkeletonText } from './Skeleton';
import ExnessSection from './ExnessSection';
import TradingCapsSection from './TradingCapsSection';
import PayoutSection from './PayoutSection';
import MarketDataSection from './settings/MarketDataSection';
import EmailServiceSection from './settings/EmailServiceSection';
import DiscordBotSection from './settings/DiscordBotSection';

interface ApiSettings {
  nvidia_api_key: string;
  alpaca_api_key: string;
  alpaca_api_secret: string;
  albaca_paper: boolean;
  binance_api_key: string;
  binance_api_secret: string;
  colab_kronos_url: string;
}

interface ExnessSettings {
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

interface WhatsAppSettings {
  phone_number: string;
  enabled: boolean;
  openwa_url: string;
  configured: boolean;
  chat_enabled?: boolean;
}

interface DiscordSettings {
  webhook_url: string;
  enabled: boolean;
  configured: boolean;
}

interface SlackSettings {
  webhook_url: string;
  enabled: boolean;
  configured: boolean;
}

interface EmailSettings {
  smtp_server: string;
  smtp_port: number;
  username: string;
  password: string;
  from_email: string;
  to_emails: string[];
  enabled: boolean;
  configured: boolean;
}

interface TelegramSettings {
  bot_token: string;
  chat_id: string;
  enabled: boolean;
  configured: boolean;
}

interface SettingsTabProps {
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  initialTab?: string;
  onNavigate?: (tab: string) => void;
}

export default function SettingsTab({ triggerToast, initialTab = 'api', onNavigate }: SettingsTabProps) {
  const [formData, setFormData] = useState<ApiSettings>({
    nvidia_api_key: '',
    alpaca_api_key: '',
    alpaca_api_secret: '',
    alpaca_paper: true,
    binance_api_key: '',
    binance_api_secret: '',
    colab_kronos_url: '',
  });

  const [exness, setExness] = useState<ExnessSettings>({
    login_id: '',
    server: '',
    password: '',
    investor_password: '',
    enabled: false,
    configured: false,
    is_connected: false,
  });

  const [whatsapp, setWhatsapp] = useState<WhatsAppSettings>({
    phone_number: '',
    enabled: false,
    openwa_url: 'http://localhost:3001',
    configured: false,
    chat_enabled: true,
  });

  const [discord, setDiscord] = useState<DiscordSettings>({
    webhook_url: '',
    enabled: false,
    configured: false,
  });

  const [slack, setSlack] = useState<SlackSettings>({
    webhook_url: '',
    enabled: false,
    configured: false,
  });

  const [email, setEmail] = useState<EmailSettings>({
    smtp_server: '',
    smtp_port: 587,
    username: '',
    password: '',
    from_email: '',
    to_emails: [],
    enabled: false,
    configured: false,
  });

  const [telegram, setTelegram] = useState<TelegramSettings>({
    bot_token: '',
    chat_id: '',
    enabled: false,
    configured: false,
  });

  const [payoutSettings, setPayoutSettings] = useState({
    crypto_wallet: '',
    crypto_chain: 'ethereum' as 'ethereum' | 'solana' | 'bsc',
    payout_enabled: false,
    payout_percentage: 50,
    payout_schedule_hour: 20,
    payout_destination: 'crypto_wallet' as 'crypto_wallet' | 'forex_account' | 'split',
    split_ratio: 50,
    min_payout_threshold: 10,
    configured: false,
  });

  const [marketData, setMarketData] = useState({
    alphavantage_key: '',
    finnhub_key: '',
    twelvedata_key: '',
    polygon_key: '',
    fred_key: '',
    coingecko_enabled: true,
  });

  const [sendgrid, setSendgrid] = useState({
    api_key: '',
    from_email: '',
    enabled: false,
  });

  const [discordBot, setDiscordBot] = useState({
    bot_token: '',
    guild_id: '',
    channel_id: '',
    enabled: false,
    chat_enabled: false,
  });

  const [deviceInfo, setDeviceInfo] = useState('');
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<string>(initialTab);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { valid: boolean; message: string }>>({});
  const [whatsappTestStatus, setWhatsappTestStatus] = useState<{testing: boolean; success?: boolean; message?: string}>({ testing: false });
  const [portfolioId, setPortfolioId] = useState<number | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const fetchSettings = async () => {
    setLoading(true);
    try {
      // Generate or get device ID
      let deviceId = localStorage.getItem('device_id');
      if (!deviceId) {
        deviceId = 'device_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('device_id', deviceId);
      }

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
        alpaca_api_key: data.alpaca_api_key || '',
        alpaca_api_secret: data.alpaca_api_secret || '',
        alpaca_paper: data.alpaca_paper ?? true,
        binance_api_key: data.binance_api_key || '',
        binance_api_secret: data.binance_api_secret || '',
        colab_kronos_url: data.colab_kronos_url || '',
      });
      
      setDeviceInfo(`Device ID: ${deviceId}`);

      // Get portfolio ID for trading caps and Exness
      const portfolioRes = await fetch(`${API_URL}/api/v1/portfolio`);
      const portfolios = await portfolioRes.json();
      if (portfolios.data && portfolios.data.length > 0) {
        setPortfolioId(portfolios.data[0].id);
      }

      // Load notification settings from unified settings endpoint
      if (data.discord_config) {
        setDiscord({ webhook_url: data.discord_config.webhook_url || '', enabled: data.discord_config.enabled, configured: !!data.discord_config.webhook_url });
      }
      if (data.slack_config) {
        setSlack({ webhook_url: data.slack_config.webhook_url || '', enabled: data.slack_config.enabled, configured: !!data.slack_config.webhook_url });
      }
      if (data.email_config) {
        setEmail({ 
          smtp_server: data.email_config.smtp_server || '',
          smtp_port: data.email_config.smtp_port || 587,
          username: data.email_config.username || '',
          password: data.email_config.password || '',
          from_email: data.email_config.from_email || '',
          to_emails: data.email_config.to_emails || [],
          enabled: data.email_config.enabled || false,
          configured: !!data.email_config.smtp_server 
        });
      }
      if (data.telegram_config) {
        setTelegram({ bot_token: data.telegram_config.bot_token || '', chat_id: data.telegram_config.chat_id || '', enabled: data.telegram_config.enabled, configured: !!data.telegram_config.bot_token });
      }
      if (data.whatsapp_config) {
        setWhatsapp({ 
          phone_number: data.whatsapp_config.phone_number || '',
          openwa_url: data.whatsapp_config.openwa_url || 'http://localhost:3001',
          enabled: data.whatsapp_config.enabled || false,
          chat_enabled: data.whatsapp_config.chat_enabled || true,
          configured: !!data.whatsapp_config.phone_number 
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
               service === 'alpaca' ? formData.alpaca_api_key :
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

  const saveDiscord = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/settings/notifications/discord/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify({ webhook_url: discord.webhook_url, enabled: discord.enabled }),
      });
      setDiscord({ ...discord, configured: true });
      triggerToast('success', 'Discord Configured', 'Discord notifications enabled.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not configure Discord.');
    }
  };

  const saveSlack = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/settings/notifications/slack/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify({ webhook_url: slack.webhook_url, enabled: slack.enabled }),
      });
      setSlack({ ...slack, configured: true });
      triggerToast('success', 'Slack Configured', 'Slack notifications enabled.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not configure Slack.');
    }
  };

  const saveEmail = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/settings/notifications/email/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify(email),
      });
      setEmail({ ...email, configured: true });
      triggerToast('success', 'Email Configured', 'Email notifications enabled.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not configure Email.');
    }
  };

  const saveTelegram = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/settings/notifications/telegram/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify(telegram),
      });
      setTelegram({ ...telegram, configured: true });
      triggerToast('success', 'Telegram Configured', 'Telegram notifications enabled.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not configure Telegram.');
    }
  };

  const saveWhatsapp = async () => {
    try {
      const deviceId = localStorage.getItem('device_id');
      await fetch(`${API_URL}/api/v1/settings/notifications/whatsapp/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId! },
        body: JSON.stringify({
          phone_number: whatsapp.phone_number,
          openwa_url: whatsapp.openwa_url,
          enabled: whatsapp.enabled,
          chat_enabled: whatsapp.chat_enabled,
        }),
      });
      setWhatsapp({ ...whatsapp, configured: true });
      triggerToast('success', 'WhatsApp Configured', 'WhatsApp notifications enabled.');
    } catch (error) {
      triggerToast('error', 'Failed', 'Could not configure WhatsApp.');
    }
  };

  const testWhatsapp = async () => {
    setWhatsappTestStatus({ testing: true });
    try {
      const res = await fetch(`${API_URL}/api/v1/whatsapp/test`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.success) {
        setWhatsappTestStatus({ testing: false, success: true, message: 'Test message sent!' });
        setTimeout(() => setWhatsappTestStatus({ testing: false }), 3000);
      } else {
        setWhatsappTestStatus({ testing: false, success: false, message: data.detail || 'Failed' });
      }
    } catch (error) {
      setWhatsappTestStatus({ testing: false, success: false, message: 'Connection failed' });
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
    <div className="max-w-4xl mx-auto p-6">
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
        {/* Notification Channels Header */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="w-5 h-5 text-[#F59E0B]" />
            <h2 className="text-lg font-semibold text-white">Multi-Channel Notifications</h2>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            Receive trade alerts, signals, and system notifications on multiple channels.
            Configure all channels below - enable/disable individually.
          </p>

          {/* WhatsApp */}
          <div className="border-t border-[#475569] pt-4 mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <MessageCircle className="w-5 h-5 text-[#25D366]" />
                <h3 className="text-md font-semibold text-white">WhatsApp</h3>
              </div>
              {whatsapp.configured && (
                <span className={`text-xs px-2 py-1 rounded ${whatsapp.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                  {whatsapp.enabled ? 'Enabled' : 'Disabled'}
                </span>
              )}
            </div>
            <div className="space-y-3">
              <input type="tel" value={whatsapp.phone_number} onChange={(e) => setWhatsapp({...whatsapp, phone_number: e.target.value})} placeholder="+1 234 567 8900" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
              <input type="url" value={whatsapp.openwa_url} onChange={(e) => setWhatsapp({...whatsapp, openwa_url: e.target.value})} placeholder="OpenWA URL (http://localhost:3001)" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
            </div>
            <div className="flex items-center gap-2 mt-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={whatsapp.enabled} onChange={(e) => setWhatsapp({...whatsapp, enabled: e.target.checked})} className="w-4 h-4" />
                <span className="text-sm text-gray-300">Enable notifications</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer ml-4">
                <input type="checkbox" checked={whatsapp.chat_enabled} onChange={(e) => setWhatsapp({...whatsapp, chat_enabled: e.target.checked})} className="w-4 h-4" />
                <span className="text-sm text-gray-300">Enable 2-way chat</span>
              </label>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={saveWhatsapp} className="flex-1 py-2 bg-[#25D366] hover:bg-[#20BD5A] text-white rounded-md text-sm">Save</button>
              <button onClick={testWhatsapp} disabled={!whatsapp.configured} className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm disabled:opacity-50">Test</button>
            </div>
            {whatsappTestStatus.message && <p className={`text-xs mt-2 ${whatsappTestStatus.success ? 'text-green-400' : 'text-red-400'}`}>{whatsappTestStatus.message}</p>}
          </div>

          {/* Discord */}
          <div className="border-t border-[#475569] pt-4 mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Hash className="w-5 h-5 text-[#5865F2]" />
                <h3 className="text-md font-semibold text-white">Discord</h3>
              </div>
              {discord.configured && <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">Configured</span>}
            </div>
            <input type="url" value={discord.webhook_url} onChange={(e) => setDiscord({...discord, webhook_url: e.target.value})} placeholder="Discord Webhook URL" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
            <div className="flex items-center gap-2 mt-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={discord.enabled} onChange={(e) => setDiscord({...discord, enabled: e.target.checked})} className="w-4 h-4" />
                <span className="text-sm text-gray-300">Enable notifications</span>
              </label>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={saveDiscord} className="flex-1 py-2 bg-[#5865F2] hover:bg-[#4752C4] text-white rounded-md text-sm">Save</button>
              <button onClick={() => testNotification('Discord')} disabled={!discord.configured} className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm disabled:opacity-50">Test</button>
            </div>
          </div>

          {/* Slack */}
          <div className="border-t border-[#475569] pt-4 mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Send className="w-5 h-5 text-[#E01E5A]" />
                <h3 className="text-md font-semibold text-white">Slack</h3>
              </div>
              {slack.configured && <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">Configured</span>}
            </div>
            <input type="url" value={slack.webhook_url} onChange={(e) => setSlack({...slack, webhook_url: e.target.value})} placeholder="Slack Webhook URL" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
            <div className="flex items-center gap-2 mt-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={slack.enabled} onChange={(e) => setSlack({...slack, enabled: e.target.checked})} className="w-4 h-4" />
                <span className="text-sm text-gray-300">Enable notifications</span>
              </label>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={saveSlack} className="flex-1 py-2 bg-[#E01E5A] hover:bg-[#C4194F] text-white rounded-md text-sm">Save</button>
              <button onClick={() => testNotification('Slack')} disabled={!slack.configured} className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm disabled:opacity-50">Test</button>
            </div>
          </div>

          {/* Email */}
          <div className="border-t border-[#475569] pt-4 mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Mail className="w-5 h-5 text-[#0EA5E9]" />
                <h3 className="text-md font-semibold text-white">Email</h3>
              </div>
              {email.configured && <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">Configured</span>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <input type="text" value={email.smtp_server} onChange={(e) => setEmail({...email, smtp_server: e.target.value})} placeholder="SMTP Server" className="col-span-2 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
              <input type="number" value={email.smtp_port} onChange={(e) => setEmail({...email, smtp_port: parseInt(e.target.value)})} placeholder="587" className="bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
              <input type="text" value={email.username} onChange={(e) => setEmail({...email, username: e.target.value})} placeholder="Username" className="bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
              <input type="password" value={email.password} onChange={(e) => setEmail({...email, password: e.target.value})} placeholder="Password" className="col-span-2 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
              <input type="email" value={email.from_email} onChange={(e) => setEmail({...email, from_email: e.target.value})} placeholder="From Email" className="bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
              <input type="text" value={email.to_emails.join(', ')} onChange={(e) => setEmail({...email, to_emails: e.target.value.split(',').map(s => s.trim())})} placeholder="To Emails (comma-separated)" className="col-span-2 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
            </div>
            <div className="flex items-center gap-2 mt-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={email.enabled} onChange={(e) => setEmail({...email, enabled: e.target.checked})} className="w-4 h-4" />
                <span className="text-sm text-gray-300">Enable notifications</span>
              </label>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={saveEmail} className="flex-1 py-2 bg-[#0EA5E9] hover:bg-[#0C8BC7] text-white rounded-md text-sm">Save</button>
              <button onClick={() => testNotification('Email')} disabled={!email.configured} className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm disabled:opacity-50">Test</button>
            </div>
          </div>

          {/* Telegram */}
          <div className="border-t border-[#475569] pt-4 mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Bell className="w-5 h-5 text-[#229ED9]" />
                <h3 className="text-md font-semibold text-white">Telegram</h3>
              </div>
              {telegram.configured && <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">Configured</span>}
            </div>
            <input type="text" value={telegram.bot_token} onChange={(e) => setTelegram({...telegram, bot_token: e.target.value})} placeholder="Bot Token" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
            <input type="text" value={telegram.chat_id} onChange={(e) => setTelegram({...telegram, chat_id: e.target.value})} placeholder="Chat ID" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm mt-2" />
            <div className="flex items-center gap-2 mt-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={telegram.enabled} onChange={(e) => setTelegram({...telegram, enabled: e.target.checked})} className="w-4 h-4" />
                <span className="text-sm text-gray-300">Enable notifications</span>
              </label>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={saveTelegram} className="flex-1 py-2 bg-[#229ED9] hover:bg-[#1E8EC4] text-white rounded-md text-sm">Save</button>
              <button onClick={() => testNotification('Telegram')} disabled={!telegram.configured} className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] text-white rounded-md text-sm disabled:opacity-50">Test</button>
            </div>
          </div>
        </section>

        {/* API Keys Section */}
        <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
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
              <Shield className="w-5 h-5 text-[#10B981]" />
              <h2 className="text-lg font-semibold text-white">Alpaca Trading</h2>
            </div>
            <button onClick={() => testConnection('alpaca')} disabled={!formData.alpaca_api_key} className="text-xs px-3 py-1.5 rounded-md bg-[#10B981]/20 text-[#10B981] disabled:opacity-50">Test</button>
          </div>
          <input type="password" value={formData.alpaca_api_key} onChange={(e) => setFormData({...formData, alpaca_api_key: e.target.value})} placeholder="API Key (PK...)" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm mb-2" />
          <input type="password" value={formData.alpaca_api_secret} onChange={(e) => setFormData({...formData, alpaca_api_secret: e.target.value})} placeholder="API Secret" className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm" />
          <div className="flex items-center gap-2 mt-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={formData.alpaca_paper} onChange={(e) => setFormData({...formData, alpaca_paper: e.target.checked})} className="w-4 h-4" />
              <span className="text-sm text-gray-400">Paper Trading</span>
            </label>
          </div>
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

        {/* Exness/MT5 Account */}
        <ExnessSection exness={exness} setExness={setExness} triggerToast={triggerToast} />

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
        <TradingCapsSection portfolioId={portfolioId} triggerToast={triggerToast} />

        {/* Market Data Providers */}
        <MarketDataSection marketData={marketData} setMarketData={setMarketData} triggerToast={triggerToast} />

        {/* Email Service (SendGrid) */}
        <EmailServiceSection email={sendgrid} setEmail={setSendgrid} triggerToast={triggerToast} />

        {/* Discord Bot */}
        <DiscordBotSection discord={discordBot} setDiscord={setDiscordBot} triggerToast={triggerToast} />

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

        {/* Save Button */}
        <button onClick={saveApiSettings} className="w-full py-3 bg-[#3B82F6] hover:bg-[#2563EB] text-white font-semibold rounded-lg flex items-center justify-center gap-2">
          <Save className="w-5 h-5" />
          Save All Settings
        </button>
      </div>
    </div>
  );
}