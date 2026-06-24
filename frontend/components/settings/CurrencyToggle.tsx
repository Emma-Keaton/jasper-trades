'use client';

import { useEffect, useState } from 'react';
import { useCurrency } from '@/lib/currencyContext';
import { RefreshCw, ToggleLeft, ToggleRight } from 'lucide-react';

interface CurrencyToggleProps {
  className?: string;
}

export default function CurrencyToggle({ className = '' }: CurrencyToggleProps) {
  const { currency, toggleCurrency, exchangeRate, lastUpdated, isLoading, refreshRate } = useCurrency();
  const [countdown, setCountdown] = useState(60);

  // Countdown timer for next auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) return 60; // Reset after 60 seconds
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const handleToggle = () => {
    toggleCurrency();
  };

  const formatLastUpdated = () => {
    if (!lastUpdated) return 'Never';
    const seconds = Math.floor((new Date().getTime() - lastUpdated.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ago`;
  };

  const inverseRate = exchangeRate > 0 ? (1 / exchangeRate) : 1527.50; // Fallback to approximate market rate

  return (
    <div className={`flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 ${className}`}>
      {/* Toggle Button */}
      <button
        onClick={handleToggle}
        className="relative flex items-center justify-center w-16 h-8 bg-[#334155] rounded-full transition-colors hover:bg-[#475569]"
        title={`Switch to ${currency === 'USD' ? 'NGN' : 'USD'}`}
      >
        <div
          className={`absolute left-1 transition-transform ${
            currency === 'NGN' ? 'translate-x-8' : 'translate-x-0'
          }`}
        >
          {currency === 'USD' ? (
            <ToggleLeft className="w-6 h-6 text-[#3B82F6]" />
          ) : (
            <ToggleRight className="w-6 h-6 text-[#10B981]" />
          )}
        </div>
        <span className="text-xs font-semibold text-white">
          {currency === 'USD' ? 'NGN' : 'USD'}
        </span>
      </button>

      {/* Exchange Rate Display */}
      <div className="flex flex-col">
        <div className="flex items-center gap-2 text-xs">
          {exchangeRate > 0 ? (
            <span className="text-gray-400">
              1 USD = ₦{inverseRate.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          ) : (
            <span className="text-orange-400 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" />
              Fetching live rate...
            </span>
          )}
          <button
            onClick={refreshRate}
            disabled={isLoading}
            className="p-1 hover:bg-[#334155] rounded transition disabled:opacity-50"
            title="Refresh rate"
          >
            <RefreshCw className={`w-3 h-3 text-gray-400 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-gray-500">
          <span>Updated {formatLastUpdated()}</span>
          {exchangeRate > 0 && (
            <>
              <span className="w-1 h-1 rounded-full bg-gray-500" />
              <span>Next: {countdown}s</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}