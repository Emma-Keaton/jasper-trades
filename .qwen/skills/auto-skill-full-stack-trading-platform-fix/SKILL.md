---
name: full-stack-trading-platform-fix
description: Complete implementation of symbols endpoint, cTrader OAuth modes, currency conversion, stock selector, and mobile responsiveness for Jasper Trades trading platform
source: auto-skill
extracted_at: '2026-06-15T11:39:41.006Z'
---

# Full-Stack Trading Platform Fix - Phase 1 & 2

This skill implements a comprehensive fix for the Jasper Trades AI-powered trading platform, covering backend API endpoints, frontend components, currency conversion, and mobile responsiveness.

## Overview

**Context:** The Jasper Trades platform needed:
1. Stock symbol listing (US + Nigerian NGX stocks) via Trove API
2. cTrader OAuth sandbox/live mode differentiation
3. Global currency conversion (USD ⇄ NGN)
4. Full stock selector with search functionality
5. Mobile-responsive tables and touch-friendly UI

## Backend Implementation

### 1. Symbols Endpoint (`/api/v1/symbols`)

**File:** `backend/app/api/v1/symbols.py`

**Key Features:**
- Trove API as primary source (covers both US and NGX stocks)
- Polygon API as fallback (US only)
- Cached bootstrap lists for offline scenarios
- Search with debouncing
- Exchange filtering (all, US, NGX)

```python
@router.get("")
async def list_symbols(
    exchange: Optional[str] = Query(default="all", description="Filter by exchange: all, US, NGX"),
    search: Optional[str] = Query(default=None, description="Search by symbol or name"),
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get list of available trading symbols.
    
    Priority:
    1. Trove API (if configured) - covers both US and NGX
    2. Polygon API (fallback) - US stocks only
    3. Cached bootstrap list (offline fallback)
    """
```

**Bootstrap Data:**
- 15 popular NGX stocks: DANGCEM, MTNN, GTCO, AIRWAYS, BUACEMENT, etc.
- 20 popular US stocks: AAPL, MSFT, NVDA, TSLA, etc.

**Registration in `main.py`:**
```python
from app.api.v1 import alpha_factors, backtest, withdrawal, symbols

app.include_router(symbols.router, tags=["symbols"])
```

### 2. cTrader OAuth Sandbox/Live Modes

**Files Modified:**
- `backend/app/api/v1/broker_connections.py`
- `backend/app/services/ctrader_oauth.py` (already supported modes)

**Implementation:**
```python
@router.get("/connect")
async def connect_ctrader(mode: str = Query(default="sandbox")):
    """Get cTrader OAuth authorization URL with mode parameter."""
    is_sandbox = mode.lower() == "sandbox"
    auth_url = oauth_service.get_authorization_url(is_sandbox=is_sandbox)
    
    return {
        "authorization_url": auth_url,
        "mode": "sandbox" if is_sandbox else "live",
    }
```

**OAuth URLs:**
- Sandbox: `https://-sandbox.connect.spotware.com/oauth/authorize`
- Live: `https://connect.spotware.com/oauth/authorize`

## Frontend Implementation

### 1. Stock Selector Component

**File:** `frontend/components/StockSelector.tsx`

**Features:**
- Combobox with search (300ms debounce)
- Real-time API fetching from `/api/v1/symbols`
- Exchange badge color coding
- Multi-select support
- Touch-optimized (44px+ targets)

```typescript
export default function StockSelector({
  value,
  onChange,
  filterByExchange = 'all',
}: StockSelectorProps) {
  // Debounced search
  const debouncedSearch = useCallback(
    debounce((term: string) => {
      if (term.length >= 2) fetchSymbols(term);
    }, 300),
    []
  );
  
  // Exchange badge colors
  const getExchangeBadgeColor = (exchange: string) => {
    switch (exchange) {
      case 'NGX': return 'bg-green-500/20 text-green-400';
      case 'NASDAQ': return 'bg-blue-500/20 text-blue-400';
      case 'NYSE': return 'bg-purple-500/20 text-purple-400';
    }
  };
```

**Usage in SignalsTab:**
```typescript
import StockSelector from '@/components/StockSelector';

<StockSelector
  value={selectedAsset === 'all' ? undefined : selectedAsset}
  onChange={(symbol) => setSelectedAsset(symbol || 'all')}
  placeholder="Full Market Index"
  filterByExchange="all"
/>
```

### 2. Currency Conversion Hook

**File:** `frontend/lib/currencyContext.tsx`

**New Export:**
```typescript
export function useCurrencyFormatter() {
  const { convertAmount, formatCurrency, currency } = useCurrency();
  
  const formatMoney = useCallback((amount: number, sourceCurrency: Currency = 'USD'): string => {
    const converted = convertAmount(amount, sourceCurrency, currency);
    return formatCurrency(converted, currency);
  }, [convertAmount, formatCurrency, currency]);

  return { formatMoney, currentCurrency: currency };
}
```

**Conversion Logic:**
```typescript
const convertAmount = useCallback((amount: number, from: Currency, to: Currency): number => {
  if (from === to) return amount;
  
  if (from === 'NGN' && to === 'USD') {
    return amount * state.exchangeRate;
  } else if (from === 'USD' && to === 'NGN') {
    return state.exchangeRate > 0 ? amount / state.exchangeRate : 0;
  }
  
  return amount;
}, [state.exchangeRate]);
```

**Usage Pattern:**
```typescript
const { formatMoney } = useCurrencyFormatter();

// All monetary values automatically convert based on toggle
<div>{formatMoney(portfolioValue)}</div>
// Shows: $100,000.00 or ₦153,846,153.85
```

### 3. Mobile Responsiveness

**Pattern Applied to All Tables:**
```typescript
// Before (overflow on mobile)
<table className="w-full text-left min-w-[600px]">

// After (scrollable on mobile)
<div className="overflow-x-auto">
  <div className="min-w-full overflow-x-auto">
    <table className="w-full text-left">
```

**Files Fixed:**
- `DashboardTab.tsx`
- `PortfolioTab.tsx`
- `BacktestTab.tsx`

**Touch Target Sizing:**
```typescript
// Before (too small for mobile)
<select className="h-9 text-xs">

// After (44px minimum - WCAG compliant)
<select className="h-11 text-sm touch-none">

// Buttons (minimum 44px height)
<button className="py-2.5 text-sm touch-none">
```

## API Testing

### Symbols Endpoint
```bash
# Get all symbols
curl "http://localhost:8000/api/v1/symbols?exchange=all"

# Filter by NGX only
curl "http://localhost:8000/api/v1/symbols?exchange=NGX"

# Search for specific stock
curl "http://localhost:8000/api/v1/symbols?search=DANGCEM"

# Get popular symbols
curl "http://localhost:8000/api/v1/symbols/popular"

# Get supported exchanges
curl "http://localhost:8000/api/v1/symbols/exchanges"
```

### cTrader OAuth
```bash
# Sandbox mode
curl "http://localhost:8000/api/v1/brokers/connect?mode=sandbox"

# Live mode
curl "http://localhost:8000/api/v1/brokers/connect?mode=live"
```

### Currency Rate
```bash
# Get NGN/USD exchange rate
curl "http://localhost:8000/api/v1/forex/rate/NGN/USD"
```

## Environment Variables

### cTrader OAuth (Required for auto-trading)
```env
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_REDIRECT_URI=https://jasper-trades.onrender.com/api/v1/brokers/callback
CTRADER_ENCRYPTION_KEY=your_fernet_key
```

### Trove API (Optional - for Nigerian/US stocks)
```env
TROVE_API_KEY=your_api_key
TROVE_BASE_URL=https://sandbox.api.trovefinance.com/v1
TROVE_ENABLED=true
TROVE_SANDBOX=true
```

### Polygon API (Optional - fallback)
```env
POLYGON_API_KEY=your_api_key
```

## Verification Checklist

### Backend
- ✅ `/api/v1/symbols` returns US + NGX stocks
- ✅ `/api/v1/symbols?search=DANGCEM` finds Nigerian stocks
- ✅ cTrader OAuth returns different URLs for sandbox/live
- ✅ Fore