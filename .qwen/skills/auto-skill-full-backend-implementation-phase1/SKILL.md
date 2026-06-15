---
name: full-backend-implementation-phase1
description: Complete Phase 1 backend implementation - symbols endpoint, cTrader OAuth modes, currency conversion (June 15, 2026)
source: auto-skill
---

## Overview

Complete Phase 1 backend foundation for Jasper Trades trading platform. Implements stock symbols API (US + NGX), cTrader OAuth sandbox/live mode support, and currency conversion framework. All endpoints verified and registered.

**Date Implemented:** 2026-06-15  
**Phase:** Phase 1 - Backend Foundation  
**Status:** ✅ Complete

---

## Symbols API Implementation

### File Created: `backend/app/api/v1/symbols.py`

**Endpoint:** `GET /api/v1/symbols?exchange=all|US|NGX&search=AAPL`

**Implementation Pattern:**
1. **Primary source:** Trove API (covers both US + NGX stocks)
2. **Fallback:** Polygon API (US stocks only)
3. **Bootstrap cache:** Popular stocks for offline fallback

**Cached Bootstrap Data:**
```python
# NGX stocks (15 popular)
NGX_BOOTSTRAP = [
    {"symbol": "DANGCEM", "name": "Dangote Cement Plc", ...},
    {"symbol": "MTNN", "name": "MTN Nigeria Communications Plc", ...},
    {"symbol": "GTCO", "name": "Guaranty Trust Holding Company Plc", ...},
    # ... 12 more
]

# US stocks (20 popular)
US_BOOTSTRAP = [
    {"symbol": "AAPL", "name": "Apple Inc.", ...},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", ...},
    {"symbol": "TSLA", "name": "Tesla Inc.", ...},
    # ... 17 more
]
```

**API Key Loading:**
- Trove: Loads from `DeviceSettings` encryption
- Polygon: Loads from `DeviceSettings.polygon_key`
- Device ID header required for both

**Response Format:**
```json
{
  "symbols": [...],
  "count": 50,
  "source": "trove|polygon|cached",
  "exchange": "all|US|NGX"
}
```

**Registration:** Add to `backend/app/main.py`:
```python
from app.api.v1 import alpha_factors, backtest, withdrawal, symbols
# ...
app.include_router(symbols.router, tags=["symbols"])
```

---

## cTrader OAuth Sandbox/Live Mode Support

### Backend Changes

**File Modified:** `backend/app/api/v1/broker_connections.py`

**Before:**
```python
@router.get("/connect")
async def connect_ctrader():
    auth_url = oauth_service.get_authorization_url()
    return {"authorization_url": auth_url}
```

**After:**
```python
@router.get("/connect")
async def connect_ctrader(
    mode: str = Query(default="sandbox", description="Trading mode: sandbox or live"),
):
    is_sandbox = mode.lower() == "sandbox"
    auth_url = oauth_service.get_authorization_url(is_sandbox=is_sandbox)
    
    return {
        "authorization_url": auth_url,
        "mode": "sandbox" if is_sandbox else "live",
        "message": "Redirect user to connect cTrader account"
    }
```

**OAuth Service:** Already had `is_sandbox` parameter support:
```python
def get_authorization_url(self, is_sandbox: Optional[bool] = None) -> str:
    sandbox = is_sandbox if is_sandbox is not None else self.default_sandbox
    auth_url = self.SANDBOX_AUTH_URL if sandbox else self.LIVE_AUTH_URL
```

---

### Frontend Integration

**File Modified:** `frontend/components/settings/CTraderConnection.tsx`

**Before:**
```typescript
const handleConnect = async () => {
  const res = await fetch(`${API_URL}/api/v1/ctrader/connect`);
  // ...
}
```

**After:**
```typescript
const handleConnect = async () => {
  const mode = isLiveMode ? 'live' : 'sandbox';
  const res = await fetch(`${API_URL}/api/v1/ctrader/connect?mode=${mode}`);
  // ...
}
```

**Key Points:**
- User toggles between Sandbox/Live mode in UI
- Mode is passed as query parameter
- OAuth flow uses correct Spotware endpoint:
  - Sandbox: `https://-sandbox.connect.spotware.com/oauth/authorize`
  - Live: `https://connect.spotware.com/oauth/authorize`

---

## Currency Conversion Framework

### Enhanced CurrencyContext

**File Modified:** `frontend/lib/currencyContext.tsx`

**New Hook Added:**
```typescript
/**
 * Hook for formatting monetary values with automatic currency conversion.
 * 
 * Example:
 * const { formatMoney } = useCurrencyFormatter();
 * <div>{formatMoney(100000)}</div> // Shows $100,000.00 or ₦153,846,153.85
 */
export function useCurrencyFormatter() {
  const { convertAmount, formatCurrency, currency } = useCurrency();

  const formatMoney = useCallback((amount: number, sourceCurrency: Currency = 'USD'): string => {
    const converted = convertAmount(amount, sourceCurrency, currency);
    return formatCurrency(converted, currency);
  }, [convertAmount, formatCurrency, currency]);

  return { formatMoney, currentCurrency: currency };
}
```

**Usage Pattern in Components:**
```typescript
import { useCurrencyFormatter } from '@/lib/currencyContext';

function DashboardTab() {
  const { formatMoney } = useCurrencyFormatter();
  
  return (
    <div>
      <div>Portfolio Value: {formatMoney(100000)}</div>
      // Shows $100,000.00 in USD mode or ₦153,846,153.85 in NGN mode
    </div>
  );
}
```

**Conversion Logic:**
- NGN → USD: `amount * exchangeRate`
- USD → NGN: `amount / exchangeRate`
- Exchange rate fetched from `/api/v1/forex/rate/NGN/USD`
- WebSocket updates every 60 seconds

---

## Verified Existing Endpoints

### Portfolio Cash Endpoint ✅
Already existed in `backend/app/api/v1/portfolio.py`:
```python
@router.get("/{portfolio_id}/cash")
async def get_cash(portfolio_id: int, db: AsyncSession = Depends(get_db)):
    return {
        "portfolio_id": portfolio_id,
        "cash": portfolio.cash,
        "currency": "USD",
    }
```

### Withdrawal Validate Wallet ✅
Already existed in `backend/app/api/v1/withdrawal.py`:
```python
@router.post("/payout/validate-wallet")
async def validate_crypto_wallet(request: ValidateWalletRequest):
    # Validates Ethereum/Solana addresses
```

---

## Key Architectural Decisions

### 1. Trove-First Symbol Sourcing
**Decision:** Trove API as primary (covers both US + NGX), Polygon as fallback

**Why:**
- Single API for both markets (simpler integration)
- Nigerian stocks (NGX) only available via Trove
- User configured via Settings page
- Fallback ensures offline capability

### 2. Per-Device cTrader Mode
**Decision:** Sandbox/Live mode stored per-device via `environment_mode`

**Why:**
- Users can test in sandbox before going live
- Mode stored in localStorage + backend settings
- OAuth flow uses different endpoints based on mode
- Clear visual distinction in UI (green sandbox, red live badge)

### 3. Currency Context Global State
**Decision:** React Context for currency state, not prop drilling

**Why:**
- All monetary values need conversion
- Real-time WebSocket updates
- Single source of truth
- Easy to use via `useCurrencyFormatter()` hook

---

## Testing Checklist

### Symbols Endpoint
```bash
# Test all symbols
curl http://localhost:8000/api/v1/symbols\?exchange\=all

# Test NGX only
curl http://localhost:8000/api/v1/symbols\?exchange\=NGX

# Test search
curl http://localhost:8000/api/v1/symbols\?search\=DANGCEM

# Test popular
curl http://localhost:8000/api/v1/symbols/popular
```

### cTrader OAuth
1. Toggle mode to Sandbox
2. Click "Connect Sandbox Account"
3. Verify redirect to `-sandbox.connect.spotware.com`
4. Toggle to Live
5. Click "Connect Live Account"
6. Verify redirect to `connect.spotware.com`

### Currency Conversion
1. Load dashboard (shows USD values)
2. Click currency toggle (switches to NGN)
3. All monetary values convert instantly
4. Verify exchange rate displayed
5. Check WebSocket connected to `/ws/forex`

---

## Dependencies

**Backend:**
- `httpx` - Async HTTP client for Trove/Polygon APIs
- `cryptography` - Fernet encryption for API keys
- `fastapi` - API framework

**Frontend:**
- `React.Context` - Global currency state
- `WebSocket` - Real-time forex rate updates

---

## Related Files

**Backend:**
- `backend/app/api/v1/symbols.py` (new)
- `backend/app/api/v1/broker_connections.py` (modified)
- `backend/app/main.py` (modified - router registration)
- `backend/app/services/ctrader_oauth.py` (existing - already had mode support)

**Frontend:**
- `frontend/lib/currencyContext.tsx` (modified - added formatter hook)
- `frontend/components/settings/CTraderConnection.tsx` (modified - mode param)

---

## Next Steps (Phase 2)

1. **Currency conversion across all components:**
   - DashboardTab - PnL, equity, holdings
   - PortfolioTab - All portfolio values
   - BacktestTab - Returns, capital
   - CopyTradeTab - AUM, returns

2. **Signals stock selector:**
   - Create `StockSelector.tsx` combobox
   - Search with debounce (300ms)
   - Fetch from `/api/v1/symbols`

3. **Mobile responsiveness:**
   - Table overflow fixes
   - Touch target sizing (44px min)
   - Responsive grids

---

## Troubleshooting

### Symbols Endpoint Returns Cached Data

**Symptom:** API always returns bootstrap list

**Check:**
1. Trove API key configured in Settings?
2. Device ID header sent?
3. Trove enabled flag set?

**Debug:**
```python
# In symbols.py, add logging
logger.info("Trove settings", trove_enabled=trove_enabled, has_key=bool(trove_key))
```

### cTrader OAuth Wrong Mode

**Symptom:** Sandbox mode goes to live URL

**Check:**
1. Frontend passes `?mode=sandbox|live`
2. Backend uses `is_sandbox` parameter
3. Default fallback is sandbox

### Currency Not Converting

**Symptom:** Toggle changes but values don't update

**Check:**
1. `useCurrencyFormatter()` imported correctly
2. Exchange rate loaded (check WebSocket)
3. Foreックス polling service running

---

## Memory Saved

This skill captures the complete Phase 1 backend implementation approach for future reference and reproducibility.