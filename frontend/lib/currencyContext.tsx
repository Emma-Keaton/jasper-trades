'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// Types
export type Currency = 'USD' | 'NGN' | 'CNY';

interface CurrencyState {
  currency: Currency;
  exchangeRate: number; // NGN/USD or CNY/USD rate
  exchangeRates: Record<string, number>; // Store all rates
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

      const results = await Promise.all(promises);
      const newRates: Record<string, number> = { ...state.exchangeRates };

      if (results[0].ok) {
        const data = await results[0].json();
        newRates['NGN/USD'] = data.data?.rate || 0;
      }
      if (results[1].ok) {
        const data = await results[1].json();
        newRates['USD/NGN'] = data.data?.rate || 0;
      }
      if (results[2].ok) {
        const data = await results[2].json();
        newRates['CNY/USD'] = data.data?.rate || 0;
      }
      if (results[3].ok) {
        const data = await results[3].json();
        newRates['USD/CNY'] = data.data?.rate || 0;
      }

      setState(prev => ({
        ...prev,
        exchangeRate: newRates['NGN/USD'] || prev.exchangeRate,
        exchangeRates: newRates,
        lastUpdated: new Date(),
        isLoading: false,
      }));
    } catch (e) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: e instanceof Error ? e.message : 'Failed to fetch rate',
      }));
    }
  }, [state.exchangeRates]);

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