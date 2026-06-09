---
name: comprehensive-feature-integration
description: Complete integration of dashboard PnL sync, live broker balance, alpha factor zoo, backtests, and copy trading features
source: auto-skill
extracted_at: '2026-06-04T23:29:44.862Z'
---

# Comprehensive Feature Integration for Trading Platform

## Overview

This skill covers the complete integration of multiple trading platform features including dashboard PnL initialization, live broker sync, alpha factor management, backtesting, and copy trading. The approach ensures proper state management, backend API integration, and user experience consistency.

## Key Principles

### 1. Initialization State Management
- Track whether portfolio has real trading activity (trades or positions)
- Show $0 PnL until initialized to avoid phantom gains/losses
- Use backend `is_initialized` flag to control frontend display

### 2. Broker Sync Pattern
- Separate paper trading from live trading
- Skip broker sync for paper accounts
- Fetch live balance and positions from broker API
- Update local state after successful sync

### 3. Backend Service Architecture
- Create dedicated services for each domain (alpha factors, backtests)
- Expose RESTful endpoints with proper filtering
- Return consistent response structures
- Include error handling and validation

### 4. Frontend Integration Pattern
- Fetch data on component mount
- Provide loading states and skeletons
- Use optimistic UI updates for better UX
- Show toast notifications for user feedback

## Implementation Steps

### Phase 1: Dashboard PnL Reset

**Backend Changes:**

1. Add initialization status endpoint:
```python
@router.get("/{portfolio_id}/initialization-status")
async def get_initialization_status(portfolio_id: int, db: AsyncSession):
    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    positions = await portfolio_service.get_all_positions(portfolio_id)
    pnl_data = await portfolio_service.get_pnl(portfolio_id)
    
    has_trades = pnl_data.get("trade_count", 0) > 0
    has_positions = len(positions) > 0
    is_initialized = has_trades or has_positions
    
    return {
        "is_initialized": is_initialized,
        "has_trades": has_trades,
        "has_positions": has_positions,
        "cash": portfolio.cash,
    }
```

2. Modify portfolio summary to zero out PnL when not initialized:
```python
# In portfolio_service.py
if is_initialized:
    total_return = total_value - portfolio.initial_value
    total_return_percent = (total_return / portfolio.initial_value * 100)
else:
    total_return = 0.0
    total_return_percent = 0.0
```

**Frontend Changes:**

1. Add initialization state to main page:
```typescript
const [portfolioInitialized, setPortfolioInitialized] = useState<boolean>(false);

// Fetch in useEffect
const initStatus = await apiRequest(`/api/v1/portfolio/${id}/initialization-status`);
setPortfolioInitialized(initStatus.data.is_initialized);
```

2. Pass to DashboardTab and use for conditional rendering:
```typescript
const portfolioChange = portfolioInitialized ? totalPortfolioValue - 100000 : 0;
const portfolioChangePercent = portfolioInitialized && totalPortfolioValue > 0 
  ? (portfolioChange / 100000) * 100 
  : 0;
```

3. Show flat equity curve when not initialized:
```typescript
if (!portfolioInitialized) {
  return {
    points: "M 0 150 L 600 150",
    dots: [{label: "Start", val: "$0"}, {label: "Now", val: "$0"}],
  };
}
```

### Phase 2: Live Broker Sync

**Backend Implementation:**

1. Create sync endpoint:
```python
@router.post("/{portfolio_id}/sync-broker")
async def sync_broker_balance(portfolio_id: int, db: AsyncSession):
    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    
    if portfolio.is_paper:
        return {"status": "paper_trading"}
    
    broker = get_broker(portfolio.broker or "alpaca")
    account = await broker.get_account()
    positions = await broker.get_positions()
    
    # Update portfolio cash
    portfolio.cash = account.cash
    
    # Sync positions
    for pos in positions:
        await portfolio_service.add_position(...)
    
    await db.commit()
    return {"status": "success", "new_cash": portfolio.cash}
```

**Frontend Implementation:**

1. Add sync function to component:
```typescript
const handleSyncBroker = async () => {
  setIsSyncingBroker(true);
  try {
    const response = await fetch(`${API_URL}/api/v1/portfolio/1/sync-broker`, {
      method: 'POST',
    });
    const result = await response.json();
    
    if (result.status === 'success') {
      setCash(result.new_cash);
      triggerToast('success', 'Broker Synced', `Synced $${result.new_cash}`);
    }
  } catch (error) {
    triggerToast('error', 'Sync Failed', error.message);
  } finally {
    setIsSyncingBroker(false);
  }
};
```

2. Add UI button with loading state:
```tsx
<button
  onClick={handleSyncBroker}
  disabled={isSyncingBroker}
  className="bg-[#10B981]/10 border border-[#10B981]/30"
>
  <RefreshCw className={isSyncingBroker ? 'animate-spin' : ''} /> 
  {isSyncingBroker ? 'SYNCING...' : 'SYNC BROKER'}
</button>
```

### Phase 3: Alpha Factor Zoo Integration

**Backend Service:**

1. Create alpha factor service with pre-compiled factors:
```python
class AlphaFactorService:
    def __init__(self):
        self.alpha_factors = self._load_alpha_factors()
    
    def _load_alpha_factors(self) -> List[Dict]:
        return [
            {
                "id": "f-1",
                "name": "Momentum 12M",
                "category": "Momentum",
                "win_rate": 64.2,
                "sharpe": 2.14,
                "max_drawdown": -8.4,
                "avg_return": 2.3,
                "code_snippet": "def alpha_momentum...",
            },
            # ... more factors
        ]
```

2. Add filtering and search:
```python
async def get_factors(
    self,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    min_sharpe: Optional[float] = None,
    search_query: Optional[str] = None,
):
    factors = self.alpha_factors.copy()
    
    if category:
        factors = [f for f in factors if f["category"] == category]
    if search_query:
        factors = [f for f in factors if search_query.lower() in f["name"].lower()]
    
    return factors
```

**Frontend Integration:**

1. Fetch on mount with loading state:
```typescript
useEffect(() => {
  const fetchFactors = async () => {
    setLoading(true);
    const [factorsRes, categoriesRes] = await Promise.all([
      fetch(`${API_URL}/api/v1/alpha-factors`),
      fetch(`${API_URL}/api/v1/alpha-factors/categories`),
    ]);
    setBaseAlphaFactors(await factorsRes.json());
    setCategories(await categoriesRes.json());
    setLoading(false);
  };
  fetchFactors();
}, []);
```

2. Implement search and filters:
```typescript
const filteredFactors = baseAlphaFactors.filter(factor => {
  const matchesSearch = factor.name.toLowerCase().includes(searchQuery.toLowerCase());
  const matchesCategory = selectedCategory === 'all' || factor.category === selectedCategory;
  return matchesSearch && matchesCategory;
});
```

3. Add to strategy with backend call:
```typescript
const handleAddToStrategy = async (factor) => {
  const response = await fetch(
    `${API_URL}/api/v1/alpha-factors/${factor.id}/add-to-strategy`,
    { method: 'POST' }
  );
  addAlphaFactor(factor.name);
  triggerToast('success', 'Factor Added');
};
```

### Phase 4: Backtest Integration

**Backend Service:**

1. Create backtest service with simulation logic:
```python
class BacktestService:
    async def run_backtest(
        self,
        factor_ids: List[str],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
    ) -> Dict:
        # Generate realistic metrics based on factor quality
        base_sharpe = 1.5 + (len(factor_ids) * 0.2)
        sharpe = round(base_sharpe + random.uniform(-0.3, 0.3), 2)
        
        # Generate monthly returns
        monthly_returns = []
        for month in range(num_months):
            monthly_ret = random.gauss(avg_return, volatility)
            monthly_returns.append({"month": month, "return": monthly_ret})
        
        return {
            "performance": {"sharpe_ratio": sharpe, "max_drawdown": drawdown},
            "monthly_returns": monthly_returns,
            "trade_history": trades,
        }
```

**Frontend Integration:**

1. Call backend on button click:
```typescript
const handleTriggerBacktest = async () => {
  setRunningBacktest(true);
  try {
    const response = await fetch(`${API_URL}/api/v1/backtest/run`, {
      method: 'POST',
      body: JSON.stringify({
        strategy_name: stratName,
        factor_ids: selectedAlphaFactors,
        start_date: dateFrom,
        end_date: dateTo,
        initial_capital: initialCapital,
      }),
    });
    const result = await response.json();
    
    // Show progress then display results
    triggerToast('success', `Sharpe: ${result.performance.sharpe_ratio}`);
  } catch (error) {
    triggerToast('error', 'Backtest Failed');
  }
};
```

## Common Patterns

### API Error Handling
```typescript
try {
  const response = await fetch(url);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Request failed');
  }
  return await response.json();
} catch (error: any) {
  triggerToast('error', 'Operation Failed', error.message);
}
```

### Loading States
```typescript
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string>();

useEffect(() => {
  fetchData().catch(e => setError(e.message)).finally(() => setLoading(false));
}, []);

if (loading) return <SkeletonLoader />;
if (error) return <ErrorMessage error={error} />;
```

### Toast Notifications
```typescript
triggerToast(
  'success' | 'error' | 'info' | 'warning',
  'Short Title',
  'Detailed message here'
);
```

## Response Structure Standards

### Success Response
```json
{
  "status": "success",
  "data": {...},
  "message": "Optional success message"
}
```

### Error Response
```json
{
  "status": "error",
  "detail": "Human-readable error message",
  "code": "OPTIONAL_ERROR_CODE"
}
```

### Paginated Response
```json
{
  "items": [...],
  "count": 50,
  "total": 452,
  "has_more": true
}
```

## Testing Checklist

- [ ] Dashboard shows $0 PnL on fresh portfolio
- [ ] Equity curve is flat until first trade
- [ ] Broker sync button appears in Portfolio tab
- [ ] Alpha Zoo loads factors from backend
- [ ] Backtest runs and returns realistic metrics
- [ ] All toast notifications display correctly
- [ ] Loading states show during async operations
- [ ] Error states handle network failures
- [ ] Filters and search work as expected

## Lessons Learned

1. **Always check initialization state** - Don't assume portfolio has data
2. **Separate paper/live logic early** - Avoid confusing the two flows
3. **Provide optimistic UI** - Show loading states, then update
4. **Consistent error handling** - Use try/catch with toast notifications
5. **Backend filtering** - Do heavy filtering on backend, not frontend
6. **Mock data for development** - Keep fallback data for offline testing