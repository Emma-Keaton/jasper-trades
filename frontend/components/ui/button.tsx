'use client';

import React from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Button({
  variant = 'primary',
  className = '',
  size = 'md',
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' | 'lg' }) {
  const base =
    variant === 'primary'
      ? 'btn-primary'
      : variant === 'secondary'
      ? 'btn-secondary'
      : variant === 'danger'
      ? 'inline-flex items-center justify-center rounded-full bg-rose-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-700 active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 disabled:opacity-50'
      : 'btn-ghost';

  const sizeClass =
    variant === 'ghost' ? (size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-5 py-2.5 text-sm') : size === 'sm' ? 'px-4 py-2 text-sm' : size === 'lg' ? 'px-8 py-4 text-base' : 'px-6 py-3 text-sm';

  return (
    <button className={`${base} ${sizeClass} ${className}`} {...rest}>
      {children}
    </button>
  );
}
