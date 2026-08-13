'use client';

import React, { useCallback, useEffect } from 'react';
import { X } from 'lucide-react';

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  size = 'md',
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}) {
  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open, onKeyDown]);

  if (!open) return null;

  const width = size === 'sm' ? 'max-w-sm' : size === 'lg' ? 'max-w-2xl' : size === 'xl' ? 'max-w-4xl' : 'max-w-lg';

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center md:items-center md:p-6">
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm dark:bg-slate-950/70"
        onClick={onClose}
        role="button"
        tabIndex={0}
        aria-label="Close"
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClose(); } }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`relative z-10 flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-card bg-white shadow-pop dark:bg-slate-900 md:rounded-card animate-fade-up ${width}`}
      >
        {(title || description) && (
          <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 dark:border-slate-800">
            <div>
              {title && <h2 className="text-lg font-display font-bold text-slate-900 dark:text-slate-50">{title}</h2>}
              {description && <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}
        <div className="overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  );
}
