# Onboarding Tutorial System - Implementation Plan

## Problem with Previous Implementation

The previous onboarding system was deleted because:
1. **Overlay was broken** - Visual highlighting didn't properly position over elements
2. **Buttons not clickable** - Z-index/pointer-events issues prevented user interaction
3. **Generic tour steps** - Didn't explain what each element/data point actually does
4. **No contextual learning** - Users couldn't explore at their own pace

---

## New Onboarding Philosophy

### Core Principles
1. **Non-blocking overlays** - Users can still click/interact with UI elements during tour
2. **Contextual tooltips** - Each data point explained with real examples
3. **Page-by-page mastery** - Focus on one tab/section at a time
4. **Progressive disclosure** - Start simple, reveal advanced features as user progresses
5. **Interactive actions** - "Try it yourself" moments instead of passive watching

---

## Architecture Overview

```
onboarding/
├── useOnboardingEngine.ts      # Core hook with element targeting logic
├── OnboardingProvider.tsx      # Context provider for global state
├── TourOverlay.tsx             # Spotlight/mask renderer (fixed positioning)
├── InteractiveTooltip.tsx      # Clickable tooltip with actions
├── OnboardingTour.tsx          # Main tour coordinator component
└── tours/                      # Per-page tour definitions
    ├── dashboard-tour.ts
    ├── agents-tour.ts
    ├── signals-tour.ts
    ├── copytrade-tour.ts
    ├── backtest-tour.ts
    ├── alphazoo-tour.ts
    ├── portfolio-tour.ts
    └── settings-tour.ts
```

---

## Technical Implementation

### 1. Element Targeting System

**Problem:** Previous overlay couldn't find elements or positioned incorrectly.

**Solution:** Use `data-onboarding` attributes + ResizeObserver for reliable targeting.

```typescript
// useOnboardingEngine.ts
interface TargetElement {
  selector: string;
  dataOnboardingId: string;
  element: HTMLElement | null;
  rect: DOMRect | null;
}

function useOnboardingEngine() {
  const [targets, setTargets] = useState<TargetElement[]>([]);
  
  // Scan DOM for all data-onboarding elements
  const scanElements = useCallback(() => {
    const elements = document.querySelectorAll('[data-onboarding]');
    const newTargets = Array.from(elements).map(el => ({
      selector: '',
      dataOnboardingId: el.getAttribute('data-onboarding') || '',
      element: el as HTMLElement,
      rect: el.getBoundingClientRect(),
    }));
    setTargets(newTargets);
  }, []);
  
  // Watch for resize/reposition
  useEffect(() => {
    const observer = new ResizeObserver(scanElements);
    targets.forEach(t => t.element && observer.observe(t.element));
    return () => observer.disconnect();
  }, [targets]);
  
  return { targets, scanElements, getTargetById };
}
```

### 2. Non-Blocking Overlay

**Problem:** Previous overlay blocked clicks on buttons.

**Solution:** Overlay uses `pointer-events: none` except for tooltip itself.

```tsx
// TourOverlay.tsx
<div className="fixed inset-0 z-[9998]" style={{ pointerEvents: 'none' }}>
  {/* Dark mask with spotlight cutout */}
  <svg className="absolute inset-0 w-full h-full">
    <defs>
      <mask id="spotlight">
        <rect width="100%" height="100%" fill="white" />
        <circle cx={spotlightX} cy={spotlightY} r={spotlightRadius} fill="black" />
      </mask>
    </defs>
    <rect width="100%" height="100%" fill="rgba(0,0,0,0.7)" mask="url(#spotlight)" />
  </svg>
  
  {/* Tooltip uses pointer-events: auto */}
  <div className="absolute z-[9999]" style={{ pointerEvents: 'auto' }}>
    <InteractiveTooltip {...tooltipProps} />
  </div>
</div>
```

### 3. Interactive Tooltip Component

**Problem:** Previous tooltips were static text with non-working buttons.

**Solution:** Tooltips have actionable buttons that trigger real interactions.

```tsx
// InteractiveTooltip.tsx
interface InteractiveTooltipProps {
  title: string;
  description: string;
  tip?: string;              // Pro tip for advanced users
  action?: {
    label: string;
    onClick: () => void;     // Real action (open modal, toggle switch, etc.)
    icon?: React.ReactNode;
  };
  skipAction?: boolean;      // For "Try it yourself" steps
  onNext: () => void;
  onPrev: () => void;
  onComplete: () => void;
}

export default function InteractiveTooltip({
  title,
  description,
  tip,
  action,
  skipAction,
  onNext,
  onPrev,
  onComplete,
}: InteractiveTooltipProps) {
  return (
    <div className="bg-[#1E293B] border border-[#475569] rounded-xl p-4 max-w-sm shadow-2xl">
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-[#94A3B8] mb-3">{description}</p>
      
      {action && !skipAction && (
        <button
          onClick={action.onClick}
          className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white rounded-lg px-4 py-2 flex items-center justify-center gap-2 transition"
        >
          {action.icon}
          {action.label}
        </button>
      )}
      
      {skipAction && (
        <div className="bg-[#334155] rounded-lg px-4 py-3 text-center text-[#94A3B8] text-sm">
          👉 Try this yourself, then click "Next" when ready
        </div>
      )}
      
      {tip && (
        <div className="mt-3 pt-3 border-t border-[#475569]">
          <p className="text-xs text-[#60A5FA] font-mono">
            💡 Pro Tip: {tip}
          </p>
        </div>
      )}
      
      <div className="flex items-center justify-between mt-4">
        <button onClick={onPrev} className="text-[#94A3B8] hover:text-white">
          ← Back
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#64748B] font-mono">
            Press ESC to close
          </span>
          <button onClick={onComplete} className="text-[#94A3B8] hover:text-white">
            ✕
          </button>
          <button onClick={onNext} className="text-white">
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 4. Tour Definitions (Per Page)

Each page gets its own tour definition file with step-by-step instructions.

```typescript
// tours/dashboard-tour.ts
import { TourStep } from '../useOnboardingEngine';

export const dashboardTour: TourStep[] = [
  {
    id: 'portfolio-value-card',
    targetElement: '[data-onboarding="portfolio-value"]',
    title: 'Total Portfolio Value',
    description: 'This shows your total account value including cash and holdings. Starts at $100,000 in paper trading mode.',
    tip: 'Click any card to see detailed breakdown by asset type',
    position: 'bottom',
  },
  {
    id: 'pnl-chart',
    targetElement: '[data-onboarding="pnl-chart"]',
    title: 'Profit & Loss Chart',
    description: 'Visual track of your portfolio performance over time. Green line = gains, red line = losses. Hover to see exact values at any point.',
    tip: 'Change timeframe (1D, 1W, 1M, ALL) to zoom into specific periods',
    position: 'top',
  },
  {
    id: 'holdings-table',
    targetElement: '[data-onboarding="holdings-table"]',
    title: 'Your Holdings',
    description: 'List of all assets you own. Shows current price, average buy price, and P&L percentage. Click any row to see detailed analytics.',
    action: {
      label: 'View Holding Details',
      onClick: () => document.querySelector('[data-onboarding="holdings-table"] tbody tr')?.click(),
    },
    position: 'right',
  },
  {
    id: 'trade-history',
    targetElement: '[data-onboarding="trade-history"]',
    title: 'Trade History Console',
    description: 'Real-time feed of all executed trades. Shows agent name, entry price, shares, and total value. This is your audit trail.',
    tip: 'Trades are color-coded: Green = BUY, Red = SELL',
    skipAction: true,  // Let user explore on their own
    position: 'left',
  },
];
```

---

## Page-by-Page Tour Breakdown

### Dashboard Tab (`DashboardTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Portfolio Value Card | Total account value, initial $100K paper balance |
| 2 | P&L Chart | Equity curve, how to read gains/losses over time |
| 3 | Cash Card | Available buying power, updates after trades |
| 4 | Holdings Table | Symbol, shares, avg price, current price, P&L% |
| 5 | Trade History | Real-time trade log, agent attribution |
| 6 | Risk Widget | Circuit breaker status, trading halt controls |
| 7 | Add Stock Button | Manual position entry (for testing) |

### Agents Tab (`AgentsTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Agent Cards | 4 agents: Director, Quant, Risk, Execution |
| 2 | Status Indicators | Running (green), Stopped (gray), Error (red) |
| 3 | Latency Badge | Response time from NVIDIA NIM API |
| 4 | Success Rate | Historical win rate per agent |
| 5 | Start/Stop Buttons | Control individual agents |
| 6 | Agent Details Panel | Configuration, model selection, temperature, max tokens |
| 7 | Model Dropdown | Llama-3.2-3B (fast), Llama-3.3-70B (smart), Nemotron-120B (deep analysis) |
| 8 | Test Connection | Send ping to verify API key works |

### Signals Tab (`SignalsTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Signal Cards | BUY/SELL/HOLD recommendations with confidence % |
| 2 | Filters | Agent, Asset Type, Signal Type, Min Confidence |
| 3 | Execute Button | One-click trade execution from signal |
| 4 | Reason/Thesis | AI-generated explanation for why signal was generated |
| 5 | Watchlist Star | Save symbols for monitoring |
| 6 | Target/Stop Prices | Suggested exit points for risk management |
| 7 | Time Filter | Show signals from last 24h, 7d, 30d |

### Copy Trading Tab (`CopyTradeTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Leaderboard Table | Top traders by return, win rate, AUM |
| 2 | Follow Button | Start copying trader's positions automatically |
| 3 | Trader Profile Card | Detailed stats: total trades, copiers, strategy description |
| 4 | Copied Positions | Your active positions from copied trader |
| 5 | Unfollow Button | Stop copying and optionally close positions |
| 6 | Active Follows Count | How many traders you're currently copying |
| 7 | Filter/Search | Find traders by name, return %, asset type |

### Backtest Tab (`BacktestTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Strategy Form | Name, engine selection, date range, capital |
| 2 | Alpha Factors | Selected factors from Alpha Zoo |
| 3 | Run Backtest Button | Start historical simulation |
| 4 | Progress Bar | Real-time execution status |
| 5 | Results Heatmap | Monthly returns visualization |
| 6 | Performance Metrics | Sharpe, Sortino, Max Drawdown, Total Return |
| 7 | Equity Curve | Compare strategy vs benchmark (SPY) |
| 8 | Save Strategy | Store configuration for reuse |

### Alpha Zoo Tab (`AlphaZooTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Search Bar | Find factors by name, category, formula type |
| 2 | Category Filters | Momentum, Mean-Reversion, Volume, Volatility |
| 3 | Difficulty Badge | Basic, Intermediate, Advanced complexity |
| 4 | Win Rate | Historical accuracy percentage |
| 5 | Sharpe Ratio | Risk-adjusted return metric |
| 6 | Formula Preview | Click to see mathematical formula |
| 7 | Code Snippet | Python implementation for custom use |
| 8 | Add to Strategy | Star factor to use in backtests |

### Portfolio Tab (`PortfolioTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | Allocation Chart | Donut/treemap view of portfolio weights |
| 2 | Cash Balance | Liquid capital available for trading |
| 3 | Position Cards | Each holding with entry price, current price, P&L |
| 4 | Sync Broker | Pull live positions from Alpaca/Binance |
| 5 | Export CSV | Download trade history for tax/accounting |
| 6 | Withdraw Button | Initiate real withdrawal (50% daily profit rule) |
| 7 | Rebalance Tool | Adjust allocation percentages |

### Settings Tab (`SettingsTab.tsx`)

| Step | Element | What to Explain |
|------|---------|-----------------|
| 1 | API Keys Section | NVIDIA NIM, Alpaca, Binance configuration |
| 2 | Exness Integration | MT5 broker connection for live trading |
| 3 | Trading Caps | Daily loss limits, position size limits |
| 4 | Payout Settings | 50% daily profit auto-withdrawal rule |
| 5 | Notifications | WhatsApp, Discord, Slack, Email webhooks |
| 6 | Market Data | Polygon, TwelveData, Yahoo Finance sources |
| 7 | Device Fingerprint | Persistent settings across app updates |
| 8 | Save/Reset | Apply changes or restore defaults |

---

## User Flow

### First-Time Experience

1. **Welcome Modal** (after landing on dashboard)
   - "Welcome to Jasper Trades! Would you like a quick tour?"
   - Options: [Start Tour] [Skip, I'll Explore]

2. **Tour Progress Tracking**
   - Store completed steps in localStorage
   - Allow resuming where user left off
   - Track which pages user has completed

3. **Completion Reward**
   - After finishing all 8 tabs: show badge/confetti
   - "You're ready to trade! Here's what to do next..."
   - Suggested next action: Configure API keys → Start paper trading

### Returning User Experience

1. **Tooltip Hints** (if tour was skipped/incomplete)
   - Small pulsing dot on unexplored features
   - Click to see mini-explanation (not full tour)

2. **Help Command**
   - Press `?` key anytime to see keyboard shortcuts
   - "Restart Tour" option in settings

---

## Implementation Checklist

### Phase 1: Core Infrastructure (2-3 days)
- [ ] Create `useOnboardingEngine.ts` hook with element scanning
- [ ] Build `OnboardingProvider` context for state management
- [ ] Implement `TourOverlay.tsx` with non-blocking spotlight
- [ ] Create `InteractiveTooltip.tsx` with action buttons
- [ ] Add `data-onboarding` attributes to all target elements in page.tsx

### Phase 2: Tour Definitions (2-3 days)
- [ ] Write `dashboard-tour.ts` (7 steps)
- [ ] Write `agents-tour.ts` (8 steps)
- [ ] Write `signals-tour.ts` (7 steps)
- [ ] Write `copytrade-tour.ts` (7 steps)
- [ ] Write `backtest-tour.ts` (8 steps)
- [ ] Write `alphazoo-tour.ts` (8 steps)
- [ ] Write `portfolio-tour.ts` (7 steps)
- [ ] Write `settings-tour.ts` (8 steps)

### Phase 3: Integration & Testing (1-2 days)
- [ ] Add tour启动 button to each tab's header
- [ ] Test spotlight positioning on all screen sizes
- [ ] Verify buttons are clickable during tour
- [ ] Add keyboard shortcuts (ESC to close, ←/→ to navigate)
- [ ] Test with real data from backend
- [ ] Add progress persistence to localStorage

### Phase 4: Polish (1 day)
- [ ] Add smooth animations (Framer Motion)
- [ ] Add sound effects (optional, muted by default)
- [ ] Create completion badge/confetti
- [ ] Add "Skip Tour" to settings
- [ ] Write help documentation

**Total Estimated Time:** 6-9 days

---

## Code Placement Guide

### Where to Add `data-onboarding` Attributes

**Example: DashboardTab.tsx**
```tsx
// Portfolio Value Card
<div 
  data-onboarding="portfolio-value"
  className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]"
>
  {/* existing content */}
</div>

// P&L Chart
<div 
  data-onboarding="pnl-chart"
  className="bg-[#1E293B] rounded-lg p-6 border border-[#475569]"
>
  {/* existing chart */}
</div>
```

**Example: AgentsTab.tsx**
```tsx
// Agent Card
<div 
  data-onboarding={`agent-${agent.id}`}
  key={agent.id}
  className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]"
>
  {/* agent status, latency, etc */}
</div>
```

### Integration in page.tsx

```tsx
import { OnboardingProvider } from '@/components/onboarding/OnboardingProvider';
import OnboardingTour from '@/components/onboarding/OnboardingTour';

export default function DashboardPage() {
  return (
    <OnboardingProvider>
      <div className="flex min-h-screen bg-[#0B1120]">
        {/* sidebar, content, etc */}
        
        {/* Tour component at root level */}
        <OnboardingTour activePage={activeTab} />
      </div>
    </OnboardingProvider>
  );
}
```

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Tour Completion Rate | > 70% | Track users who finish all 8 tabs |
| Time to First Trade | < 5 minutes | From landing page to executed trade |
| Feature Discovery | > 80% | Users find 5+ features in first session |
| Support Tickets | -50% | Reduce "how do I..." questions |
| User Retention (D7) | > 60% | Users return after 7 days |

---

## Files to Create

1. `frontend/components/onboarding/OnboardingProvider.tsx`
2. `frontend/components/onboarding/useOnboardingEngine.ts`
3. `frontend/components/onboarding/TourOverlay.tsx`
4. `frontend/components/onboarding/InteractiveTooltip.tsx`
5. `frontend/components/onboarding/OnboardingTour.tsx`
6. `frontend/components/onboarding/tours/dashboard-tour.ts`
7. `frontend/components/onboarding/tours/agents-tour.ts`
8. `frontend/components/onboarding/tours/signals-tour.ts`
9. `frontend/components/onboarding/tours/copytrade-tour.ts`
10. `frontend/components/onboarding/tours/backtest-tour.ts`
11. `frontend/components/onboarding/tours/alphazoo-tour.ts`
12. `frontend/components/onboarding/tours/portfolio-tour.ts`
13. `frontend/components/onboarding/tours/settings-tour.ts`

**Total:** 13 new files

---

## Next Steps

1. **Approve this plan** - Confirm scope and approach
2. **Create infrastructure files** - OnboardingProvider, engine, overlay, tooltip
3. **Write tour definitions** - Start with dashboard, then iterate
4. **Add data-onboarding attributes** - Instrument all pages
5. **Test extensively** - Ensure positioning, clicks, and flow work
6. **Polish & ship** - Animations, sounds, docs

**Key Difference from Previous Attempt:**
- Element targeting uses `data-onboarding` attributes (robust)
- Overlay uses `pointer-events: none` except tooltip (non-blocking)
- Tooltips have real actions (not just static text)
- Tours are page-specific with contextual explanations