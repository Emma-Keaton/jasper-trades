'use client';

import { useEffect, useState } from 'react';
import { BrainCircuit, CheckCircle2, Loader2, RefreshCw, Zap, AlertTriangle } from 'lucide-react';
import { API_URL } from '@/lib/constants';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { apiFetch } from '@/lib/api-client';

type ProviderId = 'groq' | 'gemini' | 'nvidia';
type TaskId = 'director' | 'quant' | 'risk' | 'execution' | 'chat';

interface ProviderMeta {
  name: string;
  keys_url: string;
  docs: string;
  key_hint: string;
}

interface TaskMeta {
  label: string;
  needs: string;
  recommended: Record<string, [string, string]>;
  default: { provider: ProviderId; model: string };
}

interface ProvidersResponse {
  providers: Record<ProviderId, ProviderMeta>;
  tasks: Record<TaskId, TaskMeta>;
  configured: Record<ProviderId, boolean>;
  selections: Record<string, { provider: ProviderId; model: string }>;
  resolved: Record<string, { provider: ProviderId; model: string; source: string }>;
}

interface TestKeyResult {
  valid: boolean;
  latency_ms?: number;
  models: string[];
  recommended?: string[];
  error?: string;
}

const inputCls =
  'w-full rounded-control border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100';

export default function LLMProvidersPanel({
  triggerToast,
}: {
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
}) {
  const deviceId = getOrCreateDeviceId();
  const [data, setData] = useState<ProvidersResponse | null>(null);
  const [keys, setKeys] = useState<Record<string, string>>({ groq: '', gemini: '', nvidia: '' });
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [testResult, setTestResult] = useState<Record<string, TestKeyResult | null>>({});
  const [models, setModels] = useState<Record<string, string[]>>({ groq: [], gemini: [], nvidia: [] });
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [picks, setPicks] = useState<Record<string, { provider: ProviderId; model: string }>>({});

  const load = async () => {
    try {
      const res = await apiFetch(`${API_URL}/api/v1/llm/providers`, { headers: { 'X-Device-ID': deviceId } });
      if (res.ok) {
        const d: ProvidersResponse = await res.json();
        setData(d);
        setPicks(d.resolved as Record<string, { provider: ProviderId; model: string }>);
      }
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId]);

  const testKey = async (provider: ProviderId) => {
    const key = keys[provider].trim();
    if (!key) {
      triggerToast('error', 'Key required', `Paste a ${data?.providers[provider]?.name ?? provider} API key first.`);
      return;
    }
    setTesting((t) => ({ ...t, [provider]: true }));
    try {
      const res = await apiFetch(`${API_URL}/api/v1/llm/test-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ provider, key }),
      });
      const result: TestKeyResult = await res.json();
      setTestResult((r) => ({ ...r, [provider]: result }));
      if (result.valid) {
        setModels((m) => ({ ...m, [provider]: result.models }));
        triggerToast('success', 'Key works', `${result.models.length} models authorized · ${result.latency_ms}ms`);
      } else {
        triggerToast('error', 'Key rejected', result.error || 'Provider rejected the key');
      }
    } catch {
      triggerToast('error', 'Test failed', 'Could not reach the provider.');
    } finally {
      setTesting((t) => ({ ...t, [provider]: false }));
    }
  };

  const saveKey = async (provider: ProviderId) => {
    const key = keys[provider].trim();
    if (!key) return;
    setSaving((s) => ({ ...s, [provider]: true }));
    try {
      const res = await apiFetch(`${API_URL}/api/v1/llm/key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ provider, key }),
      });
      if (res.ok) {
        triggerToast('success', 'Key saved', `${data?.providers[provider]?.name ?? provider} key stored encrypted for this device.`);
        await load();
      } else {
        triggerToast('error', 'Save failed', 'Could not save the key.');
      }
    } catch {
      triggerToast('error', 'Save failed', 'Could not save the key.');
    } finally {
      setSaving((s) => ({ ...s, [provider]: false }));
    }
  };

  const loadModels = async (provider: ProviderId) => {
    try {
      const res = await apiFetch(`${API_URL}/api/v1/llm/models?provider=${provider}`, { headers: { 'X-Device-ID': deviceId } });
      if (res.ok) {
        const d: TestKeyResult = await res.json();
        if (d.valid) setModels((m) => ({ ...m, [provider]: d.models }));
      }
    } catch {
      /* ignore */
    }
  };

  const savePick = async (task: TaskId, provider: ProviderId, model: string) => {
    setPicks((p) => ({ ...p, [task]: { provider, model } }));
    try {
      await apiFetch(`${API_URL}/api/v1/llm/selection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
        body: JSON.stringify({ task, provider, model }),
      });
    } catch {
      /* non-fatal */
    }
  };

  if (!data) return <p className="text-xs text-slate-400">Loading providers…</p>;

  const providerIds = Object.keys(data.providers) as ProviderId[];
  const taskIds = Object.keys(data.tasks) as TaskId[];

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-control bg-brand-50 p-3 text-xs text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
        <Zap className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Providers run <strong>side by side</strong> — plug a key for any of them and its models handle agentic
          tasks. Defaults are pre-selected and work even if you never pick a model; recommended models are listed
          first so speed-critical tasks (execution, risk) never get a slow model.
        </span>
      </div>

      {providerIds.map((provider) => {
        const meta = data.providers[provider];
        const configured = data.configured[provider];
        const result = testResult[provider];
        return (
          <div key={provider} className="rounded-control border border-slate-200 p-3 dark:border-slate-700">
            <div className="mb-2 flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-brand-500" />
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{meta.name}</p>
              <span
                className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  configured ? 'bg-emerald-500/15 text-emerald-500' : 'bg-slate-500/15 text-slate-400'
                }`}
              >
                {configured ? 'Key configured' : 'No key'}
              </span>
            </div>
            <p className="mb-2 text-[11px] text-slate-400">
              {meta.docs}{' '}
              <a className="text-brand-500 underline" href={meta.keys_url} target="_blank" rel="noreferrer">
                {meta.keys_url}
              </a>
              {meta.key_hint ? ` · ${meta.key_hint}` : ''}
            </p>
            <div className="flex gap-2">
              <input
                type="password"
                value={keys[provider]}
                onChange={(e) => setKeys((k) => ({ ...k, [provider]: e.target.value }))}
                placeholder={`${meta.name} API key`}
                className={inputCls}
              />
              <button
                onClick={() => testKey(provider)}
                disabled={testing[provider]}
                className="shrink-0 rounded-control bg-slate-700 px-3 py-2 text-xs font-medium text-white hover:bg-slate-600 disabled:opacity-50 dark:bg-slate-600"
              >
                {testing[provider] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Test key'}
              </button>
              <button
                onClick={() => saveKey(provider)}
                disabled={saving[provider] || !keys[provider].trim()}
                className="shrink-0 rounded-control bg-brand-500 px-3 py-2 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"
              >
                {saving[provider] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Save'}
              </button>
              <button
                onClick={() => loadModels(provider)}
                title="Load authorized models"
                className="shrink-0 rounded-control border border-slate-200 p-2 text-slate-400 hover:text-slate-600 dark:border-slate-700"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
            {result && (
              <p className={`mt-2 flex items-center gap-1 text-[11px] ${result.valid ? 'text-emerald-500' : 'text-rose-500'}`}>
                {result.valid ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                {result.valid
                  ? `Valid · ${result.models.length} models · ${result.latency_ms}ms`
                  : `Invalid: ${result.error ?? 'rejected'}`}
              </p>
            )}
          </div>
        );
      })}

      <div className="rounded-control border border-slate-200 p-3 dark:border-slate-700">
        <p className="mb-1 text-sm font-semibold text-slate-900 dark:text-slate-100">Model per agent task</p>
        <p className="mb-3 text-[11px] text-slate-400">
          Defaults are pre-selected (marked “default”). Pick any authorized model — recommended ones are marked ★.
        </p>
        <div className="space-y-3">
          {taskIds.map((task) => {
            const t = data.tasks[task];
            const pick = picks[task] ?? { provider: t.default.provider, model: t.default.model };
            const providerModels = models[pick.provider] ?? [];
            const rec = t.recommended[pick.provider];
            const fallbackOptions = [rec?.[0], t.recommended.groq?.[0], pick.model].filter(Boolean) as string[];
            const options = providerModels.length > 0 ? providerModels : fallbackOptions;
            const isDefault = !data.selections[task];
            return (
              <div key={task}>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{t.label}</p>
                  <span className="rounded-full bg-slate-500/10 px-1.5 py-0.5 text-[9px] text-slate-400">{t.needs}</span>
                  {isDefault && (
                    <span className="rounded-full bg-brand-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-brand-500">default</span>
                  )}
                </div>
                {rec && (
                  <p className="mb-1 flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400">
                    <Zap className="h-3 w-3" /> Best on {data.providers[pick.provider]?.name}: <strong>{rec[0]}</strong> — {rec[1]}
                  </p>
                )}
                <div className="flex gap-2">
                  <select
                    value={pick.provider}
                    onChange={(e) => {
                      const provider = e.target.value as ProviderId;
                      const def = t.recommended[provider]?.[0] ?? pick.model;
                      savePick(task, provider, def);
                    }}
                    className={inputCls}
                  >
                    {providerIds.map((p) => (
                      <option key={p} value={p}>
                        {data.providers[p].name}
                        {data.configured[p] ? '' : ' (no key)'}
                      </option>
                    ))}
                  </select>
                  <select
                    value={pick.model}
                    onChange={(e) => savePick(task, pick.provider, e.target.value)}
                    className={inputCls}
                  >
                    {options.map((m) => (
                      <option key={m} value={m}>
                        {(rec?.[0] === m ? '★ ' : '') + m}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
