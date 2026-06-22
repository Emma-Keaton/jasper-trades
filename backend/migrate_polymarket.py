"""
Database Migration: Add Polymarket CLOB Trading Tables

Creates:
- polymarket_accounts: Encrypted API credentials, account metadata
- polymarket_leader_configs: Copytrading leader configurations
- polymarket_positions: Open positions tracking
- polymarket_trades: Trade history

Run: cd backend && python migrate_polymarket.py
"""
import asyncio
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from pathlib import Path

logger = structlog.get_logger(__name__)

DATABASE_URL = "sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"


async def create_polymarket_tables():
    """Create Polymarket trading tables"""
    logger.info("Creating Polymarket tables...")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.connect() as conn:
        try:
            # 1. Create polymarket_accounts table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS polymarket_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id VARCHAR(255) NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    encrypted_api_secret TEXT NOT NULL,
                    wallet_address VARCHAR(50),
                    account_currency VARCHAR(3) DEFAULT 'USD',
                    account_balance FLOAT DEFAULT 0.0,
                    account_equity FLOAT DEFAULT 0.0,
                    ai_trading_enabled BOOLEAN DEFAULT 0,
                    copytrading_enabled BOOLEAN DEFAULT 0,
                    max_position_size FLOAT DEFAULT 100.0,
                    max_portfolio_risk FLOAT DEFAULT 0.20,
                    is_active BOOLEAN DEFAULT 1,
                    is_connected BOOLEAN DEFAULT 0,
                    connection_status VARCHAR(50),
                    last_balance_sync_at DATETIME,
                    last_trade_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create index on device_id
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_polymarket_accounts_device_id 
                ON polymarket_accounts(device_id)
            """))
            
            logger.info("✓ Created polymarket_accounts table")
            
            # 2. Create polymarket_leader_configs table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS polymarket_leader_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    is_active BOOLEAN DEFAULT 1,
                    last_copy_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES polymarket_accounts(id)
                )
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_leader_configs_account_id 
                ON polymarket_leader_configs(account_id)
            """))
            
            logger.info("✓ Created polymarket_leader_configs table")
            
            # 3. Create polymarket_positions table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS polymarket_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated_at DATETIME,
                    FOREIGN KEY (account_id) REFERENCES polymarket_accounts(id)
                )
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_polymarket_positions_account_id 
                ON polymarket_positions(account_id)
            """))
            
            logger.info("✓ Created polymarket_positions table")
            
            # 4. Create polymarket_trades table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS polymarket_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    execution_timestamp DATETIME,
                    was_copytrade BOOLEAN DEFAULT 0,
                    copied_from_leader_id VARCHAR(100),
                    ai_agent_decision VARCHAR(50),
                    realized_pnl FLOAT DEFAULT 0.0,
                    realized_pnl_percent FLOAT DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES polymarket_accounts(id)
                )
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_polymarket_trades_account_id 
                ON polymarket_trades(account_id)
            """))
            
            logger.info("✓ Created polymarket_trades table")
            
            await conn.commit()
            
            logger.info("✅ All Polymarket tables created successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await conn.rollback()
            raise


async def drop_polymarket_tables():
    """Drop all Polymarket tables (for testing/reset)"""
    logger.info("Dropping Polymarket tables...")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.connect() as conn:
        try:
            tables = [
                'polymarket_trades',
                'polymarket_positions',
                'polymarket_leader_configs',
                'polymarket_accounts',
            ]
            
            for table in tables:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                logger.info(f"✓ Dropped {table}")
            
            await conn.commit()
            logger.info("✅ All Polymarket tables dropped")
            
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            await conn.rollback()
            raise


if __name__ == "__main__":
    import sys
    
    print("Polymarket Database Migration")
    print("=" * 50)
    print()
    print("This will create tables for:")
    print("  - Polymarket CLOB accounts (encrypted credentials)")
    print("  - Leader copytrading configurations")
    print("  - Position tracking")
    print("  - Trade history")
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--drop':
        response = input("⚠️  DANGER: This will DELETE all Polymarket data. Continue? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            asyncio.run(drop_polymarket_tables())
        else:
            print("Cancelled.")
    else:
        response = input("Create tables? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            asyncio.run(create_polymarket_tables())
        else:
            print("Cancelled.")