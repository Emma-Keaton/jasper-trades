'use client';

import React, { useState, useEffect } from 'react';
import { ChevronDown, LucideIcon } from 'lucide-react';

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
  const [isOpen, setIsOpen] = useState(() => {
    if (storageKey) {
      const stored = localStorage.getItem(storageKey);
      return stored ? stored === 'true' : defaultOpen;
    }
    return defaultOpen;
  });

  useEffect(() => {
    if (storageKey) {
      localStorage.setItem(storageKey, String(isOpen));
    }
  }, [isOpen, storageKey]);

  const IconComponent = typeof icon === 'string' 
    ? null 
    : icon;

  return (
    <div className="border border-[#475569] rounded-xl overflow-hidden mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-3 sm:p-4 bg-[#1E293B] flex items-center justify-between hover:bg-[#334155] transition gap-3"
      >
        <div className="flex items-start gap-3 flex-1 text-left">
          {/* Icon */}
          {IconComponent && (
            <div className="flex-shrink-0 mt-0.5">
              <IconComponent className="w-5 h-5 text-[#3B82F6]" />
            </div>
          )}
          {typeof icon === 'string' && (
            <div className="flex-shrink-0 mt-0.5 text-lg">
              {icon}
            </div>
          )}
          {/* Title and subtitle */}
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-bold text-[#F8FAFC]">{title}</h3>
            {subtitle && <p className="text-xs text-[#94A3B8] mt-0.5">{subtitle}</p>}
            {completionStatus && (
              <p className="text-xs text-[#64748B] mt-0.5">{completionStatus}</p>
            )}
          </div>
        </div>
        {/* Chevron */}
        <ChevronDown
          className={`w-5 h-5 text-[#94A3B8] transition-transform flex-shrink-0 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>
      {isOpen && (
        <div className="p-3 sm:p-4 bg-[#0F172A] border-t border-[#475569]">
          {children}
        </div>
      )}
    </div>
  );
}