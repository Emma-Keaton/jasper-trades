---
name: frappe-charts-portfolio-initialization
description: Configure Frappe Charts pie chart to show placeholder state when portfolio is not initialized with real trading activity
source: auto-skill
extracted_at: '2026-06-11T00:00:00.000Z'
---

# Frappe Charts Portfolio Initialization Check

## Problem
The portfolio pie chart was rendering allocation percentages even when the portfolio had $0 value and no real trading activity, giving users a confusing empty-state experience.

## Solution
Pass the `portfolioInitialized` flag from the parent component and conditionally render a placeholder state when the portfolio hasn't been initialized with real trades.

## Implementation

### Step 1: Pass `portfolioInitialized` prop from parent
In `app/page.tsx`, add the prop to the PortfolioTab component:

```tsx
{activeTab === 'portfolio' && (
  <PortfolioTab 
    cash={cash} 
    setCash={setCash} 
    holdings={holdings} 
    setHoldings={setHoldings} 
    tradeHistory={tradeHistory} 
    triggerToast={triggerToast} 
    portfolioInitialized={portfolioInitialized}  // Pass this prop
  />
)}
```

### Step 2: Add prop to component interface
In `components/PortfolioTab.tsx`, update the interface and function signature:

```tsx
interface PortfolioTabProps {
  cash: number;
  setCash: React.Dispatch<React.SetStateAction<number>>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  tradeHistory: TradeHistoryItem[];
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  portfolioInitialized?: boolean;  // Add this
}

export default function PortfolioTab({
  cash,
  setCash,
  holdings,
  setHoldings,
  tradeHistory,
  triggerToast,
  portfolioInitialized = false  // Default to false
}: PortfolioTabProps) {
```

### Step 3: Conditional rendering in chart area
Replace the always-rendering Frappe Chart with conditional logic:

```tsx
<div className="w-full h-[250px] flex items-center justify-center">
  {!portfolioInitialized ? (
    <div className="text-center">
      <div className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
        <Briefcase className="w-8 h-8 text-gray-500" />
      </div>
      <h4 className="text-lg font-bold text-white mb-2">Portfolio Not Initialized</h4>
      <p className="text-sm text-gray-400 mb-4">Complete your first trade to see allocation breakdown</p>
      <button
        onClick={() => triggerToast('info', 'Get Started', 'Navigate to Signals tab to execute your first trade')}
        className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
      >
        View Trading Signals
      </button>
    </div>
  ) : (
    <ReactFrappeChart
      type={'pie' as any}
      height={250}
      colors={['#3B82F6', '#14F195', '#10B981', '#F59E0B', '#EF4444']}
      data={allocationData}
    />
  )}
</div>
```

## Backend Integration

The `portfolioInitialized` flag comes from the backend initialization status endpoint:

```typescript
// In app/page.tsx
const initStatusResult = await apiRequest<any>(
  `/api/v1/portfolio/${portfolioId}/initialization-status`
);
if (initStatusResult.data) {
  setPortfolioInitialized(initStatusResult.data.is_initialized);
}
```

Backend endpoint: `GET /api/v1/portfolio/{portfolio_id}/initialization-status`

Returns:
```json
{
  "portfolio_id": 1,
  "is_initialized": false,  // true if has_trades OR has_positions
  "has_trades": false,
  "has_positions": false,
  "has_account_setup": true,
  "cash": 100000,
  "initial_value": 0
}
```

## Why This Matters

1. **User Experience**: New users see a clear call-to-action instead of an empty/broken chart
2. **Consistency**: Matches the pattern used in DashboardTab for equity curve initialization
3. **Contextual Guidance**: Provides actionable next steps ("View Trading Signals") rather than leaving users confused
4. **Performance**: Avoids rendering Frappe Charts with invalid data

## Key Takeaways

- Always check `portfolioInitialized` before rendering portfolio visualization components
- Use backend's `initialization-status` endpoint as the source of truth
- Provide helpful placeholder states with CTAs for uninitialized portfolios
- Default the prop to `false` to handle edge cases where the flag isn't passed