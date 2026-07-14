"""
Database Migration System
Automatically migrates database schema on application startup.
No external tools (Alembic) needed - simple SQLAlchemy-based migrations.
"""
import structlog
from sqlalchemy import text, inspect
from app.models import Base
from app.database import engine

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


async def migrate():
    """
    Run database migrations.
    Creates tables and adds missing columns automatically.
    """
    logger.info("Starting database migration...")

    try:
        # Step 1: Create all tables that don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[OK] Created/verified all tables")

        # Step 2: Add missing columns to device_settings (if needed)
        await _migrate_device_settings()
        
        # Step 3: Add missing columns to portfolios (if needed)
        await _migrate_portfolios()

        logger.info("[OK] Database migration completed successfully")

    except Exception as e:
        logger.error(f"Database migration failed: {e}", exc_info=True)
        raise


async def _migrate_device_settings():
    """Add missing columns to device_settings table."""

    # Define expected columns and their types
    expected_columns = {
        # Market Data APIs
        'alphavantage_key': 'TEXT',
        'finnhub_key': 'TEXT',
        'twelvedata_key': 'TEXT',
        'polygon_key': 'TEXT',
        'fred_key': 'TEXT',
        'coingecko_enabled': 'BOOLEAN',

        # News/Sentiment
        'newsapi_key': 'TEXT',
        'cryptopanic_key': 'TEXT',
        'av_news_sentiment_enabled': 'BOOLEAN',

        # Email Service
        'sendgrid_config': 'TEXT',

        # Discord Bot
        'discord_bot_config': 'TEXT',

        # Tatum for payouts
        'tatum_api_key': 'TEXT',

        # Trove API (Nigerian/US stocks)
        'trove_api_key': 'TEXT',
        'trove_base_url': 'TEXT',
        'trove_enabled': 'BOOLEAN',
        'trove_account_id': 'TEXT',
        'trove_sandbox': 'BOOLEAN DEFAULT 1',

        # AKShare (Chinese stocks)
        'akshare_config': 'TEXT',
        'akshare_sandbox': 'BOOLEAN DEFAULT 1',

        # cTrader sandbox mode
        'ctrader_sandbox': 'BOOLEAN DEFAULT 1',

        # Currency preferences
        'default_currency': "TEXT DEFAULT 'USD'",
        'currency_conversion_enabled': 'BOOLEAN DEFAULT 1',

        # Nigerian payout support
        'naira_bank_details': 'TEXT',

        # Solana/Jupiter (may be missing in older DBs)
        'solana_rpc_url': 'TEXT',
        'jupiter_enabled': 'BOOLEAN',

        # Environment mode
        'environment_mode': 'TEXT DEFAULT "sandbox"',
        
        # Broker paper trading config
        'broker_paper_trading_config': 'TEXT',
        'universal_paper_trading_config': 'TEXT',
    }

    existing_columns = await get_existing_columns('device_settings')

    for column_name, column_type in expected_columns.items():
        if column_name not in existing_columns:
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"ALTER TABLE device_settings ADD COLUMN {column_name} {column_type}")
                    )
                logger.info(f"âœ“ Added column: {column_name} ({column_type})")
            except Exception as e:
                logger.warning(f"Could not add column {column_name}: {e}")


async def _migrate_portfolios():
    """Add missing columns to portfolios table."""
    
    # Define expected columns and their types based on the Portfolio model
    expected_columns = {
        'device_id': "TEXT NOT NULL DEFAULT 'legacy_device'",  # String(255) becomes TEXT, NOT NULL with default
        'name': "TEXT DEFAULT 'Default'",
        'cash': 'REAL DEFAULT 100000.0',  # FLOAT in SQLite is REAL
        'initial_value': 'REAL DEFAULT 100000.0',
        'initial_capital': 'REAL DEFAULT 10000.0',
        'is_paper': 'BOOLEAN DEFAULT 1',  # SQLite BOOLEAN is INTEGER (0/1)
        'broker': 'TEXT',
        'is_active': 'BOOLEAN DEFAULT 1',
    }
    
    # Note: id and created_at are handled by table creation, not needing migration usually
    
    existing_columns = await get_existing_columns('portfolios')

    for column_name, column_type in expected_columns.items():
        if column_name not in existing_columns:
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"ALTER TABLE portfolios ADD COLUMN {column_name} {column_type}")
                    )
                logger.info(f"âœ“ Added column: {column_name} ({column_type}) to portfolios")
            except Exception as e:
                logger.warning(f"Could not add column {column_name} to portfolios: {e}")


async def _migrate_whatsapp_users():
    """Add missing columns to whatsapp_users table if needed."""
    
    # Define expected columns and their types
    expected_columns = {
        'device_id': "TEXT NOT NULL",
        'phone_number': 'TEXT NOT NULL',
        'trade_notifications_enabled': 'BOOLEAN DEFAULT 1',
        'daily_summary_enabled': 'BOOLEAN DEFAULT 1',
        'summary_time_wat': "TEXT DEFAULT '20:00'",
        'chat_enabled': 'BOOLEAN DEFAULT 1',
        'ai_explanations_enabled': 'BOOLEAN DEFAULT 1',
        'is_verified': 'BOOLEAN DEFAULT 0',
        'verification_code': 'TEXT',
        'verification_expires_at': 'TIMESTAMP',
        'last_active_at': 'TIMESTAMP',
    }
    
    existing_columns = await get_existing_columns('whatsapp_users')
    
    for column_name, column_type in expected_columns.items():
        if column_name not in existing_columns:
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"ALTER TABLE whatsapp_users ADD COLUMN {column_name} {column_type}")
                    )
                logger.info(f"âœ“ Added column: {column_name} ({column_type}) to whatsapp_users")
            except Exception as e:
                logger.warning(f"Could not add column {column_name} to whatsapp_users: {e}")
