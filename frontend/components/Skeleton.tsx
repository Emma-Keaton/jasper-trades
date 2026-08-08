'use client';

import React from 'react';

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`card p-4 animate-pulse ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="skeleton h-3 w-20" />
        <div className="skeleton h-8 w-8 rounded-lg" />
      </div>
      <div className="skeleton h-7 w-32 mb-2" />
      <div className="skeleton h-3 w-24" />
    </div>
  );
}

export function SkeletonTable() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="skeleton h-5 w-48 mb-4" />
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="skeleton h-4 w-20" />
            <div className="skeleton h-4 w-32" />
            <div className="skeleton h-4 w-16 ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="skeleton h-5 w-40" />
        <div className="flex gap-2"><div className="skeleton h-7 w-12" /><div className="skeleton h-7 w-12" /></div>
      </div>
      <div className="skeleton h-44" />
      <div className="flex justify-between mt-3">{[0,1,2,3,4,5,6].map(i => <div key={i} className="skeleton h-3 w-12" />)}</div>
    </div>
  );
}

export function SkeletonConsole() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="skeleton h-5 w-48 mb-2" />
      <div className="space-y-3 mt-3">{[0,1,2,3].map(i => (
        <div key={i} className="space-y-2">
          <div className="flex items-center gap-2"><div className="skeleton h-3 w-16" /><div className="skeleton h-4 w-20" /></div>
          <div className="skeleton h-2 w-full" />
          <div className="skeleton h-2 w-3/4" />
        </div>
      ))}</div>
    </div>
  );
}

export function SkeletonText({ lines = 1, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-4" style={{ width: `${100 - (i * 5)}%` }} />
      ))}
    </div>
  );
}
