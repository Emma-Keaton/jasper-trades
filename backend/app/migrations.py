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
        logger.info("✓ Created/verified all tables")
        
        # Step 2: Add missing columns to device_settings (if needed)
        await _migrate_device_settings()
        
        logger.info("✓ Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}", exc_info=True)
        raise


async def _migrate_device_settings():
    """Add missing columns to device_settings table."""
    
    # Define expected columns and their types
    expected_columns = {
        # Exness/MT5
        'exness_login_id': 'TEXT',
        'exness_server': 'TEXT',
        'exness_password': 'TEXT',
        'exness_investor_password': 'TEXT',
        'exness_enabled': 'BOOLEAN',
        
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
        
        # Solana/Jupiter (may be missing in older DBs)
        'solana_rpc_url': 'TEXT',
        'jupiter_enabled': 'BOOLEAN',
        
        # IBKR (may be missing in older DBs)
        'ibkr_host': 'TEXT',
        'ibkr_port': 'INTEGER',
        'ibkr_client_id': 'INTEGER',
        'ibkr_enabled': 'BOOLEAN',
    }
    
    existing_columns = await get_existing_columns('device_settings')
    
    for column_name, column_type in expected_columns.items():
        if column_name not in existing_columns:
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"ALTER TABLE device_settings ADD COLUMN {column_name} {column_type}")
                    )
                logger.info(f"✓ Added column: {column_name} ({column_type})")
            except Exception as e:
                logger.warning(f"Could not add column {column_name}: {e}")