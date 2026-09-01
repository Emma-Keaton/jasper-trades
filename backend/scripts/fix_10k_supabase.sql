-- fix_10k_supabase.sql
-- Safe UPDATE-only script: fixes $100k → $10k without dropping anything
-- Run this on Supabase SQL Editor to fix the HomeScreen balance

-- 1. Fix all portfolios to $10K
UPDATE portfolios SET cash = 10000.0, initial_value = 10000.0, initial_capital = 10000.0;

-- 2. Fix all device_settings paper config to $10K
UPDATE device_settings
SET universal_paper_trading_config = jsonb_set(
  COALESCE(universal_paper_trading_config::jsonb, '{}'),
  '{initial_capital}',
  '10000'
)::text
WHERE universal_paper_trading_config IS NOT NULL;

UPDATE device_settings
SET universal_paper_trading_config = jsonb_set(
  COALESCE(universal_paper_trading_config::jsonb, '{}'),
  '{current_balance}',
  '10000'
)::text
WHERE universal_paper_trading_config IS NOT NULL;

-- 3. Add portfolio_snapshots table (safe to re-run)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              SERIAL PRIMARY KEY,
    portfolio_id    INTEGER NOT NULL REFERENCES portfolios(id),
    device_id       VARCHAR(255) NOT NULL,
    snapshot_date   VARCHAR(10) NOT NULL,
    total_value     DOUBLE PRECISION NOT NULL,
    cash            DOUBLE PRECISION NOT NULL,
    market_value    DOUBLE PRECISION DEFAULT 0.0,
    unrealized_pnl  DOUBLE PRECISION DEFAULT 0.0,
    realized_pnl    DOUBLE PRECISION DEFAULT 0.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(portfolio_id, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_ps_portfolio ON portfolio_snapshots (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_ps_device ON portfolio_snapshots (device_id);
CREATE INDEX IF NOT EXISTS idx_ps_date ON portfolio_snapshots (snapshot_date);
