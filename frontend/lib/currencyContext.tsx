'use client';

import type { ReactNode } from 'react';
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { API_URL, WS_URL } from '@/lib/constants';

// Types
export type Currency = 'USD' | 'NGN' | 'CNY';

interface CurrencyState {
  currency: Currency;
  exchangeRate: number; // NGN/USD or CNY/USD rate
  exchangeRates: Record<string, number>; // Store all rates
  lastUpdated: Date | null;
  isLoading: boolean;
  error: string | null;
  currency_conversion_enabled: boolean;
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
  exchangeRate: 1, // Default to 1.0
  exchangeRates: {
    'NGN/USD': 0.00065, // Default fallback
    'USD/NGN': 1538.46,
    'CNY/USD': 0.14, // ~7.1 CNY per USD
    'USD/CNY': 7.1,
  },
  lastUpdated: null,
  isLoading: false,
  error: null,
  currency_conversion_enabled: true,
};

// Create context
const CurrencyContext = createContext<CurrencyContextType | undefined>(undefined);

// Currency symbols and formatting
const currencySymbols: Record<Currency, string> = {
  USD: '$',
  NGN: '₦',
  CNY: '¥',
};

const localeMap: Record<Currency, string> = {
  USD: 'en-US',
  NGN: 'en-NG',
  CNY: 'zh-CN',
};

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CurrencyState>(initialState);
  const [, setWsConnected] = useState(false);

  // Load currency preference on mount and fetch initial rate
  
  useEffect(() => {
    loadCurrencyPreference();
    // Fetch initial exchange rate on mount
    refreshRateHelper();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Connect to WebSocket for real-time rate updates
  useEffect(() => {
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
              const newRates: Record<string, number> = {};
              
              // Parse all rates
              Object.keys(data.rates).forEach(pair => {
                const rate = data.rates[pair]?.rate || 0;
                newRates[pair] = rate;
              });

              setState(prev => ({
                ...prev,
                exchangeRate: data.rates['NGN/USD']?.rate || prev.exchangeRate,
                exchangeRates: { ...prev.exchangeRates, ...newRates },
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
          // WebSocket error events carry an empty {} object in browsers;
          // the onclose handler already manages reconnection, so only log
          // when there's meaningful detail to avoid console spam.
          if (process.env.NODE_ENV === 'development' && error) {
            console.warn('[CurrencyContext] WebSocket error (reconnecting):', error);
          }
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
      // Backend may be unavailable during local dev or before first start;
      // silently fall back to defaults already set in initialState.
      if (process.env.NODE_ENV === 'development') {
        console.warn('[CurrencyContext] Backend unavailable, using default currency preference');
      }
    }
  };

  const refreshRateHelper = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const deviceId = getOrCreateDeviceId();
      // Fetch all major currency pairs
      const promises = [
        fetch(`${API_URL}/api/v1/forex/rate/NGN/USD`, { headers: { 'X-Device-ID': deviceId } }),
        fetch(`${API_URL}/api/v1/forex/rate/USD/NGN`, { headers: { 'X-Device-ID': deviceId } }),
        fetch(`${API_URL}/api/v1/forex/rate/CNY/USD`, { headers: { 'X-Device-ID': deviceId } }),
        fetch(`${API_URL}/api/v1/forex/rate/USD/CNY`, { headers: { 'X-Device-ID': deviceId } }),
      ];

      const results = await Promise.allSettled(promises);
      const newRates: Record<string, number> = {};

      const pairs = ['NGN/USD', 'USD/NGN', 'CNY/USD', 'USD/CNY'];
      for (let i = 0; i < results.length; i++) {
        const result = results[i];
        if (result.status === 'fulfilled' && result.value.ok) {
          try {
            const data = await result.value.json();
            newRates[pairs[i]] = data.data?.rate || 0;
          } catch {
            // ignore parse errors for individual pairs
          }
        }
      }

      setState(prev => ({
        ...prev,
        exchangeRate: newRates['NGN/USD'] || prev.exchangeRate,
        exchangeRates: { ...prev.exchangeRates, ...newRates },
        lastUpdated: new Date(),
        isLoading: false,
      }));
    } catch (e) {
      // Backend may be unavailable; fall back to default rates already in state.
      if (process.env.NODE_ENV === 'development') {
        console.warn('[CurrencyContext] Backend unavailable, using default rates');
      }
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  // Public refreshRate that can be called from components
  const refreshRate = useCallback(async () => {
    await refreshRateHelper();
  }, [refreshRateHelper]);

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
    const cycle = state.currency === 'USD' ? 'NGN' : state.currency === 'NGN' ? 'CNY' : 'USD';
    setCurrency(cycle);
  }, [state.currency, setCurrency]);

  const convertAmount = useCallback((amount: number, from: Currency, to: Currency): number => {
    if (from === to) return amount;

    // Convert to USD first, then from USD to target currency
    const rates = state.exchangeRates;

    // If both currencies are USD, return amount
    if (from === 'USD') {
      // USD to NGN
      if (to === 'NGN') return rates['USD/NGN'] > 0 ? amount * rates['USD/NGN'] : amount;
      // USD to CNY
      if (to === 'CNY') return rates['USD/CNY'] > 0 ? amount * rates['USD/CNY'] : amount;
    } else if (from === 'NGN') {
      // NGN to USD
      if (to === 'USD') return rates['NGN/USD'] > 0 ? amount * rates['NGN/USD'] : amount;
      // NGN to CNY (via USD)
      if (to === 'CNY') {
        const usdAmount = rates['NGN/USD'] > 0 ? amount * rates['NGN/USD'] : amount;
        return rates['USD/CNY'] > 0 ? usdAmount * rates['USD/CNY'] : usdAmount;
      }
    } else if (from === 'CNY') {
      // CNY to USD
      if (to === 'USD') return rates['CNY/USD'] > 0 ? amount * rates['CNY/USD'] : amount;
      // CNY to NGN (via USD)
      if (to === 'NGN') {
        const usdAmount = rates['CNY/USD'] > 0 ? amount * rates['CNY/USD'] : amount;
        return rates['USD/NGN'] > 0 ? usdAmount * rates['USD/NGN'] : usdAmount;
      }
    }

    return amount;
  }, [state.exchangeRates]);

  const formatCurrency = useCallback((amount: number, currency?: Currency): string => {
    const curr = currency || state.currency;
    const symbol = currencySymbols[curr];

    // Adaptive decimals: show more precision for very small amounts (memecoins)
    const maxDecimals = Math.abs(amount) < 0.01 ? 8 : Math.abs(amount) < 1 ? 4 : 2;
    const formatted = amount.toLocaleString(localeMap[curr], {
      minimumFractionDigits: 2,
      maximumFractionDigits: maxDecimals,
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
    if (amount == null || isNaN(amount)) return '-';
    const converted = convertAmount(amount, sourceCurrency, currency);
    return formatCurrency(converted, currency);
  }, [convertAmount, formatCurrency, currency]);

  return { formatMoney, currentCurrency: currency };
}