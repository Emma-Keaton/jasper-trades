'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// Types
export type Currency = 'USD' | 'NGN';

interface CurrencyState {
  currency: Currency;
  exchangeRate: number; // NGN to USD rate
  lastUpdated: Date | null;
  isLoading: boolean;
  error: string | null;
}

interface CurrencyContextType extends CurrencyState {
  setCurrency: (currency: Currency) => void;
  toggleCurrency: () => void;
  convertAmount: (amount: number, from: Currency, to: Currency) => number;
  formatCurrency: (amount: number, currency?: Currency) => string;
  refreshRate: () => Promise<void>;
}

// Initial state
const initialState: CurrencyState = {
  currency: 'USD',
  exchangeRate: 0,
  lastUpdated: null,
  isLoading: false,
  error: null,
};

// Create context
const CurrencyContext = createContext<CurrencyContextType | undefined>(undefined);

// Currency symbols and formatting
const currencySymbols: Record<Currency, string> = {
  USD: '$',
  NGN: '₦',
};

const localeMap: Record<Currency, string> = {
  USD: 'en-US',
  NGN: 'en-NG',
};

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CurrencyState>(initialState);
  const [wsConnected, setWsConnected] = useState(false);

  // Load currency preference on mount
  useEffect(() => {
    loadCurrencyPreference();
  }, []);

  // Connect to WebSocket for real-time rate updates
  useEffect(() => {
    const deviceId = getOrCreateDeviceId();
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connectWebSocket = () => {
      try {
        // Construct WebSocket URL properly
        let wsUrl = WS_URL;
        if (!wsUrl.startsWith('ws://') && !wsUrl.startsWith('wss://')) {
          wsUrl = wsUrl.replace(/^https?:\/\//, (match) => {
            return match === 'https://' ? 'wss://' : 'ws://';
          });
        }
        if (!wsUrl.startsWith('ws://') && !wsUrl.startsWith('wss://')) {
          wsUrl = `ws://${wsUrl}`;
        }

        ws = new WebSocket(`${wsUrl}/ws/forex`);

        ws.onopen = () => {
          setWsConnected(true);
          console.log('[CurrencyContext] WebSocket connected to forex rates');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'forex_update' && data.rates) {
              const ngnUsdRate = data.rates['NGN/USD']?.rate || 0;
              setState(prev => ({
                ...prev,
                exchangeRate: ngnUsdRate,
                lastUpdated: new Date(),
                isLoading: false,
              }));
            }
          } catch (e) {
            console.error('[CurrencyContext] WebSocket message parse error:', e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          // Reconnect after 5 seconds
          reconnectTimeout = setTimeout(connectWebSocket, 5000);
        };

        ws.onerror = (error) => {
          console.error('[CurrencyContext] WebSocket error:', error);
          setWsConnected(false);
        };
      } catch (e) {
        console.error('[CurrencyContext] WebSocket connection failed:', e);
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
      }
    };

    connectWebSocket();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  const loadCurrencyPreference = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await fetch(`${API_URL}/api/v1/settings/currency/preference`, {
        headers: { 'X-Device-ID': deviceId },
      });

      if (res.ok) {
        const data = await res.json();
        setState(prev => ({
          ...prev,
          currency: data.default_currency || 'USD',
          currency_conversion_enabled: data.currency_conversion_enabled !== false,
        }));
      }
    } catch (e) {
      console.error('[CurrencyContext] Failed to load currency preference:', e);
    }
  };

  const refreshRate = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const deviceId = getOrCreateDeviceId();
      const res = await fetch(`${API_URL}/api/v1/forex/rate/NGN/USD`, {
        headers: { 'X-Device-ID': deviceId },
      });

      if (res.ok) {
        const data = await res.json();
        setState(prev => ({
          ...prev,
          exchangeRate: data.data?.rate || 0,
          lastUpdated: new Date(),
          isLoading: false,
        }));
      } else {
        throw new Error('Failed to fetch exchange rate');
      }
    } catch (e) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: e instanceof Error ? e.message : 'Failed to fetch rate',
      }));
    }
  }, []);

  const saveCurrencyPreference = async (currency: Currency) => {
    try {
      const deviceId = getOrCreateDeviceId();
      await fetch(`${API_URL}/api/v1/settings/currency/preference`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify({
          default_currency: currency,
          currency_conversion_enabled: true,
        }),
      });
    } catch (e) {
      console.error('[CurrencyContext] Failed to save currency preference:', e);
    }
  };

  const setCurrency = useCallback((currency: Currency) => {
    setState(prev => ({ ...prev, currency }));
    saveCurrencyPreference(currency);
  }, []);

  const toggleCurrency = useCallback(() => {
    const newCurrency = state.currency === 'USD' ? 'NGN' : 'USD';
    setCurrency(newCurrency);
  }, [state.currency, setCurrency]);

  const convertAmount = useCallback((amount: number, from: Currency, to: Currency): number => {
    if (from === to) return amount;

    // NGN to USD: multiply by exchange rate (e.g., 0.00065)
    // USD to NGN: divide by exchange rate (e.g., 1 / 0.00065 = 1538.46)
    if (from === 'NGN' && to === 'USD') {
      return amount * state.exchangeRate;
    } else if (from === 'USD' && to === 'NGN') {
      return state.exchangeRate > 0 ? amount / state.exchangeRate : 0;
    }

    return amount;
  }, [state.exchangeRate]);

  const formatCurrency = useCallback((amount: number, currency?: Currency): string => {
    const curr = currency || state.currency;
    const symbol = currencySymbols[curr];

    // Handle very large NGN amounts (use commas)
    const formatted = amount.toLocaleString(localeMap[curr], {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    return `${symbol}${formatted}`;
  }, [state.currency]);

  const value: CurrencyContextType = {
    ...state,
    setCurrency,
    toggleCurrency,
    convertAmount,
    formatCurrency,
    refreshRate,
  };

  return (
    <CurrencyContext.Provider value={value}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency() {
  const context = useContext(CurrencyContext);
  if (context === undefined) {
    throw new Error('useCurrency must be used within a CurrencyProvider');
  }
  return context;
}

/**
 * Hook for formatting monetary values with automatic currency conversion.
 * Use this in components to display any monetary value.
 * 
 * Example:
 * const { formatMoney } = useCurrencyFormatter();
 * <div>{formatMoney(100000)}</div> // Shows $100,000.00 or ₦153,846,153.85
 */
export function useCurrencyFormatter() {
  const { convertAmount, formatCurrency, currency } = useCurrency();

  const formatMoney = useCallback((amount: number, sourceCurrency: Currency = 'USD'): string => {
    const converted = convertAmount(amount, sourceCurrency, currency);
    return formatCurrency(converted, currency);
  }, [convertAmount, formatCurrency, currency]);

  return { formatMoney, currentCurrency: currency };
}