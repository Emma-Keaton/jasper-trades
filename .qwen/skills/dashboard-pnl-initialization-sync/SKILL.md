---
name: dashboard-pnl-initialization-sync
description: Implementation pattern for resetting dashboard PnL and equity curve to $0 until portfolio has real trading activity, with backend sync
source: auto-skill
extracted_at: '2026-06-04T12:30:00.000Z'
---

# Dashboard PnL Initialization & Backend Sync

## Problem
Dashboard was showing phantom PnL calculations (e.g., -$100,000 total PnL) when portfolio had no real trading activity. The $100,000 initial cash was being treated as a baseline for PnL calculations, creating misleading metrics.

## Solution Architecture

### Backend Changes

#### 1. Add Initialization Status Endpoint
```python
@router.get("/{portfolio_id}/initialization-status")
async def get_initialization_status(portfolio_id: int, db: AsyncSession):
    """Check if portfolio has real trading activity."""
    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    positions = await portfolio_service.get_all_positions(portfolio_id, include_empty=False)
    trades_result = await portfolio_service.get_pnl(portfolio_id)
    
    has_trades = trades_result.get("trade_count", 0) > 0
    has_positions = len(positions) > 0
    is_initialized = has_trades or has_positions
    
    return {
        "portfolio_id": portfolio_id,
        "is_initialized": is_initialized,
        "has_trades": has_trades,
        "has_positions": has_positions,
        "cash": portfolio.cash,
        "initial_value": portfolio.initial_value if is_initialized else 0,
    }
```

#### 2. Modify Portfolio Summary to Zero PnL When Not Initialized
```python
async def get_portfolio_summary(self, portfolio_id: int) -> Dict[str, Any]:
    # ... existing code ...
    
    # Check if portfolio is initialized
    has_positions = len([p for p in positions if p.quantity > 0]) > 0
    trades_result = await self.get_pnl(portfolio_id)
    has_trades = trades_result.get("trade_count", 0) > 0
    is_initialized = has_positions or has_trades
    
    if is_initialized:
        total_return = total_value - portfolio.initial_value
        total_return_percent = (total_return / portfolio.initial_value * 100)
    else:
        # No trading activity - PnL should be $0
        total_return = 0.0
        total_return_percent = 0.0
    
    return {
        "id": portfolio.id,
        "total_value": total_value,
        "cash": portfolio.cash,
        "initial_value": portfolio.initial_value if is_initialized else 0.0,
        "total_return": total_return,
        "total_return_percent": total_return_percent,
        "is_initialized": is_initialized,
        # ... other fields ...
    }
```

### Frontend Changes

#### 1. Add Initialization State to Main Page
```typescript
const [portfolioInitialized, setPortfolioInitialized] = useState<boolean>(false);

// In fetchBackendData:
const initStatusResult = await apiRequest<any>(
  `/api/v1/portfolio/${portfolioId}/initialization-status`
);
if (initStatusResult.data) {
  setPortfolioInitialized(initStatusResult.data.is_initialized);
}
```

#### 2. Pass Initialization Flag to DashboardTab
```typescript
<DashboardTab 
  cash={cash} 
  holdings={holdings} 
  agents={agents} 
  tradeHistory={tradeHistory} 
  triggerToast={triggerToast} 
  loading={loading} 
  portfolioInitialized={portfolioInitialized} 
/>
```

#### 3. Update DashboardTab PnL Calculations
```typescript
interface DashboardTabProps {
  portfolioInitialized?: boolean;
}

// PnL calculation
const portfolioChange = portfolioInitialized ? totalPortfolioValue - 100000 : 0;
const portfolioChangePercent = portfolioInitialized && totalPortfolioValue > 0 
  ? (portfolioChange / 100000) * 100 
  : 0;
```

#### 4. Update Equity Curve Visualization
```typescript
const getChartCoordinates = () => {
  // Show flat line at $0 when not initialized
  if (loading || !portfolioInitialized || totalPortfolioValue === 0) {
    return {
      points: "M 0 150 L 600 150",
      dots: [
        {cx: 0, cy: 150, label: "Start", val: "$0"},
        {cx: 600, cy: 150, label: "Now", val: "$0"}
      ],
      fillGradient: "M 0 150 L 600 150 L 600 200 L 0 200 Z",
      high: "$0", low: "$0", current: "$0"
    };
  }
  
  // Normal chart rendering when initialized
  // ...
};
```

## Key Principles

1. **Backend is Source of Truth**: PnL calculations happen on backend, frontend just displays
2. **Initialization Flag**: Single boolean determines whether to show real metrics or $0
3. **Visual Consistency**: Both PnL card and equity curve show $0 until initialized
4. **Database-Driven**: Initialization status comes from actual trades/positions in DB

## Testing

Test with SQLite directly:
```bash
# Before initialization (should show $0 PnL)
curl http://localhost:8000/api/v1/portfolio

# Add test data
python -c "import sqlite3; conn = sqlite3.connect('data/sqlite/jasper_trades.db'); cursor = conn.cursor(); cursor.execute(\"INSERT INTO trades (symbol, side, quantity, price, status, entry_price) VALUES ('AAPL', 'buy', 10, 150.0, 'filled', 150.0)\"); cursor.execute(\"INSERT INTO positions (portfolio_id, symbol, quantity, avg_price, current_price, market_value) VALUES (1, 'AAPL', 10, 150.0, 150.0, 1500.0)\"); conn.commit(); conn.close()"

# After initialization (should show real PnL)
curl http://localhost:8000/api/v1/portfolio
```

## Files Modified

**Backend:**
- `backend/app/services/portfolio_service.py` - Modified `get_portfolio_summary()`
- `backend/app/api/v1/portfolio.py` - Added `/initialization-status` endpoint

**Frontend:**
- `frontend/app/page.tsx` - Added `portfolioInitialized` state and fetch
- `frontend/components/DashboardTab.tsx` - Added `portfolioInitialized` prop and conditional rendering

## Related Patterns

This same pattern applies to:
- Live broker balance sync (use `/sync-broker` endpoint)
- Performance metrics endpoint (returns zeroed data when not initialized)
- Any dashboard metric that should be zero before real activity