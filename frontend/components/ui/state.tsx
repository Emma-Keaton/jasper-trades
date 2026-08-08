'use client';

import React from 'react';
import { ChevronRight } from 'lucide-react';

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-slate-300 bg-slate-50/50 px-6 py-14 text-center dark:border-slate-700 dark:bg-slate-900/40">
      {icon && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-slate-500 dark:text-slate-400">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function RowLink({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="group inline-flex items-center gap-1 text-sm font-semibold text-brand-600 transition hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
    >
      {children}
      <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
    </button>
  );
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600 dark:border-brand-800 dark:border-t-brand-400 ${className}`}
    />
  );
}
