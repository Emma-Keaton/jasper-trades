# Automatic Database Setup for Deployment

## Overview

Jasper Trades now includes **automatic database migration** that runs on every application startup. No manual database setup is required when deploying to production.

## How It Works

### 1. Application Startup Flow

```
App Start → Lifespan Event → init_db() → migrate() → Check Tables → Add Missing Columns → Ready
```

### 2. Migration System (`app/migrations.py`)

The migration system:
- ✅ Creates all tables that don't exist
- ✅ Adds missing columns to existing tables
- ✅ Preserves existing data
- ✅ Runs automatically on every startup
- ✅ Safe to run multiple times (idempotent)

### 3. What Gets Migrated

**Tables Created:**
- `device_settings` - API keys and configuration
- `portfolios` - Trading portfolios
- `positions` - Stock/crypto positions
- `signals` - Trading signals
- `withdrawals` - Payout records
- All other application tables

**Columns Added to `device_settings`:**
- Exness/MT5 integration (login_id, server, password, etc.)
- Market data APIs (alphavantage, finnhub, twelvedata, etc.)
- Notification configs (discord, slack, email, telegram, whatsapp)
- Email service (sendgrid)
- Discord bot config
- Tatum API key for payouts
- And more...

## Deployment Checklist

### Render Deployment

1. **Build Script (`render-build.sh`)**:
   ```bash
   # Creates data directories
   mkdir -p backend/data/sqlite
   mkdir -p backend/data/swarm_tasks
   ```

2. **Start Command**:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
   - Migrations run automatically via `lifespan` event
   - No manual intervention needed

3. **Environment Variables**:
   ```env
   DATABASE_URL=sqlite+aiosqlite:///./data/sqlite/jasper_trades.db
   DATA_DIR=./data
   PORT=8080
   ```

### Docker Deployment

1. **Dockerfile**:
   ```dockerfile
   # Data directories created during build
   RUN mkdir -p /app/backend/data/sqlite
   
   # Migrations run on container start
   CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
   ```

2. **Volume Mounts** (for persistent data):
   ```yaml
   volumes:
     - ./data:/app/backend/data
   ```

### Local Development

1. **First Run**:
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```
   - Database auto-initializes
   - No manual setup needed

2. **Reset Database** (if needed):
   ```bash
   rm backend/data/sqlite/jasper_trades.db
   # Restart server - fresh database created automatically
   ```

## Troubleshooting

### Database Locked Error

**Symptom:** `sqlite3.OperationalError: database is locked`

**Solution:**
```bash
# Kill any running backend processes
taskkill /F /IM python.exe

# Remove lock file
rm backend/data/sqlite/jasper_trades.db-shm
rm backend/data/sqlite/jasper_trades.db-wal

# Restart backend
```

### Missing Columns After Update

**Symptom:** `no such column: exness_login_id`

**Solution:**
```bash
# Backend should auto-migrate on startup
# Check logs for migration messages:
# "✓ Added column: exness_login_id"

# If not auto-migrating, check:
# 1. app/migrations.py exists
# 2. app/database.py calls migrate()
# 3. app/main.py lifespan event runs
```

### Manual Migration (Last Resort)

If automatic migration fails:

```bash
cd backend
python -c "
import asyncio
from app.migrations import migrate

async def run_migration():
    await migrate()
    print('Migration completed!')

asyncio.run(run_migration())
"
```

## What Changed

### New Files
- `backend/app/migrations.py` - Migration system

### Modified Files
- `backend/app/database.py` - Calls `migrate()` instead of `create_all()`
- `backend/Dockerfile` - Added startup message
- `backend/render-build.sh` - Creates data directories
- `backend/app/api/v1/portfolio.py` - Added GET `/holdings` and `/cash` endpoints
- `backend/app/services/scheduler.py` - Fixed signal generation error

### Fixed Issues
1. ✅ **Signal generation error**: `'list' object has no attribute 'items'`
2. ✅ **Missing holdings endpoint**: 404 error
3. ✅ **Missing cash endpoint**: 405 error (now supports GET)
4. ✅ **Database schema mismatches**: Auto-migration handles this

## Verification

After deployment, verify the database is set up correctly:

```bash
# Check health endpoint
curl https://your-backend.onrender.com/api/v1/health

# Check settings endpoint (should return "No settings found")
curl -H "X-Device-ID: test" https://your-backend.onrender.com/api/v1/settings

# Check portfolio endpoints
curl https://your-backend.onrender.com/api/v1/portfolio/1/holdings
curl https://your-backend.onrender.com/api/v1/portfolio/1/cash
```

All endpoints should respond without database errors.

## Summary

**Before:** Manual database setup required, schema mismatches caused errors

**After:** Fully automatic - just deploy and the database is ready

**Zero manual intervention needed** 🎉