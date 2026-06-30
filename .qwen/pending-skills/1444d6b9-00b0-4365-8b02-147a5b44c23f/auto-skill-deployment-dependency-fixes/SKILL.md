---
name: deployment-dependency-fixes
description: Troubleshoot Render deployment failures from missing Python dependencies and model constraints
source: auto-skill
extracted_at: '2026-06-30T00:06:46.130Z'
---

# Render Deployment Dependency Troubleshooting

## Pattern
Fixed recurring `ModuleNotFoundError` failures on Render caused by:
1. Missing Python packages in `requirements.txt`
2. Model constraint violations (missing required fields like `device_id`)
3. Missing imports in startup code (`asyncio`)

## Issues Encountered

### 1. Missing `loguru` Dependency
**Symptom:** 
```
ModuleNotFoundError: No module named 'loguru'
at /app/backend/app/services/agent_reach/market_intel_service.py:17
```

**Root Cause:** Code imported `loguru` but it was not listed in `requirements.txt`

**Fix:**
```bash
# In requirements.txt, under # Logging section
loguru>=0.7.0
```

**Commit:** `git add backend/requirements.txt && git commit -m "fix: Add loguru dependency" && git push`

Render auto-deploys on push to `main`.

---

### 2. Missing `device_id` in Portfolio Creation
**Symptom:**
```
sqlite3.IntegrityError: NOT NULL constraint failed: portfolios.device_id
[SQL: INSERT INTO portfolios (device_id, ...) VALUES (None, ...)]
```

**Root Cause:** 
- `Portfolio` model requires `device_id` (field is `nullable=False`)
- Startup code in `main.py` called `create_portfolio()` without passing `device_id`

**Fix - Two step process:**

**Step A:** Update `PortfolioService.create_portfolio()` signature to accept `device_id`:
```python
# backend/app/services/portfolio_service.py

async def create_portfolio(
    self,
    name: str,
    initial_cash: float = 100000.0,
    is_paper: bool = True,
    broker: str = "ctrader",
    device_id: Optional[str] = None,  # ✅ Added parameter
) -> Portfolio:
    portfolio = Portfolio(
        device_id=device_id,  # ✅ Pass to model
        name=name,
        cash=initial_cash,
        initial_value=initial_cash,
        is_paper=is_paper,
        broker=broker,
    )
```

**Step B:** Generate `device_id` in startup code before creating portfolio:
```python
# backend/app/main.py

import uuid  # ✅ Added import

# In on_event("startup") handler
if not portfolios:
    device_id = str(uuid.uuid4())  # ✅ Generate unique ID
    await portfolio_service.create_portfolio(
        name="Default",
        initial_cash=100000.0,
        is_paper=True,
        device_id=device_id,  # ✅ Pass generated ID
    )
```

**Commit:** `git add backend/app/main.py backend/app/services/portfolio_service.py && git commit -m "fix: Add device_id to portfolio creation" && git push`

---

### 3. Missing `asyncio` Import
**Symptom:**
```
Telegram Bot startup failed: name 'asyncio' is not defined
```

**Root Cause:** Code used `asyncio.create_task()` but forgot `import asyncio`

**Fix:**
```python
# backend/app/main.py - top of file
import logging
import asyncio  # ✅ Added
import uuid  # ✅ Added (also needed for device_id)
from fastapi import FastAPI, Depends, HTTPException
```

---

## Deployment Verification
After pushing fixes, monitor Render logs:
```bash
# Expected success indicators
INFO: Created default portfolio for device a1b2c3d4...
INFO: Jasper Trades startup complete
INFO: Scheduler started
INFO: Market data started with X symbols
```

**Health Check:** 
```bash
curl https://jasper-trades.onrender.com/api/v1/health
# Should return: {"status":"ok"}
```

---

## Why These Failures Occur

1. **Dependencies:** Python packages used in code must be explicitly listed in `requirements.txt`. Unlike local dev where you might have globally installed packages, production builds are clean environments.

2. **Database Constraints:** When model fields are marked `nullable=False`, every creation must provide that field. Missing fields cause hard failures, not warnings.

3. **Imports:** Python requires explicit imports even for standard library modules like `asyncio`. The interpreter doesn't auto-import common modules.

---

## Prevention Checklist

Before deploying to Render:

- [ ] Run locally: `pip freeze > backend/requirements.txt` to ensure all packages are listed
- [ ] Check that `.env.example` includes all required environment variables
- [ ] Verify all model `create()` calls provide required (non-nullable) fields
- [ ] Test startup code locally: `python -m uvicorn app.main:app --reload`
- [ ] Check logs for `ModuleNotFoundError` and `IntegrityError` during local startup
- [ ] Ensure `import asyncio` is present in any file using `asyncio.create_task()`

---

## Learnings

- **Loguru was imported but forgotten from requirements**: The `market_intel_service.py` file used `from loguru import logger` but the dependency was listed under `# Logging` section as `structlog` only. Need to review ALL imports across the codebase when adding new dependencies.

- **Startup errors are silent warnings**: The portfolio creation error was logged as `logger.warning()` which didn't prevent the app from starting, but the Telegram bot error repeated twice indicated a real problem. Distinguish between recoverable warnings and hard failures.

- **Device ID is critical for user isolation**: The `device_id` field connects portfolios, settings, and notifications. Without it, the app cannot function in production since there's no user authentication system—device ID *is* the identity.