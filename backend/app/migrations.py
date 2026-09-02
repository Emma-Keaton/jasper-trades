"""
Database Migration System
Automatically migrates database schema on application startup.
No external tools (Alembic) needed - simple SQLAlchemy-based migrations.
"""
import structlog
from sqlalchemy import text, inspect
from app.models import Base
from app.database import engine
from app.config import settings

logger = structlog.get_logger(__name__)


async def get_existing_tables() -> set:
    """Get set of existing table names in database."""
    async with engine.begin() as conn:
        result = await conn.run_sync(lambda conn: inspect(conn).get_table_names())
        return set(result)


async def get_existing_columns(table_name: str) -> set:
    """Get set of existing column names for a table."""
    async with engine.begin() as conn:
        def _get_columns(conn):
            inspector = inspect(conn)
            columns = inspector.get_columns(table_name)
            return {col['name'] for col in columns}
        result = await conn.run_sync(_get_columns)
        return result


async def add_column_if_missing(table: str, column: str, sqlite_def: str, pg_def: str) -> None:
    """Add a column when it doesn't exist, using dialect-appropriate DDL."""
    existing = await get_existing_columns(table)
    if column in existing:
        return
    definition = pg_def if settings.using_postgres else sqlite_def
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            )
        logger.info(f"[OK] Added column: {column} ({definition}) -> {table}")
    except Exception as e:
        logger.warning(f"Could not add column {column} to {table}: {e}")


async def migrate():
    """
    Run database migrations.
    Creates tables and adds missing columns automatically.

    - Both SQLite and Postgres: create_all is authoritative for the full
      schema on a fresh database.
    - Existing databases (either backend) get incremental ALTER TABLE column
      adds with dialect-appropriate DDL for SQLite and Postgres.
    """
    logger.info("Starting database migration...")

    try:
        # Step 1: Create all tables that don't exist.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[OK] Created/verified all tables")

        # Step 2: Incremental column additions are safe on both dialects now.
        await _migrate_device_settings()
        await _migrate_portfolios()
        await _migrate_signal_tips()
        await _migrate_trades()

        logger.info("[OK] Database migration completed successfully")

    except Exception as e:
        logger.error(f"Database migration failed: {e}", exc_info=True)
        raise


async def _migrate_device_settings():
    """Add missing columns to device_settings table."""
    # (name, SQLite DDL, Postgres DDL)
    expected_columns = [
        # Market Data APIs
        ("alphavantage_key", "TEXT", "TEXT"),
        ("finnhub_key", "TEXT", "TEXT"),
        ("twelvedata_key", "TEXT", "TEXT"),
        ("polygon_key", "TEXT", "TEXT"),
        ("fred_key", "TEXT", "TEXT"),
        ("coingecko_enabled", "BOOLEAN", "BOOLEAN"),

        # News/Sentiment
        ("newsapi_key", "TEXT", "TEXT"),
        ("cryptopanic_key", "TEXT", "TEXT"),
        ("av_news_sentiment_enabled", "BOOLEAN", "BOOLEAN"),

        # Email Service
        ("sendgrid_config", "TEXT", "TEXT"),

        # Discord Bot
        ("discord_bot_config", "TEXT", "TEXT"),

        # Tatum for payouts
        ("tatum_api_key", "TEXT", "TEXT"),

        # Trove API (Nigerian/US stocks)
        ("trove_api_key", "TEXT", "TEXT"),
        ("trove_base_url", "TEXT", "TEXT"),
        ("trove_enabled", "BOOLEAN", "BOOLEAN"),
        ("trove_account_id", "TEXT", "TEXT"),
        ("trove_sandbox", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),

        # Tiger OpenAPI (live CN/US stocks - encrypted)
        ("tiger_id", "TEXT", "TEXT"),
        ("tiger_api_key", "TEXT", "TEXT"),
        ("tiger_private_key", "TEXT", "TEXT"),
        ("tiger_enabled", "BOOLEAN", "BOOLEAN"),

        # AKShare (Chinese stocks)
        ("akshare_config", "TEXT", "TEXT"),
        ("akshare_sandbox", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),

        # cTrader sandbox mode
        ("ctrader_sandbox", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),

        # Currency preferences
        ("default_currency", "TEXT DEFAULT 'USD'", "TEXT DEFAULT 'USD'"),
        ("currency_conversion_enabled", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),

        # Nigerian payout support
        ("naira_bank_details", "TEXT", "TEXT"),

        # Solana/Jupiter (may be missing in older DBs)
        ("solana_rpc_url", "TEXT", "TEXT"),
        ("jupiter_enabled", "BOOLEAN", "BOOLEAN"),

        # Environment mode
        ("environment_mode", 'TEXT DEFAULT "sandbox"', "TEXT DEFAULT 'sandbox'"),

        # Broker paper trading config
        ("broker_paper_trading_config", "TEXT", "TEXT"),
        ("universal_paper_trading_config", "TEXT", "TEXT"),

        # Payout config (crypto wallet / naira bank auto-payout)
        ("payout_config", "TEXT", "TEXT"),

        # Frontend trading mode + UI preferences
        ("trading_mode", "TEXT DEFAULT 'practice'", "TEXT DEFAULT 'practice'"),
        ("preferences", "TEXT", "TEXT"),
    ]

    for col, sqlite_ddl, pg_ddl in expected_columns:
        await add_column_if_missing("device_settings", col, sqlite_ddl, pg_ddl)


async def _migrate_portfolios():
    """Add missing columns to portfolios table."""
    expected_columns = [
        ("device_id", "TEXT NOT NULL DEFAULT 'legacy_device'", "VARCHAR(255) NOT NULL DEFAULT 'legacy_device'"),
        ("name", "TEXT DEFAULT 'Default'", "VARCHAR(255) DEFAULT 'Default'"),
        ("cash", "REAL DEFAULT 10000.0", "FLOAT DEFAULT 10000.0"),
        ("initial_value", "REAL DEFAULT 10000.0", "FLOAT DEFAULT 10000.0"),
        ("initial_capital", "REAL DEFAULT 10000.0", "FLOAT DEFAULT 10000.0"),
        ("is_paper", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),
        ("broker", "TEXT", "VARCHAR(64)"),
        ("is_active", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),
    ]

    for col, sqlite_ddl, pg_ddl in expected_columns:
        await add_column_if_missing("portfolios", col, sqlite_ddl, pg_ddl)


async def _migrate_signal_tips():
    """Add hands-free execution columns to the signal_tips table."""
    expected_columns = [
        ("execution_status", "VARCHAR(32) DEFAULT 'pending'", "VARCHAR(32) DEFAULT 'pending'"),
        ("execution_detail", "TEXT", "TEXT"),
        ("executed_at", "TIMESTAMP", "TIMESTAMP"),
    ]

    for col, sqlite_ddl, pg_ddl in expected_columns:
        await add_column_if_missing("signal_tips", col, sqlite_ddl, pg_ddl)


async def _migrate_whatsapp_users():
    """Add missing columns to whatsapp_users table if needed."""
    expected_columns = [
        ("device_id", "TEXT NOT NULL", "VARCHAR(255) NOT NULL"),
        ("phone_number", "TEXT NOT NULL", "VARCHAR(64) NOT NULL"),
        ("trade_notifications_enabled", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),
        ("daily_summary_enabled", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),
        ("summary_time_wat", "TEXT DEFAULT '20:00'", "VARCHAR(8) DEFAULT '20:00'"),
        ("chat_enabled", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),
        ("ai_explanations_enabled", "BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT true"),
        ("is_verified", "BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT false"),
        ("verification_code", "TEXT", "TEXT"),
        ("verification_expires_at", "TIMESTAMP", "TIMESTAMP"),
        ("last_active_at", "TIMESTAMP", "TIMESTAMP"),
    ]

    for col, sqlite_ddl, pg_ddl in expected_columns:
        await add_column_if_missing("whatsapp_users", col, sqlite_ddl, pg_ddl)


async def _migrate_trades():
    """Add missing columns to trades table."""
    expected_columns = [
        ("portfolio_id", "INTEGER", "INTEGER"),
        ("entry_price", "REAL", "FLOAT"),
        ("exit_price", "REAL", "FLOAT"),
        ("pnl", "REAL", "FLOAT"),
        ("pnl_percent", "REAL", "FLOAT"),
    ]

    for col, sqlite_ddl, pg_ddl in expected_columns:
        await add_column_if_missing("trades", col, sqlite_ddl, pg_ddl)
