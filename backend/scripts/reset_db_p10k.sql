-- jasper-trades DB Reset Script
-- Purpose: Drop all tables, recreate fresh schema, seed paper capital = $10,000
-- Target: SQLite main database (backend/test.db) or Supabase Postgres
--
-- Paper capital changed from $100,000 → $10,000 across:
--   portfolios.initial_capital, portfolios.cash, portfolios.initial_value defaults
--   device_settings.universal_paper_trading_config JSON default
--
-- Usage:
--   sqlite3 backend/test.db < reset_db_p10k.sql
--   # or inside python:
--   import sqlite3; c = sqlite3.connect("backend/test.db"); c.executescript(open("reset_db_p10k.sql").read()); c.commit()

PRAGMA foreign_keys = OFF;

-- ============================================================
-- DROP ALL TABLES (foreign-key order reversed)
-- ============================================================
DROP TABLE IF EXISTS portfolio_snapshots;
DROP TABLE IF EXISTS checkpoints;
DROP TABLE IF EXISTS seq_predictions;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS watchlist_items;
DROP TABLE IF EXISTS source_follows;
DROP TABLE IF EXISTS signal_settings;
DROP TABLE IF EXISTS signal_tips;
DROP TABLE IF EXISTS telegram_accounts;
DROP TABLE IF EXISTS signal_sources;
DROP TABLE IF EXISTS telegram_users;
DROP TABLE IF EXISTS daily_summaries;
DROP TABLE IF EXISTS trading_caps;
DROP TABLE IF EXISTS copy_trades;
DROP TABLE IF EXISTS follows;
DROP TABLE IF EXISTS challenge_trades;
DROP TABLE IF EXISTS challenge_participants;
DROP TABLE IF EXISTS challenges;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS signals_enhanced;
DROP TABLE IF EXISTS decision_logs;
DROP TABLE IF EXISTS risk_snapshots;
DROP TABLE IF EXISTS withdrawals;
DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS device_settings;
DROP TABLE IF EXISTS memories;
DROP TABLE IF EXISTS user_preferences;
DROP TABLE IF EXISTS backtest_results;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS positions;
DROP TABLE IF EXISTS portfolios;
DROP TABLE IF EXISTS signals;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS token_refresh_logs;
DROP TABLE IF EXISTS execution_logs;
DROP TABLE IF EXISTS trading_accounts;
DROP TABLE IF EXISTS broker_connections;

-- ============================================================
-- RECREATE ALL TABLES
-- Paper capital default = 10000.0 ($10K)
-- ============================================================

-- ── trades ─────────────────────────────────────────────────
CREATE TABLE trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol        VARCHAR(32) NOT NULL,
    side          VARCHAR(10) NOT NULL,
    quantity      REAL NOT NULL,
    price         REAL,
    order_type    VARCHAR(20) DEFAULT 'market',
    status        VARCHAR(20) DEFAULT 'pending',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    broker        VARCHAR(50),
    broker_order_id VARCHAR(100),
    agent_name    VARCHAR(100),
    signal_id     VARCHAR(100),
    entry_price   REAL,
    exit_price    REAL,
    pnl           REAL,
    pnl_percent   REAL
);

-- ── signals ────────────────────────────────────────────────
CREATE TABLE signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      VARCHAR(32) NOT NULL,
    action      VARCHAR(10) NOT NULL,
    strength    REAL,
    agent_name  VARCHAR(100) NOT NULL,
    reasoning   TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME,
    signal_data JSON,
    is_public   BOOLEAN DEFAULT 1,
    copied_by   INTEGER DEFAULT 0
);

-- ── portfolios ─────────────────────────────────────────────
-- NOTE: initial_capital / cash / initial_value all default to 10000.0 ($10K paper)
CREATE TABLE portfolios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id  VARCHAR(255) NOT NULL,
    name       VARCHAR(100) DEFAULT 'Default',
    cash       REAL DEFAULT 10000.0,
    initial_value REAL DEFAULT 10000.0,
    initial_capital REAL DEFAULT 10000.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_paper   BOOLEAN DEFAULT 1,
    broker     VARCHAR(50),
    is_active  BOOLEAN DEFAULT 1
);

-- ── positions ──────────────────────────────────────────────
CREATE TABLE positions (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id              INTEGER REFERENCES portfolios(id),
    symbol                    VARCHAR(32) NOT NULL,
    quantity                  REAL DEFAULT 0,
    avg_price                 REAL DEFAULT 0,
    current_price             REAL,
    market_value              REAL,
    unrealized_pnl            REAL,
    unrealized_pnl_percent    REAL,
    updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── portfolio_snapshots ────────────────────────────────────
-- Daily equity curve data for the frontend chart
CREATE TABLE portfolio_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL REFERENCES portfolios(id),
    device_id       VARCHAR(255) NOT NULL,
    snapshot_date   VARCHAR(10) NOT NULL,
    total_value     REAL NOT NULL,
    cash            REAL NOT NULL,
    market_value    REAL DEFAULT 0.0,
    unrealized_pnl  REAL DEFAULT 0.0,
    realized_pnl    REAL DEFAULT 0.0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, snapshot_date)
);

-- ── agents ─────────────────────────────────────────────────
CREATE TABLE agents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          VARCHAR(100) NOT NULL UNIQUE,
    type          VARCHAR(50),
    model         VARCHAR(200),
    is_active     BOOLEAN DEFAULT 0,
    config        JSON,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_signals INTEGER DEFAULT 0,
    win_rate      REAL,
    total_pnl     REAL
);

-- ── backtest_results ───────────────────────────────────────
CREATE TABLE backtest_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          VARCHAR(200),
    strategy      VARCHAR(100),
    symbol        VARCHAR(32),
    start_date    DATETIME,
    end_date      DATETIME,
    initial_capital REAL,
    final_capital REAL,
    total_return  REAL,
    sharpe_ratio  REAL,
    max_drawdown  REAL,
    win_rate      REAL,
    config        JSON,
    trades        JSON,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── user_preferences ───────────────────────────────────────
CREATE TABLE user_preferences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    key        VARCHAR(200) NOT NULL UNIQUE,
    value      JSON,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── memories ───────────────────────────────────────────────
CREATE TABLE memories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   VARCHAR(100),
    content      TEXT NOT NULL,
    category     VARCHAR(100),
    importance   REAL DEFAULT 0.5,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── device_settings ────────────────────────────────────────
-- NOTE: universal_paper_trading_config seeds with initial_capital = 10000.0
CREATE TABLE device_settings (
    device_id                              VARCHAR(255) PRIMARY KEY,
    nvidia_key                             VARCHAR(500),
    binance_key                            VARCHAR(500),
    binance_secret                         VARCHAR(500),
    solana_rpc_url                         VARCHAR(500),
    jupiter_enabled                        BOOLEAN DEFAULT 0,
    colab_url                              VARCHAR(500),
    ctrader_sandbox                        BOOLEAN DEFAULT 1,
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
    coingecko_enabled                      BOOLEAN DEFAULT 1,
    newsapi_key                            VARCHAR(500),
    cryptopanic_key                        VARCHAR(500),
    av_news_sentiment_enabled              BOOLEAN DEFAULT 1,
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
    trove_enabled                          BOOLEAN DEFAULT 0,
    trove_account_id                       VARCHAR(200),
    trove_sandbox                          BOOLEAN DEFAULT 1,
    tiger_id                               VARCHAR(200),
    tiger_api_key                          VARCHAR(500),
    tiger_private_key                      VARCHAR(500),
    tiger_enabled                          BOOLEAN DEFAULT 0,
    akshare_config                         TEXT,
    akshare_sandbox                        BOOLEAN DEFAULT 1,
    default_currency                       VARCHAR(3) DEFAULT 'USD',
    currency_conversion_enabled            BOOLEAN DEFAULT 1,
    naira_bank_details                     TEXT,
    created_at                             DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                             DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── chat_messages ──────────────────────────────────────────
CREATE TABLE chat_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number  VARCHAR(50) NOT NULL,
    message       TEXT NOT NULL,
    direction     VARCHAR(20) NOT NULL,
    message_type  VARCHAR(20) DEFAULT 'text',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    intent        VARCHAR(100),
    response_to_id INTEGER REFERENCES chat_messages(id)
);

-- ── withdrawals ────────────────────────────────────────────
CREATE TABLE withdrawals (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id         INTEGER REFERENCES portfolios(id),
    amount               REAL NOT NULL,
    currency             VARCHAR(3) DEFAULT 'USD',
    withdrawal_type      VARCHAR(50) NOT NULL,
    destination_type     VARCHAR(50),
    destination_address  VARCHAR(200),
    status               VARCHAR(20) DEFAULT 'pending',
    transaction_hash     VARCHAR(200),
    fee                  REAL DEFAULT 0.0,
    net_amount           REAL,
    daily_pnl            REAL,
    payout_percentage    REAL DEFAULT 50.0,
    requested_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at         DATETIME,
    error_message        TEXT
);

-- ── risk_snapshots ─────────────────────────────────────────
CREATE TABLE risk_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id   INTEGER REFERENCES portfolios(id),
    var_95         REAL,
    max_drawdown   REAL,
    sharpe_ratio   REAL,
    sortino_ratio  REAL,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── decision_logs ──────────────────────────────────────────
CREATE TABLE decision_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          VARCHAR(32) NOT NULL,
    action          VARCHAR(10) NOT NULL,
    reasoning       TEXT,
    confidence      REAL,
    agent_name      VARCHAR(100) DEFAULT 'Director',
    context         JSON,
    status          VARCHAR(20) DEFAULT 'pending',
    realized_return REAL,
    reflection      TEXT,
    portfolio_id    INTEGER DEFAULT 1 REFERENCES portfolios(id),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── signals_enhanced ───────────────────────────────────────
CREATE TABLE signals_enhanced (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id              INTEGER NOT NULL REFERENCES agents(id),
    agent_name            VARCHAR(100) NOT NULL,
    message_type          VARCHAR(32) NOT NULL,
    market                VARCHAR(32),
    symbol                VARCHAR(32),
    action                VARCHAR(10),
    price                 REAL,
    quantity              REAL,
    side                  VARCHAR(10),
    title                 VARCHAR(200),
    content               TEXT,
    tags                  VARCHAR(500),
    reply_count           INTEGER DEFAULT 0,
    participant_count     INTEGER DEFAULT 0,
    is_following_author   BOOLEAN DEFAULT 0,
    signal_data           JSON,
    is_public             BOOLEAN DEFAULT 1,
    executed_at           DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── subscriptions ──────────────────────────────────────────
CREATE TABLE subscriptions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_agent_id INTEGER NOT NULL REFERENCES agents(id),
    leader_agent_id  INTEGER NOT NULL REFERENCES agents(id),
    status           VARCHAR(20) DEFAULT 'active',
    copied_count     INTEGER DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── challenges ─────────────────────────────────────────────
CREATE TABLE challenges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_key   VARCHAR(100) NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    market          VARCHAR(32),
    track           VARCHAR(32),
    symbol          VARCHAR(32),
    variant_key     VARCHAR(50),
    start_at        DATETIME,
    end_at          DATETIME,
    status          VARCHAR(20) DEFAULT 'upcoming',
    scoring_method  VARCHAR(50) DEFAULT 'return_pct',
    starting_cash   REAL DEFAULT 1000.0,
    max_position_size REAL,
    max_drawdown    REAL,
    rules           TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── challenge_participants ─────────────────────────────────
CREATE TABLE challenge_participants (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id     INTEGER NOT NULL REFERENCES challenges(id),
    agent_id         INTEGER NOT NULL REFERENCES agents(id),
    return_pct       REAL DEFAULT 0.0,
    max_drawdown     REAL DEFAULT 0.0,
    risk_adjusted_score REAL DEFAULT 0.0,
    final_score      REAL DEFAULT 0.0,
    trade_count      INTEGER DEFAULT 0,
    rank             INTEGER,
    disqualified_reason VARCHAR(500),
    starting_cash    REAL DEFAULT 1000.0,
    current_cash     REAL DEFAULT 1000.0,
    portfolio_value  REAL DEFAULT 1000.0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── challenge_trades ───────────────────────────────────────
CREATE TABLE challenge_trades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id   INTEGER NOT NULL REFERENCES challenges(id),
    participant_id INTEGER NOT NULL REFERENCES challenge_participants(id),
    agent_id       INTEGER NOT NULL REFERENCES agents(id),
    side           VARCHAR(10) NOT NULL,
    symbol         VARCHAR(32) NOT NULL,
    price          REAL NOT NULL,
    quantity       REAL NOT NULL,
    content        TEXT,
    cash_before    REAL,
    cash_after     REAL,
    executed_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── follows ────────────────────────────────────────────────
CREATE TABLE follows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id     INTEGER NOT NULL REFERENCES portfolios(id),
    leader_id       VARCHAR(100) NOT NULL,
    leader_type     VARCHAR(20) DEFAULT 'agent',
    copy_percentage REAL DEFAULT 100.0,
    max_position_size REAL DEFAULT 10000.0,
    auto_copy       BOOLEAN DEFAULT 1,
    active          BOOLEAN DEFAULT 1,
    paused_at       DATETIME,
    signals_copied  INTEGER DEFAULT 0,
    total_pnl       REAL DEFAULT 0.0,
    followed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── copy_trades ────────────────────────────────────────────
CREATE TABLE copy_trades (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    follow_id        INTEGER NOT NULL REFERENCES follows(id),
    original_signal_id INTEGER NOT NULL REFERENCES signals(id),
    resulting_trade_id INTEGER REFERENCES trades(id),
    copy_percentage  REAL NOT NULL,
    original_quantity REAL NOT NULL,
    copied_quantity  REAL NOT NULL,
    pnl              REAL DEFAULT 0.0,
    pnl_percent      REAL DEFAULT 0.0,
    copied_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at        DATETIME,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── trading_caps ───────────────────────────────────────────
CREATE TABLE trading_caps (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id              INTEGER NOT NULL REFERENCES portfolios(id),
    max_position_amount       REAL,
    max_position_percentage   REAL,
    daily_loss_limit          REAL,
    daily_loss_percentage     REAL,
    hard_limit                BOOLEAN DEFAULT 1,
    soft_limit_enabled        BOOLEAN DEFAULT 0,
    enabled                   BOOLEAN DEFAULT 1,
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── daily_summaries ────────────────────────────────────────
CREATE TABLE daily_summaries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id     INTEGER NOT NULL REFERENCES portfolios(id),
    device_id        VARCHAR(255) NOT NULL,
    chat_id          VARCHAR(100) NOT NULL,
    summary_date     VARCHAR(10) NOT NULL,
    total_pnl        REAL DEFAULT 0.0,
    total_pnl_percent REAL DEFAULT 0.0,
    total_trades     INTEGER DEFAULT 0,
    wins             INTEGER DEFAULT 0,
    losses           INTEGER DEFAULT 0,
    breakeven        INTEGER DEFAULT 0,
    win_rate         REAL DEFAULT 0.0,
    best_trade       JSON,
    worst_trade      JSON,
    agent_stats      JSON,
    top_symbols      JSON,
    summary_sent     BOOLEAN DEFAULT 0,
    sent_at          DATETIME,
    send_time_wat    VARCHAR(10) DEFAULT '20:00',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── telegram_users ─────────────────────────────────────────
CREATE TABLE telegram_users (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id                   VARCHAR(255) NOT NULL UNIQUE,
    chat_id                     VARCHAR(100) NOT NULL,
    trade_notifications_enabled BOOLEAN DEFAULT 1,
    daily_summary_enabled       BOOLEAN DEFAULT 1,
    summary_time_wat            VARCHAR(10) DEFAULT '20:00',
    chat_enabled                BOOLEAN DEFAULT 1,
    ai_explanations_enabled     BOOLEAN DEFAULT 1,
    is_verified                 BOOLEAN DEFAULT 0,
    verification_code           VARCHAR(50),
    verification_expires_at     DATETIME,
    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at              DATETIME
);

-- ── signal_sources ─────────────────────────────────────────
CREATE TABLE signal_sources (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id                VARCHAR(255) NOT NULL,
    source_type              VARCHAR(64) NOT NULL,
    config                   JSON NOT NULL DEFAULT '{}',
    display_name             VARCHAR(255) NOT NULL,
    is_active                BOOLEAN DEFAULT 1,
    fetch_interval_minutes   INTEGER DEFAULT 30,
    last_fetched_at          DATETIME,
    created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── telegram_accounts ──────────────────────────────────────
CREATE TABLE telegram_accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    VARCHAR(255) NOT NULL UNIQUE,
    tg_phone     VARCHAR(64) NOT NULL,
    tg_session   TEXT,
    tg_user_id   VARCHAR(64),
    tg_username  VARCHAR(128),
    tg_first_name VARCHAR(128),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── signal_tips ────────────────────────────────────────────
CREATE TABLE signal_tips (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id         VARCHAR(255) NOT NULL,
    source_id         INTEGER NOT NULL REFERENCES signal_sources(id),
    slug              VARCHAR(255) NOT NULL,
    symbol            VARCHAR(64) NOT NULL,
    side              VARCHAR(16) NOT NULL,
    timeframe         VARCHAR(16),
    confidence        REAL DEFAULT 0.0,
    rationale         VARCHAR(500),
    text              TEXT,
    url               VARCHAR(500),
    source_created_at DATETIME,
    entry_price       REAL,
    exit_price        REAL,
    pnl               REAL,
    pnl_percent       REAL,
    hit               BOOLEAN,
    executed          BOOLEAN DEFAULT 0,
    execution_status  VARCHAR(32) DEFAULT 'pending',
    execution_detail  VARCHAR(500),
    executed_at       DATETIME,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── signal_settings ────────────────────────────────────────
CREATE TABLE signal_settings (
    device_id           VARCHAR(255) PRIMARY KEY,
    auto_execute_enabled BOOLEAN DEFAULT 1,
    min_confidence      REAL DEFAULT 0.60,
    max_position_pct    REAL DEFAULT 0.05,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── source_follows ─────────────────────────────────────────
CREATE TABLE source_follows (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id  VARCHAR(255) NOT NULL,
    source_id  INTEGER NOT NULL REFERENCES signal_sources(id),
    active     BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── watchlist_items ────────────────────────────────────────
CREATE TABLE watchlist_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   VARCHAR(255) NOT NULL,
    symbol      VARCHAR(32) NOT NULL,
    name        VARCHAR(128),
    asset_class VARCHAR(32) DEFAULT 'crypto',
    source      VARCHAR(64),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── broker_connections ─────────────────────────────────────
CREATE TABLE broker_connections (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL,
    broker_type          VARCHAR(20) NOT NULL,
    broker_name          VARCHAR(100),
    account_id           VARCHAR(100),
    account_currency     VARCHAR(3) DEFAULT 'USD',
    account_balance      REAL DEFAULT 0.0,
    ctrader_account_id   VARCHAR(100),
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    token_expires_at     DATETIME,
    encrypted_api_key    TEXT,
    encrypted_api_secret TEXT,
    is_active            BOOLEAN DEFAULT 1,
    is_connected         BOOLEAN DEFAULT 0,
    connection_status    VARCHAR(50),
    last_sync_at         DATETIME,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── trading_accounts ───────────────────────────────────────
CREATE TABLE trading_accounts (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                   INTEGER NOT NULL,
    account_type              VARCHAR(20) NOT NULL DEFAULT 'ctrader',
    ctid_trader_account_id    VARCHAR(50),
    ctid_account_name         VARCHAR(100),
    encrypted_access_token    TEXT,
    encrypted_refresh_token   TEXT,
    token_expires_at          DATETIME,
    token_last_refreshed      DATETIME,
    broker_name               VARCHAR(50),
    account_currency          VARCHAR(3) DEFAULT 'USD',
    account_leverage          REAL DEFAULT 1.0,
    account_balance           REAL DEFAULT 0.0,
    account_equity            REAL DEFAULT 0.0,
    is_active                 BOOLEAN DEFAULT 1,
    is_connected              BOOLEAN DEFAULT 0,
    connection_status         VARCHAR(50),
    last_sync_at              DATETIME,
    created_at                DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── execution_logs ─────────────────────────────────────────
CREATE TABLE execution_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_account_id  INTEGER NOT NULL REFERENCES trading_accounts(id),
    strategy_name       VARCHAR(100),
    action_type         VARCHAR(20),
    symbol              VARCHAR(20),
    volume              REAL,
    execution_price     REAL,
    cTrader_order_id    VARCHAR(50),
    status              VARCHAR(20),
    error_message       TEXT,
    execution_time_ms   INTEGER,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── token_refresh_logs ─────────────────────────────────────
CREATE TABLE token_refresh_logs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_account_id      INTEGER NOT NULL REFERENCES trading_accounts(id),
    old_token_expires_at    DATETIME,
    new_token_expires_at    DATETIME,
    refresh_successful      BOOLEAN,
    error_message           TEXT,
    refreshed_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

PRAGMA foreign_keys = ON;

-- ============================================================
-- SEED: Insert default portfolio with $10K paper capital
-- Uses INSERT OR REPLACE to overwrite any existing $100k rows
-- ============================================================
INSERT OR REPLACE INTO portfolios (device_id, name, cash, initial_value, initial_capital, is_paper, is_active, created_at)
VALUES ('__system__', 'System Paper Portfolio', 10000.0, 10000.0, 10000.0, 1, 1, datetime('now'));

-- ============================================================
-- SEED: Insert default device settings with $10K paper config
-- ============================================================
INSERT OR REPLACE INTO device_settings (device_id, trading_mode, environment_mode, universal_paper_trading_config, created_at)
VALUES ('__system__', 'practice', 'sandbox',
        '{"enabled": true, "initial_capital": 10000.0, "current_balance": 10000.0, "total_pnl": 0.0, "currency": "USD"}',
        datetime('now'));

-- ============================================================
-- FIX: Force ALL existing portfolios to $10K (catches stale $100k rows)
-- ============================================================
UPDATE portfolios SET cash = 10000.0, initial_value = 10000.0, initial_capital = 10000.0;

-- ============================================================
-- FIX: Force ALL existing device_settings paper config to $10K
-- ============================================================
UPDATE device_settings
SET universal_paper_trading_config = '{"enabled": true, "initial_capital": 10000.0, "current_balance": 10000.0, "total_pnl": 0.0, "currency": "USD"}'
WHERE universal_paper_trading_config LIKE '%100000%';
