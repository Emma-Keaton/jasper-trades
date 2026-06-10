---
name: portfolio-component-initialization-state
description: Pass portfolio initialization state from parent to child components to show appropriate empty/uninitialized states instead of misleading data
source: auto-skill
extracted_at: '2026-06-10T23:08:03.974Z'
---

# Portfolio Component Initialization State

When building portfolio dashboards, child components need to know whether the portfolio has real trading activity or is still in a "not initialized" state. This prevents showing misleading charts/data when there's no actual trading history.

## The Problem

Portfolio components (pie charts, allocation breakdowns, PnL displays) may show data that looks legitimate but is actually just placeholder or initialization data:

- ❌ Pie chart showing 100% "Cash" when user hasn't made any trades yet
- ❌ PnL showing $0.00 (0.00%) which looks like they broke even instead of never starting
- ❌ Allocation percentages calculated from initial cash balance, not trading activity

## The Solution: Initialization State Prop

Pass an `is_initialized` flag from the backend through the parent component to all child components that display portfolio data.

### 1. Backend: Initialization Status Endpoint

Create an endpoint that checks for real trading activity:

```python
@router.get("/{portfolio_id}/initialization-status")
async def get_initialization_status(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Check if portfolio is initialized with real trading activity."""
    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    
    # Check for trading activity
    positions = await portfolio_service.get_all_positions(portfolio_id, include_empty=False)
    trades_result = await portfolio_service.get_pnl(portfolio_id)
    has_trades = trades_result.get("trade_count", 0) > 0
    has_positions = len(positions) > 0
    
    # Portfolio is "initialized" only if there's actual trading activity
    # Just having a portfolio with initial cash doesn't count
    is_initialized = has_trades or has_positions
    
    return {
        "is_initialized": is_initialized,
        "has_trades": has_trades,
        "has_positions": has_positions,
        "has_account_setup": portfolio.cash > 0 and (portfolio.is_paper or portfolio.broker),
        "initial_value": portfolio.initial_value if is_initialized else 0,
    }
```

**Key Logic:**
- `is_initialized = has_trades OR has_positions`
- Initial cash balance alone does NOT count as "initialized"
- Returns separate flags for trades, positions, and account setup

### 2. Parent Component: Fetch and Pass State

In the main page/layout component, fetch initialization status and pass to children:

```tsx
// page.tsx
const [portfolioInitialized, setPortfolioInitialized] = useState<boolean>(false);

useEffect(() => {
  const fetchInitStatus = async () => {
    const initStatusResult = await apiRequest<any>(`/api/v1/portfolio/${portfolioId}/initialization-status`);
    if (initStatusResult.data) {
      setPortfolioInitialized(initStatusResult.data.is_initialized);
    }
  };
  fetchInitStatus();
}, []);

// Pass to child components
{activeTab === 'portfolio' && (
  <PortfolioTab 
    cash={cash} 
    holdings={holdings} 
    portfolioInitialized={portfolioInitialized}  // ← Pass the flag
    triggerToast={triggerToast} 
  />
)}
```

### 3. Child Component: Conditional Rendering

Child components use the flag to show appropriate empty states:

```tsx
interface PortfolioTabProps {
  cash: number;
  holdings: Holding[];
  portfolioInitialized?: boolean;  // ← Accept the prop
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

export default function PortfolioTab({
  cash,
  holdings,
  portfolioInitialized = false,  // Default to false
  triggerToast
}: PortfolioTabProps) {
  
  return (
    <div>
      {/* Allocation Chart */}
      <div className="allocation-chart">
        {!portfolioInitialized ? (
          <div className="text-center">
            <Briefcase className="w-16 h-16 text-gray-500" />
            <h4>Portfolio Not Initialized</h4>
            <p>Complete your first trade to see allocation breakdown</p>
            <button onClick={() => triggerToast('info', 'Get Started', 'Navigate to Signals tab')}>
              View Trading Signals
            </button>
          </div>
        ) : (
          <ReactFrappeChart data={allocationData} />
        )}
      </div>
    </div>
  );
}
```

### 4. PnL Calculations Respect Initialization

Dashboard PnL should only show after initialization:

```tsx
// DashboardTab.tsx
const portfolioChange = portfolioInitialized 
  ? totalPortfolioValue - 100000  // Show PnL from initial value
  : 0;  // Show 0 when not initialized

const portfolioChangePercent = portfolioInitialized && totalPortfolioValue > 0
  ? ((totalPortfolioValue - 100000) / 100000) * 100
  : 0;
```

## Components That Need This Pattern

Any component displaying portfolio metrics should check initialization:

1. **Allocation/Pie Charts** - Show empty state until first trade
2. **PnL Display** - Don't show "$0.00 (0.00%) which looks like breakeven
3. **Equity Curve Charts** - Show flat line or empty state
4. **Position Holdings Table** - May show "No positions" vs loading state
5. **Withdraw/Profit Settings** - Disable until profits exist

## Why This Matters

### User Experience
- ❌ **Without init check:** User sees "0.00% PnL" and thinks algo broke even
- ✅ **With init check:** User sees "Not Initialized" and knows they haven't started

### Data Integrity
- Prevents calculating meaningless percentages from initial cash
- Avoids displaying placeholder data as if it's real trading data
- Clear distinction between "no data yet" vs "no gains/losses"

### Onboarding Flow
- Empty states can include CTAs ("View Trading Signals", "Execute First Trade")
- Guides users toward meaningful actions
- Reduces confusion about what they're seeing

## Pattern Consistency

Apply the same pattern across all portfolio-related components:

```tsx
// All children receive the same prop
<DashboardTab portfolioInitialized={portfolioInitialized} />
<PortfolioTab portfolioInitialized={portfolioInitialized} />
<EquityChart portfolioInitialized={portfolioInitialized} />
<WithdrawModal portfolioInitialized={portfolioInitialized} />
```

This ensures consistent UX: either ALL components show initialized data, or ALL show empty states.

## Related Patterns

- **[Silent Refresh Architecture](./silent-refresh-architecture.md)** - Initialize data loading without blocking UI
- **[Recharts Equity Curve Implementation](./recharts-equity-curve-implementation.md)** - Don't hardcode benchmarks, use backend-provided initial values
- **[Frontend Build Error Resolution](./frontend-build-error-resolution.md)** - Fix TypeScript errors when adding new props