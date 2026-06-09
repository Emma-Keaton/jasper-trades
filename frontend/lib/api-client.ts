/**
 * Jasper Trades API Client
 * Connects frontend to the FastAPI backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

// Helper function for API calls (exported for extensions)
export async function apiRequest<T>(
  endpoint: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  const url = `${API_URL}${endpoint}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options?.headers,
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

// Copy Trading APIs
export const copyTradeAPI = {
  getLeaderboard: () =>
    apiRequest<any[]>('/api/v1/copy-trading/leaderboard'),
  getStrategies: () => apiRequest<any[]>('/api/v1/copy-trading/strategies'),
  followStrategy: (strategyId: string, allocation: number) =>
    apiRequest<any>('/api/v1/copy-trading/follow', {
      method: 'POST',
      body: JSON.stringify({ strategy_id: strategyId, allocation }),
    }),
  unfollowStrategy: (strategyId: string) =>
    apiRequest<any>('/api/v1/copy-trading/unfollow', {
      method: 'POST',
      body: JSON.stringify({ strategy_id: strategyId }),
    }),
  getMyFollows: () => apiRequest<any[]>('/api/v1/copy-trading/my-follows'),
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
  getFactors: (category?: string) => {
    const params = category ? `?category=${category}` : '';
    return apiRequest<AlphaFactor[]>(`/api/v1/alpha/factors${params}`);
  },
  getFactor: (id: string) =>
    apiRequest<AlphaFactor>(`/api/v1/alpha/factors/${id}`),
  getCategories: () => apiRequest<string[]>('/api/v1/alpha/categories'),
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

// Export API URL for use in components
export { API_URL };