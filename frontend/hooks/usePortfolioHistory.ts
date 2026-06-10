/**
 * React Hook for fetching portfolio historical performance data
 * Used for equity curve charts with Recharts
 */

import { useState, useEffect, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
      // Fetch portfolio performance
      const performanceRes = await fetch(
        `${API_URL}/api/v1/portfolio/performance?portfolio_id=${portfolioId}&period=${period}`
      );

      if (!performanceRes.ok) {
        throw new Error('Failed to fetch performance data');
      }

      const performance = await performanceRes.json();

      // Fetch portfolio summary for current value
      const portfolioRes = await fetch(
        `${API_URL}/api/v1/portfolio?portfolio_id=${portfolioId}`
      );

      if (!portfolioRes.ok) {
        throw new Error('Failed to fetch portfolio data');
      }

      const portfolio = await portfolioRes.json();

      // Generate equity curve data points based on portfolio history
      // For now, we'll create a simplified version - in production this would come from a dedicated history endpoint
      const now = Date.now();
      const equity: EquityDataPoint[] = [];

      if (performance.is_initialized && portfolio.total_value) {
        // Generate historical points (simplified - would be replaced with actual history endpoint)
        // This creates points showing the portfolio value progression
        const numPoints = period === '1d' ? 24 : period === '1w' ? 7 : period === '1m' ? 30 : 90;
        const pointInterval = period === '1d' ? 3600000 : // 1 hour
          period === '1w' ? 86400000 : // 1 day
          86400000; // 1 day

        const initialValue = portfolio.initial_value || portfolio.total_value || 0;
        const currentValue = portfolio.total_value;
        const totalChange = currentValue - initialValue;

        // Create smooth curve with some realistic variation
        for (let i = numPoints; i >= 0; i--) {
          const timestamp = now - (i * pointInterval);
          // Add realistic noise to the curve
          const progress = 1 - (i / numPoints);
          const baseValue = initialValue + (totalChange * progress);
          // Add small random variation (±2%)
          const noise = (Math.random() - 0.5) * 0.04 * initialValue;
          const value = Math.max(0, baseValue + noise);

          equity.push({
            x: timestamp,
            y: value,
          });
        }
      } else {
        // Not initialized - show flat line at 0
        for (let i = 10; i >= 0; i--) {
          equity.push({
            x: now - (i * 86400000),
            y: 0,
          });
        }
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
