'use client';

import React from 'react';

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  className = '',
}: {
  options: { value: T; label: React.ReactNode }[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div
      className={`inline-flex flex-wrap rounded-full border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-800 ${className}`}
      role="tablist"
    >
      {options.map(opt => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              active
                ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-50'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function Switch({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  description?: string;
}) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="group flex w-full items-center justify-between gap-4 text-left">
      {(label || description) && (
        <div>
          {label && <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">{label}</span>}
          {description && <span className="mt-0.5 block text-sm text-slate-500 dark:text-slate-400">{description}</span>}
        </div>
      )}
      <span className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition ${checked ? 'bg-brand-600' : 'bg-slate-300 dark:bg-slate-700'}`}>
        <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
      </span>
    </button>
  );
}
