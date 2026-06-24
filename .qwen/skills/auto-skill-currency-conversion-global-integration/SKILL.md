---
name: currency-conversion-global-integration
description: Implement global currency conversion (USD/NGN) with live forex rates from ExchangeRate-API and reactive currency toggle across all monetary values
source: auto-skill
extracted_at: '2026-06-24'
---

# Global Currency Conversion Integration

## Problem
The app had a currency toggle (USD ⇄ NGN) but monetary values were not being converted globally. Only the toggle button showed the rate, but all dollar amounts throughout the dashboard remained in USD regardless of selection.

## Solution: Context-Based Conversion Pattern

### 1. Enhanced CurrencyContext

**File:** `frontend/lib/currencyContext.tsx`

**Key additions:**
```tsx
interface CurrencyContextType {
  currency: 'USD' | 'NGN';
  exchangeRate: number;  // NGN → USD rate (e.g., 0.00065)
  toggleCurrency: () => void;
  convertAmount: (amount: number, from: 'USD' | 'NGN', to: 'USD' | 'NGN') => number;
  formatCurrency: (amount: number, currency?: 'USD' | 'NGN') => string;
}

// Conversion functions
const convertAmount = (amount: number, from: 'USD' | 'NGN', to: 'USD' | 'NGN'): number => {
  if (from === to) return amount;
  
  if (from === 'USD' && to === 'NGN') {
    return amount / exchangeRate;  // USD to NGN
  }
  return amount * exchangeRate;  // NGN to USD
};

const formatCurrency = (amount: number, currency?: 'USD' | 'NGN'): string => {
  const targetCurrency = currency || displayCurrency;
  
  if (targetCurrency === 'USD') {
    return `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  } else {
    return `₦${amount.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
};
```

### 2. Component Integration Pattern

**Every component with monetary values must:**

1. **Import the hook:**
```tsx
import { useCurrency } from '@/lib/currencyContext';
```

2. **Get conversion helpers:**
```tsx
const { convertAmount, formatCurrency, currency } = useCurrency();
```

3. **Convert before display:**
```tsx
// Before
<div>${balance.toLocaleString()}</div>

// After
<div>{formatCurrency(balance)}</div>
```

### 3. Components to Update

**DashboardTab.tsx:**
```tsx
// Equity card
<div>{formatCurrency(equity)}</div>

// PnL
<div className={pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
  {formatCurrency(pnl)}
</div>

// Holdings table
{holdings.map(holding => (
  <td>{formatCurrency(holding.marketValue)}</td>
  <td>{formatCurrency(holding.unrealizedPnl)}</td>
))}
```

**PortfolioTab.tsx:**
```tsx
// Portfolio value
<div>Total: {formatCurrency(totalValue)}</div>

// Cash balance
<div>Cash: {formatCurrency(cashBalance)}</div>
```

**BacktestTab.tsx:**
```tsx
// Initial capital (make editable but display converted)
<div>Initial: {formatCurrency(initialCapital)}</div>

// Returns
<div>Return: {formatCurrency(totalReturn)}</div>
```

**CopyTradeTab.tsx:**
```tsx
// Trader AUM
<div>AUM: {formatCurrency(trader.aum)}</div>

// Returns
<div>Return: {formatCurrency(trader.totalReturn)}%</div>
```

### 4. Backend Rate Sync

**File:** `backend/app/api/v1/forex.py`

**Endpoint:** `GET /api/v1/forex/rate/NGN/USD`

```python
@router.get("/rate/{from_currency}/{to_currency}")
async def get_forex_rate(
    from_currency: str,
    to_currency: str,
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """
    Get current exchange rate between two currencies.
    
    Priority:
    1. Trove API (if configured in Settings)
    2. Alpha Vantage (fallback)
    """
    # Load Trove settings
    trove_enabled, trove_api_key, trove_base_url = load_trove_settings(device_id)
    
    # Try Trove first
    if trove_enabled and trove_api_key:
        result = await market_data._get_forex_rate_trove(
            from_currency, to_currency, trove_api_key, trove_base_url
        )
        if result.get('success'):
            return result
    
    # Fallback to Alpha Vantage
    result = await market_data.get_forex_rate_alphavantage(from_currency, to_currency)
    
    return result
```

### 5. Frontend Rate Polling

**File:** `frontend/lib/currencyContext.tsx`

```tsx
// WebSocket for real-time rates
useEffect(() => {
  const ws = new WebSocket(`${WS_URL}/ws/forex`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'rate_update') {
      setExchangeRate(data.rate);
      setLastUpdated(new Date());
    }
  };
  
  return () => ws.close();
}, []);

// Fallback polling (60s interval)
useEffect(() => {
  const fetchRate = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/forex/rate/NGN/USD`);
      const data = await res.json();
      if (data.success) {
        setExchangeRate(data.data.rate);
        setLastUpdated(new Date());
      }
    } catch (e) {
      console.error('Failed to fetch forex rate:', e);
    }
  };
  
  fetchRate();
  const interval = setInterval(fetchRate, 60000); // 60 seconds
  return () => clearInterval(interval);
}, []);
```

### 6. Currency Toggle Component

**File:** `frontend/components/settings/CurrencyToggle.tsx`

```tsx
export default function CurrencyToggle() {
  const { currency, toggleCurrency, exchangeRate, lastUpdated } = useCurrency();
  
  const inverseRate = exchangeRate > 0 ? (1 / exchangeRate) : 0;
  
  return (
    <div className="flex items-center gap-3">
      <button onClick={toggleCurrency} className="...">
        {currency === 'USD' ? 'NGN' : 'USD'}
      </button>
      
      <div className="flex flex-col">
        <span className="text-xs text-gray-400">
          1 USD = ₦{inverseRate.toLocaleString('en-NG', { minimumFractionDigits: 2 })}
        </span>
        <span className="text-[10px] text-gray-500">
          Updated {formatLastUpdated()}
        </span>
      </div>
    </div>
  );
}
```

## Integration Checklist

- [ ] Add `convertAmount` and `formatCurrency` to CurrencyContext
- [ ] Update CurrencyContext to poll `/api/v1/forex/rate/NGN/USD`
- [ ] Import `useCurrency` in ALL components with monetary values
- [ ] Replace all hardcoded `$` formatting with `formatCurrency()`
- [ ] Replace all hardcoded `₦` formatting with `formatCurrency()`
- [ ] Add currency indicator in header (shows current currency)
- [ ] Test toggle updates all values in real-time
- [ ] Verify rate sync between backend and frontend

## Common Pitfalls

1. **Not converting in table cells** - Every table cell showing money must use `formatCurrency()`
2. **Hardcoded currency symbols** - Never use `$` or `₦` directly, always use `formatCurrency()`
3. **Forgetting to convert in calculations** - Convert BEFORE calculations, not after
4. **Not handling 0 or null** - Handle edge cases: `formatCurrency(amount || 0)`
5. **Charts not converting** - Chart data must be converted before passing to chart library

## Testing

1. **Toggle Test:**
   - Set to USD → Verify all values in $
   - Toggle to NGN → Verify all values in ₦
   - Values should update INSTANTLY

2. **Rate Accuracy:**
   - Check rate in CurrencyToggle matches displayed conversions
   - 1 USD = ₦X rate should match: $1000 → ₦(1000 / rate)

3. **Persistance:**
   - Toggle to NGN
   - Refresh page
   - Should remain in NGN (localStorage)

## Why This Pattern Matters

Multi-currency support is critical for Nigerian users who:
- Trade US stocks but think in Naira
- Need to understand PnL in local currency
- Want to compare against local investment options

The context pattern ensures:
- Single source of truth for exchange rate
- Consistent formatting across app
- Easy to add more currencies later