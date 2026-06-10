---
name: automatic-database-migration-system
description: SQLite database auto-migration on startup - creates tables and adds missing columns without manual intervention
source: auto-skill
extracted_at: '2026-06-10T23:59:00.000Z'
---

# Automatic Database Migration System

## Problem Solved

When deploying updates with new database columns (e.g., Exness integration, market data APIs), the existing SQLite database would be missing columns, causing 500 errors like:
```
(sqlite3.OperationalError) no such column: device_settings.exness_login_id
```

Manual database migration (Alembic) was overkill for this project's needs. A simpler, automatic solution was required.

## Solution Approach

Created a lightweight migration system that runs on every application startup via FastAPI's lifespan event.

## Implementation

### 1. Create Migration Module (`backend/app/migrations.py`)

```python
"""
Database Migration System - Automatically migrates schema on startup.
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
    """Run database migrations - creates tables and adds missing columns."""
    logger.info("Starting database migration...")
    
    try:
        # Step 1: Create all tables that don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ Created/verified all tables")
        
        # Step 2: Add missing columns to device_settings
        await _migrate_device_settings()
        
        logger.info("✓ Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}", exc_info=True)
        raise


async def _migrate_device_settings():
    """Add missing columns to device_settings table."""
    
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
```

### 2. Update Database Init (`backend/app/database.py`)

```python
async def init_db():
    """Initialize database with migrations."""
    from app.migrations import migrate
    await migrate()  # Was: await conn.run_sync(Base.metadata.create_all)
```

### 3. Ensure Lifespan Event Calls Init (`backend/app/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up Jasper Trades...")
    await init_db()  # This triggers migrations
    logger.info("Database initialized")
    # ... rest of startup
```

### 4. Update Deployment Scripts

**render-build.sh:**
```bash
# Ensure data directories exist for runtime
mkdir -p backend/data/sqlite
mkdir -p backend/data/swarm_tasks
```

**Dockerfile:**
```dockerfile
# Run application with automatic migrations
CMD ["sh", "-c", "echo '🚀 Starting with automatic migrations...' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

## Key Learnings

1. **No external tools needed**: SQLAlchemy's `inspect()` provides all the introspection needed
2. **Idempotent migrations**: Safe to run on every startup - checks existence before creating
3. **Preserves data**: ALTER TABLE ADD COLUMN preserves existing data
4. **Fast startup**: Only adds missing columns, doesn't scan all data
5. **Works everywhere**: Local dev, Render, Docker - same automatic behavior

## Deployment Flow

```
App Start → Lifespan Event → init_db() → migrate()
    ↓
Check tables exist → Create if missing
    ↓
Check columns exist → Add if missing
    ↓
Database ready - no manual intervention needed
```

## Troubleshooting

**Database locked error:**
```bash
# Kill backend processes
taskkill /F /IM python.exe
# Remove lock files
rm backend/data/sqlite/*.db-shm backend/data/sqlite/*.db-wal
```

**Manual migration (if auto fails):**
```bash
cd backend
python -c "
import asyncio
from app.migrations import migrate
asyncio.run(migrate())
"
```

## When to Use This Pattern

- ✅ SQLite-based applications
- ✅ Frequent schema changes during development
- ✅ Simple column additions (not complex transformations)
- ✅ Zero-manual-intervention deployments
- ✅ Single-instance applications (not distributed DBs)

**Don't use for:**
- ❌ Complex data migrations (use Alembic)
- ❌ Multi-database setups
- ❌ Schema deprecations (need manual review)
- ❌ Production databases with strict compliance requirements