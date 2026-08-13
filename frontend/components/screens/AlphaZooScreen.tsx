'use client';

import React, { useState, useEffect } from 'react';
import { Compass, Search, Plus, Check } from 'lucide-react';
import { Card, Button, Modal, EmptyState } from '@/components/ui';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Factor { id: string; name: string; category: string; difficulty: string; win: string; sharpe: string; drawdown: string; avgReturn: string; description: string; }

interface AlphaZooScreenProps {
  addAlphaFactor: (factorName: string) => void;
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
}

export default function AlphaZooScreen({ addAlphaFactor, triggerToast }: AlphaZooScreenProps) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [loading, setLoading] = useState(true);
  const [factors, setFactors] = useState<Factor[]>([]);
  const [categories, setCategories] = useState<string[]>(['Momentum', 'Mean-Reversion', 'Volume', 'Volatility']);
  const [preview, setPreview] = useState<Factor | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [fRes, cRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/alpha-factors?limit=50`),
          fetch(`${API_URL}/api/v1/alpha-factors/categories`),
        ]);
        if (fRes.ok) {
          const data = await fRes.json();
          setFactors((data.factors || []).map((f: any) => ({
            id: f.id, name: f.name, category: f.category, difficulty: f.difficulty || 'Intermediate',
            win: `${f.win_rate ?? 0}%`, sharpe: String(f.sharpe ?? 0), drawdown: `${f.max_drawdown ?? 0}%`,
            avgReturn: `${f.avg_return ?? 0}%`, description: f.description || f.description_blurb || '',
          })));
        }
        if (cRes.ok) { const d = await cRes.json(); if (d.categories) setCategories(d.categories); }
      } catch { triggerToast('error', 'Load failed', 'Could not load alpha factors.'); }
      finally { setLoading(false); }
    })();
  }, [triggerToast]);

  const filtered = factors.filter(f =>
    (category === 'all' || f.category === category) &&
    (f.name.toLowerCase().includes(query.toLowerCase()) || f.category.toLowerCase().includes(query.toLowerCase()))
  );

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Research</p>
        <h1 className="page-title mt-1">Alpha Factor Zoo</h1>
        <p className="mt-2 max-w-xl muted-caption">Browse quantitative factors, understand what they do, and add them to a backtest strategy.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search factors..." className="input pl-9" />
        </div>
        <div className="flex flex-wrap gap-2">
          {['all', ...categories].slice(0, 6).map(c => (
            <button key={c} onClick={() => setCategory(c)} className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition ${category === c ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'}`}>{c}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0,1,2,3,4,5].map(i => <div key={i} className="skeleton h-40 w-full" />)}</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={<Compass className="h-6 w-6" />} title="No factors found" description="Try a different search or category." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map(f => (
            <Card key={f.id} hover onClick={() => setPreview(f)} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-display font-bold text-slate-900 dark:text-slate-50">{f.name}</p>
                  <p className="text-xs capitalize text-slate-400 dark:text-slate-500">{f.category} · {f.difficulty}</p>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); addAlphaFactor(f.name); }}
                  className="rounded-full p-2 text-slate-400 transition hover:bg-brand-50 hover:text-brand-600 dark:hover:bg-brand-500/10 dark:hover:text-brand-300"
                  title="Add to strategy"
                ><Plus className="h-4 w-4" /></button>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-control bg-slate-50 p-2 dark:bg-slate-800/60"><p className="text-[10px] uppercase text-slate-400">Win</p><p className="tnum text-sm font-bold text-emerald-600 dark:text-emerald-400">{f.win}</p></div>
                <div className="rounded-control bg-slate-50 p-2 dark:bg-slate-800/60"><p className="text-[10px] uppercase text-slate-400">Sharpe</p><p className="tnum text-sm font-bold text-brand-600 dark:text-brand-300">{f.sharpe}</p></div>
                <div className="rounded-control bg-slate-50 p-2 dark:bg-slate-800/60"><p className="text-[10px] uppercase text-slate-400">Drawdown</p><p className="tnum text-sm font-bold text-rose-600 dark:text-rose-400">{f.drawdown}</p></div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!preview} onClose={() => setPreview(null)} size="lg" title={preview?.name} description={preview ? `${preview.category} · ${preview.difficulty}` : ''}>
        {preview && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60"><p className="text-xs text-slate-400">Win rate</p><p className="tnum text-lg font-bold text-emerald-600 dark:text-emerald-400">{preview.win}</p></div>
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60"><p className="text-xs text-slate-400">Sharpe</p><p className="tnum text-lg font-bold text-brand-600 dark:text-brand-300">{preview.sharpe}</p></div>
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60"><p className="text-xs text-slate-400">Avg return</p><p className="tnum text-lg font-bold text-slate-900 dark:text-slate-100">{preview.avgReturn}</p></div>
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60"><p className="text-xs text-slate-400">Max drawdown</p><p className="tnum text-lg font-bold text-rose-600 dark:text-rose-400">{preview.drawdown}</p></div>
            </div>
            <div>
              <p className="field-label">What it does</p>
              <p className="text-sm text-slate-600 dark:text-slate-300">{preview.description || 'A quantitative factor used to generate trading signals.'}</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button variant="secondary" onClick={() => setPreview(null)}>Cancel</Button>
              <Button onClick={() => { addAlphaFactor(preview.name); setPreview(null); }}><Check className="h-4 w-4" /> Add to strategy</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
