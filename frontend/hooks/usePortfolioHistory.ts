/**
 * React Hook for fetching portfolio historical performance data
 * Used for equity curve charts with Recharts
 */

import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '@/lib/api-client';

interface EquityDataPoint {
  x: number; // timestamp
  y: number; // portfolio value
}

interface PortfolioHistory {
  equity: EquityDataPoint[];
  pnl: {
    realized: number;
    unrealized: number;
    total: number;
  };
  isInitialized: boolean;
  initialValue?: number; // Initial portfolio value from backend
}

interface UsePortfolioHistoryOptions {
  portfolioId?: number;
  period?: '1d' | '1w' | '1m' | '3m' | '6m' | '1y' | 'all';
  refreshInterval?: number; // ms, default 30000 (30s)
}

export function usePortfolioHistory(options: UsePortfolioHistoryOptions = {}) {
  const {
    portfolioId = 1,
    period = '1m',
    refreshInterval = 30000,
  } = options;

  const [data, setData] = useState<PortfolioHistory | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    try {
      // Fetch real equity curve from backend snapshots
      const equityRes = await apiFetch(
        `/api/v1/portfolio/equity-curve?portfolio_id=${portfolioId}&period=${period}`
      );

      if (equityRes.ok) {
        const equityData = await equityRes.json();
        const equity: EquityDataPoint[] = (equityData.equity || []).map(
          (pt: { date: string; value: number }) => ({
            x: new Date(pt.date).getTime(),
            y: pt.value,
          })
        );

        // Fetch portfolio summary for PnL
        const portfolioRes = await apiFetch(
          `/api/v1/portfolio?portfolio_id=${portfolioId}`
        );
        const portfolio = portfolioRes.ok ? await portfolioRes.json() : {};
        const performanceRes = await apiFetch(
          `/api/v1/portfolio/performance?portfolio_id=${portfolioId}&period=${period}`
        );
        const performance = performanceRes.ok ? await performanceRes.json() : {};

        setData({
          equity,
          pnl: {
            realized: performance.realized_pnl || 0,
            unrealized: performance.unrealized_pnl || 0,
            total: performance.total_pnl || 0,
          },
          isInitialized: performance.is_initialized ?? equity.length > 1,
          initialValue: equityData.initial_value || portfolio.initial_value || portfolio.total_value || 0,
        });
        setError(null);
        setLoading(false);
        return;
      }

      // Fallback: construct from portfolio summary if equity-curve endpoint fails
      const portfolioRes = await apiFetch(
        `/api/v1/portfolio?portfolio_id=${portfolioId}`
      );
      if (!portfolioRes.ok) throw new Error('Failed to fetch portfolio data');
      const portfolio = await portfolioRes.json();

      const performanceRes = await apiFetch(
        `/api/v1/portfolio/performance?portfolio_id=${portfolioId}&period=${period}`
      );
      const performance = performanceRes.ok ? await performanceRes.json() : {};

      const now = Date.now();
      const equity: EquityDataPoint[] = [];
      if (portfolio.total_value && performance.is_initialized) {
        const initialValue = portfolio.initial_value || portfolio.total_value;
        const currentValue = portfolio.total_value;
        const numPoints = period === '1d' ? 24 : period === '1w' ? 7 : period === '1m' ? 30 : 90;
        const pointInterval = period === '1d' ? 3600000 : 86400000;
        const totalChange = currentValue - initialValue;
        for (let i = numPoints; i >= 0; i--) {
          const timestamp = now - i * pointInterval;
          const progress = 1 - i / numPoints;
          equity.push({ x: timestamp, y: Math.max(0, initialValue + totalChange * progress) });
        }
      } else {
        equity.push({ x: now, y: portfolio.total_value || 0 });
      }

      setData({
        equity,
        pnl: {
          realized: performance.realized_pnl || 0,
          unrealized: performance.unrealized_pnl || 0,
          total: performance.total_pnl || 0,
        },
        isInitialized: performance.is_initialized,
        initialValue: portfolio.initial_value || portfolio.total_value || 0,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [portfolioId, period]);

  useEffect(() => {
    fetchHistory();

    if (refreshInterval > 0) {
      const interval = setInterval(fetchHistory, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchHistory, refreshInterval]);

  return {
    data,
    loading,
    error,
    refetch: fetchHistory,
  };
}

export type { EquityDataPoint, PortfolioHistory };
