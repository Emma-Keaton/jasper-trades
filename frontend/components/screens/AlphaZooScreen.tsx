'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Compass, Search, Plus, Check } from 'lucide-react';
import { Card, Button, Modal, EmptyState } from '@/components/ui';
import { apiFetch } from '@/lib/api-client';

interface Factor {
  id: string;
  name: string;
  category: string;
  difficulty: string;
  win: string;
  sharpe: string;
  drawdown: string;
  avgReturn: string;
  description: string;
  zoo: string;
  theme: string[];
  has_compute: boolean;
}

interface AlphaZooScreenProps {
  addAlphaFactor: (factor: { id: string; name: string }) => void;
  triggerToast: (type: 'success' | 'error' | 'info' | 'warning', title: string, message: string) => void;
}

const ZOO_COLORS: Record<string, string> = {
  academic: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  alpha101: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  gtja191: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  qlib158: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
};

const ZOO_KEYS = ['academic', 'alpha101', 'gtja191', 'qlib158'] as const;
const ZOO_LABELS: Record<string, string> = {
  academic: 'Academic',
  alpha101: 'Alpha101',
  gtja191: 'GTJA191',
  qlib158: 'QLib158',
};

const PAGE_SIZE = 30;

export default function AlphaZooScreen({ addAlphaFactor, triggerToast }: AlphaZooScreenProps) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [zoo, setZoo] = useState('all');
  const [loading, setLoading] = useState(true);
  const [factors, setFactors] = useState<Factor[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [preview, setPreview] = useState<Factor | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queryRef = useRef(query);
  queryRef.current = query;

  const fetchFactors = useCallback(async (searchQuery: string) => {
    try {
      setLoading(true);
      const searchParam = searchQuery ? `&search=${encodeURIComponent(searchQuery)}` : '';
      const [fRes, cRes] = await Promise.all([
        apiFetch(`/api/v1/alpha-factors?limit=500${searchParam}`),
        apiFetch(`/api/v1/alpha-factors/categories`),
      ]);
      if (fRes.ok) {
        const data = await fRes.json();
        setFactors(
          (data.factors || []).map((f: any) => ({
            id: f.id,
            name: f.name,
            category: f.category,
            difficulty: f.difficulty || 'Intermediate',
            win: `${f.win_rate ?? 0}%`,
            sharpe: String(f.sharpe ?? 0),
            drawdown: `${f.max_drawdown ?? 0}%`,
            avgReturn: `${f.avg_return ?? 0}%`,
            description: f.description || f.description_blurb || '',
            zoo: f.zoo || 'academic',
            theme: Array.isArray(f.theme) ? f.theme : [],
            has_compute: Boolean(f.has_compute),
          })),
        );
      }
      if (cRes.ok) {
        const d = await cRes.json();
        if (d.categories) setCategories(d.categories);
      }
    } catch {
      triggerToast('error', 'Load failed', 'Could not load alpha factors.');
    } finally {
      setLoading(false);
    }
  }, [triggerToast]);

  useEffect(() => {
    fetchFactors('');
  }, [fetchFactors]);

  const handleQueryChange = (value: string) => {
    setQuery(value);
    setVisibleCount(PAGE_SIZE);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchFactors(value);
    }, 350);
  };

  const handleCategoryChange = (c: string) => {
    setCategory(c);
    setVisibleCount(PAGE_SIZE);
  };

  const handleZooChange = (z: string) => {
    setZoo(z);
    setVisibleCount(PAGE_SIZE);
  };

  const sorted = [...factors]
    .filter(f => category === 'all' || f.category === category)
    .filter(f => zoo === 'all' || f.zoo === zoo)
    .sort((a, b) => a.name.localeCompare(b.name));

  const clientFiltered = query
    ? sorted.filter(
        f =>
          f.name.toLowerCase().includes(query.toLowerCase()) ||
          f.category.toLowerCase().includes(query.toLowerCase()) ||
          f.description.toLowerCase().includes(query.toLowerCase()),
      )
    : sorted;

  const visible = clientFiltered.slice(0, visibleCount);
  const hasMore = visibleCount < clientFiltered.length;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow">Research</p>
        <h1 className="page-title mt-1">Alpha Factor Zoo</h1>
        <p className="mt-2 max-w-xl muted-caption">
          Browse quantitative factors, understand what they do, and add them to a backtest strategy.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={e => handleQueryChange(e.target.value)}
              placeholder="Search factors..."
              className="input pl-9"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleCategoryChange('all')}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition ${
              category === 'all'
                ? 'bg-brand-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
          >
            All
          </button>
          {categories.map(c => (
            <button
              key={c}
              onClick={() => handleCategoryChange(c)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition ${
                category === c
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleZooChange('all')}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              zoo === 'all'
                ? 'bg-brand-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
          >
            All Sources
          </button>
          {ZOO_KEYS.map(z => (
            <button
              key={z}
              onClick={() => handleZooChange(z)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                zoo === z
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              {ZOO_LABELS[z]}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map(i => (
            <div key={i} className="skeleton h-40 w-full" />
          ))}
        </div>
      ) : clientFiltered.length === 0 ? (
        <EmptyState
          icon={<Compass className="h-6 w-6" />}
          title="No factors found"
          description="Try adjusting your search or filters."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map(f => (
              <Card key={f.id} hover onClick={() => setPreview(f)} className="flex flex-col p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-display font-bold text-slate-900 dark:text-slate-50 truncate">{f.name}</p>
                    <p className="text-xs capitalize text-slate-400 dark:text-slate-500">
                      {f.category} · {f.difficulty}
                    </p>
                  </div>
                  <button
                    onClick={e => {
                      e.stopPropagation();
                      addAlphaFactor({ id: f.id, name: f.name });
                    }}
                    className="rounded-full p-2 text-slate-400 transition hover:bg-brand-50 hover:text-brand-600 dark:hover:bg-brand-500/10 dark:hover:text-brand-300"
                    title="Add to strategy"
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>

                <div className="mt-2 flex flex-wrap gap-1">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${ZOO_COLORS[f.zoo] || ZOO_COLORS.academic}`}>
                    {ZOO_LABELS[f.zoo] || f.zoo}
                  </span>
                  {f.theme.slice(0, 3).map(t => (
                    <span
                      key={t}
                      className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                    >
                      {t}
                    </span>
                  ))}
                </div>

                <div className="mt-auto grid grid-cols-3 gap-2 pt-3 text-center">
                  <div className="rounded-control bg-slate-50 p-2 dark:bg-slate-800/60">
                    <p className="text-[10px] uppercase text-slate-400">Win</p>
                    <p className="tnum text-sm font-bold text-emerald-600 dark:text-emerald-400">{f.win}</p>
                  </div>
                  <div className="rounded-control bg-slate-50 p-2 dark:bg-slate-800/60">
                    <p className="text-[10px] uppercase text-slate-400">Sharpe</p>
                    <p className="tnum text-sm font-bold text-brand-600 dark:text-brand-300">{f.sharpe}</p>
                  </div>
                  <div className="rounded-control bg-slate-50 p-2 dark:bg-slate-800/60">
                    <p className="text-[10px] uppercase text-slate-400">Drawdown</p>
                    <p className="tnum text-sm font-bold text-rose-600 dark:text-rose-400">{f.drawdown}</p>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {hasMore && (
            <div className="flex justify-center pt-2">
              <Button variant="secondary" onClick={() => setVisibleCount(prev => prev + PAGE_SIZE)}>
                Load more ({clientFiltered.length - visibleCount} remaining)
              </Button>
            </div>
          )}
        </>
      )}

      <Modal
        open={!!preview}
        onClose={() => setPreview(null)}
        size="lg"
        title={preview?.name}
        description={preview ? `${preview.category} · ${preview.difficulty}` : ''}
      >
        {preview && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1">
              <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${ZOO_COLORS[preview.zoo] || ZOO_COLORS.academic}`}>
                {ZOO_LABELS[preview.zoo] || preview.zoo}
              </span>
              {preview.theme.map(t => (
                <span
                  key={t}
                  className="inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                >
                  {t}
                </span>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-xs text-slate-400">Win rate</p>
                <p className="tnum text-lg font-bold text-emerald-600 dark:text-emerald-400">{preview.win}</p>
              </div>
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-xs text-slate-400">Sharpe</p>
                <p className="tnum text-lg font-bold text-brand-600 dark:text-brand-300">{preview.sharpe}</p>
              </div>
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-xs text-slate-400">Avg return</p>
                <p className="tnum text-lg font-bold text-slate-900 dark:text-slate-100">{preview.avgReturn}</p>
              </div>
              <div className="rounded-control bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-xs text-slate-400">Max drawdown</p>
                <p className="tnum text-lg font-bold text-rose-600 dark:text-rose-400">{preview.drawdown}</p>
              </div>
            </div>

            <div>
              <p className="field-label">What it does</p>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {preview.description || 'A quantitative factor used to generate trading signals.'}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button variant="secondary" onClick={() => setPreview(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  addAlphaFactor({ id: preview.id, name: preview.name });
                  setPreview(null);
                }}
              >
                <Check className="h-4 w-4" /> Add to strategy
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
