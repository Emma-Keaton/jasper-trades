---
name: full-stack-mobile-responsive-fix
description: Comprehensive mobile responsiveness fixes for Next.js trading dashboard with overflow handling, touch targets, and responsive layouts
source: auto-skill
extracted_at: '2026-06-15'
---

# Full-Stack Mobile Responsive Fix for Trading Dashboard

## Problem
Trading dashboard with complex tables, charts, and forms was not mobile-responsive. Tables overflowed horizontally, touch targets were too small, and layouts broke on screens < 768px.

## Solution Approach

### 1. Table Overflow Fixes
**Pattern:** Replace fixed-width tables with horizontal scroll containers

**Before:**
```tsx
<div className="min-w-[600px] overflow-hidden">
  <table>...</table>
</div>
```

**After:**
```tsx
<div className="overflow-x-auto">
  <div className="min-w-full">
    <table className="w-full">...</table>
  </div>
</div>
```

**Files to apply:**
- `DashboardTab.tsx` - Holdings table
- `PortfolioTab.tsx` - Portfolio positions table
- `CopyTradeTab.tsx` - Leaderboard table
- `BacktestTab.tsx` - Heatmap (min-w-[650px] → overflow-x-auto)

### 2. Touch Target Sizing
**Pattern:** Ensure all interactive elements meet 44px minimum touch target

**Before:**
```tsx
<select className="h-9 ...">  // 36px - too small
<button className="h-9 ...">  // 36px - too small
```

**After:**
```tsx
<select className="h-11 ...">  // 44px minimum
<button className="h-11 ...">  // 44px minimum
```

**Files to update:**
- All `<select>` elements (SignalsTab, AgentsTab, SettingsTab, etc.)
- All action buttons (Execute, Save, Test buttons)
- Dropdown triggers

### 3. Responsive Grid & Flex Patterns
**Pattern:** Stack vertically on mobile, row on desktop

**Common patterns used:**
```tsx
// Grid responsive
<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">

// Flex responsive
<div className="flex flex-col md:flex-row gap-4">

// Padding responsive
<div className="p-4 md:p-6 lg:p-8">

// Conditional visibility
<div className="hidden md:block">  // Desktop only
<div className="md:hidden">  // Mobile only
```

### 4. Modal & Overlay Fixes
**Pattern:** Full-screen modals on mobile, centered on desktop

```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
  <div className="bg-[#1E293B] rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
    {/* Content */}
  </div>
</div>
```

### 5. Settings Form Stacking
**Pattern:** Stack form sections vertically on mobile

```tsx
{/* Before */}
<div className="grid grid-cols-2 gap-3">
  <input />
  <input />
</div>

{/* After - responsive */}
<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
  <input />
  <input />
</div>
```

## Implementation Checklist

- [ ] Replace all `min-w-[XXXpx]` with `overflow-x-auto` wrappers
- [ ] Update all height classes from `h-9` to `h-11` for interactive elements
- [ ] Add responsive grid classes everywhere (`grid-cols-1 md:grid-cols-X`)
- [ ] Test modals at 375px width (iPhone SE)
- [ ] Verify all buttons have 44px minimum touch target
- [ ] Add horizontal scroll indicators where needed
- [ ] Test on Chrome DevTools at breakpoints: 375px, 768px, 1024px

## Verification

**Test at these breakpoints:**
1. **375px** (iPhone SE) - All tables scroll, content accessible
2. **768px** (iPad) - 2-column grids engage
3. **1024px** (Desktop) - Full layout as designed

**Tools:**
- Chrome DevTools → Toggle Device Toolbar
- Test: iPhone SE, iPad Air, Desktop

## Why This Matters

Mobile responsiveness is critical for trading platforms where users may:
- Check positions on-the-go
- Receive urgent notifications
- Need to execute trades from mobile devices

The fix maintains full functionality while adapting layout to screen size, ensuring professional UX across all devices.