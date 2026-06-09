'use client';

import React from 'react';

interface SkeletonCardProps {
  className?: string;
}

export function SkeletonCard({ className = '' }: SkeletonCardProps) {
  return (
    <div className={`bg-gray-800 border border-gray-700 rounded-xl p-4 animate-pulse ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="h-3 bg-gray-700 rounded w-20" />
        <div className="h-8 w-8 bg-gray-700 rounded-lg" />
      </div>
      <div className="h-7 bg-gray-700 rounded w-32 mb-2" />
      <div className="h-3 bg-gray-700 rounded w-24" />
    </div>
  );
}

export function SkeletonTable() {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 animate-pulse">
      <div className="h-5 bg-gray-700 rounded w-48 mb-4" />
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="h-4 bg-gray-700 rounded w-20" />
            <div className="h-4 bg-gray-700 rounded w-32" />
            <div className="h-4 bg-gray-700 rounded w-16" />
            <div className="h-4 bg-gray-700 rounded w-24 ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="h-5 bg-gray-700 rounded w-40" />
        <div className="flex gap-2">
          <div className="h-7 w-12 bg-gray-700 rounded" />
          <div className="h-7 w-12 bg-gray-700 rounded" />
        </div>
      </div>
      <div className="h-44 bg-gray-700 rounded-lg" />
      <div className="flex justify-between mt-3">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="h-3 bg-gray-600 rounded w-12" />
        ))}
      </div>
    </div>
  );
}

export function SkeletonConsole() {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 animate-pulse">
      <div className="h-5 bg-gray-700 rounded w-48 mb-2" />
      <div className="space-y-3 mt-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-3 bg-gray-700 rounded w-16" />
              <div className="h-4 bg-gray-700 rounded w-20" />
            </div>
            <div className="h-3 bg-gray-700 rounded w-full" />
            <div className="h-2 bg-gray-700 rounded w-3/4" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonText({ lines = 1, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {[...Array(lines)].map((_, i) => (
        <div
          key={i}
          className="h-4 bg-gray-700 rounded animate-pulse"
          style={{ width: `${100 - (i * 5)}%` }}
        />
      ))}
    </div>
  );
}