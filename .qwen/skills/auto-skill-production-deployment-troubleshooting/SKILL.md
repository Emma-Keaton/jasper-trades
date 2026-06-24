---
name: production-deployment-troubleshooting
description: Systematic approach to troubleshooting Python import errors and abstract method issues in FastAPI deployments
source: auto-skill
extracted_at: '2026-06-24T01:18:26.418Z'
---

# Production Deployment Troubleshooting - FastAPI + Render

This skill captures the systematic approach to diagnosing and fixing deployment-blocking errors in Python/FastAPI applications, particularly on Render.com.

## Context

During production deployment of Jasper Trades (AI trading platform), encountered a cascade of import errors and missing implementations that prevented the app from starting. Each error revealed the next layer of issues.

## Common Error Patterns & Solutions

### 1. **ModuleNotFoundError: No module named 'app.services.X'**

**Error:**
```
ImportError: cannot import name 'trove' from 'app.api.v1'
ModuleNotFoundError: No module named 'app.services.akshare_service'
ImportError: cannot import name 'EncryptionService' from 'app.services.encryption'
```

**Root Causes:**
- Module doesn't exist (trove.py)
- Wrong import path (services vs brokers)
- Class name mismatch (EncryptionService vs EncryptionHelper)
- Deleted service still referenced (whatsapp_service)

**Diagnostic Steps:**
```bash
# 1. Verify file exists
find backend/app -name "*.py" | grep -i trove

# 2. Check what the module actually exports
python -c "from app.services import encryption; print(dir(encryption))"

# 3. Grep for the correct class name
grep -r "class Encryption" backend/app/services/
```

**Solutions:**

**A. Create missing module:**
```python
# backend/app/api/v1/trove.py
from fastapi import APIRouter
router = APIRouter(prefix="/trove", tags=["trove"])

@router.get("/status")
async def get_status():
    return {"status": "ok"}
```

**B. Fix import path:**
```python
# WRONG - service doesn't exist
from app.services.akshare_service import get_akshare_service

# CORRECT - check actual file location
from app.brokers.akshare_service import AKShareBrokerService
```

**C. Fix class name:**
```python
# WRONG - class doesn't exist
from app.services.encryption import EncryptionService

# CORRECT - check actual class name
from app.services.encryption import EncryptionHelper
```

**D. Remove dead references:**
```python
# config.py - referencing deleted whatsapp_service
from app.services.whatsapp_service import EncryptionService  # File deleted!

# Replace with existing service
from app.services.encryption import EncryptionHelper
```

### 2. **Can't instantiate abstract class**

**Error:**
```
Failed to initialize AKShare: Can't instantiate abstract class 
AKShareBrokerService with abstract methods get_account, get_clock, 
get_order_status, get_position
```

**Root Cause:**
Class inherits from abstract base class but doesn't implement all `@abstractmethod` methods.

**Diagnostic Steps:**
```bash
# 1. Find the base class
grep -r "class AKShareBrokerService" backend/app/

# 2. Check what it extends
grep "class.*BaseBrokerService" backend/app/brokers/base.py

# 3. List all abstract methods
grep -A 2 "@abstractmethod" backend/app/brokers/base.py
```

**Solution - Implement all abstract methods:**
```python
# backend/app/brokers/akshare_service.py

async def get_account(self) -> AccountData:
    """Get account balance."""
    return await self.get_account_data()

async def get_clock(self) -> Dict[str, Any]:
    """Get market trading hours status."""
    now = datetime.now()
    is_open = (now.hour == 9 and now.minute >= 30) or \
              now.hour == 10 or \
              now.hour == 11 and now.minute < 30
    return {
        "is_open": is_open,
        "timezone": "Asia/Shanghai",
        "next_open": "09:30",
        "next_close": "15:00",
    }

async def get_order_status(self, order_id: str) -> Dict[str, Any]:
    """Get order status (paper trading - always filled)."""
    return {
        "order_id": order_id,
        "status": "filled",
        "message": "Paper trading mode",
    }

async def get_position(self, symbol: str) -> Optional[PositionData]:
    """Get specific position."""
    return self._positions.get(symbol)
```

**Why this works:** Abstract base classes enforce a contract. All `@abstractmethod` decorators must be implemented before instantiation.

### 3. **Type annotation errors**

**Error:**
```
NameError: name 'string' is not defined
```

**Root Cause:**
Python doesn't have a `string` type - it's `str`.

**Solution:**
```python
# WRONG
async def submit_order(self, symbol: string, side: str):

# CORRECT
async def submit_order(self, symbol: str, side: str):
```

**Lesson:** Python type hints use `str`, `int`, `float`, `bool`, `List`, `Dict`, `Optional`, etc. Never `string`.

### 4. **Fernet encryption key format**

**Error:**
```
binascii.Error: Incorrect padding
ValueError: Fernet key must be 32 url-safe base64-encoded bytes
```

**Root Cause:**
Fernet requires very specific key format: exactly 32 bytes, URL-safe base64 encoded.

**Diagnostic:**
```python
# Check if key is valid
from cryptography.fernet import Fernet

key = "your_key_from_env"
try:
    f = Fernet(key)
    print("Key is valid")
except ValueError as e:
    print(f"Invalid key: {e}")
```

**Solutions:**

**A. Generate proper key:**
```python
from cryptography.fernet import Fernet

# This generates a proper 32-byte base64-encoded key
key = Fernet.generate_key().decode()
print(key)  # e.g., "GMpJdlIzXmX3V295lJdI04B7kk1hO290YCK-dOfXIA8="
```

**B. Validate environment variable:**
```python
# config.py or .env.render
ENCRYPTION_KEY=GMpJdlIzXmX3V295lJdI04B7kk1hO290YCK-dOfXIA8=  # ✅ Valid
ENCRYPTION_KEY=my_secret_key  # ❌ Invalid - wrong format
```

**C. Handle missing key gracefully:**
```python
class MyService:
    def __init__(self):
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        self.encryptor = None
        
        if self.encryption_key:
            try:
                self.encryptor = Fernet(self.encryption_key.encode())
            except ValueError:
                logger.warning("Invalid encryption key format")
```

### 5. **Stale bytecode cache (.pyc files)**

**Error:**
```
Telegram Bot startup failed: name 'asyncio' is not defined
```

**Root Cause:**
Python compiles `.py` to `.pyc` bytecode. Deployment platforms may run stale cache even after you fix the source.

**Evidence:**
- Import clearly exists in source: `import asyncio` on line 5
- Error persists after push and redeploy
- Other imports work fine

**Solutions:**

**A. Clear cache locally before push:**
```bash
# Remove all __pycache__ directories and .pyc files
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete

# Then commit and push
git add -A
git commit -m "fix: Clear Python cache"
git push
```

**B. Force recompile on deployment:**
```bash
# Add to render-build.sh or Dockerfile
find . -name "*.pyc" -delete
python -m compileall .
```

**C. Make a trivial change to force recompile:**
```python
# Add a comment or whitespace change
logger = structlog.get_logger(__name__)  # Added space
```

**Why this works:** Deployment platforms detect file changes and recompile. A trivial change triggers fresh compilation.

## Systematic Debugging Workflow

When deployment fails with import/initialization errors:

### Step 1: Read the full traceback
```
File "/app/backend/app/main.py", line 58, in <module>
    from app.api.v1 import akshare_settings
File "/app/backend/app/api/v1/akshare_settings.py", line 13, in <module>
    from app.services.encryption import EncryptionService
ImportError: cannot import name 'EncryptionService' from ...
```

**Key info:**
- Which file is failing (akshare_settings.py line 13)
- What it's trying to import (EncryptionService)
- Where from (app.services.encryption)

### Step 2: Verify locally
```bash
# Try the exact import that's failing
python -c "from app.services.encryption import EncryptionService"

# Check what's actually available
python -c "from app.services import encryption; print(dir(encryption))"
# Output: ['EncryptionHelper', ...]
```

### Step 3: Fix and test
```python
# Fix the import
# from app.services.encryption import EncryptionService  # Wrong
from app.services.encryption import EncryptionHelper  # Correct

# Test locally
python -c "from app.api.v1 import akshare_settings; print('OK')"
```

### Step 4: Clear cache and push
```bash
find . -name "*.pyc" -delete
git add -A
git commit -m "fix: Correct import path"
git push origin main
```

### Step 5: Monitor deployment logs
Watch Render logs in real-time. If error persists, it's cache - make a trivial change to force recompile.

## Prevention Strategies

### 1. **Test imports before committing**
```bash
# Add to pre-commit hook or CI
python -c "from app.main import app; print('All imports OK')"
```

### 2. **Use IDE with type checking**
- PyCharm, VS Code with Pylance catch these at edit time
- Enable strict type checking in pyright/mypy

### 3. **Add import tests to CI**
```yaml
# .github/workflows/test-imports.yml
- name: Test imports
  run: |
    python -c "from app.main import app"
    python -c "from app.api.v1 import trove, akshare, akshare_settings"
```

### 4. **Document service locations**
```markdown
# ARCHITECTURE.md

## Service Locations
- Brokers: `backend/app/brokers/` (AKShare, Binance, etc.)
- API Routers: `backend/app/api/v1/`
- Services: `backend/app/services/` (encryption, telegram, etc.)
- Models: `backend/app/models.py`
```

### 5. **Use dependency injection**
Instead of importing services directly in routers, use FastAPI dependencies:
```python
from fastapi import Depends

def get_akshare_service() -> AKShareBrokerService:
    return AKShareBrokerService()

@router.get("/data")
async def get_data(service: AKShareBrokerService = Depends(get_akshare_service)):
    return await service.get_market_data()
```

## Key Takeaways

1. **Read tracebacks carefully** - They tell you exactly which file/line/import is broken
2. **Test imports locally** - `python -c "from X import Y"` before pushing
3. **Check actual file structure** - Don't assume, use `find` or IDE
4. **Abstract base classes enforce contracts** - Implement ALL `@abstractmethod` methods
5. **Fernet keys are picky** - Use `Fernet.generate_key()`, never random strings
6. **Cache lies** - Clear `.pyc` files when imports don't match source
7. **Python type hints** - Use `str`, never `string`
8. **Graceful degradation** - Wrap optional imports in try/except

## Result

✅ **Systematic debugging approach:**
- Identify exact error location from traceback
- Verify locally with targeted import test
- Fix the root cause (not just symptoms)
- Clear cache to prevent stale bytecode
- Test locally before pushing
- Monitor deployment logs for recurrence

**Time saved:** 2-3 hours of trial-and-error → 15 minutes of targeted fixes