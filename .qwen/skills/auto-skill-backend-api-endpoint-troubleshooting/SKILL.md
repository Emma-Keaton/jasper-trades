---
name: backend-api-endpoint-troubleshooting
description: Fix corrupted Python files, route registration issues, and Pydantic validation errors in FastAPI backend
source: auto-skill
extracted_at: '2026-06-13T15:20:28.843Z'
---

# Backend API Endpoint Troubleshooting

When backend endpoints return 404, 500 errors, or fail to start due to file corruption, follow this systematic approach.

## Common Issues & Solutions

### 1. File Corruption (Null Bytes)

**Symptom:** `SyntaxError: source code string cannot contain null bytes`

**Cause:** Interrupted write operations or disk errors can corrupt Python files.

**Fix:**
```bash
# Find corrupted files
powershell -Command "Get-ChildItem -Recurse -Filter *.py | Where-Object { (Get-Content -Path $_.FullName -Encoding Byte -ReadCount 0) -contains 0 } | Select-Object FullName"

# Remove null bytes from specific file
powershell -Command "$content = Get-Content -Path 'app\main.py' -Raw -Encoding Byte; $clean = $content | Where-Object { $_ -ne 0 }; [System.IO.File]::WriteAllBytes('E:\Projects\jasper-trades\backend\app\main.py', $clean)"

# Clean __pycache__ folders
rmdir /s /q __pycache__ app\__pycache__ app\*\__pycache__ app\*\*\__pycache__
```

**After cleaning:** Manually inspect the file for any remaining garbage text at the end and remove it.

### 2. Router Registration Issues

**Symptom:** Endpoints return 404 Not Found even though the file exists.

**Cause:** Router prefix mismatch between the router definition and main.py registration.

**Diagnosis:**
```bash
# Check actual registered paths
curl -s http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print('\n'.join([p for p in d.get('paths',{}).keys() if 'your_endpoint' in p.lower()]))"
```

**Patterns to check:**
- If router has `prefix="/api/v1"` in its definition → register in main.py **without** prefix
- If router has **no** prefix in its definition → register in main.py **with** `prefix="/api/v1"`

**Example fixes:**

```python
# In main.py - CORRECT registration patterns:

# Router with NO prefix in definition (e.g., banks.py)
app.include_router(banks.router, prefix="/api/v1", tags=["banks"])

# Router WITH prefix in definition (e.g., copytrade.py has prefix="/api/v1")
app.include_router(copytrade.router, tags=["Copy Trading"])  # NO prefix here!

# cTrader OAuth router has prefix="/api/v1/ctrader" in definition
app.include_router(broker_connections.router, tags=["Broker Connections"])  # NO prefix
```

**Double-prefix symptom:** Paths like `/api/v1/api/v1/copytrade/stats` mean you added prefix twice.

### 3. Pydantic Validation Errors

**Symptom:** `500 Internal Server Error` with `pydantic_core.ValidationError: N validation errors`

**Cause:** Service method returns dict missing required fields that the Pydantic model expects.

**Fix:**
```python
# In service method, ensure ALL required fields are returned:

# BEFORE (missing fields when no data):
if not follows:
    return {
        "following_count": 0,
        "total_copied_trades": 0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        # Missing: avg_pnl, total_signals_copied
    }

# AFTER (all fields present):
if not follows:
    return {
        "following_count": 0,
        "total_copied_trades": 0,
        "total_pnl": 0.0,
        "avg_pnl": 0.0,              # Added
        "win_rate": 0.0,
        "total_signals_copied": 0,   # Added
    }
```

**Check Pydantic model:**
```python
class CopyTradeStats(BaseModel):
    following_count: int
    total_copied_trades: int
    total_pnl: float
    avg_pnl: float           # ← Must be in response dict
    win_rate: float
    total_signals_copied: int  # ← Must be in response dict
```

### 4. Async Session Errors

**Symptom:** `AttributeError: 'AsyncSession' object has no attribute 'query'`

**Cause:** Using SQLAlchemy sync `session.query()` in async context.

**Fix:**
```python
# WRONG (sync style in async function):
result = db.query(BrokerConnection).filter(...).first()

# CORRECT (async style):
from sqlalchemy import select
result = await db.execute(select(BrokerConnection).filter(...))
connection = result.scalar_one_or_none()
```

## Verification Workflow

After applying fixes:

1. **Full restart** (hot reload may not pick up main.py changes):
   ```bash
   # Stop current server, then:
   cd E:\Projects\jasper-trades\backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Test all affected endpoints:**
   ```bash
   # Core endpoints
   curl -s http://localhost:8000/api/v1/health
   curl -s http://localhost:8000/api/v1/agents
   
   # Previously broken endpoints
   curl -s http://localhost:8000/api/v1/nigeria  # Banks
   curl -s http://localhost:8000/api/v1/copytrade/stats
   curl -s http://localhost:8000/api/v1/whatsapp/config
   curl -s http://localhost:8000/api/v1/ctrader/connect
   ```

3. **Check startup logs** for any remaining errors:
   ```bash
   type <shell-output-file> | findstr /c:"ERROR" /c:"Traceback" /i
   ```

## Prevention

- Always use `select()` + `execute()` pattern in async code
- Double-check router prefix patterns before adding to main.py
- Validate Pydantic models match service method return dicts exactly
- Clean `__pycache__` after file corruption fixes
- Perform full server restart (not reload) after main.py changes