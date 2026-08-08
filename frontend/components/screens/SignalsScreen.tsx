'use client';

import React, { useState, useEffect } from 'react';
import { Plus, RefreshCw, CheckCircle, XCircle, Send, Radio, Wifi, MessageSquare, User } from 'lucide-react';
import { Card, Button, Badge, Modal, EmptyState } from '@/components/ui';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Source { id: number; source_type: string; display_name: string; is_active: boolean; last_fetched_at: string | null; }
interface Tip { id: number; slug: string; symbol: string; side: string; timeframe: string | null; confidence: number; rationale: string | null; source_type: string; text: string | null; url: string | null; created_at: string; executed: boolean; }
interface Channel { id: number; username: string | null; title: string | null; type: string; }

const SOURCE_TYPES = ['rss', 'reddit', 'stocktwits'];
const sourceIcon: Record<string, React.ReactNode> = {
  rss: <Wifi className="h-4 w-4" />, reddit: <MessageSquare className="h-4 w-4" />,
  stocktwits: <User className="h-4 w-4" />, telegram: <Send className="h-4 w-4" />,
};

interface SignalsScreenProps {
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
  executeTrade?: (symbol: string, type: 'BUY' | 'SELL', shares: number, price: number, total: number, agentName: string) => void;
}

export default function SignalsScreen({ triggerToast, executeTrade }: SignalsScreenProps) {
  const deviceId = getOrCreateDeviceId();
  const headers = { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' };

  const [sources, setSources] = useState<Source[]>([]);
  const [tips, setTips] = useState<Tip[]>([]);
  const [tgConnected, setTgConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  const [showForm, setShowForm] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newType, setNewType] = useState('rss');
  const [newName, setNewName] = useState('');
  const [newConfig, setNewConfig] = useState('{}');

  const [tgOpen, setTgOpen] = useState(false);
  const [tgStep, setTgStep] = useState(0);
  const [tgPhone, setTgPhone] = useState('');
  const [tgCode, setTgCode] = useState('');
  const [tgPassword, setTgPassword] = useState('');
  const [tgChannels, setTgChannels] = useState<Channel[]>([]);
  const [tgSelected, setTgSelected] = useState<Set<number>>(new Set());
  const [tgBusy, setTgBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [sRes, tRes, aRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/signals/sources`, { headers }),
        fetch(`${API_URL}/api/v1/signals/tips`, { headers }),
        fetch(`${API_URL}/api/v1/signals/telegram/account`, { headers }),
      ]);
      if (sRes.ok) setSources(await sRes.json());
      if (tRes.ok) setTips(await tRes.json());
      if (aRes.ok) { const a = await aRes.json(); setTgConnected(!!a.connected); }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const addSource = async (e: React.FormEvent) => {
    e.preventDefault(); setAdding(true);
    let cfg: object = {};
    try { cfg = JSON.parse(newConfig); } catch { triggerToast('error', 'Something is off', 'The config must be valid JSON.'); setAdding(false); return; }
    const r = await fetch(`${API_URL}/api/v1/signals/sources`, { method: 'POST', headers, body: JSON.stringify({ source_type: newType, display_name: newName, config: cfg }) });
    if (r.ok) {
      const created = await r.json();
      await fetch(`${API_URL}/api/v1/signals/follow`, { method: 'POST', headers, body: JSON.stringify({ source_id: created.id }) });
      triggerToast('success', 'Source added', 'The AI can now look here for ideas.');
      setShowForm(false); setNewName(''); setNewConfig('{}'); load();
    } else triggerToast('error', 'Could not add', 'Please check the details and try again.');
    setAdding(false);
  };

  const fetchNow = async () => {
    triggerToast('info', 'Fetching ideas', 'Scanning your sources for tradeable tips...');
    try { const r = await fetch(`${API_URL}/api/v1/signals/fetch`, { method: 'POST', headers }); if (r.ok) { triggerToast('success', 'Done', 'New tips are ready.'); load(); } } catch { /* ignore */ }
  };

  const resolveTip = async (id: number, hit: boolean) => {
    try {
      await fetch(`${API_URL}/api/v1/signals/tips/${id}/resolve`, { method: 'POST', headers, body: JSON.stringify({ hit }) });
      triggerToast(hit ? 'success' : 'info', hit ? 'Marked as a hit' : 'Marked as a miss', 'Thanks for the feedback.');
      load();
    } catch { /* ignore */ }
  };

  const executeTip = async (t: Tip) => {
    if (executeTrade) executeTrade(t.symbol, t.side === 'SHORT' ? 'SELL' : 'BUY', 0.01, 0, 0, 'Signals');
    else triggerToast('info', 'Signal source', 'This needs a connected portfolio.');
  };

  const sendCode = async () => { setTgBusy(true); try { const r = await fetch(`${API_URL}/api/v1/signals/telegram/send-code`, { method: 'POST', headers, body: JSON.stringify({ phone: tgPhone }) }); if (r.ok) setTgStep(1); else triggerToast('error', 'Could not send code', 'Check the phone number.'); } finally { setTgBusy(false); } };
  const verifyCode = async () => { setTgBusy(true); try { const r = await fetch(`${API_URL}/api/v1/signals/telegram/verify`, { method: 'POST', headers, body: JSON.stringify({ phone: tgPhone, code: tgCode, password: tgPassword || undefined }) }); if (r.ok) { const d = await r.json(); setTgChannels(d.channels || []); setTgStep(2); } else triggerToast('error', 'Could not verify', 'Try again.'); } finally { setTgBusy(false); } };
  const savePicks = async () => { setTgBusy(true); try { const r = await fetch(`${API_URL}/api/v1/signals/telegram/channels`, { method: 'POST', headers, body: JSON.stringify({ channel_ids: Array.from(tgSelected) }) }); if (r.ok) { triggerToast('success', 'Connected', 'Telegram channels are now watched.'); setTgOpen(false); setTgStep(0); setTgPhone(''); setTgCode(''); setTgPassword(''); setTgSelected(new Set()); load(); } } finally { setTgBusy(false); } };
  const togglePick = (id: number) => setTgSelected(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Signals</p>
        <h1 className="page-title mt-1">Places Jasper looks for ideas</h1>
        <p className="mt-2 max-w-xl muted-caption">Plug in news feeds, Reddit, StockTwits or Telegram channels and get ranked trading tips from the AI.</p>
      </div>

      <section>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50" data-onboarding="signals-sources">My sources</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowForm(true)}><Plus className="h-4 w-4" /> Add source</Button>
            <Button size="sm" onClick={fetchNow} disabled={loading}><RefreshCw className="h-4 w-4" /> Fetch now</Button>
          </div>
        </div>

        {loading ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0,1,2].map(i => <div key={i} className="skeleton h-28 w-full" />)}</div>
        ) : sources.length === 0 ? (
          <div className="mt-4">
            <EmptyState icon={<Radio className="h-6 w-6" />} title="No sources yet" description="Add a feed, subreddit or StockTwits list so the AI has somewhere to look for ideas." action={<Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4" /> Add your first source</Button>} />
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {sources.map(s => (
              <Card key={s.id} className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">{sourceIcon[s.source_type] || <Wifi className="h-4 w-4" />}</span>
                    <p className="text-sm font-semibold capitalize text-slate-900 dark:text-slate-100">{s.display_name || s.source_type}</p>
                  </div>
                  <Badge tone={s.is_active ? 'up' : 'neutral'}>{s.is_active ? 'Active' : 'Off'}</Badge>
                </div>
                <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{s.last_fetched_at ? `Last checked ${new Date(s.last_fetched_at).toLocaleString()}` : 'Not checked yet'}</p>
              </Card>
            ))}
            {!tgConnected && (
              <Card hover onClick={() => setTgOpen(true)} className="flex cursor-pointer flex-col items-center justify-center gap-2 border-dashed p-4 text-center">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"><Send className="h-4 w-4" /></span>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Connect Telegram</p>
                <p className="text-xs text-slate-400 dark:text-slate-500">Get ideas from your channels</p>
              </Card>
            )}
          </div>
        )}
      </section>

      {/* Ranked Tips */}
      <section>
        <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">Ranked tips</h2>
        {tips.length === 0 ? (
          <p className="mt-4 rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
            No tips yet. Press Fetch now to scan your sources.
          </p>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {tips.map(t => {
              const side = t.side === 'SELL' || t.side === 'SHORT' ? 'down' : 'up';
              const sideLabel = t.side === 'SELL' || t.side === 'SHORT' ? 'Short' : 'Long';
              return (
                <Card key={t.id} className="p-5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-lg font-bold text-slate-900 dark:text-slate-50">{t.symbol}</span>
                      <Badge tone={side === 'up' ? 'up' : 'down'}>{sideLabel}</Badge>
                      {t.timeframe && <span className="text-xs text-slate-400 dark:text-slate-500">{t.timeframe}</span>}
                    </div>
                    <span className="tnum text-sm font-semibold text-slate-700 dark:text-slate-200">{t.confidence}%</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t.rationale || t.text || 'No reason given yet.'}</p>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs text-slate-400 dark:text-slate-500">{t.source_type}</span>
                    <div className="flex items-center gap-1">
                      <button onClick={() => executeTip(t)} title="Send to AI to trade" className="rounded-lg p-2 text-slate-400 transition hover:bg-brand-50 hover:text-brand-600 dark:hover:bg-brand-500/10 dark:hover:text-brand-300"><Send className="h-4 w-4" /></button>
                      <button onClick={() => resolveTip(t.id, true)} title="Mark as a hit" className="rounded-lg p-2 text-slate-400 transition hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-emerald-500/10 dark:hover:text-emerald-300"><CheckCircle className="h-4 w-4" /></button>
                      <button onClick={() => resolveTip(t.id, false)} title="Mark as a miss" className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"><XCircle className="h-4 w-4" /></button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Add source modal */}
      <Modal open={showForm} onClose={() => setShowForm(false)} title="Add a source" description="Where should Jasper look for ideas?">
        <form onSubmit={addSource} className="space-y-4">
          <div>
            <label className="field-label">Type</label>
            <select value={newType} onChange={e => setNewType(e.target.value)} className="input">
              {SOURCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              <option value="telegram">Telegram</option>
            </select>
          </div>
          <div>
            <label className="field-label">Name</label>
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="e.g. My crypto news feed" className="input" required />
          </div>
          <div>
            <label className="field-label">Config (JSON)</label>
            <textarea value={newConfig} onChange={e => setNewConfig(e.target.value)} rows={3} className="input font-mono text-xs" placeholder='{ "url": "https://example.com/rss" }' />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button type="submit" disabled={adding}>{adding ? 'Adding...' : 'Add source'}</Button>
          </div>
        </form>
      </Modal>

      {/* Telegram modal */}
      <Modal open={tgOpen} onClose={() => setTgOpen(false)} title="Connect Telegram" description="Watch channels and get ideas from them.">
        {tgStep === 0 && (
          <div className="space-y-4">
            <div>
              <label className="field-label">Phone number (with country code)</label>
              <input value={tgPhone} onChange={e => setTgPhone(e.target.value)} placeholder="+2348012345678" className="input" />
            </div>
            <Button className="w-full" onClick={sendCode} disabled={tgBusy || !tgPhone}>{tgBusy ? 'Sending...' : 'Send code'}</Button>
          </div>
        )}
        {tgStep === 1 && (
          <div className="space-y-4">
            <div>
              <label className="field-label">Code from Telegram</label>
              <input value={tgCode} onChange={e => setTgCode(e.target.value)} placeholder="12345" className="input" />
            </div>
            <div>
              <label className="field-label">Two-factor password</label>
              <input value={tgPassword} onChange={e => setTgPassword(e.target.value)} placeholder="Only if you have 2FA enabled" className="input" />
            </div>
            <Button className="w-full" onClick={verifyCode} disabled={tgBusy || !tgCode}>{tgBusy ? 'Verifying...' : 'Verify and connect'}</Button>
          </div>
        )}
        {tgStep === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">Pick the channels Jasper should watch:</p>
            <div className="max-h-60 divide-y divide-slate-100 overflow-y-auto rounded-control border border-slate-200 dark:divide-slate-800 dark:border-slate-700">
              {tgChannels.length === 0 && <p className="px-4 py-3 text-sm text-slate-400">No channels found.</p>}
              {tgChannels.map(c => (
                <label key={c.id} className="flex cursor-pointer items-center gap-3 px-4 py-3 text-sm hover:bg-slate-50 dark:hover:bg-slate-800">
                  <input type="checkbox" checked={tgSelected.has(c.id)} onChange={() => togglePick(c.id)} className="accent-brand-600" />
                  <span className="flex-1 text-slate-800 dark:text-slate-100">{c.title || c.username || ('Channel ' + c.id)}</span>
                </label>
              ))}
            </div>
            <Button className="w-full" onClick={savePicks} disabled={tgBusy}>{tgBusy ? 'Saving...' : 'Watch selected channels'}</Button>
          </div>
        )}
      </Modal>
    </div>
  );
}
