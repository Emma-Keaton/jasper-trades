"""
Trove Integration - Database Migrations

This migration adds support for Trove API (Nigerian/US stocks trading)
and currency conversion preferences.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime


def add_trove_columns(migrator, db):
    """Add Trove-related columns to device_settings table"""

    # Add Trove API columns
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN trove_api_key VARCHAR(500)
    """)
    
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN trove_base_url VARCHAR(200)
    """)
    
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN trove_enabled BOOLEAN DEFAULT 0
    """)
    
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN trove_account_id VARCHAR(100)
    """)
    
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN trove_sandbox BOOLEAN DEFAULT 1
    """)

    # Add currency preference columns
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN default_currency VARCHAR(3) DEFAULT 'USD'
    """)
    
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN currency_conversion_enabled BOOLEAN DEFAULT 1
    """)

    # Add Nigerian payout support
    migrator.add_sql("""
        ALTER TABLE device_settings ADD COLUMN naira_bank_details TEXT
    """)

    print("✅ Trove integration columns added")


def remove_trove_columns(migrator, db):
    """Remove Trove columns (rollback)"""
    # Note: SQLite doesn't support DROP COLUMN directly, 
    # this would require table recreation in a real rollback scenario
    print("⚠️  Rollback not supported in SQLite - columns would remain")


def migrate(migrator, database, fake=False, **kwargs):
    """Apply migration"""
    add_trove_columns(migrator, database)


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback migration"""
    remove_trove_columns(migrator, database)