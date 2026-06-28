---
name: endpoint-testing-and-verification
description: Systematic approach to testing FastAPI endpoints, diagnosing failures, and verifying frontend-backend integration
source: auto-skill
extracted_at: '2026-06-28T15:35:00.000Z'
---

# Endpoint Testing and Verification Workflow

## Overview
Complete workflow for testing backend endpoints, diagnosing connection issues, and verifying frontend integration in FastAPI + Next.js trading platforms.

## Procedure

### 1. Create Endpoint Test Script
Create `backend/test_endpoints.py` that:
- Defines all endpoints as dictionary with `(path, method)` tuples
- Supports optional headers for endpoints requiring device auth: `(path, method, {headers})`
- Tests each endpoint with configurable timeout (15s recommended for slow endpoints)
- Categorizes results: 200/422 = healthy, 400 = needs config, 404 = missing route, 500 = server error, timeout = slow endpoint
- Exports JSON report for CI/CD integration

```python
ENDPOINTS = {
    "Health Check": ("/api/v1/health", "GET"),
    "Nigerian Banks": ("/api/v1/nigeria", "GET"),
    "Payout Settings": ("/api/v1/withdrawal/payout/settings", "GET", {"X-Device-ID": "test-device"}),
}

def test_endpoint(name, path, method, headers=None):
    response = requests.get(f"{BASE_URL}{path}", timeout=15, headers=headers)
    return response.status_code
```

### 2. Common Endpoint Path Issues

**Router Prefix Confusion:**
- When `app.include_router(banks.router, prefix="/api/v1")` and router has no prefix → endpoint is at `/api/v1/nigeria` (not `/api/v1/banks/nigeria`)
- When router has prefix like `router = APIRouter(prefix="/chat")` and included with `prefix="/api/v1"` → endpoint is at `/api/v1/chat/*`

**Fix pattern:**
```python
# In main.py
from app.api.v1 import chat  # Missing import causes NameError
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
```

### 3. Diagnose 404 Errors
- Check router import exists in `main.py`
- Verify prefix stacking: `include_router(router, prefix="/api/v1")` + router prefix = final path
- Run: `curl http://localhost:8000/docs` to see all registered routes

### 4. Diagnose 400 Errors (Bad Request)
**Expected for:**
- Endpoints requiring API keys (Trove, certain payment gateways)
- Missing required parameters (market type, portfolio_id)
- Missing headers (X-Device-ID)

**Action:** Set required environment variables or add missing params to test

### 5. Diagnose 500 Errors (Server Error)
Check backend logs for:
- Database schema mismatches (missing columns)
- Optional dependency import failures
- Device ID header parsing errors

**Common fix:**
```python
# Ensure dependency accepts None
def get_device_id(x_device_id: Optional[str] = Header(None)) -> str:
    return x_device_id or str(uuid.uuid4())
```

### 6. Diagnose Timeout Issues
- Increase timeout from 5s to 15s for endpoints hitting external APIs
- Mark as "warning" rather than "error" if endpoint is functional but slow
- Check if same data source has faster alternative endpoint

### 7. Header-Required Endpoints
Many endpoints need `X-Device-ID` header for device-specific settings:
```python
# Test script
"Payout Settings": ("/api/v1/withdrawal/payout/settings", "GET", {"X-Device-ID": "test-device"})

# Backend
device_id: str = Header(None, alias="X-Device-ID")
```

### 8. API Key Loading Strategy (Nigerian Banks Example)
Implement flexible API key loading from multiple sources:

```python
async def get_gateway_api_key(device_id: str) -> tuple[Optional[str], str]:
    """Try env vars first, then database settings."""
    # 1. Check environment variables (Render deployment)
    paystack_key = os.getenv("PAYSTACK_SECRET_KEY")
    flutterwave_key = os.getenv("FLUTTERWAVE_SECRET_KEY")
    
    # Prefer Paystack
    if paystack_key:
        return paystack_key, "paystack"
    if flutterwave_key:
        return flutterwave_key, "flutterwave"
    
    # 2. Fall back to device settings database
    if device_id:
        # Query DeviceSettings for encrypted bank_config
        # Return paystack_api_key or flutterwave_api_key if found
    
    return None, "none"
```

**Benefits:**
- Works in production (Render env vars) and local dev (database settings)
- Auto-selects best available gateway
- Graceful fallback to cached data when no credentials

### 9. Frontend Integration Checklist
After all endpoints pass 200/422, verify frontend:
- [ ] Dashboard loads portfolio data without errors
- [ ] Settings page can read/write device settings
- [ ] Bank list dropdown populates in payout section
- [ ] WebSocket connects successfully
- [ ] Chat widget can send/receive messages
- [ ] Trade history displays correctly
- [ ] Risk metrics show in dashboard

### 10. CI/CD Integration
Use `endpoint_test_results.json` output in deployment pipelines:
```bash
python backend/test_endpoints.py
# Exit code 0 if healthy_count > 0.9 * total (90% pass rate)
```

## Success Criteria
- ✅ 90%+ endpoints return 200/422
- ⚡ <5% endpoints return 400 (expected - missing credentials)
- ❌ <5% endpoints return 404/500/timeout (actual bugs)

## Example Results
```
✓ Healthy:   38 endpoints (90.5%)
⚡ Setup:     2 endpoints (Trove API key needed)
✗ Error:      2 endpoints (timeout - acceptable for slow APIs)

Total:       42 endpoints tested
```

## Key Learnings
1. **Router imports matter:** Missing `from app.api.v1 import chat` causes NameError at startup
2. **Prefix stacking:** `include_router(router, prefix="/api/v1")` + router prefix `/chat` = `/api/v1/chat/*`
3. **Flexible auth:** Support both environment variables (production) and database settings (local dev)
4. **Timeout tuning:** Increase from 5s to 15s for APIs hitting external services
5. **Device ID pattern:** Make device_id optional with auto-generation fallback

## Files Modified
- `backend/test_endpoints.py` - Endpoint health check script
- `backend/app/api/v1/banks.py` - Flexible API key loading from env vars or settings
- `backend/app/main.py` - Added missing chat router import

## When to Apply
- Before production deployment (sanity check)
- After adding new endpoints
- When debugging frontend-backend integration issues
- When endpoints return unexpected status codes