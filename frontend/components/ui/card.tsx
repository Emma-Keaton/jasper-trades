'use client';

import React from 'react';

export function Card({
  className = '',
  children,
  hover = false,
  onClick,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      className={`card ${hover ? 'card-hover cursor-pointer' : ''} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
  caption,
  tone = 'neutral',
  className = '',
}: {
  label: string;
  value: React.ReactNode;
  caption?: string;
  tone?: 'neutral' | 'up' | 'down' | 'accent';
  className?: string;
}) {
  const valueColor =
    tone === 'up'
      ? 'text-emerald-600 dark:text-emerald-400'
      : tone === 'down'
      ? 'text-rose-600 dark:text-rose-400'
      : tone === 'accent'
      ? 'text-brand-600 dark:text-brand-400'
      : 'text-slate-900 dark:text-slate-50';

  return (
    <div className={className}>
      <p className="text-[13px] font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl md:text-3xl font-display font-bold tracking-tight tnum ${valueColor}`}>{value}</p>
      {caption && <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{caption}</p>}
    </div>
  );
}
