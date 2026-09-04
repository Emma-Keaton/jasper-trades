-- jasper-trades DB Reset Script (PostgreSQL / Supabase)
-- Purpose: Drop all tables, recreate fresh schema, seed paper capital = $10,000
-- Target: Supabase PostgreSQL
--
-- WARNING: This drops ALL tables. Use the UPDATE-only version below if you want to keep data.

-- ============================================================
-- DROP ALL TABLES ( CASCADE handles foreign keys)
-- ============================================================
DROP TABLE IF EXISTS portfolio_snapshots CASCADE;
DROP TABLE IF EXISTS checkpoints CASCADE;
DROP TABLE IF EXISTS seq_predictions CASCADE;
DROP TABLE IF EXISTS predictions CASCADE;
DROP TABLE IF EXISTS watchlist_items CASCADE;
DROP TABLE IF EXISTS source_follows CASCADE;
DROP TABLE IF EXISTS signal_settings CASCADE;
DROP TABLE IF EXISTS signal_tips CASCADE;
DROP TABLE IF EXISTS telegram_accounts CASCADE;
DROP TABLE IF EXISTS signal_sources CASCADE;
DROP TABLE IF EXISTS telegram_users CASCADE;
DROP TABLE IF EXISTS daily_summaries CASCADE;
DROP TABLE IF EXISTS trading_caps CASCADE;
DROP TABLE IF EXISTS copy_trades CASCADE;
DROP TABLE IF EXISTS follows CASCADE;
DROP TABLE IF EXISTS challenge_trades CASCADE;
DROP TABLE IF EXISTS challenge_participants CASCADE;
DROP TABLE IF EXISTS challenges CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS signals_enhanced CASCADE;
DROP TABLE IF EXISTS decision_logs CASCADE;
DROP TABLE IF EXISTS risk_snapshots CASCADE;
DROP TABLE IF EXISTS withdrawals CASCADE;
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS device_settings CASCADE;
DROP TABLE IF EXISTS memories CASCADE;
DROP TABLE IF EXISTS user_preferences CASCADE;
DROP TABLE IF EXISTS backtest_results CASCADE;
DROP TABLE IF EXISTS agents CASCADE;
DROP TABLE IF EXISTS positions CASCADE;
DROP TABLE IF EXISTS portfolios CASCADE;
DROP TABLE IF EXISTS signals CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS token_refresh_logs CASCADE;
DROP TABLE IF EXISTS execution_logs CASCADE;
DROP TABLE IF EXISTS trading_accounts CASCADE;
DROP TABLE IF EXISTS broker_connections CASCADE;

-- ============================================================
-- RECREATE ALL TABLES
-- Paper capital default = 10000.0 ($10K)
-- ============================================================

-- ── trades ─────────────────────────────────────────────────
CREATE TABLE trades (
    id            SERIAL PRIMARY KEY,
    symbol        VARCHAR(32) NOT NULL,
    side          VARCHAR(10) NOT NULL,
    quantity      DOUBLE PRECISION NOT NULL,
    price         DOUBLE PRECISION,
    order_type    VARCHAR(20) DEFAULT 'market',
    status        VARCHAR(20) DEFAULT 'pending',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    broker        VARCHAR(50),
    broker_order_id VARCHAR(100),
    agent_name    VARCHAR(100),
    signal_id     VARCHAR(100),
    entry_price   DOUBLE PRECISION,
    exit_price    DOUBLE PRECISION,
    pnl           DOUBLE PRECISION,
    pnl_percent   DOUBLE PRECISION
);

-- ── signals ────────────────────────────────────────────────
CREATE TABLE signals (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(32) NOT NULL,
    action      VARCHAR(10) NOT NULL,
    strength    DOUBLE PRECISION,
    agent_name  VARCHAR(100) NOT NULL,
    reasoning   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    metadata    JSONB,
    is_public   BOOLEAN DEFAULT true,
    copied_by   INTEGER DEFAULT 0
);

-- ── portfolios ─────────────────────────────────────────────
CREATE TABLE portfolios (
    id              SERIAL PRIMARY KEY,
    device_id       VARCHAR(255) NOT NULL,
    name            VARCHAR(100) DEFAULT 'Default',
    cash            DOUBLE PRECISION DEFAULT 10000.0,
    initial_value   DOUBLE PRECISION DEFAULT 10000.0,
    initial_capital DOUBLE PRECISION DEFAULT 10000.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    is_paper        BOOLEAN DEFAULT true,
    broker          VARCHAR(50),
    is_active       BOOLEAN DEFAULT true
);
CREATE INDEX idx_portfolios_device ON portfolios (device_id);

-- ── positions ──────────────────────────────────────────────
CREATE TABLE positions (
    id                        SERIAL PRIMARY KEY,
    portfolio_id              INTEGER REFERENCES portfolios(id),
    symbol                    VARCHAR(32) NOT NULL,
    quantity                  DOUBLE PRECISION DEFAULT 0,
    avg_price                 DOUBLE PRECISION DEFAULT 0,
    current_price             DOUBLE PRECISION,
    market_value              DOUBLE PRECISION,
    unrealized_pnl            DOUBLE PRECISION,
    unrealized_pnl_percent    DOUBLE PRECISION,
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

-- ── portfolio_snapshots ────────────────────────────────────
CREATE TABLE portfolio_snapshots (
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
CREATE INDEX idx_ps_portfolio ON portfolio_snapshots (portfolio_id);
CREATE INDEX idx_ps_device ON portfolio_snapshots (device_id);
CREATE INDEX idx_ps_date ON portfolio_snapshots (snapshot_date);

-- ── agents ─────────────────────────────────────────────────
CREATE TABLE agents (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL UNIQUE,
    type          VARCHAR(50),
    model         VARCHAR(200),
    is_active     BOOLEAN DEFAULT false,
    config        JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    total_signals INTEGER DEFAULT 0,
    win_rate      DOUBLE PRECISION,
    total_pnl     DOUBLE PRECISION
);

-- ── backtest_results ───────────────────────────────────────
CREATE TABLE backtest_results (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200),
    strategy        VARCHAR(100),
    symbol          VARCHAR(32),
    start_date      TIMESTAMPTZ,
    end_date        TIMESTAMPTZ,
    initial_capital DOUBLE PRECISION,
    final_capital   DOUBLE PRECISION,
    total_return    DOUBLE PRECISION,
    sharpe_ratio    DOUBLE PRECISION,
    max_drawdown    DOUBLE PRECISION,
    win_rate        DOUBLE PRECISION,
    config          JSONB,
    trades          JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── user_preferences ───────────────────────────────────────
CREATE TABLE user_preferences (
    id         SERIAL PRIMARY KEY,
    key        VARCHAR(200) NOT NULL UNIQUE,
    value      JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── memories ───────────────────────────────────────────────
CREATE TABLE memories (
    id           SERIAL PRIMARY KEY,
    session_id   VARCHAR(100),
    content      TEXT NOT NULL,
    category     VARCHAR(100),
    importance   DOUBLE PRECISION DEFAULT 0.5,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── device_settings ────────────────────────────────────────
CREATE TABLE device_settings (
    device_id                              VARCHAR(255) PRIMARY KEY,
    nvidia_key                             VARCHAR(500),
    binance_key                            VARCHAR(500),
    binance_secret                         VARCHAR(500),
    solana_rpc_url                         VARCHAR(500),
    jupiter_enabled                        BOOLEAN DEFAULT false,
    ctrader_sandbox                        BOOLEAN DEFAULT true,
    discord_config                         TEXT,
    slack_config                           TEXT,
    email_config                           TEXT,
    telegram_config                        TEXT,
    whatsapp_config                        TEXT,
    broker_paper_trading_config            TEXT,
    universal_paper_trading_config         TEXT,
    trading_mode                           VARCHAR(10) DEFAULT 'practice',
    preferences                            TEXT,
    alphavantage_key                       VARCHAR(500),
    finnhub_key                            VARCHAR(500),
    twelvedata_key                         VARCHAR(500),
    polygon_key                            VARCHAR(500),
    fred_key                               VARCHAR(500),
    coingecko_enabled                      BOOLEAN DEFAULT true,
    newsapi_key                            VARCHAR(500),
    cryptopanic_key                        VARCHAR(500),
    av_news_sentiment_enabled              BOOLEAN DEFAULT true,
    sendgrid_config                        TEXT,
    discord_bot_config                     TEXT,
    environment_mode                       VARCHAR(20) DEFAULT 'sandbox',
    nvidia_model                           VARCHAR(200) DEFAULT 'nvidia/nemotron-mini-4b-instruct',
    default_brokers                        VARCHAR(200),
    routing_mode                           VARCHAR(50) DEFAULT 'asset_class',
    payout_config                          TEXT,
    tatum_api_key                          VARCHAR(500),
    trove_api_key                          VARCHAR(500),
    trove_base_url                         VARCHAR(500),
    trove_enabled                          BOOLEAN DEFAULT false,
    trove_account_id                       VARCHAR(200),
    trove_sandbox                          BOOLEAN DEFAULT true,
    tiger_id                               VARCHAR(200),
    tiger_api_key                          VARCHAR(500),
    tiger_private_key                      VARCHAR(500),
    tiger_enabled                          BOOLEAN DEFAULT false,
    akshare_config                         TEXT,
    akshare_sandbox                        BOOLEAN DEFAULT true,
    default_currency                       VARCHAR(3) DEFAULT 'USD',
    currency_conversion_enabled            BOOLEAN DEFAULT true,
    naira_bank_details                     TEXT,
    created_at                             TIMESTAMPTZ DEFAULT NOW(),
    updated_at                             TIMESTAMPTZ DEFAULT NOW()
);

-- ── chat_messages ──────────────────────────────────────────
CREATE TABLE chat_messages (
    id            SERIAL PRIMARY KEY,
    phone_number  VARCHAR(50) NOT NULL,
    message       TEXT NOT NULL,
    direction     VARCHAR(20) NOT NULL,
    message_type  VARCHAR(20) DEFAULT 'text',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    intent        VARCHAR(100),
    response_to_id INTEGER REFERENCES chat_messages(id)
);

-- ── withdrawals ────────────────────────────────────────────
CREATE TABLE withdrawals (
    id                   SERIAL PRIMARY KEY,
    portfolio_id         INTEGER REFERENCES portfolios(id),
    amount               DOUBLE PRECISION NOT NULL,
    currency             VARCHAR(3) DEFAULT 'USD',
    withdrawal_type      VARCHAR(50) NOT NULL,
    destination_type     VARCHAR(50),
    destination_address  VARCHAR(200),
    status               VARCHAR(20) DEFAULT 'pending',
    transaction_hash     VARCHAR(200),
    fee                  DOUBLE PRECISION DEFAULT 0.0,
    net_amount           DOUBLE PRECISION,
    daily_pnl            DOUBLE PRECISION,
    payout_percentage    DOUBLE PRECISION DEFAULT 50.0,
    requested_at         TIMESTAMPTZ DEFAULT NOW(),
    processed_at         TIMESTAMPTZ,
    error_message        TEXT
);

-- ── risk_snapshots ─────────────────────────────────────────
CREATE TABLE risk_snapshots (
    id             SERIAL PRIMARY KEY,
    portfolio_id   INTEGER REFERENCES portfolios(id),
    var_95         DOUBLE PRECISION,
    max_drawdown   DOUBLE PRECISION,
    sharpe_ratio   DOUBLE PRECISION,
    sortino_ratio  DOUBLE PRECISION,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ── decision_logs ──────────────────────────────────────────
CREATE TABLE decision_logs (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,
    action          VARCHAR(10) NOT NULL,
    reasoning       TEXT,
    confidence      DOUBLE PRECISION,
    agent_name      VARCHAR(100) DEFAULT 'Director',
    context         JSONB,
    status          VARCHAR(20) DEFAULT 'pending',
    realized_return DOUBLE PRECISION,
    reflection      TEXT,
    portfolio_id    INTEGER DEFAULT 1 REFERENCES portfolios(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── signals_enhanced ───────────────────────────────────────
CREATE TABLE signals_enhanced (
    id                    SERIAL PRIMARY KEY,
    agent_id              INTEGER NOT NULL REFERENCES agents(id),
    agent_name            VARCHAR(100) NOT NULL,
    message_type          VARCHAR(32) NOT NULL,
    market                VARCHAR(32),
    symbol                VARCHAR(32),
    action                VARCHAR(10),
    price                 DOUBLE PRECISION,
    quantity              DOUBLE PRECISION,
    side                  VARCHAR(10),
    title                 VARCHAR(200),
    content               TEXT,
    tags                  VARCHAR(500),
    reply_count           INTEGER DEFAULT 0,
    participant_count     INTEGER DEFAULT 0,
    is_following_author   BOOLEAN DEFAULT false,
    signal_data           JSONB,
    is_public             BOOLEAN DEFAULT true,
    executed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ── subscriptions ──────────────────────────────────────────
CREATE TABLE subscriptions (
    id               SERIAL PRIMARY KEY,
    follower_agent_id INTEGER NOT NULL REFERENCES agents(id),
    leader_agent_id  INTEGER NOT NULL REFERENCES agents(id),
    status           VARCHAR(20) DEFAULT 'active',
    copied_count     INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── challenges ─────────────────────────────────────────────
CREATE TABLE challenges (
    id              SERIAL PRIMARY KEY,
    challenge_key   VARCHAR(100) NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    market          VARCHAR(32),
    track           VARCHAR(32),
    symbol          VARCHAR(32),
    variant_key     VARCHAR(50),
    start_at        TIMESTAMPTZ,
    end_at          TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'upcoming',
    scoring_method  VARCHAR(50) DEFAULT 'return_pct',
    starting_cash   DOUBLE PRECISION DEFAULT 1000.0,
    max_position_size DOUBLE PRECISION,
    max_drawdown    DOUBLE PRECISION,
    rules           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── challenge_participants ─────────────────────────────────
CREATE TABLE challenge_participants (
    id               SERIAL PRIMARY KEY,
    challenge_id     INTEGER NOT NULL REFERENCES challenges(id),
    agent_id         INTEGER NOT NULL REFERENCES agents(id),
    return_pct       DOUBLE PRECISION DEFAULT 0.0,
    max_drawdown     DOUBLE PRECISION DEFAULT 0.0,
    risk_adjusted_score DOUBLE PRECISION DEFAULT 0.0,
    final_score      DOUBLE PRECISION DEFAULT 0.0,
    trade_count      INTEGER DEFAULT 0,
    rank             INTEGER,
    disqualified_reason VARCHAR(500),
    starting_cash    DOUBLE PRECISION DEFAULT 1000.0,
    current_cash     DOUBLE PRECISION DEFAULT 1000.0,
    portfolio_value  DOUBLE PRECISION DEFAULT 1000.0,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── challenge_trades ───────────────────────────────────────
CREATE TABLE challenge_trades (
    id             SERIAL PRIMARY KEY,
    challenge_id   INTEGER NOT NULL REFERENCES challenges(id),
    participant_id INTEGER NOT NULL REFERENCES challenge_participants(id),
    agent_id       INTEGER NOT NULL REFERENCES agents(id),
    side           VARCHAR(10) NOT NULL,
    symbol         VARCHAR(32) NOT NULL,
    price          DOUBLE PRECISION NOT NULL,
    quantity       DOUBLE PRECISION NOT NULL,
    content        TEXT,
    cash_before    DOUBLE PRECISION,
    cash_after     DOUBLE PRECISION,
    executed_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ── follows ────────────────────────────────────────────────
CREATE TABLE follows (
    id              SERIAL PRIMARY KEY,
    follower_id     INTEGER NOT NULL REFERENCES portfolios(id),
    leader_id       VARCHAR(100) NOT NULL,
    leader_type     VARCHAR(20) DEFAULT 'agent',
    copy_percentage DOUBLE PRECISION DEFAULT 100.0,
    max_position_size DOUBLE PRECISION DEFAULT 10000.0,
    auto_copy       BOOLEAN DEFAULT true,
    active          BOOLEAN DEFAULT true,
    paused_at       TIMESTAMPTZ,
    signals_copied  INTEGER DEFAULT 0,
    total_pnl       DOUBLE PRECISION DEFAULT 0.0,
    followed_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── copy_trades ────────────────────────────────────────────
CREATE TABLE copy_trades (
    id               SERIAL PRIMARY KEY,
    follow_id        INTEGER NOT NULL REFERENCES follows(id),
    original_signal_id INTEGER NOT NULL REFERENCES signals(id),
    resulting_trade_id INTEGER REFERENCES trades(id),
    copy_percentage  DOUBLE PRECISION NOT NULL,
    original_quantity DOUBLE PRECISION NOT NULL,
    copied_quantity  DOUBLE PRECISION NOT NULL,
    pnl              DOUBLE PRECISION DEFAULT 0.0,
    pnl_percent      DOUBLE PRECISION DEFAULT 0.0,
    copied_at        TIMESTAMPTZ DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── trading_caps ───────────────────────────────────────────
CREATE TABLE trading_caps (
    id                        SERIAL PRIMARY KEY,
    portfolio_id              INTEGER NOT NULL REFERENCES portfolios(id),
    max_position_amount       DOUBLE PRECISION,
    max_position_percentage   DOUBLE PRECISION,
    daily_loss_limit          DOUBLE PRECISION,
    daily_loss_percentage     DOUBLE PRECISION,
    hard_limit                BOOLEAN DEFAULT true,
    soft_limit_enabled        BOOLEAN DEFAULT false,
    enabled                   BOOLEAN DEFAULT true,
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

-- ── daily_summaries ────────────────────────────────────────
CREATE TABLE daily_summaries (
    id               SERIAL PRIMARY KEY,
    portfolio_id     INTEGER NOT NULL REFERENCES portfolios(id),
    device_id        VARCHAR(255) NOT NULL,
    chat_id          VARCHAR(100) NOT NULL,
    summary_date     VARCHAR(10) NOT NULL,
    total_pnl        DOUBLE PRECISION DEFAULT 0.0,
    total_pnl_percent DOUBLE PRECISION DEFAULT 0.0,
    total_trades     INTEGER DEFAULT 0,
    wins             INTEGER DEFAULT 0,
    losses           INTEGER DEFAULT 0,
    breakeven        INTEGER DEFAULT 0,
    win_rate         DOUBLE PRECISION DEFAULT 0.0,
    best_trade       JSONB,
    worst_trade      JSONB,
    agent_stats      JSONB,
    top_symbols      JSONB,
    summary_sent     BOOLEAN DEFAULT false,
    sent_at          TIMESTAMPTZ,
    send_time_wat    VARCHAR(10) DEFAULT '20:00',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ds_device ON daily_summaries (device_id);
CREATE INDEX idx_ds_chat ON daily_summaries (chat_id);
CREATE INDEX idx_ds_date ON daily_summaries (summary_date);

-- ── telegram_users ─────────────────────────────────────────
CREATE TABLE telegram_users (
    id                          SERIAL PRIMARY KEY,
    device_id                   VARCHAR(255) NOT NULL UNIQUE,
    chat_id                     VARCHAR(100) NOT NULL,
    trade_notifications_enabled BOOLEAN DEFAULT true,
    daily_summary_enabled       BOOLEAN DEFAULT true,
    summary_time_wat            VARCHAR(10) DEFAULT '20:00',
    chat_enabled                BOOLEAN DEFAULT true,
    ai_explanations_enabled     BOOLEAN DEFAULT true,
    is_verified                 BOOLEAN DEFAULT false,
    verification_code           VARCHAR(50),
    verification_expires_at     TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    last_active_at              TIMESTAMPTZ
);
CREATE INDEX idx_tg_user_device ON telegram_users (device_id);

-- ── signal_sources ─────────────────────────────────────────
CREATE TABLE signal_sources (
    id                       SERIAL PRIMARY KEY,
    device_id                VARCHAR(255) NOT NULL,
    source_type              VARCHAR(64) NOT NULL,
    config                   JSONB NOT NULL DEFAULT '{}',
    display_name             VARCHAR(255) NOT NULL,
    is_active                BOOLEAN DEFAULT true,
    fetch_interval_minutes   INTEGER DEFAULT 30,
    last_fetched_at          TIMESTAMPTZ,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ss_device ON signal_sources (device_id);

-- ── telegram_accounts ──────────────────────────────────────
CREATE TABLE telegram_accounts (
    id           SERIAL PRIMARY KEY,
    device_id    VARCHAR(255) NOT NULL UNIQUE,
    tg_phone     VARCHAR(64) NOT NULL,
    tg_session   TEXT,
    tg_user_id   VARCHAR(64),
    tg_username  VARCHAR(128),
    tg_first_name VARCHAR(128),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ta_device ON telegram_accounts (device_id);

-- ── signal_tips ────────────────────────────────────────────
CREATE TABLE signal_tips (
    id                SERIAL PRIMARY KEY,
    device_id         VARCHAR(255) NOT NULL,
    source_id         INTEGER NOT NULL REFERENCES signal_sources(id),
    slug              VARCHAR(255) NOT NULL,
    symbol            VARCHAR(64) NOT NULL,
    side              VARCHAR(16) NOT NULL,
    timeframe         VARCHAR(16),
    confidence        DOUBLE PRECISION DEFAULT 0.0,
    rationale         VARCHAR(500),
    text              TEXT,
    url               VARCHAR(500),
    source_created_at TIMESTAMPTZ,
    entry_price       DOUBLE PRECISION,
    exit_price        DOUBLE PRECISION,
    pnl               DOUBLE PRECISION,
    pnl_percent       DOUBLE PRECISION,
    hit               BOOLEAN,
    executed          BOOLEAN DEFAULT false,
    execution_status  VARCHAR(32) DEFAULT 'pending',
    execution_detail  VARCHAR(500),
    executed_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_st_device ON signal_tips (device_id);
CREATE INDEX idx_st_slug ON signal_tips (slug);

-- ── signal_settings ────────────────────────────────────────
CREATE TABLE signal_settings (
    device_id           VARCHAR(255) PRIMARY KEY,
    auto_execute_enabled BOOLEAN DEFAULT true,
    min_confidence      DOUBLE PRECISION DEFAULT 0.60,
    max_position_pct    DOUBLE PRECISION DEFAULT 0.05,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── source_follows ─────────────────────────────────────────
CREATE TABLE source_follows (
    id         SERIAL PRIMARY KEY,
    device_id  VARCHAR(255) NOT NULL,
    source_id  INTEGER NOT NULL REFERENCES signal_sources(id),
    active     BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sf_device ON source_follows (device_id);

-- ── watchlist_items ────────────────────────────────────────
CREATE TABLE watchlist_items (
    id          SERIAL PRIMARY KEY,
    device_id   VARCHAR(255) NOT NULL,
    symbol      VARCHAR(32) NOT NULL,
    name        VARCHAR(128),
    asset_class VARCHAR(32) DEFAULT 'crypto',
    source      VARCHAR(64),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_wl_device ON watchlist_items (device_id);

-- ── broker_connections ─────────────────────────────────────
CREATE TABLE broker_connections (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL,
    broker_type          VARCHAR(20) NOT NULL,
    broker_name          VARCHAR(100),
    account_id           VARCHAR(100),
    account_currency     VARCHAR(3) DEFAULT 'USD',
    account_balance      DOUBLE PRECISION DEFAULT 0.0,
    ctrader_account_id   VARCHAR(100),
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    token_expires_at     TIMESTAMPTZ,
    encrypted_api_key    TEXT,
    encrypted_api_secret TEXT,
    is_active            BOOLEAN DEFAULT true,
    is_connected         BOOLEAN DEFAULT false,
    connection_status    VARCHAR(50),
    last_sync_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bc_user ON broker_connections (user_id);
CREATE INDEX idx_bc_type ON broker_connections (broker_type, is_connected, is_active);

-- ── trading_accounts ───────────────────────────────────────
CREATE TABLE trading_accounts (
    id                        SERIAL PRIMARY KEY,
    user_id                   INTEGER NOT NULL,
    account_type              VARCHAR(20) NOT NULL DEFAULT 'ctrader',
    ctid_trader_account_id    VARCHAR(50),
    ctid_account_name         VARCHAR(100),
    encrypted_access_token    TEXT,
    encrypted_refresh_token   TEXT,
    token_expires_at          TIMESTAMPTZ,
    token_last_refreshed      TIMESTAMPTZ,
    broker_name               VARCHAR(50),
    account_currency          VARCHAR(3) DEFAULT 'USD',
    account_leverage          DOUBLE PRECISION DEFAULT 1.0,
    account_balance           DOUBLE PRECISION DEFAULT 0.0,
    account_equity            DOUBLE PRECISION DEFAULT 0.0,
    is_active                 BOOLEAN DEFAULT true,
    is_connected              BOOLEAN DEFAULT false,
    connection_status         VARCHAR(50),
    last_sync_at              TIMESTAMPTZ,
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ta_user ON trading_accounts (user_id);
CREATE INDEX idx_ta_active ON trading_accounts (is_active, is_connected);

-- ── execution_logs ─────────────────────────────────────────
CREATE TABLE execution_logs (
    id                  SERIAL PRIMARY KEY,
    trading_account_id  INTEGER NOT NULL REFERENCES trading_accounts(id),
    strategy_name       VARCHAR(100),
    action_type         VARCHAR(20),
    symbol              VARCHAR(20),
    volume              DOUBLE PRECISION,
    execution_price     DOUBLE PRECISION,
    cTrader_order_id    VARCHAR(50),
    status              VARCHAR(20),
    error_message       TEXT,
    execution_time_ms   INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── token_refresh_logs ─────────────────────────────────────
CREATE TABLE token_refresh_logs (
    id                      SERIAL PRIMARY KEY,
    trading_account_id      INTEGER NOT NULL REFERENCES trading_accounts(id),
    old_token_expires_at    TIMESTAMPTZ,
    new_token_expires_at    TIMESTAMPTZ,
    refresh_successful      BOOLEAN,
    error_message           TEXT,
    refreshed_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SEED: Insert default portfolio with $10K paper capital
-- ============================================================
INSERT INTO portfolios (device_id, name, cash, initial_value, initial_capital, is_paper, is_active)
VALUES ('__system__', 'System Paper Portfolio', 10000.0, 10000.0, 10000.0, true, true)
ON CONFLICT DO NOTHING;

-- ============================================================
-- SEED: Insert default device settings with $10K paper config
-- ============================================================
INSERT INTO device_settings (device_id, trading_mode, environment_mode, universal_paper_trading_config)
VALUES ('__system__', 'practice', 'sandbox',
        '{"enabled": true, "initial_capital": 10000.0, "current_balance": 10000.0, "total_pnl": 0.0, "currency": "USD"}')
ON CONFLICT (device_id) DO NOTHING;
