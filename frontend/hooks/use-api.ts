/**
 * React Hooks for Jasper Trades API
 */

import { useState, useEffect, useCallback } from 'react';
import * as api from '@/lib/api-client';

// Generic hook for fetching data
interface UseFetchOptions<T> {
  initialValue?: T;
  refreshInterval?: number;
  enabled?: boolean;
}

export function useFetch<T>(
  fetchFn: () => Promise<api.ApiResponse<T>>,
  options: UseFetchOptions<T> = {}
) {
  const { initialValue, refreshInterval, enabled = true } = options;
  const [data, setData] = useState<T | undefined>(initialValue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();

  const fetchData = useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError(undefined);

    try {
      const result = await fetchFn();
      if (result.error) {
        setError(result.error);
      } else if (result.data) {
        setData(result.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [fetchFn, enabled]);

  useEffect(() => {
    fetchData();

    if (refreshInterval && enabled) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, refreshInterval, enabled]);

  return { data, loading, error, refetch: fetchData };
}

// Portfolio hooks
export function usePortfolio(portfolioId?: string) {
  const fetchFn = portfolioId
    ? () => api.portfolioAPI.getPortfolio(portfolioId)
    : () => api.portfolioAPI.getPortfolios();

  return useFetch<any>(fetchFn, { refreshInterval: 5000 });
}

export function useHoldings(portfolioId: string) {
  return useFetch<api.Holding[]>(
    () => api.portfolioAPI.getHoldings(portfolioId),
    { refreshInterval: 4500 }
  );
}

export function useTrades(portfolioId?: string) {
  return useFetch<api.Trade[]>(
    () => api.portfolioAPI.getTrades(portfolioId || ''),
    { refreshInterval: 5000 }
  );
}

// Trading hooks
export function useTradeHistory(portfolioId?: string) {
  return useFetch<api.Trade[]>(
    () => api.tradingAPI.getTradeHistory(portfolioId),
    { refreshInterval: 5000 }
  );
}

export function useExecuteTrade() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const executeTrade = useCallback(
    async (data: {
      portfolio_id: string;
      symbol: string;
      type: 'BUY' | 'SELL';
      shares: number;
      order_type: 'MARKET' | 'LIMIT';
      limit_price?: number;
    }) => {
      setLoading(true);
      setError(undefined);

      try {
        const result = await api.tradingAPI.executeTrade(data);
        if (result.error) {
          setError(result.error);
          return null;
        }
        return result.data;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { executeTrade, loading, error };
}

// Signal hooks
export function useSignals(limit = 50) {
  return useFetch<api.Signal[]>(
    () => api.signalAPI.getSignals(limit),
    { refreshInterval: 3000 }
  );
}

export function useActiveSignals() {
  return useFetch<api.Signal[]>(
    () => api.signalAPI.getActiveSignals(),
    { refreshInterval: 2000 }
  );
}

// Agent hooks
export function useAgents() {
  return useFetch<api.Agent[]>(() => api.agentAPI.getAgents(), {
    refreshInterval: 3000,
  });
}

export function useAgent(id: string) {
  return useFetch<api.Agent>(() => api.agentAPI.getAgent(id), {
    refreshInterval: 5000,
  });
}

export function useAgentControl() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const startAgent = useCallback(async (agentId: string) => {
    setLoading(true);
    setError(undefined);

    try {
      const result = await api.agentAPI.startAgent(agentId);
      if (result.error) {
        setError(result.error);
        return false;
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const stopAgent = useCallback(async (agentId: string) => {
    setLoading(true);
    setError(undefined);

    try {
      const result = await api.agentAPI.stopAgent(agentId);
      if (result.error) {
        setError(result.error);
        return false;
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { startAgent, stopAgent, loading, error };
}

// Copy Trading hooks
export function useLeaderboard() {
  return useFetch<any[]>(() => api.copyTradeAPI.getLeaderboard(), {
    refreshInterval: 10000,
  });
}

export function useStrategies() {
  return useFetch<any[]>(() => api.copyTradeAPI.getStrategies(), {
    refreshInterval: 10000,
  });
}

export function useMyFollows() {
  return useFetch<any[]>(() => api.copyTradeAPI.getMyFollows(), {
    refreshInterval: 5000,
  });
}

// Backtest hooks
export function useBacktestResults() {
  return useFetch<api.BacktestResult[]>(
    () => api.backtestAPI.getBacktestResults(),
    { refreshInterval: 5000 }
  );
}

export function useRunBacktest() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [result, setResult] = useState<{ id: string } | undefined>();

  const runBacktest = useCallback(async (data: {
    name: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    symbols: string[];
    factors: string[];
    strategy: string;
  }) => {
    setLoading(true);
    setError(undefined);

    try {
      const apiResult = await api.backtestAPI.runBacktest(data);
      if (apiResult.error) {
        setError(apiResult.error);
        return null;
      }
      setResult(apiResult.data);
      return apiResult.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { runBacktest, loading, error, result };
}

// Alpha Zoo hooks
export function useAlphaFactors(category?: string) {
  return useFetch<api.AlphaFactor[]>(
    () => api.alphaAPI.getFactors(category),
    { refreshInterval: 30000 }
  );
}

export function useAlphaCategories() {
  return useFetch<string[]>(() => api.alphaAPI.getCategories(), {
    refreshInterval: 30000,
  });
}

// System Status hook
export function useSystemStatus() {
  return useFetch<api.SystemStatus>(() => api.healthAPI.check(), {
    refreshInterval: 5000,
  });
}

// Settings hooks
export function useSettings() {
  return useFetch<any>(() => api.settingsAPI.getSettings(), {
    refreshInterval: 10000,
  });
}

export function useUpdateSettings() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const updateSettings = useCallback(async (settings: Record<string, any>) => {
    setLoading(true);
    setError(undefined);

    try {
      const result = await api.settingsAPI.updateSettings(settings);
      if (result.error) {
        setError(result.error);
        return false;
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { updateSettings, loading, error };
}

export function useValidateApiKey() {
  const [validating, setValidating] = useState(false);

  const validateKey = useCallback(async (key: string, service: string) => {
    setValidating(true);
    try {
      const result = await api.settingsAPI.validateApiKey(key, service);
      return result.data?.valid ?? false;
    } catch {
      return false;
    } finally {
      setValidating(false);
    }
  }, []);

  return { validateKey, validating };
}

// Health check hook
export function useHealthCheck() {
  const { data, loading, error, refetch } = useFetch<api.SystemStatus>(
    () => api.healthAPI.check(),
    { refreshInterval: 10000, initialValue: undefined }
  );

  const isHealthy = data?.status === 'healthy';
  const isDegraded = data?.status === 'degraded';
  const isDown = data?.status === 'down' || !!error;

  return {
    data,
    loading,
    error,
    isHealthy,
    isDegraded,
    isDown,
    refetch,
  };
}