'use client';

import React, { useState, useEffect } from 'react';
import { ChevronDown, LucideIcon } from 'lucide-react';
import { loadCollapsibleState, saveCollapsibleState } from '@/lib/preferences';

interface CollapsibleSectionProps {
  title: string;
  subtitle?: string;
  icon?: LucideIcon | string; // Lucide component or emoji
  defaultOpen?: boolean;
  storageKey?: string;
  completionStatus?: string; // e.g., "2 of 3 configured"
  children: React.ReactNode;
}

export function CollapsibleSection({
  title,
  subtitle,
  icon,
  defaultOpen = false,
  storageKey,
  completionStatus,
  children,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // Load persisted open state from the DB (per device).
  useEffect(() => {
    if (!storageKey) return;
    let cancelled = false;
    loadCollapsibleState(storageKey).then((stored) => {
      if (!cancelled && stored !== null) setIsOpen(stored);
    });
    return () => { cancelled = true; };
  }, [storageKey]);

  // Persist open state changes.
  useEffect(() => {
    if (!storageKey) return;
    saveCollapsibleState(storageKey, isOpen);
  }, [isOpen, storageKey]);

  const IconComponent = typeof icon === 'string' 
    ? null 
    : icon;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-3 sm:p-4 bg-white dark:bg-slate-900 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/60 transition gap-3"
      >
        <div className="flex items-start gap-3 flex-1 text-left">
          {/* Icon */}
          {IconComponent && (
            <div className="flex-shrink-0 mt-0.5">
              <IconComponent className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            </div>
          )}
          {typeof icon === 'string' && (
            <div className="flex-shrink-0 mt-0.5 text-lg">
              {icon}
            </div>
          )}
          {/* Title and subtitle */}
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-50">{title}</h3>
            {subtitle && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
            {completionStatus && (
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{completionStatus}</p>
            )}
          </div>
        </div>
        {/* Chevron */}
        <ChevronDown
          className={`w-5 h-5 text-slate-400 dark:text-slate-500 transition-transform flex-shrink-0 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>
      {isOpen && (
        <div className="p-3 sm:p-4 bg-slate-50 dark:bg-slate-950 border-t border-slate-200 dark:border-slate-800">
          {children}
        </div>
      )}
    </div>
  );
}
