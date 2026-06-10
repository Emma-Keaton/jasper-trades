---
name: no-hardcoded-financial-values
description: Never hardcode financial values like initial capital or portfolio balances in frontend - always use backend-provided values
source: auto-skill
extracted_at: '2026-06-10T23:11:50.598Z'
---

# No Hardcoded Financial Values in Frontend

## Problem Statement

Hardcoding financial values (e.g., `$100,000` initial capital, portfolio balances, reference lines) in frontend code causes miscalculations and incorrect UI display when users have different account configurations:
- Paper trading with different starting balances
- Live trading with custom deposit amounts
- Multiple portfolios with varying initial values

## What NOT to Hardcode

❌ **Never hardcode these values in frontend:**
- Initial portfolio/capital amounts (`100000`, `$100K`)
- Reference lines at specific dollar amounts
- PnL calculation baselines
- Account balance assumptions
- Starting equity values

## Correct Approach

✅ **Always use backend-provided values:**

### 1. Dashboard PnL Calculations

```typescript
// WRONG - hardcoded reference value
const portfolioChange = totalPortfolioValue - 100000;

// CORRECT - use initialValue from backend
const portfolioChange = totalPortfolioValue - initialValue;
```

### 2. Chart Data Generation

```typescript
// WRONG - assumes $100K starting point
const chartData = [
  { x: 0, y: 100000 }, // hardcoded!
  { x: 1, y: totalPortfolioValue }
];

// CORRECT - uses actual initial value from backend
const chartData = equityData.length > 0 
  ? equityData.map(point => ({ x: point.x, y: point.y }))
  : [
      { x: 0, y: initialValue }, // from backend
      { x: 1, y: totalPortfolioValue }
    ];
```

### 3. Component Props Pattern

```typescript
interface DashboardTabProps {
  cash: number;
  holdings: Holding[];
  initialValue?: number; // ✅ from backend
  // NOT: portfolioInitialized?: boolean (used for hardcoded logic)
}

// Pass from parent (page.tsx)
<DashboardTab 
  cash={cash}
  initialValue={portfolioHistory?.initialValue || 0} // backend value
/>
```

### 4. Backtest Configuration

For user-configurable values (like backtest initial capital), make them **editable** with defaults:

```typescript
// User-editable with sensible default
const [initialCapital, setInitialCapital] = useState<number>(100000);

// Pass to API (backend validates)
await fetch('/api/backtest', {
  body: JSON.stringify({
    initial_capital: initialCapital, // user's choice
  }),
});
```

## File Locations to Check

When implementing financial features, audit these files for hardcoded values:

- `components/DashboardTab.tsx` - PnL calculations, chart data
- `components/charts/EquityChart.tsx` - Y-axis domains, reference lines
- `components/BacktestTab.tsx` - Initial capital, asset scope
- `hooks/usePortfolioHistory.ts` - Data transformations
- `app/page.tsx` - Props passed to child components
- `components/onboarding/tours/*.ts` - Tour descriptions

## UI/UX Guidelines

1. **Charts**: Y-axis should always start at $0 (or actual data min), never assume a baseline
2. **Reference Lines**: Only show if backend provides the reference value
3. **Labels**: Display actual values (e.g., "Start: $50,000") not assumed ones
4. **Onboarding Text**: Never mention specific dollar amounts in tooltips/tours

## Example: Equity Chart Implementation

```typescript
// EquityChart.tsx - No hardcoded values
const yAxisDomain = [0, maxValue * 1.15]; // starts from 0, scales to data

// No $100K reference line
// {portfolioInitialized && <ReferenceLine y={100000} />} // ❌ WRONG

// Reference line only if backend provides it
{referenceValue && <ReferenceLine y={referenceValue} />} // ✅ CORRECT
```

## Verification Checklist

Before merging financial features:
- [ ] Search for `100000`, `100,000`, `$100K` in frontend code
- [ ] Verify all PnL calculations use `initialValue` prop
- [ ] Confirm chart data comes from backend `equityData` or uses `initialValue`
- [ ] Check that user-configurable values are editable inputs
- [ ] Remove any hardcoded reference lines or benchmarks
- [ ] Update onboarding/tour text to not mention specific amounts

## Related Skills

- `recharts-equity-curve-implementation` - Chart rendering best practices
- `dashboard-pnl-initialization-sync` - Portfolio state synchronization