"""Create broker_connections table for multi-broker support

This migration adds support for:
- cTrader OAuth connections (secure, no passwords)
- Binance API key storage (encrypted)

Users can connect multiple broker accounts and toggle auto-trading on/off.
"""

def migrate(migrator, database, fake=False, **kwargs):
    """Apply migration"""
    
    # Create broker_connections table
    migrator.add_sql("""
        CREATE TABLE IF NOT EXISTS broker_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            broker_type VARCHAR(20) NOT NULL,
            broker_name VARCHAR(100),
            account_id VARCHAR(100),
            account_currency VARCHAR(3) DEFAULT 'USD',
            account_balance REAL DEFAULT 0.0,
            
            -- cTrader OAuth
            ctrader_account_id VARCHAR(100),
            encrypted_access_token TEXT,
            encrypted_refresh_token TEXT,
            token_expires_at DATETIME,
            
            -- API keys (Binance, etc.)
            encrypted_api_key TEXT,
            encrypted_api_secret TEXT,
            
            -- Status
            is_active BOOLEAN DEFAULT 1,
            is_connected BOOLEAN DEFAULT 0,
            connection_status VARCHAR(50),
            last_sync_at DATETIME,
            
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Create indexes for fast lookups
    migrator.add_sql("""
        CREATE INDEX IF NOT EXISTS idx_broker_connections_user_id 
        ON broker_connections(user_id)
    """)
    
    migrator.add_sql("""
        CREATE INDEX IF NOT EXISTS idx_broker_connections_type 
        ON broker_connections(broker_type, is_connected, is_active)
    """)
    
    print("✅ broker_connections table created")


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback migration"""
    migrator.add_sql("DROP TABLE IF EXISTS broker_connections")
    print("❌ broker_connections table removed")