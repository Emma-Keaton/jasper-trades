---
name: editable-backtest-configuration
description: Make backtest parameters (asset scope, initial capital, date ranges) user-editable with proper API integration
source: auto-skill
extracted_at: '2026-06-10T23:11:50.598Z'
---

# Editable Backtest Configuration UI

## Overview

Backtest parameters should be user-configurable rather than hardcoded, allowing traders to test strategies with different capital allocations, asset universes, and time periods.

## Key Configuration Fields

### 1. Asset Index Scope (Editable Text Input)

```typescript
const [assetScope, setAssetScope] = useState<string>('NVDA, AAPL, MSFT, BTC, ETH');

// UI Component
<input
  type="text"
  value={assetScope}
  onChange={(e) => setAssetScope(e.target.value)}
  placeholder="e.g., NVDA, AAPL, MSFT, BTC, ETH"
  className="..."
/>

// Send to backend as array
asset_scope: assetScope
  .split(',')
  .map((s: string) => s.trim())
  .filter((s: string) => s.length > 0)
```

### 2. Initial Investment Capital (Editable Number Input)

```typescript
const [initialCapital, setInitialCapital] = useState<number>(100000);

// UI Component - allow user input
<input
  type="number"
  value={initialCapital}
  onChange={(e) => setInitialCapital(Number(e.target.value))}
  placeholder="100000"
  className="..."
/>

// Send to backend
initial_capital: initialCapital
```

### 3. Date Range (Date Pickers)

```typescript
const [dateFrom, setDateFrom] = useState<string>('2024-01-01');
const [dateTo, setDateTo] = useState<string>('2025-04-01');

// UI Components
<input
  type="date"
  value={dateFrom}
  onChange={(e) => setDateFrom(e.target.value)}
/>
<input
  type="date"
  value={dateTo}
  onChange={(e) => setDateTo(e.target.value)}
/>
```

## Complete Implementation Pattern

```typescript
// State declarations
const [stratName, setStratName] = useState<string>('My Strategy');
const [initialCapital, setInitialCapital] = useState<number>(100000);
const [assetScope, setAssetScope] = useState<string>('NVDA, AAPL, MSFT');
const [dateFrom, setDateFrom] = useState<string>('2024-01-01');
const [dateTo, setDateTo] = useState<string>('2025-01-01');

// API call with all parameters
const handleTriggerBacktest = async () => {
  const response = await fetch('/api/v1/backtest/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      strategy_name: stratName,
      initial_capital: initialCapital,
      asset_scope: assetScope.split(',').map(s => s.trim()).filter(s => s),
      start_date: dateFrom,
      end_date: dateTo,
      engine: selectedEngine,
      feed: selectedFeed,
    }),
  });
};
```

## UI Layout Best Practices

### Grid Layout for Parameters

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
  {/* Asset Scope */}
  <div className="flex flex-col gap-1.5">
    <label className="text-xs text-gray-400 font-mono">Asset Index Scope</label>
    <input type="text" value={assetScope} onChange={...} />
  </div>

  {/* Initial Capital */}
  <div className="flex flex-col gap-1.5">
    <label className="text-xs text-gray-400 font-mono">Initial Capital</label>
    <input type="number" value={initialCapital} onChange={...} />
  </div>

  {/* Start Date */}
  <div className="flex flex-col gap-1.5">
    <label className="text-xs text-gray-400 font-mono">Interval Start</label>
    <input type="date" value={dateFrom} onChange={...} />
  </div>

  {/* End Date */}
  <div className="flex flex-col gap-1.5">
    <label className="text-xs text-gray-400 font-mono">Interval Terminate</label>
    <input type="date" value={dateTo} onChange={...} />
  </div>
</div>
```

## Styling Guidelines

### Input Field Styles (Tailwind)

```tsx
// Standard text input
className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"

// Number input
className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"

// Date input
className="w-full h-10 bg-[#0F172A] border border-[#475569] rounded-lg px-3 text-xs text-white font-mono focus:outline-none focus:border-[#3B82F6]"
```

### Label Styles

```tsx
className="text-xs text-[#94A3B8] font-mono leading-none"
```

## Validation & Error Handling

```typescript
const validateBacktestParams = () => {
  if (initialCapital <= 0) {
    triggerToast('error', 'Invalid Capital', 'Initial capital must be > 0');
    return false;
  }
  
  if (assetScope.split(',').filter(s => s.trim()).length === 0) {
    triggerToast('error', 'No Assets', 'Please specify at least one asset');
    return false;
  }
  
  if (new Date(dateFrom) > new Date(dateTo)) {
    triggerToast('error', 'Invalid Dates', 'Start date must be before end date');
    return false;
  }
  
  return true;
};
```

## Backend Integration Notes

1. **Asset Scope**: Send as comma-separated string, backend parses to array
2. **Initial Capital**: Send as number, backend validates against minimum/maximum limits
3. **Dates**: Send as ISO format strings (YYYY-MM-DD), backend handles timezone conversion
4. **Error Responses**: Backend should return specific validation errors for each field

## Related Skills

- `no-hardcoded-financial-values` - Avoid hardcoded capital amounts
- `dashboard-pnl-initialization-sync` - Portfolio value synchronization