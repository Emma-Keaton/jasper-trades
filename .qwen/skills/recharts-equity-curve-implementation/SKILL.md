---
name: recharts-equity-curve-implementation
description: Implement interactive equity curve chart using Recharts with fullscreen, timeframe selection, proper Y-axis scaling from $0, and NO hardcoded benchmarks
source: auto-skill
extracted_at: '2026-06-10T22:51:53.798Z'
---

# Recharts Equity Curve Implementation

When building fintech/portfolio dashboards, use **Recharts** instead of ChartGPU for equity curves. ChartGPU adds unnecessary complexity (WebGPU requirement, GPU warmup) for simple area/line charts.

## Critical: Don't Hardcode Benchmarks

**NEVER hardcode reference lines or starting values** like $100K in the frontend.

- ❌ **Bad:** `<ReferenceLine y={100000} />` - assumes all portfolios start at $100K
- ✅ **Good:** Display whatever backend provides as initial/current value
- **Why:** Backend determines initial balance (e.g., 100K paper trading, 0 for new users, different amounts per user)

The frontend should **only display** actual backend data without making assumptions about starting values.

## Why Recharts for Equity Curves

- **Lightweight**: SVG-based, no GPU required
- **React-native**: Built specifically for React components
- **Responsive**: Handles window resizing perfectly
- **Fintech standard**: Used by Robinhood, Wealthfront, etc.
- **Better UX**: Easy tooltip customization for financial data ($, %, dates)

## Installation

```bash
npm install recharts
```

## Chart Component Structure

Create a reusable chart component with these features:

### 1. Fullscreen Mode

```tsx
const [isFullscreen, setIsFullscreen] = useState(false);
const containerRef = useRef<HTMLDivElement>(null);

const toggleFullscreen = async () => {
  if (!containerRef.current) return;
  if (!document.fullscreenElement) {
    await containerRef.current.requestFullscreen();
    setIsFullscreen(true);
  } else {
    await document.exitFullscreen();
    setIsFullscreen(false);
  }
};
```

### 2. Timeframe Selection

Provide buttons for different time periods (1W, 1M, 3M, 1Y, ALL) and pass selected timeframe to chart component.

### 3. Y-Axis Domain (Critical for PnL)

**Always start Y-axis from 0** to show proper portfolio context:

```tsx
const yAxisDomain = useMemo(() => {
  return [0, maxValue * 1.15]; // 15% headroom at top
}, [maxValue]);

// In YAxis component:
<YAxis domain={yAxisDomain} />
```

**Why this matters:** Auto-scaling (e.g., 95K-105K) makes small fluctuations look exaggerated and doesn't show the true "from zero" growth trajectory.

### 4. Color-Coded Area Chart

```tsx
<defs>
  <linearGradient id="colorPositive" x1="0" y1="0" x2="0" y2="1">
    <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
    <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
  </linearGradient>
  <linearGradient id="colorNegative" x1="0" y1="0" x2="0" y2="1">
    <stop offset="5%" stopColor="#EF4444" stopOpacity={0.4} />
    <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
  </linearGradient>
</defs>

<Area
  type="monotone"
  dataKey="value"
  stroke={isPositive ? '#10B981' : '#EF4444'}
  fill={isPositive ? 'url(#colorPositive)' : 'url(#colorNegative)'}
  strokeWidth={3}
/>
```

### 5. Enhanced Tooltips

Show comprehensive PnL information:

```tsx
const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const currentValue = payload[0].value;
    const change = currentValue - 100000; // Assuming 100K start
    const changePercent = (change / 100000) * 100;
    
    return (
      <div className="bg-[#0F172A] border border-[#475569] rounded-lg px-4 py-3">
        <p className="text-xs text-[#94A3B8] mb-1">
          {payload[0].payload.label}
        </p>
        <p className="text-lg font-black text-white">
          ${currentValue.toLocaleString()}
        </p>
        <div className={`text-xs font-bold ${change >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
          {change >= 0 ? '▲' : '▼'} ${change.toLocaleString()} ({changePercent.toFixed(2)}%)
        </div>
      </div>
    );
  }
  return null;
};
```

### 6. Reference Lines

Add context markers (e.g., starting capital line):

```tsx
<ReferenceLine 
  y={100000} 
  stroke="#475569" 
  strokeDasharray="3 3"
  label={{ 
    value: '$100K',
    fill: '#94A3B8',
    fontSize: 10,
    position: 'right'
  }}
/>
```

### 7. Y-Axis Formatting

Format large numbers appropriately:

```tsx
<YAxis
  tickFormatter={(value) => {
    if (value >= 1000000) return `$${(value/1000000).toFixed(1)}M`;
    if (value >= 1000) return `$${(value/1000).toFixed(0)}K`;
    return `$${value}`;
  }}
/>
```

## Complete Component Template

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
  ReferenceLine,
} from 'recharts';
import { Maximize, Minimize } from 'lucide-react';

interface EquityChartProps {
  data: Array<{ x: number | string; y: number }>;
  timeframe?: '1D' | '1W' | '1M' | '3M' | '1Y' | 'ALL';
  onTimeframeChange?: (timeframe: string) => void;
}

export default function EquityChart({ data, timeframe, onTimeframeChange }: EquityChartProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const chartData = useMemo(() => {
    return data.map((point, index) => ({
      index,
      value: point.y,
      label: index === 0 ? 'Inception' : index === data.length - 1 ? 'Now' : ''
    }));
  }, [data]);

  const maxValue = Math.max(...data.map(d => d.y));
  const minValue = Math.min(...data.map(d => d.y));
  const isPositive = maxValue >= 100000;

  return (
    <div ref={containerRef} className={`relative w-full ${isFullscreen ? 'h-full' : 'h-[350px]'}`}>
      {/* Header with timeframe + fullscreen button */}
      <div className="absolute top-0 left-0 right-0 z-10 flex justify-between p-3">
        {/* Timeframe buttons */}
        {onTimeframeChange && (
          <div className="flex gap-1 bg-[#0F172A] rounded-lg p-1">
            {['1W', '1M', '3M', '1Y', 'ALL'].map(btn => (
              <button
                key={btn}
                onClick={() => onTimeframeChange(btn)}
                className={`px-2 py-1 rounded ${timeframe === btn ? 'bg-[#3B82F6] text-white' : 'text-[#94A3B8]'}`}
              >
                {btn}
              </button>
            ))}
          </div>
        )}
        
        {/* Fullscreen toggle */}
        <button onClick={toggleFullscreen}>
          {isFullscreen ? <Minimize /> : <Maximize />}
        </button>
      </div>

      {/* Chart */}
      <div className="absolute inset-0 pt-14">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis domain={[0, maxValue * 1.15]} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={100000} strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="value"
              stroke={isPositive ? '#10B981' : '#EF4444'}
              fill={isPositive ? 'url(#positive)' : 'url(#negative)'}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

## Key Takeaways

1. **Always start Y-axis at 0** - Shows true growth context
2. **Add 10-15% headroom** - Prevents line touching top of chart
3. **Color-code by performance** - Green for profit, red for loss
4. **Include reference lines** - Mark starting capital, break-even, etc.
5. **Fullscreen for detail analysis** - Let users expand to see patterns
6. **Timeframe selection** - Different strategies need different time horizons
7. **Professional tooltips** - Show absolute + relative changes together

This approach works for any portfolio/equity tracking use case where you need clean, professional financial visualization without the overhead of GPU-accelerated charts.