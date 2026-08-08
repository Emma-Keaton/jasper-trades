'use client';

import React, { useState, useEffect } from 'react';
import { Briefcase, Coins, Plug, Trash2, Loader2, Zap, Globe, Link as LinkIcon, Save, CheckCircle2 } from 'lucide-react';
import { Card, Button } from '@/components/ui';
import WalletConnect from '@/components/portfolio/WalletConnect';
import { API_URL } from '@/lib/constants';

export type ConnectionsTab = 'wallet' | 'broker';

interface BrokerCredential {
  id: number;
  exchange: string;
  wallet_address?: string;
  api_key?: string | null;
  api_secret?: string | null;
}

interface ConnectionsPanelProps {
  initialTab?: ConnectionsTab;
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
}

export default function ConnectionsPanel({ initialTab = 'wallet', triggerToast }: ConnectionsPanelProps) {
  const [tab, setTab] = useState<ConnectionsTab>(initialTab);
  const [ccxtCreds, setCcxtCreds] = useState<BrokerCredential[]>([]);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [loadingCcxt, setLoadingCcxt] = useState(true);

  const [ccxtExchange, setCcxtExchange] = useState('');
  const [ccxtApiKey, setCcxtApiKey] = useState('');
  const [ccxtSecret, setCcxtSecret] = useState('');
  const [savingCcxt, setSavingCcxt] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/crypto-connector`, { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => setCcxtCreds(Array.isArray(d) ? d : []))
      .catch(() => console.error('Failed to load crypto creds'))
      .finally(() => setLoadingCcxt(false));

    fetch(`${API_URL}/api/v1/exchanges/`, { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => setExchanges(Array.isArray(d) ? d : []))
      .catch(() => console.error('Failed to load exchanges'));
  }, []);

  const handleSaveCcxt = async () => {
    if (!ccxtExchange) {
      triggerToast('error', 'Exchange Missing', 'Please choose an exchange.');
      return;
    }
    setSavingCcxt(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/crypto-connector`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exchange: ccxtExchange,
          api_key: ccxtApiKey || null,
          api_secret: ccxtSecret || null,
        }),
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Failed to save');
      const refreshed = await fetch(`${API_URL}/api/v1/crypto-connector`, { credentials: 'include' }).then((r) => r.json());
      setCcxtCreds(Array.isArray(refreshed) ? refreshed : []);
      setCcxtApiKey('');
      setCcxtSecret('');
      triggerToast('success', 'Exchange Linked', `${ccxtExchange} connected via CCXT.`);
    } catch (e) {
      console.error('Failed to save CCXT credential:', e);
      triggerToast('error', 'Save Failed', 'Could not link this exchange.');
    } finally {
      setSavingCcxt(false);
    }
  };

  const handleDeleteCcxt = async (id: number) => {
    if (!confirm('Delete this exchange credential?')) return;
    try {
      await fetch(`${API_URL}/api/v1/crypto-connector/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      setCcxtCreds((prev) => prev.filter((c) => c.id !== id));
      triggerToast('success', 'Removed', 'Exchange credential removed.');
    } catch (e) {
      console.error('Failed to delete credential:', e);
      triggerToast('error', 'Delete Failed', 'Could not remove credential.');
    }
  };

  const inputCls =
    'w-full rounded-control border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

  return (
    <div className="space-y-5">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setTab('wallet')}
          className={`flex flex-1 items-center justify-center gap-2 rounded-control border px-3 py-2.5 text-sm font-semibold transition ${
            tab === 'wallet'
              ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
              : 'border-slate-200 text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:text-slate-300'
          }`}
        >
          <Coins className="h-4 w-4" /> Crypto Wallets
        </button>
        <button
          type="button"
          onClick={() => setTab('broker')}
          className={`flex flex-1 items-center justify-center gap-2 rounded-control border px-3 py-2.5 text-sm font-semibold transition ${
            tab === 'broker'
              ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
              : 'border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-300'
          }`}
        >
          <Briefcase className="h-4 w-4" /> Stock Brokers
        </button>
      </div>

      {tab === 'wallet' ? (
        <div className="space-y-5">
          <Card className="p-5">
            <div className="mb-3 flex items-center gap-2">
              <Coins className="h-4 w-4 text-brand-600 dark:text-brand-400" />
              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-50">Wallet (EVM / Solana)</h4>
            </div>
            <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
              Link a wallet to use on-chain features. Mainnet only.
            </p>
            <WalletConnect />
          </Card>

          <Card className="p-5">
            <div className="mb-3 flex items-center gap-2">
              <Plug className="h-4 w-4 text-brand-600 dark:text-brand-400" />
              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-50">CCXT Exchange Keys</h4>
            </div>
            <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
              Link a cryptocurrency exchange through CCXT to let Jasper read balances and trade.
            </p>

            <div className="mb-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Exchange</label>
                <select value={ccxtExchange} onChange={(e) => setCcxtExchange(e.target.value)} className={inputCls}>
                  <option value="">Select exchange…</option>
                  {exchanges.map((ex) => (
                    <option key={ex} value={ex}>
                      {ex}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">API Key</label>
                <input
                  type="text"
                  value={ccxtApiKey}
                  onChange={(e) => setCcxtApiKey(e.target.value)}
                  placeholder="Your API key"
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">API Secret</label>
                <input
                  type="password"
                  value={ccxtSecret}
                  onChange={(e) => setCcxtSecret(e.target.value)}
                  placeholder="Your API secret"
                  className={inputCls}
                />
              </div>
              <Button variant="secondary" size="sm" onClick={handleSaveCcxt} disabled={savingCcxt || !ccxtExchange}>
                {savingCcxt ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
                {savingCcxt ? 'Linking…' : 'Link exchange'}
              </Button>
            </div>

            {loadingCcxt ? (
              <p className="text-xs text-slate-400 dark:text-slate-500">Loading linked exchanges…</p>
            ) : ccxtCreds.length > 0 ? (
              <ul className="space-y-2">
                {ccxtCreds.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center gap-2 rounded-control border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800/60"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                      <Coins className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold capitalize text-slate-900 dark:text-slate-100">{c.exchange}</p>
                      {c.wallet_address && (
                        <p className="truncate font-mono text-xs text-slate-400 dark:text-slate-500">
                          {c.wallet_address.slice(0, 10)}…{c.wallet_address.slice(-6)}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteCcxt(c.id)}
                      className="rounded-full p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10"
                      aria-label={`Remove ${c.exchange}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500">No exchanges linked yet.</p>
            )}
          </Card>
        </div>
      ) : (
        <BrokerConnections triggerToast={triggerToast} />
      )}
    </div>
  );
}

function BadgeDot({ tone, label }: { tone: 'up' | 'down' | 'neutral'; label: string }) {
  const color =
    tone === 'up'
      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
      : tone === 'down'
      ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300'
      : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${tone === 'up' ? 'bg-emerald-500' : tone === 'down' ? 'bg-rose-500' : 'bg-slate-400'}`} />
      {label}
    </span>
  );
}

function getDeviceId(): string {
  if (typeof window === 'undefined') return 'dev_unknown';
  let deviceId = localStorage.getItem('device_id');
  if (!deviceId) {
    deviceId = 'dev_' + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('device_id', deviceId);
  }
  return deviceId;
}

function SectionField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">{label}</label>
      {children}
    </div>
  );
}

const inputCls =
  'w-full rounded-control border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

interface BrokerCardDef {
  id: string;
  name: string;
  desc: string;
  badge: string;
  icon: React.ReactNode;
  render: (props: { onSaved: () => void; triggerToast: (t: 'success' | 'error' | 'info', title: string, message: string) => void }) => React.ReactNode;
}

function BrokerConnections({ triggerToast }: { triggerToast: (t: 'success' | 'error' | 'info', title: string, message: string) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [, setSavedTick] = useState(0);
  const onSaved = () => setSavedTick((t) => t + 1);

  const cards: BrokerCardDef[] = [
    {
      id: 'trove',
      name: 'Trove Finance',
      desc: 'US stocks + Nigerian NGX equities with fractional shares.',
      badge: 'US · NGX',
      icon: <Zap className="h-4 w-4" />,
      render: ({ triggerToast: tt, onSaved: os }) => (
        <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
          <TroveBroker triggerToast={tt} onSaved={os} />
        </div>
      ),
    },
    {
      id: 'ctrader',
      name: 'cTrader',
      desc: 'OAuth2 auto-trading for FX and CFDs.',
      badge: 'OAuth2',
      icon: <Globe className="h-4 w-4" />,
      render: ({ triggerToast: tt }) => (
        <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
          <CTraderBroker triggerToast={tt} />
        </div>
      ),
    },
    {
      id: 'akshare',
      name: 'AKShare (China)',
      desc: 'Shanghai & Shenzhen exchanges, A/B-shares.',
      badge: 'SSE · SZSE',
      icon: <Coins className="h-4 w-4" />,
      render: ({ triggerToast: tt, onSaved: os }) => (
        <div className="rounded-control border border-slate-200 p-4 dark:border-slate-700">
          <AKShareBroker triggerToast={tt} onSaved={os} />
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
        Connect a stock broker for automated execution. Paper trading is handled by the global <strong>Practice</strong>{' '}
        mode in Settings, so brokers here run in <strong>live</strong> mode when you switch to it.
      </p>
      {cards.map((c) => {
        const isOpen = open === c.id;
        return (
          <Card key={c.id} hover={!isOpen} onClick={() => setOpen(isOpen ? null : c.id)} className="p-4">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                {c.icon}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{c.name}</p>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                    {c.badge}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{c.desc}</p>
              </div>
              <CheckCircle2 className={`h-5 w-5 shrink-0 ${isOpen ? 'text-brand-500' : 'text-slate-200 dark:text-slate-700'}`} />
            </div>
            {isOpen && (
              <div className="mt-4">
                {c.render({ onSaved, triggerToast })}
                <div className="mt-3 flex justify-end">
                  <Button variant="ghost" size="sm" onClick={() => setOpen(null)}>
                    Close
                  </Button>
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function TroveBroker({
  triggerToast,
  onSaved,
}: {
  triggerToast: (t: 'success' | 'error' | 'info', title: string, message: string) => void;
  onSaved: () => void;
}) {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('https://sandbox.api.trovefinance.com/v1');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'unknown' | 'connected' | 'error'>('unknown');
  const deviceId = getDeviceId();

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/settings/trove`, { headers: { 'X-Device-ID': deviceId } });
        if (res.ok) {
          const d = await res.json();
          setEnabled(!!d.trove_enabled);
          setBaseUrl(d.trove_base_url || baseUrl);
          if (d.trove_enabled && d.trove_api_key) {
            const t = await fetch(`${API_URL}/api/v1/trove/status`, { headers: { 'X-Device-ID': deviceId } }).then((r) => r.json());
            setStatus(t.connected ? 'connected' : 'error');
          }
        }
      } catch (e) {
        console.error('Failed to load Trove settings:', e);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (test: boolean) => {
    if (!apiKey) {
      triggerToast('error', 'API Key Required', 'Please enter your Trove API key.');
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/trove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ trove_api_key: apiKey, trove_base_url: baseUrl, trove_enabled: enabled }),
      });
      if (!res.ok) {
        const err = await res.json();
        triggerToast('error', 'Save Failed', err.detail || 'Failed to save Trove settings.');
        return;
      }
      if (test) {
        const tr = await fetch(`${API_URL}/api/v1/settings/trove/test`, { headers: { 'X-Device-ID': deviceId } }).then((r) => r.json());
        if (tr.valid) {
          setStatus('connected');
          triggerToast('success', 'Trove Connected', `Connected to Trove API (${tr.account_id || 'N/A'}).`);
        } else {
          setStatus('error');
          triggerToast('error', 'Connection Failed', tr.message || 'Failed to connect.');
        }
      } else {
        setStatus('connected');
        triggerToast('success', 'Trove Saved', 'Trove API configuration saved.');
      }
      onSaved();
    } catch (e) {
      console.error(e);
      triggerToast('error', 'Save Failed', 'Could not save Trove settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <BadgeDot
          tone={status === 'connected' ? 'up' : status === 'error' ? 'down' : 'neutral'}
          label={status === 'connected' ? 'Connected' : status === 'error' ? 'Check key' : 'Not connected'}
        />
        <Button variant="secondary" size="sm" onClick={() => save(true)} disabled={saving || !apiKey}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Test connection
        </Button>
      </div>
      <SectionField label="Trove API Key">
        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="trv_sk_…" className={inputCls} />
      </SectionField>
      <SectionField label="Base URL">
        <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className={inputCls} />
      </SectionField>
      <label className="mb-4 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="h-4 w-4" />
        Enable Trove for stock trading
      </label>
      <Button variant="secondary" onClick={() => save(false)} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save Trove
      </Button>
    </div>
  );
}

function CTraderBroker({ triggerToast }: { triggerToast: (t: 'success' | 'error' | 'info', title: string, message: string) => void }) {
  const [connecting, setConnecting] = useState(false);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/ctrader/accounts`);
        if (res.ok) {
          const data = await res.json();
          setAccounts(data.accounts || []);
        }
      } catch (e) {
        console.error('Failed to fetch cTrader accounts:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const connect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/ctrader/connect?mode=sandbox`);
      const data = await res.json();
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        setError(data.detail || 'Failed to get authorization URL');
      }
    } catch (e) {
      console.error('cTrader connect failed:', e);
      setError('Connection failed. Please try again.');
    } finally {
      setConnecting(false);
    }
  };

  const disconnect = async (id: number) => {
    if (!confirm('Disconnect this cTrader account? Auto-trading will stop.')) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/ctrader/disconnect/${id}`, { method: 'POST' });
      if (res.ok) {
        setAccounts((prev) => prev.filter((a) => a.id !== id));
        triggerToast('success', 'Account Disconnected', 'Auto-trading stopped.');
      }
    } catch (e) {
      console.error(e);
      setError('Failed to disconnect account.');
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500 dark:text-slate-400">
        cTrader uses high-security OAuth2. You will log in on cTrader's secure site — no secrets stored on device.
      </p>
      {error && <p className="text-xs text-rose-600 dark:text-rose-400">{error}</p>}
      {loading ? (
        <p className="text-xs text-slate-400 dark:text-slate-500">Loading accounts…</p>
      ) : accounts.length > 0 ? (
        <ul className="space-y-2">
          {accounts.map((a) => (
            <li key={a.id} className="rounded-control border border-slate-200 p-3 text-sm dark:border-slate-700">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{a.account_name}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {a.broker_name} · {a.account_currency} · {a.account_balance?.toFixed?.(2)}
                  </p>
                </div>
                <button onClick={() => disconnect(a.id)} className="rounded-full p-1.5 text-slate-400 hover:text-rose-600" aria-label="Disconnect account">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-400 dark:text-slate-500">No cTrader accounts connected yet.</p>
      )}
      <Button variant="secondary" onClick={connect} disabled={connecting}>
        {connecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <LinkIcon className="h-4 w-4" />}
        {connecting ? 'Redirecting…' : 'Connect cTrader account'}
      </Button>
    </div>
  );
}

function AKShareBroker({
  triggerToast,
  onSaved,
}: {
  triggerToast: (t: 'success' | 'error' | 'info', title: string, message: string) => void;
  onSaved: () => void;
}) {
  const [enabled, setEnabled] = useState(false);
  const [currency, setCurrency] = useState('CNY');
  const [initialCapital, setInitialCapital] = useState('1000000');
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'unknown' | 'connected' | 'error'>('unknown');
  const deviceId = getDeviceId();

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/settings/akshare`, { headers: { 'X-Device-ID': deviceId } });
        if (res.ok) {
          const d = await res.json();
          setEnabled(!!d.enabled);
          setCurrency(d.currency || 'CNY');
          setInitialCapital(d.initial_capital?.toString?.() ?? '1000000');
          if (d.enabled) {
            const s = await fetch(`${API_URL}/api/v1/akshare/status`).then((r) => r.json());
            setStatus(s.connected ? 'connected' : 'error');
          }
        }
      } catch (e) {
        console.error('Failed to load AKShare settings:', e);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/settings/akshare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ enabled, currency, initial_capital: initialCapital, paper_trading: true }),
      });
      if (res.ok) {
        setStatus('connected');
        triggerToast('success', 'AKShare Saved', 'Chinese stock trading configured.');
        onSaved();
      } else {
        triggerToast('error', 'Save Failed', 'Could not save AKShare settings.');
      }
    } catch (e) {
      console.error(e);
      triggerToast('error', 'Save Failed', 'Error saving AKShare settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <BadgeDot
        tone={status === 'connected' ? 'up' : status === 'error' ? 'down' : 'neutral'}
        label={status === 'connected' ? 'Connected' : status === 'error' ? 'Check backend' : 'Not connected'}
      />
      <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="h-4 w-4" />
        Enable Chinese stock trading
      </label>
      <SectionField label="Trading currency">
        <select value={currency} onChange={(e) => setCurrency(e.target.value)} className={inputCls}>
          <option value="CNY">CNY — A-shares</option>
          <option value="USD">USD — B-shares SSE</option>
          <option value="HKD">HKD — B-shares SZSE</option>
        </select>
      </SectionField>
      <SectionField label="Paper trading capital">
        <input type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)} className={inputCls} />
      </SectionField>
      <Button variant="secondary" onClick={save} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
        {saving ? 'Saving…' : 'Save AKShare'}
      </Button>
    </div>
  );
}
