'use client';

import { useState, useEffect } from 'react';
import { X, Check, ExternalLink, ChevronRight, ChevronLeft, CircleHelp } from 'lucide-react';
import { Button } from '@/components/ui';

export interface GuideStep {
  title: string;
  body: React.ReactNode;
  href?: string;
  hrefLabel?: string;
  hint?: string;
}

interface SetupGuideProps {
  title: string;
  intro?: React.ReactNode;
  steps: GuideStep[];
  open: boolean;
  onClose: () => void;
  accent?: string;
}

/**
 * Reusable step-by-step setup guide rendered in a modal.
 * Theme-aware (light + dark) and keyboard accessible.
 */
export default function SetupGuide({ title, intro, steps, open, onClose, accent }: SetupGuideProps) {
  const [step, setStep] = useState(0);
  const isLast = step === steps.length - 1;

  useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === 'ArrowRight' && !isLast) setStep((s) => s + 1);
      if (e.key === 'ArrowLeft' && step > 0) setStep((s) => s - 1);
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, isLast, step, onClose]);

  if (!open) return null;

  const active = steps[step];

  const handleOverlayMouseDown = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm"
      onMouseDown={handleOverlayMouseDown}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-md overflow-hidden rounded-card bg-white shadow-pop dark:bg-slate-900"
      >
        <div className="relative overflow-hidden p-7 pb-5">
          <div className="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-brand-100/70 blur-2xl dark:bg-brand-500/10" />
          <button
            onClick={onClose}
            className="absolute right-3 top-3 rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            aria-label="Close guide"
          >
            <X className="h-4 w-4" />
          </button>
          {intro && (
            <p className="mb-3 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
              {intro}
            </p>
          )}
          <p className="eyebrow text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-300">
            Step {step + 1} of {steps.length}
          </p>
          <h3 className="mt-1 font-display text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
            {active.title}
          </h3>
          <div className="mt-2 space-y-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            {typeof active.body === 'string' ? <p>{active.body}</p> : active.body}
          </div>
          {active.href && (
            <a
              href={active.href}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-brand-600 transition hover:border-brand-300 hover:bg-brand-50 dark:border-slate-700 dark:bg-slate-800 dark:text-brand-300 dark:hover:border-brand-500/50 dark:hover:bg-brand-500/10"
            >
              {active.hrefLabel || 'Open'}
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          {active.hint && (
            <p className="mt-3 rounded-control border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
              {active.hint}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 px-7 pb-6 pt-2">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="inline-flex items-center gap-1 text-sm font-medium text-slate-400 transition hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:text-slate-200"
          >
            <ChevronLeft className="h-4 w-4" /> Back
          </button>

          <div className="flex items-center gap-1.5">
            {steps.map((_, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                aria-label={`Go to step ${i + 1}`}
                className={`h-1.5 rounded-full transition-all ${i === step ? `w-6 ${accent ? accent : 'bg-brand-600'}` : 'w-1.5 bg-slate-200 dark:bg-slate-700'}`}
              />
            ))}
          </div>

          {isLast ? (
            <Button onClick={onClose} size="sm">
              <Check className="h-4 w-4" /> Got it
            </Button>
          ) : (
            <Button onClick={() => setStep((s) => s + 1)} size="sm">
              Next <ChevronRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export function SetupGuideButton({
  title,
  steps,
  intro,
  label,
  accent,
}: {
  title: string;
  steps: GuideStep[];
  intro?: React.ReactNode;
  label?: string;
  accent?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-brand-500/50 dark:hover:bg-brand-500/10 dark:hover:text-brand-300"
      >
        <CircleHelp className="h-3.5 w-3.5" />
        {label || 'Setup guide'}
      </button>
      <SetupGuide title={title} steps={steps} intro={intro} open={open} onClose={() => setOpen(false)} accent={accent} />
    </>
  );
}