"""
cTrader OAuth Integration - Database Migrations

This migration adds support for cTrader OpenAPI OAuth authentication
and multi-tenant copy trading architecture.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime


def add_ctrader_tables(migrator, db):
    """Add cTrader OAuth and trading accounts tables"""
    
    # Create trading_accounts table (replaces deprecated brokers)
    migrator.add_sql("""
        CREATE TABLE IF NOT EXISTS trading_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_type VARCHAR(20) NOT NULL DEFAULT 'ctrader',  -- 'ctrader' or other
            
            -- cTrader OAuth fields
            ctid_trader_account_id VARCHAR(50),  -- cTrader account ID from API
            ctid_account_name VARCHAR(100),      -- User-friendly account name
            encrypted_access_token TEXT,         -- OAuth access token (encrypted)
            encrypted_refresh_token TEXT,        -- OAuth refresh token (encrypted)
            token_expires_at DATETIME,           -- When access token expires
            token_last_refreshed DATETIME,       -- Last token refresh time
            
            -- Account metadata from cTrader API
            broker_name VARCHAR(50),             -- e.g., 'FxPro', 'IronFX'
            account_currency VARCHAR(3) DEFAULT 'USD',
            account_leverage REAL DEFAULT 1.0,
            account_balance REAL DEFAULT 0.0,
            account_equity REAL DEFAULT 0.0,
            
            -- Status
            is_active BOOLEAN DEFAULT 1,         -- User can enable/disable bot
            is_connected BOOLEAN DEFAULT 0,      -- OAuth connection status
            connection_status VARCHAR(50),       -- 'connected', 'expired', 'revoked', 'error'
            last_sync_at DATETIME,               -- Last successful API sync
            
            -- Timestamps
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Create index for fast lookups
    migrator.add_sql("""
        CREATE INDEX IF NOT EXISTS idx_trading_accounts_user_id 
        ON trading_accounts(user_id)
    """)
    
    migrator.add_sql("""
        CREATE INDEX IF NOT EXISTS idx_trading_accounts_active 
        ON trading_accounts(is_active, is_connected)
    """)
    
    # Create execution_log table for audit trail
    migrator.add_sql("""
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_account_id INTEGER NOT NULL,
            strategy_name VARCHAR(100),
            action_type VARCHAR(20),  -- 'BUY', 'SELL', 'CLOSE'
            symbol VARCHAR(20),
            volume REAL,
            execution_price REAL,
            cTrader_order_id VARCHAR(50),
            status VARCHAR(20),  -- 'pending', 'executed', 'failed', 'cancelled'
            error_message TEXT,
            execution_time_ms INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (trading_account_id) REFERENCES trading_accounts(id)
        )
    """)
    
    # Create token_refresh_log for monitoring
    migrator.add_sql("""
        CREATE TABLE IF NOT EXISTS token_refresh_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_account_id INTEGER NOT NULL,
            old_token_expires_at DATETIME,
            new_token_expires_at DATETIME,
            refresh_successful BOOLEAN,
            error_message TEXT,
            refreshed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (trading_account_id) REFERENCES trading_accounts(id)
        )
    """)
    
    print("✅ cTrader OAuth tables created")


def remove_ctrader_tables(migrator, db):
    """Remove cTrader tables (rollback)"""
    migrator.add_sql("DROP TABLE IF EXISTS token_refresh_logs")
    migrator.add_sql("DROP TABLE IF EXISTS execution_logs")
    migrator.add_sql("DROP TABLE IF EXISTS trading_accounts")
    print("❌ cTrader OAuth tables removed")


def migrate(migrator, database, fake=False, **kwargs):
    """Apply migration"""
    add_ctrader_tables(migrator, database)


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback migration"""
    remove_ctrader_tables(migrator, database)