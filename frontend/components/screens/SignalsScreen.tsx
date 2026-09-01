'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Plus, RefreshCw, CheckCircle, XCircle, Send, Radio, Wifi, MessageSquare, User, Trash2, Bot, Link2, Zap } from 'lucide-react';
import { Card, Button, Badge, Modal, EmptyState } from '@/components/ui';
import { Switch } from '@/components/ui/segmented';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { signalsAPI } from '@/lib/api-client';

import { API_URL } from '@/lib/constants';

interface Source { id: number; source_type: string; display_name: string; config?: Record<string, unknown>; is_active: boolean; last_fetched_at: string | null; }
interface Tip { id: number; slug: string; symbol: string; side: string; timeframe: string | null; confidence: number; rationale: string | null; source_type: string; text: string | null; url: string | null; created_at: string; executed: boolean; execution_status?: string; execution_detail?: string | null; }
interface Channel { id: number; username: string | null; title: string | null; type: string; }
interface SignalSettings { auto_execute_enabled: boolean; min_confidence: number; max_position_pct: number; }
interface SignalsStatus { telegram_connected: boolean; listener_active: boolean; watched_count: number; }

const SOURCE_TYPES = ['rss', 'reddit', 'stocktwits'];
const sourceIcon: Record<string, React.ReactNode> = {
  rss: <Wifi className="h-4 w-4" />, reddit: <MessageSquare className="h-4 w-4" />,
  stocktwits: <User className="h-4 w-4" />, telegram: <Send className="h-4 w-4" />,
  telegram_public: <Send className="h-4 w-4" />,
};

interface SignalsScreenProps {
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
}

export default function SignalsScreen({ triggerToast }: SignalsScreenProps) {
  const deviceId = getOrCreateDeviceId();
  const headers = { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' };

  const [sources, setSources] = useState<Source[]>([]);
  const [tips, setTips] = useState<Tip[]>([]);
  const [tgConnected, setTgConnected] = useState(false);
  const [status, setStatus] = useState<SignalsStatus | null>(null);
  const [settings, setSettings] = useState<SignalSettings>({ auto_execute_enabled: true, min_confidence: 0.6, max_position_pct: 0.05 });
  const [loading, setLoading] = useState(true);

  const [showForm, setShowForm] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newType, setNewType] = useState('rss');
  const [newName, setNewName] = useState('');
  const [rssUrls, setRssUrls] = useState('');
  const [redditSubs, setRedditSubs] = useState('');
  const [redditFilter, setRedditFilter] = useState('');
  const [stSymbols, setStSymbols] = useState('');

  const [tgOpen, setTgOpen] = useState(false);
  const [tgStep, setTgStep] = useState(0);
  const [tgPhone, setTgPhone] = useState('');
  const [tgCode, setTgCode] = useState('');
  const [tgPassword, setTgPassword] = useState('');
  const [tgChannels, setTgChannels] = useState<Channel[]>([]);
  const [tgSelected, setTgSelected] = useState<Set<number>>(new Set());
  const [tgBusy, setTgBusy] = useState(false);

  const [pubChannel, setPubChannel] = useState('');
  const [addingPub, setAddingPub] = useState(false);
  const [executingId, setExecutingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, tRes, aRes, stRes, setRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/signals/sources`, { headers }),
        fetch(`${API_URL}/api/v1/signals/tips`, { headers }),
        fetch(`${API_URL}/api/v1/signals/telegram/account`, { headers }),
        fetch(`${API_URL}/api/v1/signals/status`, { headers }),
        fetch(`${API_URL}/api/v1/signals/settings`, { headers }),
      ]);
      if (sRes.ok) setSources(await sRes.json());
      if (tRes.ok) setTips(await tRes.json());
      if (aRes.ok) { const a = await aRes.json(); setTgConnected(!!a.connected); }
      if (stRes.ok) setStatus(await stRes.json());
      if (setRes.ok) setSettings(await setRes.json());
    } catch {
      /* ignore */
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateSettings = async (patch: Partial<SignalSettings>) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    const res = await signalsAPI.saveSignalSettings(deviceId, {
      auto_execute_enabled: next.auto_execute_enabled,
      min_confidence: next.min_confidence,
      max_position_pct: next.max_position_pct,
    });
    if (res.error) triggerToast('error', 'Could not save', res.error);
  };

  const addSource = async (e: React.FormEvent) => {
    e.preventDefault(); setAdding(true);
    let cfg: Record<string, unknown> = {};
    if (newType === 'rss') {
      const urls = rssUrls.split('\n').map(s => s.trim()).filter(Boolean);
      if (!urls.length) { triggerToast('error', 'URL required', 'Paste at least one RSS feed URL.'); setAdding(false); return; }
      cfg = { urls };
    } else if (newType === 'reddit') {
      const subs = redditSubs.split(',').map(s => s.trim()).filter(Boolean);
      if (!subs.length) { triggerToast('error', 'Subreddits required', 'Enter at least one subreddit name.'); setAdding(false); return; }
      cfg = { subreddits: subs };
      if (redditFilter.trim()) cfg.filter_keyword = redditFilter.trim();
    } else if (newType === 'stocktwits') {
      const syms = stSymbols.split(',').map(s => s.trim()).filter(Boolean);
      if (!syms.length) { triggerToast('error', 'Symbols required', 'Enter at least one StockTwits symbol.'); setAdding(false); return; }
      cfg = { symbols: syms };
    }
    const r = await fetch(`${API_URL}/api/v1/signals/sources`, { method: 'POST', headers, body: JSON.stringify({ source_type: newType, display_name: newName || newType, config: cfg }) });
    if (r.ok) {
      const created = await r.json();
      await fetch(`${API_URL}/api/v1/signals/follow`, { method: 'POST', headers, body: JSON.stringify({ source_id: created.id }) });
      triggerToast('success', 'Source added', 'The AI can now look here for ideas.');
      setShowForm(false); setNewName(''); setRssUrls(''); setRedditSubs(''); setRedditFilter(''); setStSymbols(''); load();
    } else triggerToast('error', 'Could not add', 'Please check the details and try again.');
    setAdding(false);
  };

  const addPublicChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    const username = pubChannel.trim();
    if (!username) return;
    setAddingPub(true);
    try {
      const res = await signalsAPI.createSource(deviceId, {
        source_type: 'telegram_public',
        display_name: username.replace(/^@/, ''),
        config: { username },
      });
      if (res.error) {
        triggerToast('error', 'Could not watch channel', res.error);
        return;
      }
      await signalsAPI.followSource(deviceId, res.data.id);
      triggerToast('success', 'Channel watched', 'The AI now watches this public channel for ideas.');
      setPubChannel('');
      load();
    } finally { setAddingPub(false); }
  };

  const deleteSource = async (s: Source) => {
    const res = await signalsAPI.deleteSource(deviceId, s.id);
    if (res.error) triggerToast('error', 'Could not remove', res.error);
    else { triggerToast('success', 'Removed', `${s.display_name} is no longer watched.`); load(); }
  };

  const fetchNow = async () => {
    triggerToast('info', 'Fetching ideas', 'Scanning your sources for tradeable tips...');
    try {
      const r = await fetch(`${API_URL}/api/v1/signals/fetch`, { method: 'POST', headers });
      if (r.ok) { triggerToast('success', 'Done', 'New tips are ready.'); load(); }
    } catch {
      /* ignore */
    }
  };

  const resolveTip = async (id: number, hit: boolean) => {
    try {
      await fetch(`${API_URL}/api/v1/signals/tips/${id}/resolve`, { method: 'POST', headers, body: JSON.stringify({ hit }) });
      triggerToast(hit ? 'success' : 'info', hit ? 'Marked as a hit' : 'Marked as a miss', 'Thanks for the feedback.');
      load();
    } catch {
      /* ignore */
    }
  };

  const executeTip = async (t: Tip) => {
    setExecutingId(t.id);
    const res = await signalsAPI.executeTip(deviceId, t.id, {});
    setExecutingId(null);
    if (res.error) triggerToast('error', 'Could not execute', res.error);
    else {
      const mode = (res.data && res.data.mode) || '';
      triggerToast('success', 'Trade placed', `Executed ${(res.data && res.data.side || '').toUpperCase()} ${t.symbol}${mode ? ` (${mode})` : ''}.`);
      load();
    }
  };

  const sendCode = async () => {
    setTgBusy(true);
    try {
      const res = await signalsAPI.telegramStart(deviceId, tgPhone);
      if (res.error) triggerToast('error', 'Could not send code', res.error);
      else setTgStep(1);
    } finally { setTgBusy(false); }
  };

  const verifyCode = async () => {
    setTgBusy(true);
    try {
      const res = await signalsAPI.telegramComplete(deviceId, tgPhone, tgCode, tgPassword || undefined);
      if (res.error) { triggerToast('error', 'Could not verify', res.error); return; }
      const ch = await signalsAPI.telegramChannels(deviceId, {});
      setTgChannels(ch.error ? [] : (ch.data && ch.data.channels) || []);
      setTgStep(2);
    } finally { setTgBusy(false); }
  };

  const savePicks = async () => {
    setTgBusy(true);
    try {
      const picks = tgChannels.filter(c => tgSelected.has(c.id)).map(c => ({ channel_id: c.id, title: c.title || c.username || ('Channel ' + c.id), username: c.username || null }));
      if (picks.length === 0) { triggerToast('warning', 'Nothing selected', 'Pick at least one channel to watch.'); return; }
      const res = await signalsAPI.telegramCreateSources(deviceId, picks);
      if (res.error) { triggerToast('error', 'Could not save', res.error); return; }
      triggerToast('success', 'Connected', `${picks.length} channel${picks.length === 1 ? '' : 's'} are now watched.`);
      setTgOpen(false); setTgStep(0); setTgPhone(''); setTgCode(''); setTgPassword(''); setTgSelected(new Set());
      load();
    } finally { setTgBusy(false); }
  };

  const togglePick = (id: number) => setTgSelected(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const disconnectTelegram = async () => {
    const res = await signalsAPI.telegramDisconnect(deviceId);
    if (res.error) triggerToast('error', 'Could not disconnect', res.error);
    else { triggerToast('success', 'Disconnected', 'Telegram is no longer connected.'); setTgConnected(false); load(); }
  };

  const tgSources = sources.filter(s => s.source_type === 'telegram' || s.source_type === 'telegram_public');
  const execBadge = (t: Tip) => {
    const st = t.execution_status || 'pending';
    if (st === 'executed') return <Badge tone="up">Executed</Badge>;
    if (st === 'failed') return <Badge tone="down">Failed</Badge>;
    if (st === 'skipped') return <Badge tone="warning">Skipped</Badge>;
    return <Badge tone="neutral">Pending</Badge>;
  };

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Signals</p>
        <h1 className="page-title mt-1">Places Jasper looks for ideas</h1>
        <p className="mt-2 max-w-xl muted-caption">Plug in news feeds, Reddit, StockTwits or Telegram channels and get ranked, auto-traded tips from the AI.</p>
      </div>

      <section>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50" data-onboarding="signals-sources">My sources</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => { setNewType('rss'); setShowForm(true); }}><Plus className="h-4 w-4" /> RSS</Button>
            <Button variant="secondary" size="sm" onClick={() => { setNewType('reddit'); setShowForm(true); }}><Plus className="h-4 w-4" /> Reddit</Button>
            <Button variant="secondary" size="sm" onClick={() => { setNewType('stocktwits'); setShowForm(true); }}><Plus className="h-4 w-4" /> StockTwits</Button>
            <Button size="sm" onClick={fetchNow} disabled={loading}><RefreshCw className="h-4 w-4" /> Fetch now</Button>
          </div>
        </div>

        {loading ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map(i => <div key={i} className="skeleton h-28 w-full" />)}</div>
        ) : sources.length === 0 ? (
          <div className="mt-4">
            <EmptyState icon={<Radio className="h-6 w-6" />} title="No sources yet" description="Add a feed, subreddit, StockTwits list or a Telegram channel so the AI has somewhere to look for ideas." action={<Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4" /> Add your first source</Button>} />
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
                <div className="mt-3 flex items-center justify-between gap-2">
                  <p className="text-xs text-slate-500 dark:text-slate-400">{s.last_fetched_at ? `Last checked ${new Date(s.last_fetched_at).toLocaleString()}` : 'Not checked yet'}</p>
                  <button onClick={() => deleteSource(s)} title={`Remove ${s.display_name}`} aria-label={`Remove ${s.display_name}`} className="rounded-lg p-1.5 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"><Trash2 className="h-4 w-4" /></button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* How to set up - collapsible */}
      <details className="rounded-card border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-700 dark:bg-slate-900/40" data-onboarding="signals-howto">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700 dark:text-slate-200">How to set up your sources</summary>
        <div className="mt-3 space-y-3 text-xs text-slate-500 dark:text-slate-400">
          <div>
            <p className="font-medium text-slate-700 dark:text-slate-200">RSS feeds</p>
            <p>Paste any RSS feed URL. Jasper reads headlines and extracts trading signals. One URL per line.</p>
          </div>
          <div>
            <p className="font-medium text-slate-700 dark:text-slate-200">Reddit</p>
            <p>Add subreddits where traders share ideas (comma-separated). Jasper reads posts for sentiment. Add a filter keyword to narrow results.</p>
          </div>
          <div>
            <p className="font-medium text-slate-700 dark:text-slate-200">StockTwits</p>
            <p>Enter symbols (comma-separated). Jasper reads trader commentary and bullish/bearish tags for each symbol.</p>
          </div>
        </div>
      </details>

      <section>
        <div className="rounded-card border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-300"><Send className="h-4 w-4" /></span>
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Telegram signals</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {tgConnected
                    ? `Connected${status && status.listener_active ? ' · live listener on' : ' · polling only'}${tgSources.length ? ` · ${tgSources.length} watched` : ''}`
                    : 'Not connected yet'}
                </p>
              </div>
            </div>
            {tgConnected ? (
              <Button variant="ghost" size="sm" onClick={disconnectTelegram}>Disconnect</Button>
            ) : (
              <Button size="sm" onClick={() => setTgOpen(true)}><Send className="h-4 w-4" /> Connect Telegram</Button>
            )}
          </div>

          <form onSubmit={addPublicChannel} className="mt-4 flex flex-wrap items-center gap-2">
            <Link2 className="h-4 w-4 text-slate-400" />
            <input id="pub-channel" value={pubChannel} onChange={e => setPubChannel(e.target.value)} placeholder="@channel or https://t.me/channel (no login needed)" className="input min-w-[240px] flex-1" />
            <Button type="submit" variant="secondary" disabled={addingPub || !pubChannel.trim()}>{addingPub ? 'Watching...' : 'Watch channel'}</Button>
          </form>
        </div>
      </section>

      <section>
        <div className="rounded-card border border-slate-200 p-4 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300"><Bot className="h-4 w-4" /></span>
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Hands-free auto-trading</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Every tip that clears its bar is traded automatically - paper first, live once you connect a broker and switch to Live.</p>
            </div>
          </div>

          <div className="mt-4 space-y-5">
            <Switch
              checked={settings.auto_execute_enabled}
              onChange={v => updateSettings({ auto_execute_enabled: v })}
              label="Auto-execute parsed signals"
              description="Trade every signal that passes the checks below - no tapping needed."
            />
            <label className="block">
              <span className="field-label">Minimum confidence</span>
              <div className="mt-1.5 flex items-center gap-3">
                <input type="range" min={40} max={95} step={5} value={Math.round(settings.min_confidence * 100)} onChange={e => updateSettings({ min_confidence: Number(e.target.value) / 100 })} className="w-full accent-brand-600" />
                <span className="tnum w-12 text-right text-sm font-semibold text-slate-700 dark:text-slate-200">{Math.round(settings.min_confidence * 100)}%</span>
              </div>
            </label>
            <label className="block" data-onboarding="position-size">
              <span className="field-label">Position size per trade</span>
              <div className="mt-1.5 flex items-center gap-3">
                <input type="range" min={1} max={25} step={1} value={Math.round(settings.max_position_pct * 100)} onChange={e => updateSettings({ max_position_pct: Number(e.target.value) / 100 })} className="w-full accent-brand-600" />
                <span className="tnum w-12 text-right text-sm font-semibold text-slate-700 dark:text-slate-200">{Math.round(settings.max_position_pct * 100)}%</span>
              </div>
              <span className="mt-1.5 block text-xs text-slate-400 dark:text-slate-500">% of portfolio equity, capped by your Trading Caps. Start small in paper and tune this to your taste as you go.</span>
            </label>
            <div className="flex items-center gap-2 rounded-control bg-slate-100 px-3 py-2 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <Zap className="h-3.5 w-3.5 shrink-0 text-brand-500" />
              <span>Trades land in your paper account by default. They only go live when trading mode is Live and a broker is connected.</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">Ranked tips</h2>
        {tips.length === 0 ? (
          <p className="mt-4 rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
            No tips yet. Press Fetch now to scan your sources - or connect Telegram and they will arrive on their own.
          </p>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {tips.map(t => {
              const upper = (t.side || '').toUpperCase();
              const isDown = upper === 'SELL' || upper === 'SHORT';
              const sideLabel = isDown ? 'Short' : 'Long';
              return (
                <Card key={t.id} className="p-5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-lg font-bold text-slate-900 dark:text-slate-50">{t.symbol}</span>
                      <Badge tone={isDown ? 'down' : 'up'}>{sideLabel}</Badge>
                      {t.timeframe && <span className="text-xs text-slate-400 dark:text-slate-500">{t.timeframe}</span>}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="tnum text-sm font-semibold text-slate-700 dark:text-slate-200">{Math.round((t.confidence || 0) * 100)}%</span>
                      {execBadge(t)}
                    </div>
                  </div>
                  <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t.rationale || t.text || 'No reason given yet.'}</p>
                  {t.execution_detail && <p className="mt-2 rounded-control bg-slate-100 px-3 py-1.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">{t.execution_detail}</p>}
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs text-slate-400 dark:text-slate-500">{t.source_type}</span>
                    <div className="flex items-center gap-1">
                      {t.execution_status !== 'executed' && (
                        <button onClick={() => executeTip(t)} disabled={executingId === t.id} title="Execute now (paper or live)" aria-label="Execute now" className="rounded-lg p-2 text-slate-400 transition hover:bg-brand-50 hover:text-brand-600 disabled:opacity-50 dark:hover:bg-brand-500/10 dark:hover:text-brand-300"><Zap className="h-4 w-4" /></button>
                      )}
                      <button onClick={() => resolveTip(t.id, true)} title="Mark as a hit" aria-label="Mark as a hit" className="rounded-lg p-2 text-slate-400 transition hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-emerald-500/10 dark:hover:text-emerald-300"><CheckCircle className="h-4 w-4" /></button>
                      <button onClick={() => resolveTip(t.id, false)} title="Mark as a miss" aria-label="Mark as a miss" className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"><XCircle className="h-4 w-4" /></button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <Modal open={showForm} onClose={() => setShowForm(false)} title="Add a source" description="Where should Jasper look for ideas?">
        <form onSubmit={addSource} className="space-y-4">
          <div>
            <label htmlFor="sig-type" className="field-label">Type</label>
            <select id="sig-type" value={newType} onChange={e => setNewType(e.target.value)} className="input" data-onboarding="signals-add-type">
              {SOURCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="sig-name" className="field-label">Name</label>
            <input id="sig-name" value={newName} onChange={e => setNewName(e.target.value)} placeholder={`e.g. My ${newType} source`} className="input" required />
          </div>
          {newType === 'rss' && (
            <div>
              <label htmlFor="rss-urls" className="field-label">Feed URL(s)</label>
              <textarea id="rss-urls" value={rssUrls} onChange={e => setRssUrls(e.target.value)} rows={3} className="input font-mono text-xs" placeholder="Paste RSS feed URLs, one per line" />
              <p className="mt-1 text-xs text-slate-400">One URL per line.</p>
            </div>
          )}
          {newType === 'reddit' && (
            <>
              <div>
                <label htmlFor="reddit-subs" className="field-label">Subreddits</label>
                <input id="reddit-subs" value={redditSubs} onChange={e => setRedditSubs(e.target.value)} placeholder="wallstreetbets,stocks,btc" className="input" />
                <p className="mt-1 text-xs text-slate-400">Comma-separated subreddit names.</p>
              </div>
              <div>
                <label htmlFor="reddit-filter" className="field-label">Filter keyword (optional)</label>
                <input id="reddit-filter" value={redditFilter} onChange={e => setRedditFilter(e.target.value)} placeholder="e.g. earnings, breakout" className="input" />
              </div>
            </>
          )}
          {newType === 'stocktwits' && (
            <div>
              <label htmlFor="st-symbols" className="field-label">Symbols</label>
              <input id="st-symbols" value={stSymbols} onChange={e => setStSymbols(e.target.value)} placeholder="AAPL,TSLA,BTC.X" className="input" />
              <p className="mt-1 text-xs text-slate-400">Comma-separated StockTwits symbols.</p>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button type="submit" disabled={adding}>{adding ? 'Adding...' : 'Add source'}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={tgOpen} onClose={() => setTgOpen(false)} title="Connect Telegram" description="Watch channels and get ideas from them.">
        {tgStep === 0 && (
          <div className="space-y-4">
            <div>
              <label htmlFor="tg-phone" className="field-label">Phone number (with country code)</label>
              <input id="tg-phone" value={tgPhone} onChange={e => setTgPhone(e.target.value)} placeholder="+2348012345678" className="input" />
            </div>
            <Button className="w-full" onClick={sendCode} disabled={tgBusy || !tgPhone}>{tgBusy ? 'Sending...' : 'Send code'}</Button>
          </div>
        )}
        {tgStep === 1 && (
          <div className="space-y-4">
            <div>
              <label htmlFor="tg-code" className="field-label">Code from Telegram</label>
              <input id="tg-code" value={tgCode} onChange={e => setTgCode(e.target.value)} placeholder="12345" className="input" />
            </div>
            <div>
              <label htmlFor="tg-password" className="field-label">Two-factor password</label>
              <input id="tg-password" value={tgPassword} onChange={e => setTgPassword(e.target.value)} placeholder="Only if you have 2FA enabled" className="input" />
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
