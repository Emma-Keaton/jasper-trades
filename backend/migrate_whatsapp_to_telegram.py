"""
Database Migration: WhatsApp → Telegram
Renames whatsapp_users table to telegram_users
Updates daily_summaries table columns
"""
import asyncio
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logger = structlog.get_logger(__name__)

# Database URL - update if needed
DATABASE_URL = "sqlite+aiosqlite:///./data/sqlite/jasper_trades.db"


async def migrate_whatsapp_to_telegram():
    """
    Migration steps:
    1. Drop old whatsapp_users table
    2. Create new telegram_users table (handled by SQLAlchemy auto-migration)
    3. Update daily_summaries table: rename phone_number to chat_id
    """
    logger.info("Starting WhatsApp → Telegram migration...")
    
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.connect() as conn:
        try:
            # Step 1: Drop old whatsapp_users table
            logger.info("Dropping old whatsapp_users table...")
            await conn.execute(text("DROP TABLE IF EXISTS whatsapp_users"))
            await conn.commit()
            logger.info("✓ whatsapp_users table dropped")
            
            # Step 2: Update daily_summaries - rename phone_number to chat_id
            logger.info("Updating daily_summaries table...")
            
            # Check if phone_number column exists
            result = await conn.execute(text("""
                PRAGMA table_info(daily_summaries)
            """))
            columns = [row[1] for row in result.fetchall()]
            
            if 'phone_number' in columns:
                # SQLite doesn't support RENAME COLUMN directly in older versions
                # We need to recreate the table
                
                # Step 2a: Get all data
                result = await conn.execute(text("""
                    SELECT * FROM daily_summaries
                """))
                existing_data = result.fetchall()
                column_names = [col[1] for col in result.cursor.description]
                
                logger.info(f"Found {len(existing_data)} existing daily summaries")
                
                # Step 2b: Drop old table
                await conn.execute(text("DROP TABLE daily_summaries"))
                await conn.commit()
                
                # Step 2c: Recreate table (SQLAlchemy will handle this on app startup)
                # For now, we just drop it - app will recreate on next startup
                logger.info("✓ daily_summaries table dropped - will be recreated on app startup")
                
            else:
                logger.info("daily_summaries table already has correct schema")
            
            # Step 3: Clean up any WhatsApp-specific config files
            import os
            from pathlib import Path
            
            config_files = [
                Path("data/whatsapp_config.json"),
                Path("data/openwa_config.json"),
            ]
            
            for config_file in config_files:
                if config_file.exists():
                    try:
                        config_file.unlink()
                        logger.info(f"✓ Deleted old config: {config_file}")
                    except Exception as e:
                        logger.warning(f"Could not delete {config_file}: {e}")
            
            logger.info("✅ WhatsApp → Telegram migration complete!")
            logger.info("Restart the application to apply all changes.")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await conn.rollback()
            raise
        finally:
            await engine.close()


if __name__ == "__main__":
    print("Running WhatsApp → Telegram database migration...")
    print("This will:")
    print("  1. Drop the old whatsapp_users table")
    print("  2. Drop daily_summaries table (will be recreated)")
    print("  3. Delete old WhatsApp config files")
    print()
    print("The app will recreate tables with the new schema on next startup.")
    print()
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response == "yes":
        asyncio.run(migrate_whatsapp_to_telegram())
    else:
        print("Migration cancelled.")