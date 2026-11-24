'use client';

import { useEffect, useState } from 'react';
import { Eye, Plus, Trash2, RefreshCw, Loader2, ShieldCheck } from 'lucide-react';
import { API_URL } from '@/lib/constants';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { apiFetch } from '@/lib/api-client';

interface WhaleTop {
  suggested: string[];
  tracked: string[];
  seen_recently: string[];
  last_events: { mint: string; whale?: string; sol_spent: number; ok: boolean; reasons?: string[] }[];
}

interface WhaleStatus {
  helius_configured: boolean;
  birdeye_configured: boolean;
  tracked_whales: string[];
  thresholds: { min_whale_sol: number; min_liquidity_usd: number; max_risk_score: number };
}

const inputCls =
  'w-full rounded-control border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

export default function WhaleWatchPanel({
  triggerToast,
}: {
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
}) {
  const deviceId = getOrCreateDeviceId();
  const [top, setTop] = useState<WhaleTop | null>(null);
  const [status, setStatus] = useState<WhaleStatus | null>(null);
  const [newWhale, setNewWhale] = useState('');
  const [mint, setMint] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [t, s] = await Promise.all([
        apiFetch(`${API_URL}/api/v1/solana/whales/top`, { headers: { 'X-Device-ID': deviceId } }).then((r) => r.json()),
        apiFetch(`${API_URL}/api/v1/solana/whales/status`, { headers: { 'X-Device-ID': deviceId } }).then((r) => r.json()),
      ]);
      setTop(t);
      setStatus(s);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId]);

  const add = async (wallet: string) => {
    setBusy(true);
    try {
      const res = await apiFetch(`${API_URL}/api/v1/solana/whales`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ wallet }),
      });
      if (res.ok) {
        triggerToast('success', 'Whale added', `${wallet.slice(0, 8)}… is now watched.`);
        await load();
      } else {
        const d = await res.json();
        triggerToast('error', 'Add failed', d.detail || 'Invalid wallet');
      }
    } finally {
      setBusy(false);
    }
  };

  const remove = async (wallet: string) => {
    await apiFetch(`${API_URL}/api/v1/solana/whales/${wallet}`, {
      method: 'DELETE',
      headers: { 'X-Device-ID': deviceId },
    });
    await load();
  };

  const evaluate = async () => {
    if (!mint.trim()) return;
    setBusy(true);
    try {
      const res = await apiFetch(`${API_URL}/api/v1/solana/whales/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ mint: mint.trim(), whale_sol_spent: 5.0 }),
      });
      const d = await res.json();
      triggerToast(
        d.verdict?.ok ? 'success' : 'error',
        d.verdict?.ok ? 'Token passes safety filters' : 'Token blocked',
        (d.verdict?.reasons || []).join('; ') || `liq $${(d.context?.liquidity || 0).toLocaleString()}, rugcheck ${d.context?.risk_score ?? 'n/a'}`
      );
    } finally {
      setBusy(false);
    }
  };

  const registerWebhook = async () => {
    setBusy(true);
    try {
      const url = `${window.location.origin.replace(':3000', ':8000')}/api/v1/solana/whales/webhook`;
      const res = await apiFetch(`${API_URL}/api/v1/solana/whales/register-webhook?webhook_url=${encodeURIComponent(url)}`, {
        method: 'POST',
        headers: { 'X-Device-ID': deviceId },
      });
      const d = await res.json();
      if (d.success) triggerToast('success', 'Helius webhook registered', 'Whale SWAP events will stream to the backend.');
      else triggerToast('error', 'Webhook registration failed', d.error || d.detail || 'Check HELIUS_API_KEY');
    } finally {
      setBusy(false);
    }
  };

  const WalletRow = ({ w, tracked }: { w: string; tracked: boolean }) => (
    <li className="flex items-center gap-2 rounded-control border border-slate-200 px-2 py-1.5 text-xs dark:border-slate-700">
      <span className="font-mono text-slate-700 dark:text-slate-200">{w.slice(0, 8)}…{w.slice(-6)}</span>
      {tracked ? (
        <button onClick={() => remove(w)} disabled={busy} className="ml-auto rounded-full p-1 text-slate-400 hover:text-rose-500" title="Stop watching">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      ) : (
        <button onClick={() => add(w)} disabled={busy} className="ml-auto rounded-full p-1 text-emerald-500 hover:bg-emerald-500/10" title="Watch this whale">
          <Plus className="h-3.5 w-3.5" />
        </button>
      )}
    </li>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-control bg-brand-50 p-3 text-xs text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
        <Eye className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Watch top Solana whales. Their SWAPs stream in via Helius webhooks, pass Birdeye/RugCheck safety
          filters, and become trades through the same engine (paper / demo / live) as everything else.
        </span>
      </div>

      {status && (
        <div className="flex flex-wrap gap-2 text-[10px]">
          <span className={`rounded-full px-2 py-0.5 ${status.helius_configured ? 'bg-emerald-500/15 text-emerald-500' : 'bg-rose-500/15 text-rose-500'}`}>
            Helius {status.helius_configured ? 'configured' : 'needs HELIUS_API_KEY'}
          </span>
          <span className={`rounded-full px-2 py-0.5 ${status.birdeye_configured ? 'bg-emerald-500/15 text-emerald-500' : 'bg-slate-500/15 text-slate-400'}`}>
            Birdeye {status.birdeye_configured ? 'configured' : 'optional'}
          </span>
          <span className="rounded-full bg-slate-500/10 px-2 py-0.5 text-slate-400">
            min {status.thresholds.min_whale_sol} SOL · liq ${status.thresholds.min_liquidity_usd.toLocaleString()} · risk ≤ {status.thresholds.max_risk_score}
          </span>
        </div>
      )}

      <div className="flex gap-2">
        <input value={newWhale} onChange={(e) => setNewWhale(e.target.value)} placeholder="Add whale wallet address (base58)…" className={inputCls} />
        <button onClick={() => newWhale.trim() && add(newWhale.trim())} disabled={busy || !newWhale.trim()} className="shrink-0 rounded-control bg-brand-500 px-3 py-2 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Watch'}
        </button>
        <button onClick={load} title="Refresh" className="shrink-0 rounded-control border border-slate-200 p-2 text-slate-400 dark:border-slate-700">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {top && (
        <>
          <div>
            <p className="mb-1 text-xs font-semibold text-slate-800 dark:text-slate-200">Watching ({top.tracked.length})</p>
            <ul className="space-y-1">{top.tracked.map((w) => <WalletRow key={w} w={w} tracked />)}</ul>
          </div>
          {top.suggested.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold text-slate-800 dark:text-slate-200">Suggested top whales</p>
              <ul className="space-y-1">{top.suggested.filter((w) => !top.tracked.includes(w)).map((w) => <WalletRow key={w} w={w} tracked={false} />)}</ul>
            </div>
          )}
          {top.seen_recently.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold text-slate-800 dark:text-slate-200">Seen recently in whale events</p>
              <ul className="space-y-1">{top.seen_recently.map((w) => <WalletRow key={w} w={w} tracked={false} />)}</ul>
            </div>
          )}
          {top.last_events.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold text-slate-800 dark:text-slate-200">Recent whale events</p>
              <ul className="space-y-1">
                {top.last_events.map((e, i) => (
                  <li key={i} className="flex items-center gap-2 rounded-control border border-slate-200 px-2 py-1 text-[11px] dark:border-slate-700">
                    <span className={e.ok ? 'text-emerald-500' : 'text-rose-500'}>{e.ok ? 'TRADED' : 'FILTERED'}</span>
                    <span className="font-mono">{e.mint.slice(0, 8)}…</span>
                    <span className="text-slate-400">{e.sol_spent.toFixed(2)} SOL by {e.whale?.slice(0, 6) ?? '?'}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <div className="flex gap-2">
        <input value={mint} onChange={(e) => setMint(e.target.value)} placeholder="Token mint to safety-check (Birdeye + RugCheck)…" className={inputCls} />
        <button onClick={evaluate} disabled={busy || !mint.trim()} className="shrink-0 rounded-control bg-slate-700 px-3 py-2 text-xs font-medium text-white hover:bg-slate-600 disabled:opacity-50 dark:bg-slate-600">
          <ShieldCheck className="h-3.5 w-3.5" />
        </button>
      </div>
      <button onClick={registerWebhook} disabled={busy} className="w-full rounded-control border border-dashed border-slate-300 py-2 text-xs text-slate-500 hover:border-brand-400 hover:text-brand-500 dark:border-slate-600">
        Register Helius webhook for watched whales
      </button>
    </div>
  );
}