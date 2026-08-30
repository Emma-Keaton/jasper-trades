/**
 * Jasper Trades API Client
 * Connects frontend to the FastAPI backend
 */

import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { API_URL } from '@/lib/constants';

// Types matching backend schemas
export interface Portfolio {
  id: string;
  name: string;
  cash: number;
  total_value: number;
  is_paper: boolean;
  broker: string;
  created_at: string;
}

export interface Holding {
  symbol: string;
  name: string;
  type: 'Stock' | 'Crypto' | 'Cash';
  shares: number;
  avg_price: number;
  current_price: number;
  pnl_percent: number;
  market_value: number;
}

export interface Trade {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  shares: number;
  price: number;
  total: number;
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  created_at: string;
  filled_at?: string;
}

export interface Signal {
  id: string;
  symbol: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  reason: string;
  agent: string;
  created_at: string;
}

export interface Agent {
  id: string;
  name: string;
  status: 'RUNNING' | 'STOPPED' | 'ERROR';
  latency_ms: number;
  success_rate: number;
  uptime_seconds: number;
  last_update: string;
}

export interface AgentConfig {
  id: string;
  name: string;
  enabled: boolean;
  model: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  max_position_size: number;
  stop_loss_percent: number;
}

export interface BacktestResult {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_value: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
}

export interface AlphaFactor {
  id: string;
  name: string;
  category: string;
  description: string;
  performance: {
    sharpe: number;
    returns: number;
    drawdown: number;
  };
}

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'down';
  agents: string[];
  active_agents: number;
  brokers: string[];
  broker_status: Record<string, any>;
  scheduler: {
    running: boolean;
    tasks: number;
  };
}

// API Response wrapper
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  detail?: string;
}

// Shared fetch wrapper that always attaches the device ID plus content type.
// Use this instead of raw fetch() for one-off backend calls so all
// device-scoped routes (portfolio, watchlist, signals, brokers) work.
export function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_URL}${endpoint}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
    'X-Device-ID': getOrCreateDeviceId(),
  };
  return fetch(url, { ...options, headers });
}

// Helper function for API calls (exported for extensions)
export async function apiRequest<T>(
  endpoint: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_URL}${endpoint}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options?.headers,
    'X-Device-ID': getOrCreateDeviceId(),
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        error: data.detail || data.error || `HTTP ${response.status}`,
        detail: data.detail,
      };
    }

    return { data };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : 'Network error',
    };
  }
}

// Health & Status APIs
export const healthAPI = {
  check: () => apiRequest<SystemStatus>('/api/v1/status'),
  systemTasks: () => apiRequest<any>('/api/v1/system/tasks'),
};

// Portfolio APIs
export const portfolioAPI = {
  getPortfolios: () => apiRequest<Portfolio[]>('/api/v1/portfolio'),
  getPortfolio: (id: string) =>
    apiRequest<Portfolio>(`/api/v1/portfolio/${id}`),
  getHoldings: (portfolioId: string) =>
    apiRequest<Holding[]>(`/api/v1/portfolio/${portfolioId}/holdings`),
  getTrades: (portfolioId: string) =>
    apiRequest<Trade[]>(`/api/v1/portfolio/${portfolioId}/trades`),
  createPortfolio: (data: {
    name: string;
    initial_cash: number;
    is_paper: boolean;
    broker: string;
  }) =>
    apiRequest<Portfolio>('/api/v1/portfolio', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updatePortfolio: (id: string, data: Partial<Portfolio>) =>
    apiRequest<Portfolio>(`/api/v1/portfolio/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};

// Trading APIs
export const tradingAPI = {
  executeTrade: (data: {
    portfolio_id: string;
    symbol: string;
    type: 'BUY' | 'SELL';
    shares: number;
    order_type: 'MARKET' | 'LIMIT';
    limit_price?: number;
  }) =>
    apiRequest<Trade>('/api/v1/trading/execute', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  cancelTrade: (tradeId: string) =>
    apiRequest<Trade>(`/api/v1/trading/${tradeId}/cancel`, {
      method: 'POST',
    }),
  getTradeHistory: (portfolioId?: string) => {
    const params = portfolioId ? `?portfolio_id=${portfolioId}` : '';
    return apiRequest<Trade[]>(`/api/v1/trading/history${params}`);
  },
};

// Signal APIs
export const signalAPI = {
  getSignals: (limit = 50) =>
    apiRequest<Signal[]>(`/api/v1/signals?limit=${limit}`),
  getActiveSignals: () => apiRequest<Signal[]>('/api/v1/signals/active'),
  acknowledgeSignal: (signalId: string) =>
    apiRequest<Signal>(`/api/v1/signals/${signalId}/ack`, {
      method: 'POST',
    }),
  executeFromSignal: (signalId: string) =>
    apiRequest<Trade>(`/api/v1/signals/${signalId}/execute`, {
      method: 'POST',
    }),
};

// Agent APIs
export const agentAPI = {
  getAgents: () => apiRequest<Agent[]>('/api/v1/agents'),
  getAgent: (id: string) => apiRequest<Agent>(`/api/v1/agents/${id}`),
  startAgent: (id: string) =>
    apiRequest<Agent>(`/api/v1/agents/${id}/start`, {
      method: 'POST',
    }),
  stopAgent: (id: string) =>
    apiRequest<Agent>(`/api/v1/agents/${id}/stop`, {
      method: 'POST',
    }),
  getConfig: (id: string) =>
    apiRequest<AgentConfig>(`/api/v1/agents/${id}/config`),
  updateConfig: (id: string, config: Partial<AgentConfig>) =>
    apiRequest<AgentConfig>(`/api/v1/agents/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify(config),
    }),
};

// Signals APIs
export const signalsAPI = {
  getSources: (deviceId: string) =>
    apiRequest<any[]>(`/api/v1/signals/sources`, {
      headers: { 'X-Device-ID': deviceId },
    }),
  createSource: (deviceId: string, payload: any) =>
    apiRequest<any>(`/api/v1/signals/sources`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteSource: (deviceId: string, id: number) =>
    apiRequest<any>(`/api/v1/signals/sources/${id}`, {
      method: 'DELETE',
      headers: { 'X-Device-ID': deviceId },
    }),
  getTips: (deviceId: string) =>
    apiRequest<any[]>(`/api/v1/signals/tips`, {
      headers: { 'X-Device-ID': deviceId },
    }),
  fetchSignals: (deviceId: string) =>
    apiRequest<any>(`/api/v1/signals/fetch`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
    }),
  executeTip: (deviceId: string, tipId: number, payload: any) =>
    apiRequest<any>(`/api/v1/signals/tips/${tipId}/execute`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  telegramAccount: (deviceId: string) =>
    apiRequest<any>(`/api/v1/signals/telegram/account`, {
      headers: { 'X-Device-ID': deviceId },
    }),
  telegramChannels: (deviceId: string, body: any) =>
    apiRequest<any>(`/api/v1/signals/telegram/channels`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  telegramCreateSources: (deviceId: string, channels: any[]) =>
    apiRequest<any>(`/api/v1/signals/telegram/sources`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify({ channels }),
    }),
  followSource: (deviceId: string, sourceId: number) =>
    apiRequest<any>(`/api/v1/signals/follow`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_id: sourceId }),
    }),
  unfollowSource: (deviceId: string, sourceId: number) =>
    apiRequest<any>(`/api/v1/signals/follow/${sourceId}`, {
      method: 'DELETE',
      headers: { 'X-Device-ID': deviceId },
    }),
  resolveTip: (deviceId: string, tipId: number, payload: any) =>
    apiRequest<any>(`/api/v1/signals/tips/${tipId}/resolve`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  telegramStart: (deviceId: string, phone: string) =>
    apiRequest<any>(`/api/v1/signals/telegram/connect/start`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
    }),
  telegramComplete: (deviceId: string, phone: string, code: string, password?: string) =>
    apiRequest<any>(`/api/v1/signals/telegram/connect/complete`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, code, password }),
    }),
  telegramDisconnect: (deviceId: string) =>
    apiRequest<any>(`/api/v1/signals/telegram/disconnect`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId },
    }),
  getSignalSettings: (deviceId: string) =>
    apiRequest<any>(`/api/v1/signals/settings`, {
      headers: { 'X-Device-ID': deviceId },
    }),
  saveSignalSettings: (deviceId: string, payload: any) =>
    apiRequest<any>(`/api/v1/signals/settings`, {
      method: 'POST',
      headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getSignalsStatus: (deviceId: string) =>
    apiRequest<any>(`/api/v1/signals/status`, {
      headers: { 'X-Device-ID': deviceId },
    }),
};

// Backtest APIs
export const backtestAPI = {
  runBacktest: (data: {
    name: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    symbols: string[];
    factors: string[];
    strategy: string;
  }) =>
    apiRequest<{ id: string }>('/api/v1/backtest/run', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getBacktest: (id: string) =>
    apiRequest<BacktestResult>(`/api/v1/backtest/${id}`),
  getBacktestResults: () =>
    apiRequest<BacktestResult[]>('/api/v1/backtest/results'),
  deleteBacktest: (id: string) =>
    apiRequest<void>(`/api/v1/backtest/${id}`, {
      method: 'DELETE',
    }),
};

// Alpha Zoo APIs
export const alphaAPI = {
  getFactors: (category?: string, deviceId?: string) => {
    const params = category ? `?category=${category}` : '';
    return apiRequest<AlphaFactor[]>(`/api/v1/alpha-factors${params}`, {
      headers: deviceId ? { 'X-Device-ID': deviceId } : undefined,
    });
  },
  getFactor: (id: string, deviceId?: string) =>
    apiRequest<AlphaFactor>(`/api/v1/alpha-factors/${id}`, {
      headers: deviceId ? { 'X-Device-ID': deviceId } : undefined,
    }),
  getCategories: (deviceId?: string) =>
    apiRequest<string[]>('/api/v1/alpha-factors/categories', {
      headers: deviceId ? { 'X-Device-ID': deviceId } : undefined,
    }),
};

// Settings API
export const settingsAPI = {
  getSettings: () => apiRequest<any>('/api/v1/settings'),
  updateSettings: (settings: Record<string, any>) =>
    apiRequest<any>('/api/v1/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  validateApiKey: (key: string, service: string) =>
    apiRequest<{ valid: boolean }>('/api/v1/settings/validate-key', {
      method: 'POST',
      body: JSON.stringify({ key, service }),
    }),
};

// ============ QUANTLIB APIs (17 endpoints) ============
export const quantlibAPI = {
  getModules: () => apiRequest<any[]>('/api/v1/quantlib/modules'),
  getBlackScholes: (data: any) =>
    apiRequest('/api/v1/quantlib/options/black-scholes', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getGreeks: (data: any) =>
    apiRequest('/api/v1/quantlib/options/greeks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getBinomialTree: (data: any) =>
    apiRequest('/api/v1/quantlib/options/binomial-tree', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getMonteCarloVaR: (data: any) =>
    apiRequest('/api/v1/quantlib/risk/monte-carlo-var', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getHistoricalVaR: (data: any) =>
    apiRequest('/api/v1/quantlib/risk/historical-var', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getParametricVaR: (data: any) =>
    apiRequest('/api/v1/quantlib/risk/parametric-var', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getCVaR: (data: any) =>
    apiRequest('/api/v1/quantlib/risk/cvar', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getMaxDrawdown: (data: any) =>
    apiRequest('/api/v1/quantlib/risk/max-drawdown', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getSharpe: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/sharpe', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getSortino: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/sortino', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getTreynor: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/treynor', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getInformationRatio: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/information', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getCalmar: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/calmar', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getSterling: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/sterling', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getBurke: (data: any) =>
    apiRequest('/api/v1/quantlib/performance/burke', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getMonteCarloSimulation: (data: any) =>
    apiRequest('/api/v1/quantlib/simulation/monte-carlo', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getHistoricalVolatility: (data: any) =>
    apiRequest('/api/v1/quantlib/volatility/historical', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getStatus: () => apiRequest<any>('/api/v1/quantlib/status'),
};

// ============ POLYMARKET APIs (10 endpoints) ============
export const polymarketAPI = {
  search: (query: string) =>
    apiRequest<any>(`/api/v1/polymarket/search?q=${encodeURIComponent(query)}`),
  getMarket: (slug: string) =>
    apiRequest<any>(`/api/v1/polymarket/market/${encodeURIComponent(slug)}`),
  getByCondition: (conditionId: string) =>
    apiRequest<any>(`/api/v1/polymarket/market/by-condition/${encodeURIComponent(conditionId)}`),
  getOrderbook: (tokenId: string) =>
    apiRequest<any>(`/api/v1/polymarket/orderbook/${encodeURIComponent(tokenId)}`),
  getPrice: (tokenId: string) =>
    apiRequest<any>(`/api/v1/polymarket/price/${encodeURIComponent(tokenId)}`),
  analyze: (slug: string) =>
    apiRequest<any>(`/api/v1/polymarket/analyze/${encodeURIComponent(slug)}`),
  getTrending: () => apiRequest<any[]>('/api/v1/polymarket/trending'),
  getByCategory: (category: string) =>
    apiRequest<any[]>(`/api/v1/polymarket/category/${encodeURIComponent(category)}`),
  getStatus: () => apiRequest<any>('/api/v1/polymarket/status'),
  refreshCache: () =>
    apiRequest('/api/v1/polymarket/cache/refresh', { method: 'POST' }),
};

// ============ SWARM APIs (6 endpoints) ============
export const swarmAPI = {
  run: (data: any) =>
    apiRequest('/api/v1/swarm/run', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  get: (runId: string) => apiRequest<any>(`/api/v1/swarm/${runId}`),
  list: () => apiRequest<any[]>('/api/v1/swarm/list'),
  retry: (runId: string) =>
    apiRequest(`/api/v1/swarm/${runId}/retry`, { method: 'POST' }),
  reapStale: () => apiRequest('/api/v1/swarm/reap-stale', { method: 'POST' }),
  getStatus: () => apiRequest<any>('/api/v1/swarm/status'),
};

// ============ LEARNING APIs (7 endpoints) ============
export const learningAPI = {
  getStatus: () => apiRequest<any>('/api/v1/learning/status'),
  predict: (data: any) =>
    apiRequest('/api/v1/learning/predict', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getWinningPatterns: () => apiRequest<any>('/api/v1/learning/patterns/winning'),
  getLosingPatterns: () => apiRequest<any>('/api/v1/learning/patterns/losing'),
  getExperiences: () => apiRequest<any[]>('/api/v1/learning/experiences'),
  getFeatureImportance: () => apiRequest<any>('/api/v1/learning/feature-importance'),
  retrain: () => apiRequest('/api/v1/learning/retrain', { method: 'POST' }),
  deleteExperiences: () =>
    apiRequest('/api/v1/learning/experiences', { method: 'DELETE' }),
};

// ============ CHECKPOINT APIs (8 endpoints) ============
export const checkpointAPI = {
  enable: (ticker: string) =>
    apiRequest(`/api/v1/checkpoint/enable`, {
      method: 'POST',
      body: JSON.stringify({ ticker }),
    }),
  disable: (ticker: string) =>
    apiRequest(`/api/v1/checkpoint/disable`, {
      method: 'POST',
      body: JSON.stringify({ ticker }),
    }),
  getStatus: (ticker: string) =>
    apiRequest<any>(`/api/v1/checkpoint/status/${ticker}`),
  list: () => apiRequest<any[]>('/api/v1/checkpoint/list'),
  clear: (ticker: string) =>
    apiRequest(`/api/v1/checkpoint/clear/${ticker}`, { method: 'POST' }),
  clearAll: () => apiRequest('/api/v1/checkpoint/clear-all', { method: 'POST' }),
  resume: (ticker: string) =>
    apiRequest(`/api/v1/checkpoint/resume/${ticker}`, { method: 'POST' }),
  save: (data: any) =>
    apiRequest('/api/v1/checkpoint/save', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  cleanup: () => apiRequest('/api/v1/checkpoint/cleanup', { method: 'POST' }),
  getStatusAll: () => apiRequest<any>('/api/v1/checkpoint/status'),
};

// ============ ENSEMBLE APIs (6 endpoints) ============
export const ensembleAPI = {
  predict: (data: any) =>
    apiRequest('/api/v1/ensemble/predict', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getModels: () => apiRequest<any[]>('/api/v1/ensemble/models'),
  updateAccuracy: (data: any) =>
    apiRequest('/api/v1/ensemble/accuracy/update', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getPerformance: () => apiRequest<any>('/api/v1/ensemble/performance'),
  getStatus: () => apiRequest<any>('/api/v1/ensemble/status'),
  compare: () => apiRequest<any>('/api/v1/ensemble/compare'),
};

// ============ DEBATE APIs (4 endpoints) ============
export const debateAPI = {
  analyze: (data: any) =>
    apiRequest('/api/v1/debate/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  recordOutcome: (data: any) =>
    apiRequest('/api/v1/debate/outcome/record', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getWinRate: (ticker: string) =>
    apiRequest<any>(`/api/v1/debate/win-rate/${ticker}`),
  getStatus: () => apiRequest<any>('/api/v1/debate/status'),
};

// ============ SYSTEM APIs (3 endpoints) ============
export const systemAPI = {
  getKronosStats: () => apiRequest<any>('/api/v1/system/kronos/stats'),
  getStatus: () => apiRequest<any>('/api/v1/system/status'),
  getMarketData: () => apiRequest<any>('/api/v1/system/market-data'),
};

export { API_URL };
