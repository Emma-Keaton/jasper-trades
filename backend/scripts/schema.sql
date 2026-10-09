-- jasper-trades: complete database schema (Supabase / PostgreSQL)
--
-- Generated from app/models.py by scripts/generate_schema.py.
-- Do not hand-edit: regenerate with `python scripts/generate_schema.py`.
--
-- RE-RUNNABLE AND NON-DESTRUCTIVE. Every statement is guarded, so this file can
-- be applied to an empty project, a partially provisioned one, or a live one,
-- any number of times:
--   * empty project      -> CREATE TABLE builds the full schema, then seeds run
--   * existing project   -> tables are left alone, the backfill block adds any
--                           column added since, seeds are skipped on conflict
--   * repeated runs      -> no-ops
--
-- Apply in the Supabase SQL editor, or:
--   psql "$DATABASE_URL" -f backend/scripts/schema.sql
--
-- The application also reconciles the schema on startup (`app/migrations.py`:
-- create_all plus incremental column adds). This file exists so the same state
-- can be reached from the SQL editor with no deploy, which matters when the
-- first deploy cannot start because the schema is missing a column it needs.
--
-- To DROP everything and start over instead, run backend/scripts/reset.sh, which
-- drops the tables first and then applies this file. That is destructive and is
-- kept as a separate, explicit step so this file never destroys data by accident.

-- Generated from SQLAlchemy metadata. Do not hand-edit.
--
-- Idempotent: every statement is IF NOT EXISTS, so this can be re-applied
-- to an existing database any number of times.

CREATE TABLE IF NOT EXISTS agents (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	type VARCHAR, 
	model VARCHAR, 
		is_active BOOLEAN DEFAULT FALSE,
	config JSON, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		total_signals INTEGER DEFAULT 0,
	win_rate FLOAT, 
	total_pnl FLOAT, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS backtest_results (
	id SERIAL NOT NULL, 
	name VARCHAR, 
	strategy VARCHAR, 
	symbol VARCHAR, 
	start_date TIMESTAMP WITHOUT TIME ZONE, 
	end_date TIMESTAMP WITHOUT TIME ZONE, 
	initial_capital FLOAT, 
	final_capital FLOAT, 
	total_return FLOAT, 
	sharpe_ratio FLOAT, 
	max_drawdown FLOAT, 
	win_rate FLOAT, 
	config JSON, 
	trades JSON, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS broker_connections (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	broker_type VARCHAR(20) NOT NULL, 
	broker_name VARCHAR(100), 
	account_id VARCHAR(100), 
		account_currency VARCHAR(3) DEFAULT 'USD',
		account_balance FLOAT DEFAULT 0.0,
	ctrader_account_id VARCHAR(100), 
	encrypted_access_token TEXT, 
	encrypted_refresh_token TEXT, 
	token_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	encrypted_api_key TEXT, 
	encrypted_api_secret TEXT, 
		is_active BOOLEAN DEFAULT TRUE,
		is_connected BOOLEAN DEFAULT FALSE,
	connection_status VARCHAR(50), 
	last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS challenge_participants (
	id SERIAL NOT NULL, 
	challenge_id INTEGER NOT NULL, 
	agent_id INTEGER NOT NULL, 
		return_pct FLOAT DEFAULT 0.0,
		max_drawdown FLOAT DEFAULT 0.0,
		risk_adjusted_score FLOAT DEFAULT 0.0,
		final_score FLOAT DEFAULT 0.0,
		trade_count INTEGER DEFAULT 0,
	rank INTEGER, 
	disqualified_reason VARCHAR, 
		starting_cash FLOAT DEFAULT 1000.0,
		current_cash FLOAT DEFAULT 1000.0,
		portfolio_value FLOAT DEFAULT 1000.0,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(challenge_id) REFERENCES challenges (id), 
	FOREIGN KEY(agent_id) REFERENCES agents (id)
);

CREATE TABLE IF NOT EXISTS challenge_trades (
	id SERIAL NOT NULL, 
	challenge_id INTEGER NOT NULL, 
	participant_id INTEGER NOT NULL, 
	agent_id INTEGER NOT NULL, 
	side VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	price FLOAT NOT NULL, 
	quantity FLOAT NOT NULL, 
	content TEXT, 
	cash_before FLOAT, 
	cash_after FLOAT, 
		executed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(challenge_id) REFERENCES challenges (id), 
	FOREIGN KEY(participant_id) REFERENCES challenge_participants (id), 
	FOREIGN KEY(agent_id) REFERENCES agents (id)
);

CREATE TABLE IF NOT EXISTS challenges (
	id SERIAL NOT NULL, 
	challenge_key VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	description TEXT, 
	market VARCHAR, 
	track VARCHAR, 
	symbol VARCHAR, 
	variant_key VARCHAR, 
	start_at TIMESTAMP WITHOUT TIME ZONE, 
	end_at TIMESTAMP WITHOUT TIME ZONE, 
		status VARCHAR DEFAULT 'upcoming',
		scoring_method VARCHAR DEFAULT 'return_pct',
		starting_cash FLOAT DEFAULT 1000.0,
	max_position_size FLOAT, 
	max_drawdown FLOAT, 
	rules TEXT, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	UNIQUE (challenge_key)
);

CREATE TABLE IF NOT EXISTS chat_messages (
	id SERIAL NOT NULL, 
	phone_number VARCHAR NOT NULL, 
	message TEXT NOT NULL, 
	direction VARCHAR NOT NULL, 
		message_type VARCHAR DEFAULT 'text',
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	intent VARCHAR, 
	response_to_id INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS copy_trades (
	id SERIAL NOT NULL, 
	follow_id INTEGER NOT NULL, 
	original_signal_id INTEGER NOT NULL, 
	resulting_trade_id INTEGER, 
	copy_percentage FLOAT NOT NULL, 
	original_quantity FLOAT NOT NULL, 
	copied_quantity FLOAT NOT NULL, 
		pnl FLOAT DEFAULT 0.0,
		pnl_percent FLOAT DEFAULT 0.0,
		copied_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	closed_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(follow_id) REFERENCES follows (id), 
	FOREIGN KEY(original_signal_id) REFERENCES signals (id), 
	FOREIGN KEY(resulting_trade_id) REFERENCES trades (id)
);

CREATE TABLE IF NOT EXISTS daily_summaries (
	id SERIAL NOT NULL, 
	portfolio_id INTEGER NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	chat_id VARCHAR NOT NULL, 
	summary_date VARCHAR NOT NULL, 
		total_pnl FLOAT DEFAULT 0.0,
		total_pnl_percent FLOAT DEFAULT 0.0,
		total_trades INTEGER DEFAULT 0,
		wins INTEGER DEFAULT 0,
		losses INTEGER DEFAULT 0,
		breakeven INTEGER DEFAULT 0,
		win_rate FLOAT DEFAULT 0.0,
	best_trade JSON, 
	worst_trade JSON, 
	agent_stats JSON, 
	top_symbols JSON, 
		summary_sent BOOLEAN DEFAULT FALSE,
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
		send_time_wat VARCHAR DEFAULT '20:00',
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS decision_logs (
	id SERIAL NOT NULL, 
	symbol VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	reasoning TEXT, 
	confidence FLOAT, 
		agent_name VARCHAR DEFAULT 'Director',
	context JSON, 
		status VARCHAR DEFAULT 'pending',
	realized_return FLOAT, 
	reflection TEXT, 
		portfolio_id INTEGER DEFAULT 1,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS device_crypto_credentials (
	id SERIAL NOT NULL, 
	device_id VARCHAR NOT NULL, 
	exchange VARCHAR NOT NULL, 
	encrypted_api_key VARCHAR, 
	encrypted_api_secret VARCHAR, 
	wallet_address VARCHAR, 
	chain VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS device_settings (
	device_id VARCHAR NOT NULL, 
	groq_key VARCHAR, 
	binance_key VARCHAR, 
	binance_secret VARCHAR, 
	solana_rpc_url VARCHAR, 
		jupiter_enabled BOOLEAN DEFAULT FALSE,
		ctrader_sandbox BOOLEAN DEFAULT TRUE,
	discord_config VARCHAR, 
	slack_config VARCHAR, 
	email_config VARCHAR, 
	telegram_config VARCHAR, 
	whatsapp_config VARCHAR, 
	broker_paper_trading_config VARCHAR, 
	universal_paper_trading_config VARCHAR, 
		trading_mode VARCHAR(10) DEFAULT 'practice',
	preferences VARCHAR, 
	alphavantage_key VARCHAR, 
	finnhub_key VARCHAR, 
	twelvedata_key VARCHAR, 
	polygon_key VARCHAR, 
	fred_key VARCHAR, 
		coingecko_enabled BOOLEAN DEFAULT TRUE,
	newsapi_key VARCHAR, 
	cryptopanic_key VARCHAR, 
		av_news_sentiment_enabled BOOLEAN DEFAULT TRUE,
	sendgrid_config VARCHAR, 
	discord_bot_config VARCHAR, 
		environment_mode VARCHAR(20) DEFAULT 'sandbox',
		groq_model VARCHAR DEFAULT 'openai/gpt-oss-120b',
	default_brokers VARCHAR, 
		routing_mode VARCHAR DEFAULT 'asset_class',
	payout_config VARCHAR, 
	payout_wallet_keys VARCHAR, 
	trove_api_key VARCHAR, 
	trove_base_url VARCHAR, 
		trove_enabled BOOLEAN DEFAULT FALSE,
	trove_account_id VARCHAR, 
		trove_sandbox BOOLEAN DEFAULT TRUE,
	tiger_id VARCHAR, 
	tiger_api_key VARCHAR, 
	tiger_private_key VARCHAR, 
		tiger_enabled BOOLEAN DEFAULT FALSE,
	akshare_config VARCHAR, 
		akshare_sandbox BOOLEAN DEFAULT TRUE,
	default_currency VARCHAR(3), 
		currency_conversion_enabled BOOLEAN DEFAULT TRUE,
	naira_bank_details VARCHAR, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (device_id)
);

CREATE TABLE IF NOT EXISTS execution_logs (
	id SERIAL NOT NULL, 
	trading_account_id INTEGER NOT NULL, 
	strategy_name VARCHAR(100), 
	action_type VARCHAR(20), 
	symbol VARCHAR(20), 
	volume FLOAT, 
	execution_price FLOAT, 
	"cTrader_order_id" VARCHAR(50), 
	status VARCHAR(20), 
	error_message TEXT, 
	execution_time_ms INTEGER, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(trading_account_id) REFERENCES trading_accounts (id)
);

CREATE TABLE IF NOT EXISTS follows (
	id SERIAL NOT NULL, 
	follower_id INTEGER NOT NULL, 
	leader_id VARCHAR NOT NULL, 
		leader_type VARCHAR DEFAULT 'agent',
		copy_percentage FLOAT DEFAULT 100.0,
		max_position_size FLOAT DEFAULT 10000.0,
		auto_copy BOOLEAN DEFAULT TRUE,
		active BOOLEAN DEFAULT TRUE,
	paused_at TIMESTAMP WITHOUT TIME ZONE, 
		signals_copied INTEGER DEFAULT 0,
		total_pnl FLOAT DEFAULT 0.0,
		followed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(follower_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS kronos_forecasts (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	symbol VARCHAR(32) NOT NULL, 
		source VARCHAR(16) NOT NULL DEFAULT 'kronos',
	model VARCHAR(64), 
	horizon INTEGER NOT NULL, 
	interval_seconds INTEGER NOT NULL, 
		sample_count INTEGER NOT NULL DEFAULT 1,
	last_close FLOAT NOT NULL, 
	mean_path JSONB, 
	trajectories JSONB, 
	terminal_low FLOAT, 
	terminal_high FLOAT, 
	probability_up FLOAT, 
	confidence INTEGER, 
		scored BOOLEAN NOT NULL DEFAULT FALSE,
	realised FLOAT, 
	was_up BOOLEAN, 
	within_band BOOLEAN, 
	absolute_error FLOAT, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	scored_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS learned_parameter_history (
	id SERIAL NOT NULL, 
		device_id VARCHAR(255) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
	name VARCHAR(64) NOT NULL, 
	previous_value FLOAT, 
	new_value FLOAT NOT NULL, 
	version INTEGER NOT NULL, 
	sample_size INTEGER NOT NULL, 
	hit_rate FLOAT, 
	reason TEXT, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS learned_parameters (
	id SERIAL NOT NULL, 
		device_id VARCHAR(255) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
	name VARCHAR(64) NOT NULL, 
	value FLOAT NOT NULL, 
		version INTEGER NOT NULL DEFAULT 1,
		sample_size INTEGER NOT NULL DEFAULT 0,
	hit_rate FLOAT, 
		validated BOOLEAN NOT NULL DEFAULT FALSE,
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	CONSTRAINT ux_learned_parameters_device_name UNIQUE (device_id, name)
);

CREATE TABLE IF NOT EXISTS memories (
	id SERIAL NOT NULL, 
	session_id VARCHAR, 
	content TEXT NOT NULL, 
	category VARCHAR, 
		importance FLOAT DEFAULT 0.5,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS model_assignments (
	id SERIAL NOT NULL, 
		device_id VARCHAR(255) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
		scope VARCHAR(16) NOT NULL DEFAULT 'global',
	symbol VARCHAR(32), 
	model VARCHAR(64) NOT NULL, 
	hit_rate FLOAT, 
		sample_size INTEGER NOT NULL DEFAULT 0,
	mean_latency_ms FLOAT, 
		promoted BOOLEAN NOT NULL DEFAULT FALSE,
		assigned_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	promoted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_model_assignments_scope UNIQUE (device_id, scope, symbol)
);

CREATE TABLE IF NOT EXISTS polymarket_accounts (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	encrypted_api_key TEXT NOT NULL, 
	encrypted_api_secret TEXT NOT NULL, 
	wallet_address VARCHAR(50), 
		account_currency VARCHAR(3) DEFAULT 'USD',
		account_balance FLOAT DEFAULT 0.0,
		account_equity FLOAT DEFAULT 0.0,
		ai_trading_enabled BOOLEAN DEFAULT FALSE,
		copytrading_enabled BOOLEAN DEFAULT FALSE,
		max_position_size FLOAT DEFAULT 100.0,
		max_portfolio_risk FLOAT DEFAULT 0.2,
		is_active BOOLEAN DEFAULT TRUE,
		is_connected BOOLEAN DEFAULT FALSE,
	connection_status VARCHAR(50), 
	last_balance_sync_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	last_trade_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS polymarket_leader_configs (
	id SERIAL NOT NULL, 
	account_id INTEGER NOT NULL, 
	leader_id VARCHAR(100) NOT NULL, 
	leader_name VARCHAR(100), 
	leader_wallet VARCHAR(50), 
		allocation_weight FLOAT DEFAULT 0.5,
		min_confidence FLOAT DEFAULT 0.7,
		max_copy_amount FLOAT DEFAULT 50.0,
		total_copied_trades INTEGER DEFAULT 0,
		successful_copies INTEGER DEFAULT 0,
		win_rate FLOAT DEFAULT 0.0,
		total_pnl FLOAT DEFAULT 0.0,
		is_active BOOLEAN DEFAULT TRUE,
	last_copy_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(account_id) REFERENCES polymarket_accounts (id)
);

CREATE TABLE IF NOT EXISTS polymarket_positions (
	id SERIAL NOT NULL, 
	account_id INTEGER NOT NULL, 
	market_id VARCHAR(100) NOT NULL, 
	market_question VARCHAR(500), 
	market_slug VARCHAR(200), 
	outcome VARCHAR(100) NOT NULL, 
	token_id VARCHAR(50), 
	quantity FLOAT NOT NULL, 
	average_entry_price FLOAT NOT NULL, 
		current_price FLOAT DEFAULT 0.0,
		unrealized_pnl FLOAT DEFAULT 0.0,
		unrealized_pnl_percent FLOAT DEFAULT 0.0,
		opened_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	last_updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(account_id) REFERENCES polymarket_accounts (id)
);

CREATE TABLE IF NOT EXISTS polymarket_trades (
	id SERIAL NOT NULL, 
	account_id INTEGER NOT NULL, 
	market_id VARCHAR(100) NOT NULL, 
	market_question VARCHAR(500), 
	outcome VARCHAR(100) NOT NULL, 
	side VARCHAR(10) NOT NULL, 
	quantity FLOAT NOT NULL, 
	execution_price FLOAT NOT NULL, 
	total_value FLOAT NOT NULL, 
	clob_order_id VARCHAR(100), 
	clob_trade_id VARCHAR(100), 
	execution_timestamp TIMESTAMP WITHOUT TIME ZONE, 
		was_copytrade BOOLEAN DEFAULT FALSE,
	copied_from_leader_id VARCHAR(100), 
	ai_agent_decision VARCHAR(50), 
		realized_pnl FLOAT DEFAULT 0.0,
		realized_pnl_percent FLOAT DEFAULT 0.0,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(account_id) REFERENCES polymarket_accounts (id)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
	id SERIAL NOT NULL, 
	portfolio_id INTEGER NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	snapshot_date VARCHAR NOT NULL, 
	total_value FLOAT NOT NULL, 
	cash FLOAT NOT NULL, 
		market_value FLOAT DEFAULT 0.0,
		unrealized_pnl FLOAT DEFAULT 0.0,
		realized_pnl FLOAT DEFAULT 0.0,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS portfolios (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
		name VARCHAR DEFAULT 'Default',
		cash FLOAT DEFAULT 10000.0,
		initial_value FLOAT DEFAULT 10000.0,
		initial_capital FLOAT DEFAULT 10000.0,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		is_paper BOOLEAN DEFAULT TRUE,
	broker VARCHAR, 
		is_active BOOLEAN DEFAULT TRUE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS positions (
	id SERIAL NOT NULL, 
	portfolio_id INTEGER, 
	symbol VARCHAR NOT NULL, 
		quantity FLOAT DEFAULT 0,
		avg_price FLOAT DEFAULT 0,
	current_price FLOAT, 
	market_value FLOAT, 
	unrealized_pnl FLOAT, 
	unrealized_pnl_percent FLOAT, 
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS risk_snapshots (
	id SERIAL NOT NULL, 
	portfolio_id INTEGER, 
	var_95 FLOAT, 
	max_drawdown FLOAT, 
	sharpe_ratio FLOAT, 
	sortino_ratio FLOAT, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS signal_settings (
	device_id VARCHAR(255) NOT NULL, 
		auto_execute_enabled BOOLEAN DEFAULT TRUE,
		min_confidence FLOAT DEFAULT 0.6,
		max_position_pct FLOAT DEFAULT 0.05,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (device_id)
);

CREATE TABLE IF NOT EXISTS signal_sources (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	source_type VARCHAR(64) NOT NULL, 
	config JSON NOT NULL, 
	display_name VARCHAR(255) NOT NULL, 
		is_active BOOLEAN DEFAULT TRUE,
		fetch_interval_minutes INTEGER DEFAULT 30,
	last_fetched_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS signal_tips (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	source_id INTEGER NOT NULL, 
	slug VARCHAR(255) NOT NULL, 
	symbol VARCHAR(64) NOT NULL, 
	side VARCHAR(16) NOT NULL, 
	timeframe VARCHAR(16), 
		confidence FLOAT DEFAULT 0.0,
	rationale VARCHAR, 
	text VARCHAR, 
	url VARCHAR, 
	source_created_at TIMESTAMP WITHOUT TIME ZONE, 
	entry_price FLOAT, 
	exit_price FLOAT, 
	pnl FLOAT, 
	pnl_percent FLOAT, 
	hit BOOLEAN, 
		executed BOOLEAN DEFAULT FALSE,
		execution_status VARCHAR(32) DEFAULT 'pending',
	execution_detail VARCHAR, 
	executed_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES signal_sources (id)
);

CREATE TABLE IF NOT EXISTS signals (
	id SERIAL NOT NULL, 
	symbol VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	strength FLOAT, 
	agent_name VARCHAR NOT NULL, 
	reasoning TEXT, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	expires_at TIMESTAMP WITHOUT TIME ZONE, 
	metadata JSON, 
		is_public BOOLEAN DEFAULT TRUE,
		copied_by INTEGER DEFAULT 0,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS signals_enhanced (
	id SERIAL NOT NULL, 
	agent_id INTEGER NOT NULL, 
	agent_name VARCHAR NOT NULL, 
	message_type VARCHAR NOT NULL, 
	market VARCHAR, 
	symbol VARCHAR, 
	action VARCHAR, 
	price FLOAT, 
	quantity FLOAT, 
	side VARCHAR, 
	title VARCHAR, 
	content TEXT, 
	tags VARCHAR, 
		reply_count INTEGER DEFAULT 0,
		participant_count INTEGER DEFAULT 0,
		is_following_author BOOLEAN DEFAULT FALSE,
	signal_data JSON, 
		is_public BOOLEAN DEFAULT TRUE,
	executed_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(agent_id) REFERENCES agents (id)
);

CREATE TABLE IF NOT EXISTS source_follows (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	source_id INTEGER NOT NULL, 
		active BOOLEAN DEFAULT TRUE,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES signal_sources (id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
	id SERIAL NOT NULL, 
	follower_agent_id INTEGER NOT NULL, 
	leader_agent_id INTEGER NOT NULL, 
		status VARCHAR DEFAULT 'active',
		copied_count INTEGER DEFAULT 0,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(follower_agent_id) REFERENCES agents (id), 
	FOREIGN KEY(leader_agent_id) REFERENCES agents (id)
);

CREATE TABLE IF NOT EXISTS telegram_accounts (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	tg_phone VARCHAR(64) NOT NULL, 
	tg_session TEXT, 
	tg_user_id VARCHAR(64), 
	tg_username VARCHAR(128), 
	tg_first_name VARCHAR(128), 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS telegram_users (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	chat_id VARCHAR NOT NULL, 
		trade_notifications_enabled BOOLEAN DEFAULT TRUE,
		daily_summary_enabled BOOLEAN DEFAULT TRUE,
		summary_time_wat VARCHAR DEFAULT '20:00',
		chat_enabled BOOLEAN DEFAULT TRUE,
		ai_explanations_enabled BOOLEAN DEFAULT TRUE,
		is_verified BOOLEAN DEFAULT FALSE,
	verification_code VARCHAR, 
	verification_expires_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	last_active_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS token_refresh_logs (
	id SERIAL NOT NULL, 
	trading_account_id INTEGER NOT NULL, 
	old_token_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	new_token_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	refresh_successful BOOLEAN, 
	error_message TEXT, 
		refreshed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(trading_account_id) REFERENCES trading_accounts (id)
);

CREATE TABLE IF NOT EXISTS trades (
	id SERIAL NOT NULL, 
	symbol VARCHAR NOT NULL, 
	side VARCHAR NOT NULL, 
	quantity FLOAT NOT NULL, 
	price FLOAT, 
		order_type VARCHAR DEFAULT 'market',
		status VARCHAR DEFAULT 'pending',
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	portfolio_id INTEGER, 
	broker VARCHAR, 
	broker_order_id VARCHAR, 
	agent_name VARCHAR, 
	signal_id VARCHAR, 
	entry_price FLOAT, 
	exit_price FLOAT, 
	pnl FLOAT, 
	pnl_percent FLOAT, 
	error_detail TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS trading_accounts (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
		account_type VARCHAR(20) NOT NULL DEFAULT 'ctrader',
	ctid_trader_account_id VARCHAR(50), 
	ctid_account_name VARCHAR(100), 
	encrypted_access_token TEXT, 
	encrypted_refresh_token TEXT, 
	token_expires_at TIMESTAMP WITHOUT TIME ZONE, 
	token_last_refreshed TIMESTAMP WITHOUT TIME ZONE, 
	broker_name VARCHAR(50), 
		account_currency VARCHAR(3) DEFAULT 'USD',
		account_leverage FLOAT DEFAULT 1.0,
		account_balance FLOAT DEFAULT 0.0,
		account_equity FLOAT DEFAULT 0.0,
		is_active BOOLEAN DEFAULT TRUE,
		is_connected BOOLEAN DEFAULT FALSE,
	connection_status VARCHAR(50), 
	last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	UNIQUE (ctid_trader_account_id)
);

CREATE TABLE IF NOT EXISTS trading_caps (
	id SERIAL NOT NULL, 
	portfolio_id INTEGER NOT NULL, 
	max_position_amount FLOAT, 
	max_position_percentage FLOAT, 
	daily_loss_limit FLOAT, 
	daily_loss_percentage FLOAT, 
		hard_limit BOOLEAN DEFAULT TRUE,
		soft_limit_enabled BOOLEAN DEFAULT FALSE,
		enabled BOOLEAN DEFAULT TRUE,
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
	id SERIAL NOT NULL, 
	key VARCHAR NOT NULL, 
	value JSON, 
		updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id), 
	UNIQUE (key)
);

CREATE TABLE IF NOT EXISTS watchlist_items (
	id SERIAL NOT NULL, 
	device_id VARCHAR(255) NOT NULL, 
	symbol VARCHAR(32) NOT NULL, 
	name VARCHAR(128), 
		asset_class VARCHAR(32) DEFAULT 'crypto',
	source VARCHAR(64), 
		created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS withdrawals (
	id SERIAL NOT NULL, 
	portfolio_id INTEGER, 
	amount FLOAT NOT NULL, 
		currency VARCHAR DEFAULT 'USD',
	withdrawal_type VARCHAR NOT NULL, 
	destination_type VARCHAR, 
	destination_address VARCHAR, 
	destination_chain VARCHAR, 
		status VARCHAR DEFAULT 'pending',
	transaction_hash VARCHAR, 
		fee FLOAT DEFAULT 0.0,
	net_amount FLOAT, 
	daily_pnl FLOAT, 
		payout_percentage FLOAT DEFAULT 50.0,
		requested_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
	processed_at TIMESTAMP WITHOUT TIME ZONE, 
	error_message VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);



CREATE INDEX IF NOT EXISTS ix_broker_connections_device_id ON broker_connections (device_id);
CREATE INDEX IF NOT EXISTS ix_broker_connections_id ON broker_connections (id);






CREATE INDEX IF NOT EXISTS ix_daily_summaries_chat_id ON daily_summaries (chat_id);
CREATE INDEX IF NOT EXISTS ix_daily_summaries_device_id ON daily_summaries (device_id);
CREATE INDEX IF NOT EXISTS ix_daily_summaries_summary_date ON daily_summaries (summary_date);


CREATE INDEX IF NOT EXISTS ix_device_crypto_credentials_device_id ON device_crypto_credentials (device_id);
CREATE INDEX IF NOT EXISTS ix_device_crypto_credentials_id ON device_crypto_credentials (id);




CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_created_at ON kronos_forecasts (created_at);
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_device_id ON kronos_forecasts (device_id);
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_pending ON kronos_forecasts (created_at, device_id);
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_scored ON kronos_forecasts (scored);
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_symbol ON kronos_forecasts (symbol);

CREATE INDEX IF NOT EXISTS ix_learned_parameter_history_created_at ON learned_parameter_history (created_at);
CREATE INDEX IF NOT EXISTS ix_learned_parameter_history_device_id ON learned_parameter_history (device_id);

CREATE INDEX IF NOT EXISTS ix_learned_parameters_device_id ON learned_parameters (device_id);


CREATE INDEX IF NOT EXISTS ix_model_assignments_device_id ON model_assignments (device_id);

CREATE INDEX IF NOT EXISTS ix_polymarket_accounts_device_id ON polymarket_accounts (device_id);
CREATE INDEX IF NOT EXISTS ix_polymarket_accounts_id ON polymarket_accounts (id);




CREATE INDEX IF NOT EXISTS ix_portfolio_snapshots_device_id ON portfolio_snapshots (device_id);
CREATE INDEX IF NOT EXISTS ix_portfolio_snapshots_portfolio_id ON portfolio_snapshots (portfolio_id);
CREATE INDEX IF NOT EXISTS ix_portfolio_snapshots_snapshot_date ON portfolio_snapshots (snapshot_date);

CREATE INDEX IF NOT EXISTS ix_portfolios_device_id ON portfolios (device_id);




CREATE INDEX IF NOT EXISTS ix_signal_sources_device_id ON signal_sources (device_id);

CREATE INDEX IF NOT EXISTS ix_signal_tips_device_id ON signal_tips (device_id);
CREATE INDEX IF NOT EXISTS ix_signal_tips_slug ON signal_tips (slug);



CREATE INDEX IF NOT EXISTS ix_source_follows_device_id ON source_follows (device_id);


CREATE UNIQUE INDEX IF NOT EXISTS ix_telegram_accounts_device_id ON telegram_accounts (device_id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_telegram_users_device_id ON telegram_users (device_id);



CREATE INDEX IF NOT EXISTS ix_trading_accounts_device_id ON trading_accounts (device_id);
CREATE INDEX IF NOT EXISTS ix_trading_accounts_id ON trading_accounts (id);



CREATE INDEX IF NOT EXISTS ix_watchlist_items_device_id ON watchlist_items (device_id);


-- ============================================================
-- BACKFILL: columns added after a database was first provisioned
--
-- CREATE TABLE IF NOT EXISTS is a no-op on a table that already exists,
-- so on an existing database these are the statements that do the work.
-- Harmless on a fresh one.
-- ============================================================

-- device_settings
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "payout_wallet_keys" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "payout_config" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "trove_api_key" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "trove_base_url" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "trove_enabled" BOOLEAN;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "trove_account_id" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "trove_sandbox" BOOLEAN DEFAULT true;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "tiger_id" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "tiger_api_key" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "tiger_private_key" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "tiger_enabled" BOOLEAN;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "akshare_config" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "akshare_sandbox" BOOLEAN DEFAULT true;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "ctrader_sandbox" BOOLEAN DEFAULT true;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "default_currency" TEXT DEFAULT 'USD';
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "currency_conversion_enabled" BOOLEAN DEFAULT true;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "naira_bank_details" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "solana_rpc_url" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "jupiter_enabled" BOOLEAN;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "environment_mode" TEXT DEFAULT 'sandbox';
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "broker_paper_trading_config" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "universal_paper_trading_config" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "trading_mode" TEXT DEFAULT 'practice';
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "preferences" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "groq_model" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "groq_key" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "default_brokers" TEXT;
ALTER TABLE device_settings ADD COLUMN IF NOT EXISTS "routing_mode" TEXT;

-- portfolios
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "device_id" VARCHAR(255) DEFAULT 'legacy_device';
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "name" VARCHAR(255) DEFAULT 'Default';
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "cash" FLOAT DEFAULT 10000.0;
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "initial_value" FLOAT DEFAULT 10000.0;
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "initial_capital" FLOAT DEFAULT 10000.0;
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "is_paper" BOOLEAN DEFAULT true;
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "broker" VARCHAR(64);
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS "is_active" BOOLEAN DEFAULT true;

-- signal_tips
ALTER TABLE signal_tips ADD COLUMN IF NOT EXISTS "execution_status" VARCHAR(32) DEFAULT 'pending';
ALTER TABLE signal_tips ADD COLUMN IF NOT EXISTS "execution_detail" TEXT;
ALTER TABLE signal_tips ADD COLUMN IF NOT EXISTS "executed_at" TIMESTAMP;

-- signals
ALTER TABLE signals ADD COLUMN IF NOT EXISTS "metadata" JSONB;

-- trades
ALTER TABLE trades ADD COLUMN IF NOT EXISTS "portfolio_id" INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS "entry_price" FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS "exit_price" FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS "pnl" FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS "pnl_percent" FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS "error_detail" TEXT;

-- withdrawals
ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS "destination_chain" VARCHAR(32);
ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS "daily_pnl" FLOAT;
ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS "payout_percentage" FLOAT DEFAULT 50.0;
ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS "fee" FLOAT DEFAULT 0.0;
ALTER TABLE withdrawals ADD COLUMN IF NOT EXISTS "net_amount" FLOAT;

-- ============================================================
-- SEED: system paper portfolio and device settings
--
-- ON CONFLICT DO NOTHING keeps this re-runnable: applying the file to a live
-- database will not disturb an existing system portfolio.
-- ============================================================
INSERT INTO portfolios
    (device_id, name, cash, initial_value, initial_capital, is_paper, is_active)
VALUES
    ('__system__', 'System Paper Portfolio', 10000.0, 10000.0, 10000.0, true, true)
ON CONFLICT DO NOTHING;

INSERT INTO device_settings (device_id, trading_mode, environment_mode, universal_paper_trading_config)
VALUES ('__system__', 'practice', 'sandbox',
        '{"enabled": true, "initial_capital": 10000.0, "current_balance": 10000.0, "total_pnl": 0.0, "currency": "USD"}')
ON CONFLICT (device_id) DO NOTHING;
