'use client';

import React, { useState, useEffect } from 'react';
import { Send, MessageCircle, ShieldCheck, Loader2, CheckCircle2, ExternalLink } from 'lucide-react';
import { Card, Button } from '@/components/ui';
import { API_URL } from '@/lib/constants';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

interface TelegramSetupProps {
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
}

interface TelegramState {
  chat_id: string;
  is_verified: boolean;
  trade_notifications_enabled: boolean;
  daily_summary_enabled: boolean;
  chat_enabled: boolean;
  ai_explanations_enabled: boolean;
  summary_time_wat: string;
}

const inputCls =
  'w-full rounded-control border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

export default function TelegramSetup({ triggerToast }: TelegramSetupProps) {
  const [telegram, setTelegram] = useState<TelegramState>({
    chat_id: '',
    is_verified: false,
    trade_notifications_enabled: true,
    daily_summary_enabled: true,
    chat_enabled: true,
    ai_explanations_enabled: true,
    summary_time_wat: '20:00',
  });
  const [verificationCode, setVerificationCode] = useState('');
  const [requesting, setRequesting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [message, setMessage] = useState<{ success?: boolean; text?: string }>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const deviceId = () => getOrCreateDeviceId();

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/settings/telegram/status`, { headers: { 'X-Device-ID': deviceId() } });
        const data = await res.json();
        if (data.is_configured) {
          setTelegram((prev) => ({
            ...prev,
            is_verified: !!data.is_verified,
            chat_id: data.chat_id || prev.chat_id,
            trade_notifications_enabled: data.preferences?.trade_notifications_enabled ?? prev.trade_notifications_enabled,
            daily_summary_enabled: data.preferences?.daily_summary_enabled ?? prev.daily_summary_enabled,
            summary_time_wat: data.preferences?.summary_time_wat ?? prev.summary_time_wat,
            chat_enabled: data.preferences?.chat_enabled ?? prev.chat_enabled,
            ai_explanations_enabled: data.preferences?.ai_explanations_enabled ?? prev.ai_explanations_enabled,
          }));
        }
      } catch (e) {
        console.error('Failed to load Telegram status:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const requestCode = async () => {
    if (!telegram.chat_id) {
      setMessage({ success: false, text: 'Please enter your Chat ID first.' });
      return;
    }
    setRequesting(true);
    setMessage({});
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/verify/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId() },
        body: JSON.stringify({ chat_id: telegram.chat_id }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setCodeSent(true);
        setMessage({ success: true, text: `Verification code sent to ${telegram.chat_id.slice(0, 5)}***` });
      } else {
        setMessage({ success: false, text: data.detail || 'Failed to send code.' });
      }
    } catch (e) {
      console.error(e);
      setMessage({ success: false, text: 'Failed to send verification code.' });
    } finally {
      setRequesting(false);
    }
  };

  const confirmCode = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      setMessage({ success: false, text: 'Please enter the 6-digit code.' });
      return;
    }
    setVerifying(true);
    setMessage({});
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/verify/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId() },
        body: JSON.stringify({ chat_id: telegram.chat_id, verification_code: verificationCode }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTelegram((prev) => ({ ...prev, is_verified: true }));
        setVerificationCode('');
        setCodeSent(false);
        setMessage({ success: true, text: 'Telegram verified successfully!' });
        triggerToast('success', 'Verified', 'Telegram number verified successfully.');
      } else {
        setMessage({ success: false, text: data.detail || 'Invalid or expired code.' });
      }
    } catch (e) {
      console.error(e);
      setMessage({ success: false, text: 'Verification failed.' });
    } finally {
      setVerifying(false);
    }
  };

  const testConnection = async () => {
    setSaving(true);
    setMessage({});
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/test`, {
        method: 'POST',
        headers: { 'X-Device-ID': deviceId() },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage({ success: true, text: 'Test message sent! Check your Telegram.' });
      } else {
        setMessage({ success: false, text: data.detail || 'Failed to send test.' });
      }
    } catch (e) {
      console.error(e);
      setMessage({ success: false, text: 'Connection failed.' });
    } finally {
      setSaving(false);
    }
  };

  const savePreferences = async () => {
    setSaving(true);
    setMessage({});
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/telegram/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId() },
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
        setMessage({ success: true, text: 'Notification preferences saved.' });
        triggerToast('success', 'Preferences Saved', 'Telegram notification preferences updated.');
      } else {
        setMessage({ success: false, text: data.detail || 'Could not save preferences.' });
      }
    } catch (e) {
      console.error(e);
      setMessage({ success: false, text: 'Could not save Telegram preferences.' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-5 text-sm text-slate-400 dark:text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin inline" /> Loading Telegram status…
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <MessageCircle className="h-4 w-4 text-brand-600 dark:text-brand-400" />
        <h4 className="text-sm font-bold text-slate-900 dark:text-slate-50">Telegram notifications</h4>
        {telegram.is_verified && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
            <ShieldCheck className="h-3.5 w-3.5" /> Verified
          </span>
        )}
      </div>
      <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
        Receive trade alerts, daily summaries, and 2-way chat. Follow the steps to link your Telegram account.
      </p>

      {!telegram.is_verified ? (
        <div className="space-y-3">
          <div className="rounded-control border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-500/30 dark:bg-emerald-500/10">
            <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">Step 1 · Start the bot</p>
            <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">
              Open <strong>@jasper_trades_bot</strong> on Telegram — it will send you your Chat ID.
            </p>
            <Button variant="secondary" size="sm" className="mt-2" onClick={() => window.open('https://t.me/jasper_trades_bot', '_blank', 'noopener,noreferrer')}>
              <ExternalLink className="h-4 w-4" /> Open on Telegram
            </Button>
          </div>

          <div>
            <label htmlFor="telegramChatId" className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Chat ID</label>
            <div className="flex gap-2">
              <input
                id="telegramChatId"
                type="text"
                value={telegram.chat_id}
                onChange={(e) => setTelegram({ ...telegram, chat_id: e.target.value })}
                placeholder="@username or 123456789"
                className={inputCls}
              />
              <Button variant="secondary" onClick={requestCode} disabled={requesting || !telegram.chat_id}>
                {requesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                {requesting ? 'Sending…' : 'Send code'}
              </Button>
            </div>
          </div>

          {codeSent && (
            <div>
              <label htmlFor="telegramVerificationCode" className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Step 2 · Enter the 6-digit code</label>
              <div className="flex gap-2">
                <input
                  id="telegramVerificationCode"
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  placeholder="000000"
                  maxLength={6}
                  className={inputCls}
                />
                <Button variant="secondary" onClick={confirmCode} disabled={verifying || verificationCode.length !== 6}>
                  {verifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                  {verifying ? 'Verifying…' : 'Verify'}
                </Button>
              </div>
            </div>
          )}

          {message.text && (
            <p className={`text-xs ${message.success ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {message.text}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            Connected as <span className="font-mono font-semibold">{telegram.chat_id}</span>
          </div>

          <div className="space-y-2">
            <PrefToggle label="Trade executions (real-time)" value={telegram.trade_notifications_enabled} onChange={(v) => setTelegram({ ...telegram, trade_notifications_enabled: v })} />
            <PrefToggle label="Daily summary" value={telegram.daily_summary_enabled} onChange={(v) => setTelegram({ ...telegram, daily_summary_enabled: v })} />
            <PrefToggle label="2-way chat (ask about portfolio)" value={telegram.chat_enabled} onChange={(v) => setTelegram({ ...telegram, chat_enabled: v })} />
            <PrefToggle label="AI trade explanations" value={telegram.ai_explanations_enabled} onChange={(v) => setTelegram({ ...telegram, ai_explanations_enabled: v })} />
          </div>

          <div>
            <label htmlFor="telegramSummaryTime" className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Daily summary time (WAT)</label>
            <input id="telegramSummaryTime" type="time" value={telegram.summary_time_wat} onChange={(e) => setTelegram({ ...telegram, summary_time_wat: e.target.value })} className={inputCls} />
          </div>

          <div className="flex gap-2">
            <Button variant="secondary" onClick={savePreferences} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Save preferences
            </Button>
            <Button variant="ghost" onClick={testConnection} disabled={saving}>
              Test connection
            </Button>
          </div>

          {message.text && (
            <p className={`text-xs ${message.success ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {message.text}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function PrefToggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={value} onClick={() => onChange(!value)} className="flex w-full items-center justify-between gap-3 text-left">
      <span className="text-sm text-slate-700 dark:text-slate-200">{label}</span>
      <span className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition ${value ? 'bg-brand-600' : 'bg-slate-300 dark:bg-slate-700'}`}>
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${value ? 'translate-x-6' : 'translate-x-1'}`} />
      </span>
    </button>
  );
}
