/**
 * Jasper Trades API Client - Extension
 * Exness, Trading Caps, and additional endpoints
 */

import { API_URL, apiRequest } from './api-client';

// ============ Exness Types ============

export interface ExnessAccountStatus {
  linked: boolean;
  configured: boolean;
  login_id?: string;
  server?: string;
  enabled?: boolean;
  is_connected?: boolean;
  balance?: number;
  equity?: number;
  margin?: number;
  free_margin?: number;
  currency?: string;
  last_sync_at?: string;
}

export interface ExnessSymbol {
  symbol: string;
  name: string;
  type: string;
  min_volume: number;
  max_volume: number;
  volume_step: number;
  spread: number;
}

export interface ExnessPosition {
  ticket: number;
  symbol: string;
  type: 'buy' | 'sell';
  volume: number;
  price_open: number;
  price_current: number;
  sl?: number;
  tp?: number;
  profit: number;
  time: string;
}

export interface ExnessTradeRequest {
  symbol: string;
  type: 'buy' | 'sell';
  volume: number;
  sl?: number;
  tp?: number;
  comment?: string;
}

export interface LinkExnessRequest {
  portfolio_id: number;
  login_id: string;
  server: string;
  password: string;
  investor_password?: string;
  broker_name?: string;
}

// ============ Trading Caps Types ============

export interface TradingCaps {
  configured: boolean;
  portfolio_id: number;
  max_position_amount?: number;
  max_position_percentage?: number;
  daily_loss_limit?: number;
  daily_loss_percentage?: number;
  hard_limit: boolean;
  soft_limit_enabled: boolean;
  enabled: boolean;
}

export interface TradingCapRequest {
  portfolio_id: number;
  max_position_amount?: number;
  max_position_percentage?: number;
  daily_loss_limit?: number;
  daily_loss_percentage?: number;
  hard_limit?: boolean;
  soft_limit_enabled?: boolean;
}

export interface TradeValidationResult {
  valid: boolean;
  exceeded?: string;
  limit?: number;
  proposed?: number;
  calculated_percentage?: number;
  message: string;
  hard_limit?: boolean;
}

// ============ Exness APIs ============

export const exnessAPI = {
  /**
   * Link Exness MT5 account
   */
  linkAccount: (data: LinkExnessRequest) =>
    apiRequest<{ success: boolean; account_id: string; server: string }>(
      '/api/v1/exness/account/link',
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  /**
   * Get Exness account status
   */
  getStatus: (portfolioId: number) =>
    apiRequest<ExnessAccountStatus>(
      `/api/v1/exness/account/status?portfolio_id=${portfolioId}`
    ),

  /**
   * Sync Exness account data (balance, equity, positions)
   */
  syncAccount: (portfolioId: number) =>
    apiRequest<{
      success: boolean;
      balance: number;
      equity: number;
      margin: number;
      free_margin: number;
      is_connected: boolean;
    }>(`/api/v1/exness/account/sync?portfolio_id=${portfolioId}`, {
      method: 'POST',
    }),

  /**
   * Get open positions
   */
  getPositions: (portfolioId: number) =>
    apiRequest<{ positions: ExnessPosition[]; count: number }>(
      `/api/v1/exness/positions?portfolio_id=${portfolioId}`
    ),

  /**
   * Get available trading symbols
   */
  getSymbols: () =>
    apiRequest<{ symbols: ExnessSymbol[]; count: number }>(
      '/api/v1/exness/symbols'
    ),

  /**
   * Execute trade on Exness
   */
  executeTrade: (portfolioId: number, data: ExnessTradeRequest) =>
    apiRequest<{
      success: boolean;
      ticket: number;
      symbol: string;
      type: string;
      volume: number;
      price: number;
    }>(`/api/v1/exness/trade?portfolio_id=${portfolioId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /**
   * Close position
   */
  closePosition: (portfolioId: number, positionId: number) =>
    apiRequest<{ success: boolean; deal?: number }>(
      `/api/v1/exness/position/close/${positionId}`,
      {
        method: 'POST',
      }
    ),

  /**
   * Request withdrawal to Exness
   */
  requestWithdrawal: (portfolioId: number, amount: number, destination_address?: string) =>
    apiRequest<{
      success: boolean;
      withdrawal_id: number;
      amount: number;
      fee: number;
      net_amount: number;
      status: string;
    }>(`/api/v1/exness/withdraw`, {
      method: 'POST',
      body: JSON.stringify({
        portfolio_id: portfolioId,
        amount,
        destination_address,
      }),
    }),
};

// ============ Trading Caps APIs ============

export const tradingCapsAPI = {
  /**
   * Get trading caps for portfolio
   */
  getCaps: (portfolioId: number) =>
    apiRequest<TradingCaps>(
      `/api/v1/trading-caps?portfolio_id=${portfolioId}`
    ),

  /**
   * Set/update trading caps
   */
  setCaps: (data: TradingCapRequest) =>
    apiRequest<{
      success: boolean;
      portfolio_id: number;
      max_position_amount?: number;
      max_position_percentage?: number;
      daily_loss_limit?: number;
      daily_loss_percentage?: number;
      hard_limit: boolean;
      soft_limit_enabled: boolean;
    }>('/api/v1/trading-caps', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /**
   * Disable trading caps
   */
  disableCaps: (portfolioId: number) =>
    apiRequest<{ success: boolean; message: string }>(
      `/api/v1/trading-caps?portfolio_id=${portfolioId}`,
      {
        method: 'DELETE',
      }
    ),

  /**
   * Validate trade against caps (before execution)
   */
  validateTrade: (portfolioId: number, positionAmount: number) =>
    apiRequest<TradeValidationResult>(
      `/api/v1/trading-caps/validate?portfolio_id=${portfolioId}&position_amount=${positionAmount}`
    ),

  /**
   * Get today's PnL (for daily loss limit checking)
   */
  getDailyPnL: (portfolioId: number) =>
    apiRequest<{
      portfolio_id: number;
      date: string;
      daily_pnl: number;
      daily_pnl_formatted: string;
    }>(`/api/v1/trading-caps/daily-pnl?portfolio_id=${portfolioId}`),
};

// Re-export main API client for convenience
export * from './api-client';