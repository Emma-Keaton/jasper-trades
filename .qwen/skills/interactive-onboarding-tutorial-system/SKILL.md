---
name: interactive-onboarding-tutorial-system
description: Building a non-blocking, interactive onboarding tour system with element highlighting, actionable tooltips, progress persistence, and auto-start on navigation for complex trading dashboards
source: auto-skill
extracted_at: '2026-06-10T22:07:13.543Z'
---

# Interactive Onboarding Tutorial System

## Problem Statement

Previous onboarding implementations failed because:
1. **Overlay blocked clicks** - Z-index/pointer-events issues prevented user interaction with highlighted elements
2. **Positioning was unreliable** - Elements moved or resized, breaking spotlight alignment
3. **Static tooltips** - Text-only explanations with no interactive actions
4. **No progress tracking** - Users couldn't resume tours or skip completed sections

## Solution Architecture

### Core Design Principles

1. **Non-blocking overlays** - Users can interact with UI during tour
2. **ResizeObserver tracking** - Spotlight stays aligned when elements move
3. **Actionable tooltips** - Buttons trigger real interactions, not just navigation
4. **Progressive disclosure** - Page-by-page tours with localStorage persistence
5. **Keyboard navigation** - ESC to close, arrow keys to navigate
6. **Auto-start on navigation** - Tours begin automatically when switching tabs (unless cancelled)

### File Structure

```
components/onboarding/
├── useOnboardingEngine.ts      # Core hook with ResizeObserver
├── OnboardingProvider.tsx      # Context for global state
├── TourOverlay.tsx             # Spotlight mask (pointer-events: none)
├── InteractiveTooltip.tsx      # Clickable tooltips with actions
├── OnboardingTour.tsx          # Main coordinator
└── tours/
    ├── dashboard-tour.ts
    ├── agents-tour.ts
    ├── signals-tour.ts
    ├── copytrade-tour.ts
    ├── backtest-tour.ts
    ├── alphazoo-tour.ts
    ├── portfolio-tour.ts
    └── settings-tour.ts
```

## Implementation Steps

### Step 1: Element Targeting with data-onboarding Attributes

Add `data-onboarding` attributes to target elements instead of relying on fragile CSS selectors:

```tsx
// DashboardTab.tsx
<div 
  data-onboarding="portfolio-value"
  className="bg-[#1E293B] border border-[#475569] p-4 rounded-xl"
>
  {/* Portfolio value content */}
</div>
```

**Why this works:** Attributes are semantic, don't break with styling changes, and are easy to scan for.

### Step 2: useOnboardingEngine Hook

Core hook that scans DOM and tracks element positions:

```typescript
function useOnboardingEngine() {
  const [tourSteps, setTourSteps] = useState<TourStep[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState(-1);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Scan DOM for all data-onboarding elements
  const scanElements = useCallback(() => {
    const elements = tourSteps.map(step => ({
      id: step.id,
      selector: `[data-onboarding="${step.id}"]`,
      element: document.querySelector(selector) as HTMLElement,
      rect: element?.getBoundingClientRect() || null,
    }));
    setTargetElements(elements);
  }, [tourSteps]);

  // Watch for resize/reposition
  useEffect(() => {
    const observer = new ResizeObserver(() => scanElements());
    targetElements.forEach(t => t.element && observer.observe(t.element));
    return () => observer.disconnect();
  }, [targetElements, scanElements]);

  return { currentStep, targetElement, startTour, nextStep, prevStep, endTour };
}
```

**Key insight:** ResizeObserver automatically updates spotlight position when elements move (e.g., sidebar collapses, window resizes).

### Step 3: Non-Blocking Overlay

TourOverlay uses SVG mask with spotlight cutout and `pointer-events: none`:

```tsx
<div className="fixed inset-0 z-[9998]" style={{ pointerEvents: 'none' }}>
  <svg>
    <mask id="spotlight-mask">
      <rect width="100%" height="100%" fill="white" />
      <rect x={left} y={top} width={w} height={h} fill="black" />
    </mask>
    <rect fill="rgba(0,0,0,0.7)" mask="url(#spotlight-mask)" />
  </svg>
  
  {/* Highlight border (also pointer-events: none) */}
  <div 
    className="absolute border-2 border-[#3B82F6] rounded-lg"
    style={{ pointerEvents: 'none' }}
  />
</div>
```

**Critical:** The overlay container has `pointer-events: none`, allowing clicks to pass through to underlying buttons.

### Step 4: Interactive Tooltip

Tooltip sits on top with `pointer-events: auto` and includes action buttons:

```tsx
<div 
  className="fixed z-[9999]"
  style={{ pointerEvents: 'auto' }}
>
  <h3>{title}</h3>
  <p>{description}</p>
  
  {action && !skipAction && (
    <button onClick={action.onClick}>
      {action.icon} {action.label}
    </button>
  )}
  
  {skipAction && (
    <div>👉 Try this yourself, then click "Next"</div>
  )}
  
  <button onClick={prevStep}>← Back</button>
  <button onClick={nextStep}>Next →</button>
</div>
```

**Action examples:**
- "Try Adding a Stock" → clicks the real Add Stock button
- "Follow a Trader" → triggers the real Follow action
- "Star a Symbol" → toggles watchlist star

### Step 5: Tour Definitions (Per Page)

Each tab gets its own tour definition file:

```typescript
// tours/dashboard-tour.ts
export const dashboardTour: TourStep[] = [
  {
    id: 'portfolio-value',
    targetElement: '[data-onboarding="portfolio-value"]',
    title: 'Total Portfolio Value',
    description: 'Shows your total account value including cash and holdings.',
    tip: 'Click any card to see detailed breakdown',
    position: 'bottom',
  },
  {
    id: 'pnl-chart',
    targetElement: '[data-onboarding="pnl-chart"]',
    title: 'Profit & Loss Chart',
    description: 'Visual track of performance over time.',
    tip: 'Change timeframe to zoom into periods',
    position: 'top',
  },
  // ... more steps
];
```

**Tour metadata:**
- `position`: 'top' | 'bottom' | 'left' | 'right' (tooltip placement relative to element)
- `skipAction`: true for "try it yourself" steps
- `action`: optional clickable action with real onClick handler

### Step 6: Progress Persistence & Completion Tracking

Store completed tours in localStorage with confirmation dialogs and reset functionality:

```typescript
const STORAGE_KEY_PREFIX = 'jasper_onboarding_';

function markTourComplete(tourId: string) {
  const completed = JSON.parse(
    localStorage.getItem(`${STORAGE_KEY_PREFIX}completed_tours`) || '[]'
  );
  if (!completed.includes(tourId)) {
    completed.push(tourId);
    localStorage.setItem(`${STORAGE_KEY_PREFIX}completed_tours`, JSON.stringify(completed));
  }
}

function isTourComplete(tourId: string): boolean {
  const completed = JSON.parse(
    localStorage.getItem(`${STORAGE_KEY_PREFIX}completed_tours`) || '[]'
  );
  return completed.includes(tourId);
}

function resetTours() {
  localStorage.removeItem(`${STORAGE_KEY_PREFIX}completed_tours`);
  setCompletedTours([]);
}
```

**InteractiveTooltip.tsx - Cancellation Flow:**

```typescript
const [showCancelConfirm, setShowCancelConfirm] = useState(false);

// Handle tour cancellation (ESC or Stop button)
const handleCancelTour = () => {
  const tourKey = getTourKeyFromPath();
  // Mark as complete so it doesn't show again on reload
  markTourComplete(tourKey);
  endTour();
};

// Show confirmation dialog
if (showCancelConfirm) {
  return (
    <div className="fixed z-[9999] bg-[#1E293B] border border-[#475569] rounded-xl p-4">
      <h3 className="text-lg font-bold text-white mb-2">Stop this tour?</h3>
      <p className="text-sm text-[#94A3B8] mb-4">
        You can restart it anytime from the Help menu.
      </p>
      <div className="flex gap-2">
        <button onClick={() => setShowCancelConfirm(false)} className="...">
          Continue
        </button>
        <button onClick={handleCancelTour} className="bg-[#EF4444] ...">
          Stop Tour
        </button>
      </div>
    </div>
  );
}
```

**Finish Tour Button (Last Step):**

```typescript
const isLastStep = currentStepIndex === totalSteps;

{isLastStep ? (
  <button
    onClick={handleFinishTour}
    className="bg-[#10B981] hover:bg-[#059669] text-white px-4 py-1.5 rounded-lg"
  >
    ✓ Finish Tour
  </button>
) : (
  <button onClick={nextStep}>Next →</button>
)}
```

**Behavior:**
- First-time users see welcome modal: "Would you like a tour?"
- ESC key or Stop button → Confirmation → Marks complete → Persists to localStorage
- Finish button (last step only) → Marks complete → Persists to localStorage
- Completed tours are skipped on future visits
- Users can restart tours from Settings

### Step 7: Integration in page.tsx

Wrap app with OnboardingProvider and render OnboardingTour:

```tsx
import { OnboardingProvider } from '@/components/onboarding/OnboardingProvider';
import OnboardingTour from '@/components/onboarding/OnboardingTour';

export default function DashboardPage() {
  return (
    <OnboardingProvider>
      <div className="min-h-screen">
        {/* App content */}
        <OnboardingTour activePage={activeTab} enabled={true} />
      </div>
    </OnboardingProvider>
  );
}
```

**OnboardingTour.tsx - Tour Mapping and Auto-Start:**

```typescript
const TOUR_MAP: { [key: string]: TourStep[] } = {
  dashboard: dashboardTour,
  agents: agentsTour,
  signals: signalsTour,
  copytrading: copyTradeTour,
  backtest: backtestTour,
  alphazoo: alphaZooTour,
  portfolio: portfolioTour,
  settings: settingsTour,
};

// Map route paths to tour keys
const PATH_TO_TOUR_KEY: { [key: string]: string } = {
  '': 'dashboard',
  'dashboard': 'dashboard',
  'agents': 'agents',
  'signals': 'signals',
  'copytrading': 'copytrading',
  'backtest': 'backtest',
  'alphazoo': 'alphazoo',
  'portfolio': 'portfolio',
  'settings': 'settings',
};

// Auto-start tour when page changes (if not completed)
useEffect(() => {
  if (!enabled || isTourActive) return;

  const tourKey = activePage.toLowerCase();
  const tourSteps = TOUR_MAP[tourKey];

  // Auto-start if tour exists and hasn't been completed/cancelled
  if (tourSteps && !isTourComplete(tourKey)) {
    const timer = setTimeout(() => {
      startTour(tourSteps);
    }, 300);
    return () => clearTimeout(timer);
  }
}, [activePage, enabled, isTourActive, isTourComplete, startTour]);
```

**Key behavior:** When user navigates between tabs, the tour for that page automatically starts (if not previously completed). This provides contextual onboarding without requiring users to manually trigger tours.

### Step 8: Keyboard Shortcuts & Tour Cancellation

ESC closes tour with confirmation and marks it complete, arrow keys navigate:

```typescript
// OnboardingTour.tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (!isTourActive) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      // Mark tour as complete so it doesn't show again
      markTourComplete(currentTourKey);
      endTour();
    }
  };
  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [isTourActive, endTour, markTourComplete, currentTourKey]);
```

**User flow:**
1. Press ESC → Shows confirmation dialog: "Stop this tour?"
2. Click "Stop Tour" → Marks tour complete in localStorage → Closes tour
3. Click "Continue" → Dismisses dialog, tour continues

**Persistence behavior:**
- Both "Stop" and "Finish" mark the tour as complete
- Completed tours are skipped on reload/app relaunch
- Users can restart tours from Help/Settings menu if desired

## Why This Works

### Previous Failure Points → Solutions

| Problem | Solution |
|---------|----------|
| Overlay blocked clicks | `pointer-events: none` on mask, `auto` only on tooltip |
| Positioning broken on resize | ResizeObserver tracks element position changes |
| Fragile CSS selectors | `data-onboarding` attributes are semantic and stable |
| Static text tooltips | Action buttons trigger real interactions |
| No progress memory | localStorage tracks completed tours |
| One-size-fits-all tour | Per-page tours with contextual explanations |

### Key Technical Decisions

1. **SVG mask for spotlight** - Hardware accelerated, smooth performance even with many elements
2. **ResizeObserver over MutationObserver** - Only tracks size/position changes, not DOM mutations (more efficient)
3. **Context provider pattern** - Global state accessible from any component without prop drilling
4. **Action callbacks** - Tooltips can trigger any function, not just tour navigation
5. **1-indexed display** - User sees "Step 3 of 8" instead of "Step 2 of 8" (currentStepIndex + 1)

## Testing Checklist

- [ ] Spotlight aligns with target element on initial load
- [ ] Spotlight follows element when window resizes
- [ ] Can click buttons underneath spotlight (non-blocking)
- [ ] Tooltip actions trigger real functions
- [ ] ESC key shows confirmation dialog
- [ ] "Stop Tour" marks tour complete in localStorage
- [ ] "Continue" dismisses dialog and resumes tour
- [ ] "Finish Tour" button appears on last step (green)
- [ ] Progress persists after page refresh
- [ ] Completed tours are skipped on return visits
- [ ] Welcome modal shows only for first-time users
- [ ] Tours work on mobile (responsive positioning)
- [ ] localStorage key is `jasper_onboarding_completed_tours`

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Tour completion rate | > 70% | Users finishing all steps in a tour |
| Time to first trade | < 5 min | From landing to executed trade |
| Feature discovery | > 80% | Users finding 5+ features in first session |
| Support tickets | -50% | Reduction in "how do I..." questions |
| D7 retention | > 60% | Users returning after 7 days |

## Common Pitfalls

1. **Forgetting pointer-events** - Tooltip must have `pointer-events: auto`, overlay must have `none`
2. **Not waiting for DOM** - Use `setTimeout(() => scanElements(), 100)` after starting tour
3. **Hardcoded positions** - Always calculate tooltip position from `targetRect`, don't hardcode
4. **Missing boundary checks** - Keep tooltip in viewport with min/max left/top calculations
5. **Not clearing observer** - Disconnect ResizeObserver in cleanup to prevent memory leaks
6. **Batch file modifications** - Avoid using PowerShell regex replacement for adding attributes across multiple files; it corrupts content. Use read_file + write_file for each file individually
7. **Corrupted file recovery** - Always use `git checkout -- <file>` to restore corrupted files before attempting edits
8. **Not marking tours complete on ESC** - ESC should call `markTourComplete()` before `endTour()` to persist state
9. **Wrong tour key** - Use `PATH_TO_TOUR_KEY` mapping to get correct tour ID from route path

## Critical Implementation Note: File Modification Safety

**Problem:** When adding `data-onboarding` attributes to multiple tab components, using PowerShell batch regex replacement corrupted files (especially PortfolioTab.tsx) by injecting replacement text throughout the entire file.

**Solution:** 
1. Read each file completely with `read_file`
2. Use targeted `edit`With explicit old_string/new_string pairs
3. If file gets corrupted, immediately restore with: `git checkout -- <filepath>`
4. For large rewrites, use `write_file` with the complete updated content

**Example of safe approach:**
```bash
# Restore corrupted files first
git checkout -- frontend/components/PortfolioTab.tsx

# Then edit one file at a time
read_file PortfolioTab.tsx
edit with explicit context (3+ lines before/after)
```

## Extension Points

- **Multi-language support** - Store tour definitions as i18n keys
- **Video walkthroughs** - Add `videoUrl` field to TourStep for embedded tutorials
- **Achievement badges** - Reward users for completing tours with gamification
- **A/B testing** - Track which tour variations lead to better retention
- **Analytics events** - Fire `tour_step_viewed`, `tour_action_clicked`, `tour_completed` events