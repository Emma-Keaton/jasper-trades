'use client';

import { useState } from 'react';
import { X, Info, ExternalLink, Check, Copy } from 'lucide-react';

interface InfoModalProps {
  title: string;
  children: React.ReactNode;
  open: boolean;
  onClose: () => void;
}

export default function InfoModal({ title, children, open, onClose }: InfoModalProps) {
  if (!open) return null;

  return (
    <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div 
        className="bg-white border border-slate-200 rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto m-4 shadow-pop dark:bg-[#1E293B] dark:border-[#475569]"
        onClick={e => e.stopPropagation()}
        role="presentation"
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-[#475569]">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded text-slate-400 dark:hover:bg-[#334155] dark:text-[#94A3B8]">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 text-sm text-slate-600 dark:text-gray-300">
          {children}
        </div>
      </div>
    </div>
  );
}

interface InfoButtonProps {
  title: string;
  children: React.ReactNode;
}

export function InfoButton({ title, children }: InfoButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-brand-600/20 text-brand-600 hover:bg-brand-600/30 transition dark:bg-[#3B82F6]/20 dark:text-[#3B82F6] dark:hover:bg-[#3B82F6]/30"
        title="Learn more"
      >
        <Info className="w-4 h-4" />
      </button>
      <InfoModal title={title} open={open} onClose={() => setOpen(false)}>
        {children}
      </InfoModal>
    </>
  );
}

interface SetupStepProps {
  number: number;
  children: React.ReactNode;
}

export function SetupStep({ number, children }: SetupStepProps) {
  return (
    <div className="flex gap-3 mb-3">
      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-600/20 text-brand-600 flex items-center justify-center text-xs font-bold dark:bg-[#3B82F6]/20 dark:text-[#3B82F6]">
        {number}
      </div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

interface ApiLinkProps {
  href: string;
  children: React.ReactNode;
}

export function ApiLink({ href, children }: ApiLinkProps) {
  const copyToClipboard = (e: React.MouseEvent) => {
    e.preventDefault();
    navigator.clipboard.writeText(href);
  };

  return (
    <div className="inline-flex items-center gap-2">
      <a 
        href={href} 
        target="_blank" 
        rel="noopener noreferrer"
        className="text-brand-600 hover:underline inline-flex items-center gap-1 dark:text-[#3B82F6]"
      >
        {children}
        <ExternalLink className="w-3 h-3" />
      </a>
      <button
        onClick={copyToClipboard}
        className="p-1 hover:bg-slate-100 rounded text-slate-400 dark:hover:bg-[#334155] dark:text-[#94A3B8]"
        title="Copy URL"
      >
        <Copy className="w-3 h-3" />
      </button>
    </div>
  );
}

interface BenefitItemProps {
  children: React.ReactNode;
}

export function BenefitItem({ children }: BenefitItemProps) {
  return (
    <li className="flex items-start gap-2 mb-2">
      <Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
      <span>{children}</span>
    </li>
  );
}