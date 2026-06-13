---
name: auth-system-removal-and-simple-trading-flow
description: Remove user authentication system and enable direct dashboard access with localStorage-based preferences
source: auto-skill
extracted_at: '2026-06-11T05:15:00.000Z'
---

## Context

User wanted to remove the entire user authentication system (login/register pages, JWT tokens, user accounts) and allow direct access to the trading dashboard. Only cTrader OAuth should be required for auto-trading connections.

## Problem

The app had a full authentication system with:
- Login/Register pages requiring email/password
- JWT token-based API authentication
- User accounts with per-user settings
- Auth provider context wrapping the entire app

This was unnecessary complexity for a single-user or device-based trading platform where:
- Users just want to access the dashboard directly
- cTrader OAuth handles broker authentication
- Settings can be stored per-device via localStorage

## Solution Approach

### 1. Remove Frontend Auth Components

**Delete files:**
- `frontend/app/login/page.tsx`
- `frontend/app/register/page.tsx`
- `frontend/app/auth-provider.tsx`

**Update `frontend/app/layout.tsx`:**
```tsx
// Remove AuthProvider wrapper
export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

**Update components that used `useAuth()`:**
- `CopyTradeTab.tsx` - Remove auth headers from API calls
- `CTraderConnection.tsx` - Use localStorage for device ID and environment mode

### 2. Remove Backend Auth API

**Delete files:**
- `backend/app/api/v1/auth.py`
- `backend/app/services/auth.py`

**Update `backend/app/main.py`:**
```python
# Remove auth router import and registration
# from app.api.v1 import auth  # REMOVED
# app.include_router(auth.router, tags=["Authentication"])  # REMOVED
```

### 3. Add Device-Based Environment Mode Endpoint

Since there's no user auth, store environment mode (sandbox/live) per-device:

**Backend endpoint (`backend/app/api/v1/settings_extensions.py`):**
```python
@router.post("/environment")
async def save_environment_mode(
    request: EnvironmentModeRequest,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Save environment mode for device (no auth required)"""
    if not device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    
    async with async_session() as session:
        # Store in DeviceSettings table
        row = await session.execute(...)
        row.environment_mode = request.environment_mode
        await session.commit()
    
    return {"success": True, "environment_mode": request.environment_mode}
```

**Frontend component (`CTraderConnection.tsx`):**
```tsx
const getDeviceId = () => {
  let deviceId = localStorage.getItem('device_id');
  if (!deviceId) {
    deviceId = 'dev_' + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('device_id', deviceId);
  }
  return deviceId;
};

const toggleEnvironmentMode = async () => {
  const newMode = isLiveMode ? 'sandbox' : 'live';
  const deviceId = getDeviceId();
  
  const res = await fetch(`${API_URL}/api/v1/settings/environment`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Device-ID': deviceId 
    },
    body: JSON.stringify({ environment_mode: newMode }),
  });
  
  if (res.ok) {
    setIsLiveMode(newMode === 'live');
    localStorage.setItem('environment_mode', newMode);
  }
};
```

### 4. Fix Syntax Errors from Alpaca Removal

The codebase had references to Alpaca broker that was previously removed. Fix all syntax errors:

**Pattern to find/replace:**
- `broker: str = ,` → `broker: str = "ibkr"`
- `"stocks": ,` → Remove the entry entirely
- `: ["stocks", ...]` → Remove from BROKER_CAPABILITIES

**Files typically affected:**
- `app/brokers/router.py` - Update ASSET_BROKER_MAP
- `app/services/portfolio_service.py` - Fix default broker parameter
- `app/api/v1/portfolio.py` - Fix broker or defaults
- `app/api/v1/trading.py` - Remove broker= references

### 5. Fix Broken Service Files

Some files had incomplete code blocks. Common fixes:

**chat_ai.py - Incomplete function:**
```python
# BROKEN:
async def _handle_market_status(self) -> str:
    try:

User's portfolio context:  # <- Syntax error
...

# FIXED - Simplified to just return market status:
async def _handle_market_status(self) -> str:
    now = datetime.utcnow()
    is_market_open = not is_weekend and 13 <= hour < 21
    status = "🟢 OPEN" if is_market_open else "🔴 CLOSED"
    return f"US Stock Market: {status}"
```

**settings.py - Orphaned except block:**
```python
# BROKEN: Missing try block
    return {"valid": valid, "message": message}

except Exception as e:  # <- Syntax error
    ...

# FIXED: Remove orphaned except
    return {"valid": valid, "message": message}
```

## Key Patterns/Decisions

### Device Fingerprinting
Generate a unique device ID on first visit and store in localStorage:
```typescript
const deviceId = localStorage.getItem('device_id') || 
                 'dev_' + Math.random().toString(36).substring(2, 15);
localStorage.setItem('device_id', deviceId);
```

This allows:
- Persistent settings per browser/device
- No login required
- Multiple devices can have different settings

### Environment Mode Storage
Store both client-side (for instant UI updates) and server-side (for persistence):
```typescript
// Client-side (instant)
localStorage.setItem('environment_mode', newMode);

// Server-side (persistent across browser clears)
await fetch('/api/v1/settings/environment', {
  headers: { 'X-Device-ID': deviceId },
  body: JSON.stringify({ environment_mode: newMode })
});
```

### Broker Default Fallback
When removing Alpaca, default to IBKR for stock trading:
```python
broker: str = "ibkr"  # Default broker for stocks/equities
```

Update routing map to reflect available brokers:
```python
ASSET_BROKER_MAP = {
    "crypto": "binance",
    "futures": "ibkr",
    "forex": "ibkr",
    "solana": "solana",
    # Removed: "stocks": "alpaca" (now handled by ibkr)
}
```

## Testing

**Frontend build:**
```bash
cd frontend
npm run build  # Should complete without errors
```

**Backend load test:**
```bash
cd backend
python -c "from app.main import app; print('Backend OK')"
```

Expected output: All services initialize successfully (WhatsApp, Circuit Breaker, Heartbeat, etc.)

## Why This Approach

1. **Simpler UX**: Users access dashboard immediately without login walls
2. **Appropriate security**: cTrader OAuth handles broker authentication securely
3. **Device-based persistence**: Settings persist per-device without requiring accounts
4. **Easier deployment**: No user database management, no password resets, no session management
5. **Matches use case**: Single user or small team trading platform doesn't need multi-tenant auth

## When to Reconsider Auth

Add authentication back if:
- Multiple users need isolated portfolios
- Cloud hosting with shared backend
- Copy trading signal marketplace (user-to-user)
- Compliance requirements for user identification