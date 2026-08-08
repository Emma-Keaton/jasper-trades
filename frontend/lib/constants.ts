/**
 * Jasper Trades - Shared frontend constants (source of truth).
 *
 * Centralises runtime endpoints, default exchange priorities and feature flags so
 * components never rely on hardcoded URLs or missing exports. Extend as needed.
 */

// Backend REST API
export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Backend WebSocket base (converted to ws/wss by clients)
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// ---------------------------------------------------------------------------
// Market data: Nigeria-accessible CEX set (priority-ordered). The backend
// geo-probe prunes these to whatever actually works from the deployment region.
// CoinGecko is default; Bybit + Binance are secondary; CoinLore is fallback.
// ---------------------------------------------------------------------------
export const CCXT_EXCHANGES = [
  'bybit',
  'okx',
  'kucoin',
  'gate',
  'htx',
  'bingx',
  'bitget',
  'mexc',
  'kraken',
  'coinbase',
  'bitfinex',
  'bitstamp',
] as const;

export const CCXT_BINANCE_OPT_IN = false;

export const MARKET_DATA_PRIORITY = ['coingecko', 'ccxt', 'coinlore'] as const;

// ---------------------------------------------------------------------------
// Asset classes supported by the execution router.
// ---------------------------------------------------------------------------
export const ASSET_CLASSES = ['crypto', 'forex', 'stocks', 'futures', 'solana'] as const;

// ---------------------------------------------------------------------------
// Feature flags (mirror backend settings so the UI can gate UI elements).
// ---------------------------------------------------------------------------
export const FEATURES = {
  universalPaperTrading: true, // all paper trading routes to the paper engine
  cTraderLive: true,           // cTrader = live forex/stocks only
  solanaMemecoins: true,       // DexScreener discovery + Jupiter execution
  telegramTradeAlerts: true,   // push trade executions to connected Telegram chat
  polymarketProbed: true,      // Polymarket only when geo-probe passes
} as const;

// Default device id used when none is provided by the client.
export const DEFAULT_DEVICE_ID = 'default-device';

// Wallet connection chains supported by the real wallet adapters.
export const WALLET_CHAINS = ['solana', 'ethereum', 'bsc'] as const;
