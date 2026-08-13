'use client';

import React, { useState, useEffect } from 'react';
import { DollarSign, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui';
import { API_URL } from '@/lib/constants';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

interface PaperTradingConfig {
  enabled: boolean;
  initial_capital: number;
  current_balance: number;
  total_pnl: number;
  currency: string;
}

interface PaperTradingPanelProps {
  mode: 'practice' | 'live';
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
  onSaved?: () => void;
}

const inputCls =
  'w-full rounded-control border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

export default function PaperTradingPanel({ mode, triggerToast, onSaved }: PaperTradingPanelProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<PaperTradingConfig>({
    enabled: true,
    initial_capital: 10000,
    current_balance: 10000,
    total_pnl: 0,
    currency: 'USD',
  });

  const deviceId = () => getOrCreateDeviceId();

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/settings/universal-paper-trading`, { headers: { 'X-Device-ID': deviceId() } });
        if (res.ok) setConfig(await res.json());
      } catch (e) {
        console.error('Failed to load paper trading config:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    setConfig((prev) => ({ ...prev, enabled: mode === 'practice' }));
  }, [mode]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/universal-paper-trading`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId() },
        body: JSON.stringify({
          enabled: mode === 'practice',
          initial_capital: config.initial_capital,
          currency: config.currency,
        }),
      });
      if (res.ok) {
        triggerToast('success', 'Settings Saved', 'Practice mode configuration updated.');
        onSaved?.();
      } else {
        throw new Error('Failed to save');
      }
    } catch (e) {
      console.error(e);
      triggerToast('error', 'Save Failed', 'Could not save practice mode settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-slate-400 dark:text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading practice funds…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {mode === 'live' ? (
        <div className="flex items-start gap-3 rounded-control bg-amber-50 p-3 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <strong>Live trading:</strong> Jasper will use connected brokers with real money. Practice balance is not
            used in live mode. Connect a broker (cTrader, Trove, AKShare) in Settings to get started.
          </span>
        </div>
      ) : (
        <>
          <div className="flex items-start gap-3 rounded-control bg-emerald-50 p-3 text-xs text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
            <SaveCircleIcon />
            <span>
              Practice mode is on. Jasper simulates trades with play money — nothing real is traded. Set your virtual
              starting balance below.
            </span>
          </div>

          <div>
            <label htmlFor="virtualStartingBalance" className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">
              Virtual starting balance
            </label>
            <div className="relative">
              <DollarSign className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="virtualStartingBalance"
                type="number"
                value={config.initial_capital}
                onChange={(e) => setConfig({ ...config, initial_capital: parseFloat(e.target.value) || 0 })}
                className={`${inputCls} pl-9`}
              />
            </div>
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
              Current balance {formatCurrency(config.current_balance, config.currency)} · P&amp;L{' '}
              <span
                className={
                  config.total_pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                }
              >
                {config.total_pnl >= 0 ? '+' : ''}
                {formatCurrency(config.total_pnl, config.currency)}
              </span>
            </p>
          </div>

          <div>
            <label htmlFor="paperCurrency" className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Currency</label>
            <select
              id="paperCurrency"
              value={config.currency}
              onChange={(e) => setConfig({ ...config, currency: e.target.value })}
              className={inputCls}
            >
              <option value="USD">USD</option>
              <option value="NGN">NGN</option>
              <option value="CNY">CNY</option>
            </select>
          </div>

          <Button variant="secondary" onClick={save} disabled={saving} size="sm">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <SaveIcon />}
            {saving ? 'Saving…' : 'Save practice balance'}
          </Button>
        </>
      )}
    </div>
  );
}

function formatCurrency(amount: number, currency: string) {
  const symbol = currency === 'NGN' ? '₦' : currency === 'CNY' ? '¥' : '$';
  return `${symbol}${Math.abs(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function SaveIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
      <path d="M17 21v-8H7v8" />
      <path d="M7 3v5h8" />
    </svg>
  );
}
function SaveCircleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2}>
      <circle cx="12" cy="12" r="10" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}