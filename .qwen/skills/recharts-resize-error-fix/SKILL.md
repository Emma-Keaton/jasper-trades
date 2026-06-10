---
name: recharts-resize-error-fix
description: Fix Recharts "width/height -1" error by validating data and using proper container dimensions
source: auto-skill
extracted_at: '2026-06-11T00:00:00.000Z'
---

# Recharts Resize Error Fix

## Problem

Recharts throws console errors when rendering with invalid dimensions:

```
The width(-1) and height(-0.4) of chart should be greater than 0,
please check the style of container, or the props width(100%) and height(undefined)
```

This happens when:
1. The chart data array is empty or contains all zero values
2. The parent container uses `absolute inset-0` without explicit height
3. Recharts renders before CSS layout is complete
4. Data has invalid values (undefined, null, or non-numeric)

## Solution

### Fix 1: Add Robust Data Validation Guard

Check that data has at least one positive value before rendering:

```tsx
const hasValidData = data && data.length > 0 && data.some(d => typeof d.y === 'number' && d.y > 0);

// Guard: Don't render chart if no valid data
if (!hasValidData) {
  return (
    <div className="relative w-full h-[350px] bg-[#1E293B] rounded-lg border border-[#475569] overflow-hidden flex items-center justify-center">
      <div className="text-center text-gray-400">
        <p className="text-sm mb-2">No portfolio data available yet</p>
        <p className="text-xs font-mono">Start trading to see your equity curve</p>
      </div>
    </div>
  );
}
```

**Key points:**
- Use `.some()` not `.every()` - require at least one positive value
- Check `typeof d.y === 'number'` to catch undefined/null
- Check `d.y > 0` to catch zero-value arrays
- Return placeholder UI instead of empty chart

### Fix 2: Set Explicit Container Height

When using `absolute inset-0` positioning, calculate height explicitly:

```tsx
<div className="absolute inset-0 pt-16" style={{ height: 'calc(100% - 4rem)' }}>
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={chartData}>
      {/* chart content */}
    </AreaChart>
  </ResponsiveContainer>
</div>
```

**Why:** `pt-16` adds padding-top but doesn't reduce available height. The `calc(100% - 4rem)` compensates for the header space.

### Fix 3: Return Empty Array for No Data

When generating fallback chart data, return empty array instead of zero-value arrays:

```tsx
const chartData = useMemo(() => {
  // If we have actual equity data from backend, use it
  if (equityData && equityData.length > 0) {
    return equityData.map(point => ({ x: point.x, y: point.y }));
  }

  // Fallback: show current portfolio value
  if (loading) {
    return []; // Empty during loading
  }

  // Show flat line at current value if portfolio exists but no history
  if (totalPortfolioValue > 0) {
    return [
      { x: 0, y: effectiveInitialValue },
      { x: 1, y: totalPortfolioValue }
    ];
  }

  // No portfolio data - return empty array (chart will show "no data" message)
  return [];
}, [equityData, loading, effectiveInitialValue, totalPortfolioValue]);
```

**Don't do this:**
```tsx
// ❌ This causes the -1 error
return [
  { x: 0, y: 0 },
  { x: 1, y: 0 }
];
```

## Alternative Approaches

### Option A: Use `aspect` Ratio
If you don't want to set explicit height:

```tsx
<ResponsiveContainer width="100%" aspect={2.5}>
  <AreaChart data={chartData}>
    {/* chart content */}
  </AreaChart>
</ResponsiveContainer>
```

**Caveat:** Aspect ratio can be ignored if parent has no defined width.

### Option B: Use `minHeight`
Add minimum height to prevent collapse:

```tsx
<div className="absolute inset-0 pt-14" style={{ minHeight: '250px' }}>
  <ResponsiveContainer width="100%" height={250} minHeight={250}>
    <AreaChart data={chartData}>
      {/* chart content */}
    </AreaChart>
  </ResponsiveContainer>
</div>
```

### Option C: The "99% Width" Trick
Prevent infinite resize loops:

```tsx
<ResponsiveContainer width="99%" height="100%">
```

This prevents Recharts from getting stuck in a "am I too big?" resizing loop.

## Complete Example

```tsx
"use client";

import { useMemo, useState, useRef } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface EquityChartDataPoint {
  x: number | string;
  y: number;
}

interface EquityChartProps {
  data: EquityChartDataPoint[];
  timeframe?: '1D' | '1W' | '1M' | '3M' | '1Y' | 'ALL';
  onTimeframeChange?: (timeframe: string) => void;
}

export default function EquityChart({ data, timeframe = '1M', onTimeframeChange }: EquityChartProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.map((point, index) => ({
      index,
      value: point.y,
      label: typeof point.x === 'string' ? point.x :
        index === 0 ? 'Start' :
        index === data.length - 1 ? 'Now' : ''
    }));
  }, [data]);

  // CRITICAL: Validate data has positive values
  const hasValidData = data && data.length > 0 && data.some(d => typeof d.y === 'number' && d.y > 0);

  if (!hasValidData) {
    return (
      <div
        ref={containerRef}
        className="relative w-full h-[350px] bg-[#1E293B] rounded-lg border border-[#475569] overflow-hidden flex items-center justify-center"
      >
        <div className="text-center text-gray-400">
          <p className="text-sm mb-2">No portfolio data available yet</p>
          <p className="text-xs font-mono">Start trading to see your equity curve</p>
        </div>
      </div>
    );
  }

  const maxValue = useMemo(() => {
    if (data.length === 0) return 0;
    return Math.max(...data.map(d => d.y));
  }, [data]);

  const yAxisMax = maxValue > 0 ? maxValue * 1.15 : 1000;

  return (
    <div
      ref={containerRef}
      className="relative w-full bg-[#1E293B] rounded-lg border border-[#475569] overflow-hidden h-[350px]"
    >
      {/* Chart with explicit height calculation */}
      <div className="absolute inset-0 pt-16" style={{ height: 'calc(100% - 4rem)' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 20, bottom: 30, left: 60 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.5} />
            <XAxis dataKey="label" tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'monospace' }} />
            <YAxis domain={[0, yAxisMax]} tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'monospace' }} />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#3B82F6"
              fill="url(#colorFill)"
              strokeWidth={3}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

## Checklist for Recharts Integration

- [ ] Validate data is not empty: `data && data.length > 0`
- [ ] Validate data has positive values: `data.some(d => d.y > 0)`
- [ ] Set explicit parent height or use `aspect` ratio
- [ ] Use `calc()` for height if using absolute positioning with padding
- [ ] Return placeholder UI when no valid data
- [ ] Consider `width="99%"` to prevent resize loops
- [ ] Add `minHeight` as safety net for dynamic layouts

## Files Modified

- `components/charts/EquityChart.tsx` - Added data validation guard
- `components/DashboardTab.tsx` - Fixed fallback data generation

## Related Issues

- Backend returns `{ holdings: [...] }` not direct array - see `frappe-charts-portfolio-initialization` skill
- ChartGPU/AllocationChartGPU removed - unused component causing build errors