'use client';

import React, { useState, useEffect } from 'react';
import { Radio, DollarSign, Wallet, BrainCircuit, Palette, ChevronRight, Settings2, Sun, Moon, MessageCircle, AlertTriangle } from 'lucide-react';
import { Card, Button, Badge, Modal, Segmented } from '@/components/ui';
import { useTheme } from '@/lib/theme';
import { useCurrency } from '@/lib/currencyContext';
import { API_URL } from '@/lib/constants';
import { fetchTradingMode, saveTradingMode } from '@/lib/preferences';
import SettingsTab from '@/components/SettingsTab';
import ConnectionsPanel from '@/components/settings/ConnectionsPanel';
import PaperTradingPanel from '@/components/settings/PaperTradingPanel';
import TelegramSettings from '@/components/settings/TelegramSettings';

interface SettingsScreenProps {
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
  onNavigate: (tab: string, opts?: { defaultOpen?: StepId }) => void;
  defaultOpen?: StepId | null;
  onDefaultOpenConsumed?: () => void;
}

export type StepId = 'signals' | 'mode' | 'wallet' | 'telegram' | 'ai' | 'appearance';

interface StepDef {
  id: StepId; icon: React.ReactNode; title: string; desc: string; optional?: boolean;
}

export default function SettingsScreen({ triggerToast, onNavigate, defaultOpen, onDefaultOpenConsumed }: SettingsScreenProps) {
  const { theme, toggleTheme } = useTheme();
  const { currency, toggleCurrency } = useCurrency();
  const [mode, setMode] = useState<'practice' | 'live'>('practice');
  const [open, setOpen] = useState<StepId | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [envStatus, setEnvStatus] = useState<{
    environment_variables?: Record<string, { configured: boolean; env_var?: string; description?: string }>;
  } | null>(null);

  useEffect(() => {
    fetchTradingMode().then(setMode);
  }, []);

  useEffect(() => {
    if (defaultOpen) {
      setOpen(defaultOpen);
      onDefaultOpenConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultOpen]);

  useEffect(() => {
    let mounted = true;
    fetch(`${API_URL}/api/v1/settings/env-status`)
      .then((r) => r.json())
      .then((d) => { if (mounted) setEnvStatus(d); })
      .catch(() => console.error('Failed to load env status'));
    return () => { mounted = false; };
  }, []);

  const geminiConfigured = !!envStatus?.environment_variables?.gemini_api_key?.configured;

  const setTradingMode = (m: 'practice' | 'live') => {
    setMode(m);
    saveTradingMode(m);
    triggerToast(
      m === 'live' ? 'warning' : 'success',
      m === 'live' ? 'Live mode on' : 'Practice mode on',
      m === 'live' ? 'Real money trading. Please be careful.' : 'Play money only. Nothing real is traded.'
    );
  };

  const steps: StepDef[] = [
    { id: 'signals', icon: <Radio className="h-5 w-5" />, title: 'Connect signal sources', desc: 'RSS, Reddit, Telegram channels, ranked by results.', optional: true },
    { id: 'mode', icon: <DollarSign className="h-5 w-5" />, title: 'Trading mode', desc: mode === 'practice' ? 'Practice, using play money.' : 'Live, using real money.' },
    { id: 'wallet', icon: <Wallet className="h-5 w-5" />, title: 'Connect wallet & brokers', desc: 'MetaMask, Phantom, CCXT, cTrader, Trove, AKShare.', optional: true },
    { id: 'telegram', icon: <MessageCircle className="h-5 w-5" />, title: 'Telegram alerts', desc: 'Trade alerts and 2-way chat on your phone.', optional: true },
    { id: 'ai', icon: <BrainCircuit className="h-5 w-5" />, title: 'AI engine', desc: geminiConfigured ? 'Gemini is connected and ready.' : 'Gemini needs an API key to trade.' },
    { id: 'appearance', icon: <Palette className="h-5 w-5" />, title: 'Appearance', desc: `${theme === 'dark' ? 'Dark' : 'Light'} mode · ${currency} currency` },
  ];

  const done = steps.filter(s => !s.optional).length;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="eyebrow">Settings</p>
          <h1 className="page-title mt-1">Make it yours</h1>
          <p className="mt-2 max-w-xl muted-caption">A guided checklist. Start simple, dig into the details only when you want to.</p>
        </div>
        <div className="max-w-xs">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Setup progress</span>
            <span className="tnum font-semibold">{done} of {steps.length}</span>
          </div>
          <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${(done / steps.length) * 100}%` }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2" data-onboarding="settings-checklist">
        {steps.map((s, i) => (
          <button
            key={s.id}
            onClick={() => setOpen(s.id)}
            className="card card-hover group flex items-center gap-4 p-4 text-left"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">{s.icon}</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100"><span className="tnum mr-1 text-slate-400">{i + 1}.</span>{s.title}</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{s.desc}</p>
            </div>
            <Badge tone={s.optional ? 'neutral' : 'up'}>
              {s.optional ? 'Optional' : 'Done'}
            </Badge>
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500 dark:text-slate-600" />
          </button>
        ))}
      </div>

      {/* Advanced (hidden from beginners) */}
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"><Settings2 className="h-5 w-5" /></span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Advanced settings</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">API keys, payouts, prediction markets, risk limits, and system status.</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setShowAdvanced(true)}>Open</Button>
        </div>
      </Card>

      {/* ===== Modals ===== */}
      <Modal open={open === 'signals'} onClose={() => setOpen(null)} size="sm" title="Connect signal sources" description="Where Jasper looks for trading ideas.">
        <p className="text-sm text-slate-600 dark:text-slate-300">Add RSS feeds, subreddits, StockTwits lists or Telegram channels. They are all managed on the Signals screen, where results are ranked for you.</p>
        <div className="mt-5 flex gap-2">
          <Button variant="secondary" onClick={() => setOpen(null)}>Close</Button>
          <Button onClick={() => { setOpen(null); onNavigate('signals'); }}>Open Signals</Button>
        </div>
      </Modal>

      <Modal open={open === 'mode'} onClose={() => setOpen(null)} title="Trading mode" description="What should Jasper trade with?">
        <div className="space-y-4">
          <Segmented<'practice' | 'live'>
            value={mode}
            onChange={setTradingMode}
            options={[{ value: 'practice', label: 'Paper (play money)' }, { value: 'live', label: 'Live (real money)' }]}
          />

          {mode === 'practice' ? (
            <>
              <div className="rounded-control bg-emerald-50 p-3 text-xs text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                <strong>Paper trading is on.</strong> Set your virtual starting balance, then press Start on Home to begin
                trading with play money. Nothing real is traded.
              </div>
              <PaperTradingPanel mode={mode} triggerToast={triggerToast} onSaved={() => triggerToast('success', 'Ready to trade', 'Set your balance, then press Start on Home.')} />
            </>
          ) : (
            <>
              <div className="flex items-start gap-3 rounded-control bg-amber-50 p-3 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  <strong>Live trading trades with real money.</strong> Connect a wallet or stock broker below before
                  pressing Start on Home. Nothing is traded until you start.
                </span>
              </div>
              <ConnectionsPanel initialTab="broker" triggerToast={triggerToast} />
            </>
          )}

          <div className="flex justify-end pt-2"><Button variant="secondary" onClick={() => setOpen(null)}>Done</Button></div>
        </div>
      </Modal>

      <Modal open={open === 'wallet'} onClose={() => setOpen(null)} size="lg" title="Connect wallet & brokers" description="Link wallets or stock brokers for trading and on-chain features.">
        <ConnectionsPanel initialTab="wallet" triggerToast={triggerToast} />
        <div className="mt-4 flex justify-end"><Button variant="secondary" onClick={() => setOpen(null)}>Done</Button></div>
      </Modal>

      <Modal open={open === 'telegram'} onClose={() => setOpen(null)} title="Telegram alerts" description="Step-by-step setup for notifications and 2-way chat.">
        <TelegramSettings triggerToast={triggerToast} />
        <div className="mt-4 flex justify-end"><Button variant="secondary" onClick={() => setOpen(null)}>Done</Button></div>
      </Modal>

      <Modal open={open === 'ai'} onClose={() => setOpen(null)} title="AI engine" description="The brain behind Jasper.">
        <div className="space-y-4">
          <div className="flex items-center gap-3 rounded-control border border-slate-200 p-4 dark:border-slate-700">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300"><BrainCircuit className="h-5 w-5" /></span>
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Gemini 2.5 (primary AI)</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                {geminiConfigured ? 'Connected and ready' : 'Not configured — needs an API key'}
              </p>
            </div>
            <Badge tone={geminiConfigured ? 'up' : 'down'} className="ml-auto">
              <span className={`h-1.5 w-1.5 rounded-full ${geminiConfigured ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              {geminiConfigured ? 'Connected' : 'Needs key'}
            </Badge>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-300">Jasper uses Gemini to watch markets, reason about trades in plain English, and explain what it did.</p>
          {!geminiConfigured && (
            <div className="rounded-control bg-amber-50 p-3 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
              Set <code className="font-semibold">GEMINI_API_KEY</code> (~3 keys, comma-separated) in your Render dashboard environment
              variables to enable the AI engine. NVIDIA NIM is kept as a deprecated fallback only.
            </div>
          )}
          <div className="flex justify-end pt-2"><Button variant="secondary" onClick={() => setOpen(null)}>Done</Button></div>
        </div>
      </Modal>

      <Modal open={open === 'appearance'} onClose={() => setOpen(null)} title="Appearance" description="Make Jasper comfortable to use.">
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Theme</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{theme === 'dark' ? 'Dark mode' : 'Light mode'}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={toggleTheme}>
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              Switch to {theme === 'dark' ? 'light' : 'dark'}
            </Button>
          </div>
          <div className="border-t border-slate-100 pt-5 dark:border-slate-800">
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Currency</p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">How amounts are shown ({currency}).</p>
            <div className="mt-3"><Button variant="secondary" size="sm" onClick={toggleCurrency}>Switch to {currency === 'USD' ? 'NGN' : currency === 'NGN' ? 'CNY' : 'USD'}</Button></div>
          </div>
        </div>
      </Modal>

      {/* ===== Advanced settings (brokers, payouts, polymarket, risk, system) ===== */}
      {showAdvanced && (
        <div className="fixed inset-0 z-[90] flex flex-col bg-slate-100 dark:bg-slate-950">
          <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-white"><Settings2 className="h-4 w-4" /></span>
              <p className="font-display font-bold text-slate-900 dark:text-slate-50">Advanced settings</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setShowAdvanced(false)}>Close</Button>
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-5xl p-2 sm:p-3 md:p-4">
              <SettingsTab triggerToast={triggerToast} initialTab="api" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
