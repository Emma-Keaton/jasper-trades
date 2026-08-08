'use client';

import React from 'react';

const badgeTones = {
  neutral: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  up: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
  down: 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300',
  accent: 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300',
  warning: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
};

export function Badge({
  tone = 'neutral',
  className = '',
  children,
}: {
  tone?: keyof typeof badgeTones;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${badgeTones[tone]} ${className}`}>
      {children}
    </span>
  );
}
