---
name: api-route-organization
description: Reorganize FastAPI routers into logical namespaces (brokers, chat) for better endpoint structure and maintainability
source: auto-skill
extracted_at: '2026-06-13T16:30:00.000Z'
---

# API Route Organization

## Problem
API endpoints become disorganized over time with inconsistent routing patterns:
- cTrader OAuth at `/api/v1/ctrader/*` (standalone)
- WhatsApp at `/api/v1/whatsapp/*` (standalone)
- Broker connections scattered across multiple files
- No clear namespace for related functionality

This makes the API harder to understand, document, and extend with new integrations.

## Solution
Consolidate related endpoints into logical namespaces with clear router prefixes.

## Organization Structure

### Brokers Namespace (`/api/v1/brokers/*`)
All broker-related operations in one place:
- `/api/v1/brokers/connect` - Connect broker (cTrader OAuth)
- `/api/v1/brokers/callback` - OAuth callback
- `/api/v1/brokers/disconnect/{id}` - Disconnect broker
- `/api/v1/brokers/accounts` - List connected accounts
- `/api/v1/trading/brokers/status` - Broker status (existing endpoint)

**Future expansion:**
- `/api/v1/brokers/alpaca/connect`
- `/api/v1/brokers/binance/connect`
- `/api/v1/brokers/ibkr/connect`

### Chat Namespace (`/api/v1/chat/*`)
All messaging platform integrations:
- `/api/v1/chat/config` - Get chat configuration
- `/api/v1/chat/configure` - Configure chat platform
- `/api/v1/chat/history` - Message history
- `/api/v1/chat/send` - Send message
- `/api/v1/chat/webhook` - Incoming webhook
- `/api/v1/chat/status` - Connection status
- `/api/v1/chat/test` - Send test message
- `/api/v1/chat/enable` / `/api/v1/chat/disable` - Toggle notifications
- `/api/v1/chat/clear/{phone}` - Clear history

**Future expansion:**
- `/api/v1/chat/telegram/configure`
- `/api/v1/chat/discord/webhook`
- `/api/v1/chat/slack/configure`

## Implementation Steps

### 1. Update Router Prefixes

**chat.py** - Change from WhatsApp-specific to generic chat:
```python
# BEFORE
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# AFTER
router = APIRouter(prefix="/chat", tags=["chat"])
```

**broker_connections.py** - Consolidate cTrader under brokers:
```python
# BEFORE
router = APIRouter(prefix="/api/v1/ctrader", tags=["cTrader OAuth"])

# AFTER
router = APIRouter(prefix="/brokers", tags=["brokers"])
```

### 2. Update main.py Registration

Register routers with consistent `/api/v1` prefix:
```python
# In app/main.py
app.include_router(broker_connections.router, prefix="/api/v1", tags=["brokers"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
```

### 3. Remove Duplicate Files

If you have multiple files for the same functionality (e.g., `ctrader_oauth.py` and `broker_connections.py`):
```bash
cd E:\Projects\jasper-trades\backend\app\api\v1
del ctrader_oauth.py  # Keep broker_connections.py as primary
```

### 4. Update Endpoint Paths

Ensure endpoint decorators match the new router prefix:

**broker_connections.py:**
```python
# Paths are now relative to /brokers prefix
@router.get("/connect")        # → /api/v1/brokers/connect
@router.get("/callback")       # → /api/v1/brokers/callback
@router.post("/disconnect/{id}")  # → /api/v1/brokers/disconnect/{id}
@router.get("/accounts")       # → /api/v1/brokers/accounts
```

**chat.py:**
```python
# Paths are now relative to /chat prefix
@router.get("/config")         # → /api/v1/chat/config
@router.get("/history")        # → /api/v1/chat/history
@router.post("/send")          # → /api/v1/chat/send
@router.post("/webhook")       # → /api/v1/chat/webhook
```

### 5. Verify New Structure

Restart backend and test:
```bash
# Check registered paths
curl -s http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); paths=[p for p in d.get('paths',{}).keys() if 'broker' in p.lower() or 'chat' in p.lower()]; print('\n'.join(sorted(paths)))"

# Test endpoints
curl -s http://localhost:8000/api/v1/brokers/connect
curl -s http://localhost:8000/api/v1/chat/config
```

## Benefits

1. **Clear Organization**: Related endpoints grouped logically
2. **Easier Documentation**: API docs show clear categories
3. **Scalability**: Easy to add new brokers/chat platforms
4. **Consistent Patterns**: All integrations follow same structure
5. **Better Discovery**: Developers can guess endpoint paths

## Common Mistakes to Avoid

1. **Double prefixing**: Don't add `/api/v1` in router if main.py already adds it
   ```python
   # WRONG: Results in /api/v1/api/v1/brokers/connect
   router = APIRouter(prefix="/api/v1/brokers")
   app.include_router(router, prefix="/api/v1")
   
   # CORRECT:
   router = APIRouter(prefix="/brokers")
   app.include_router(router, prefix="/api/v1")
   ```

2. **Keeping old paths**: Update all references to old endpoint paths in frontend code
3. **Forgetting to restart**: Hot reload may not pick up router changes - do full restart

## Migration Checklist

- [ ] Update router prefixes in each file
- [ ] Update main.py registration
- [ ] Remove duplicate router files
- [ ] Verify endpoint paths relative to new prefix
- [ ] Restart backend (full restart, not reload)
- [ ] Test all affected endpoints
- [ ] Update frontend API client calls
- [ ] Update API documentation
- [ ] Update any hardcoded URLs in code