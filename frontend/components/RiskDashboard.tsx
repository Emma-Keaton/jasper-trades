'use client';

import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  AlertTriangle, 
  TrendingDown, 
  TrendingUp, 
  Activity,
  RefreshCcw,
  Info
} from 'lucide-react';

interface RiskMetrics {
  var_95: {
    value: number;
    percent: number;
    description: string;
    interpretation: string;
  };
  drawdown: {
    current: number;
    peak_value: number;
    current_value: number;
    description: string;
  };
  sharpe_ratio: {
    value: number;
    interpretation: string;
  };
  sortino_ratio: {
    value: number;
    interpretation: string;
  };
}

interface RiskExposure {
  total_value: number;
  market_value: number;
  cash: number;
  allocation_by_type: Record<string, { value: number; weight: number }>;
  top_concentrations: Array<{ symbol: string; value: number; weight: number }>;
  long_short_breakdown: {
    long_value: number;
    short_value: number;
    net_exposure: number;
  };
}

interface RiskDashboardProps {
  portfolioId?: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function RiskDashboard({ portfolioId }: RiskDashboardProps) {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [exposure, setExposure] = useState<RiskExposure | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchRiskData = async () => {
    try {
      const [metricsRes, exposureRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/risk/metrics${portfolioId ? `?portfolio_id=${portfolioId}` : ''}`),
        fetch(`${API_URL}/api/v1/risk/exposure${portfolioId ? `?portfolio_id=${portfolioId}` : ''}`),
      ]);

      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }

      if (exposureRes.ok) {
        const exposureData = await exposureRes.json();
        setExposure(exposureData);
      }

      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to fetch risk data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRiskData();
    const interval = setInterval(fetchRiskData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [portfolioId]);

  const getVarColor = (percent: number) => {
    if (percent > 5) return 'text-red-500';
    if (percent > 3) return 'text-yellow-500';
    return 'text-green-500';
  };

  const getDrawdownColor = (drawdown: number) => {
    if (drawdown > 10) return 'text-red-500';
    if (drawdown > 5) return 'text-yellow-500';
    return 'text-green-500';
  };

  const getRatioColor = (value: number, type: 'sharpe' | 'sortino') => {
    const threshold = type === 'sharpe' ? 1.5 : 2.0;
    if (value >= threshold) return 'text-green-500';
    if (value >= threshold * 0.7) return 'text-yellow-500';
    return 'text-red-500';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCcw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-sm text-gray-400">Loading risk metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Shield className="w-6 h-6 text-blue-500" />
            Risk Dashboard
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Real-time portfolio risk monitoring
            {lastUpdated && (
              <span className="ml-2 text-xs">
                (Updated: {lastUpdated.toLocaleTimeString()})
              </span>
            )}
          </p>
        </div>
        <button
          onClick={fetchRiskData}
          className="p-2 hover:bg-gray-800 rounded-lg transition"
        >
          <RefreshCcw className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      {/* Risk Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* VaR Card */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase font-mono text-gray-400">
              Value at Risk (95%)
            </span>
            <AlertTriangle className="w-5 h-5 text-gray-400" />
          </div>
          {metrics && (
            <>
              <div className={`text-2xl font-bold font-mono ${getVarColor(metrics.var_95.percent)}`}>
                ${metrics.var_95.value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {metrics.var_95.interpretation}
              </div>
            </>
          )}
        </div>

        {/* Drawdown Card */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase font-mono text-gray-400">
              Current Drawdown
            </span>
            <TrendingDown className="w-5 h-5 text-gray-400" />
          </div>
          {metrics && (
            <>
              <div className={`text-2xl font-bold font-mono ${getDrawdownColor(metrics.drawdown.current)}`}>
                {metrics.drawdown.current.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-400 mt-1">
                From peak: ${metrics.drawdown.peak_value.toLocaleString()}
              </div>
            </>
          )}
        </div>

        {/* Sharpe Ratio Card */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase font-mono text-gray-400">
              Sharpe Ratio
            </span>
            <Activity className="w-5 h-5 text-gray-400" />
          </div>
          {metrics && (
            <>
              <div className={`text-2xl font-bold font-mono ${getRatioColor(metrics.sharpe_ratio.value, 'sharpe')}`}>
                {metrics.sharpe_ratio.value.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {metrics.sharpe_ratio.interpretation}
              </div>
            </>
          )}
        </div>

        {/* Sortino Ratio Card */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase font-mono text-gray-400">
              Sortino Ratio
            </span>
            <TrendingUp className="w-5 h-5 text-gray-400" />
          </div>
          {metrics && (
            <>
              <div className={`text-2xl font-bold font-mono ${getRatioColor(metrics.sortino_ratio.value, 'sortino')}`}>
                {metrics.sortino_ratio.value.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {metrics.sortino_ratio.interpretation}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Exposure Section */}
      {exposure && (
        <>
          {/* Asset Allocation */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h3 className="text-lg font-bold text-white mb-4">Asset Allocation</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(exposure.allocation_by_type).map(([type, data]) => (
                <div key={type} className="space-y-1">
                  <div className="text-xs text-gray-400 uppercase">{type}</div>
                  <div className="text-lg font-bold text-white">
                    {data.weight.toFixed(1)}%
                  </div>
                  <div className="text-xs text-gray-500">
                    ${data.value.toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Concentrations */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <h3 className="text-lg font-bold text-white mb-4">Top 5 Concentrations</h3>
            <div className="space-y-3">
              {exposure.top_concentrations.map((conc, index) => (
                <div key={conc.symbol} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">
                      {index + 1}
                    </div>
                    <span className="font-bold text-white">{conc.symbol}</span>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-white">{conc.weight.toFixed(1)}%</div>
                    <div className="text-xs text-gray-500">${conc.value.toLocaleString()}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Long/Short Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
              <div className="text-xs text-gray-400 uppercase mb-1">Long Exposure</div>
              <div className="text-2xl font-bold text-green-500">
                {exposure.long_short_breakdown.long_value > 0 ? '100%' : '0%'}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                ${exposure.long_short_breakdown.long_value.toLocaleString()}
              </div>
            </div>

            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
              <div className="text-xs text-gray-400 uppercase mb-1">Short Exposure</div>
              <div className="text-2xl font-bold text-red-500">
                {exposure.long_short_breakdown.short_value > 0 ? '100%' : '0%'}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                ${exposure.long_short_breakdown.short_value.toLocaleString()}
              </div>
            </div>

            <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
              <div className="text-xs text-gray-400 uppercase mb-1">Net Exposure</div>
              <div className="text-2xl font-bold text-blue-500">
                {exposure.long_short_breakdown.net_exposure.toFixed(0)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Portfolio directionality
              </div>
            </div>
          </div>
        </>
      )}

      {/* Risk Info */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-gray-300">
          <p className="font-bold text-blue-400 mb-1">Risk Metrics Explained</p>
          <ul className="space-y-1">
            <li><strong className="text-white">VaR (95%):</strong> Maximum expected 1-day loss with 95% confidence</li>
            <li><strong className="text-white">Drawdown:</strong> Decline from portfolio peak value</li>
            <li><strong className="text-white">Sharpe Ratio:</strong> Risk-adjusted return (greater than 1.5 is good)</li>
            <li><strong className="text-white">Sortino Ratio:</strong> Sharpe with downside deviation only (greater than 2.0 is good)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
