---
name: onboarding-tour-cancel-persistence
description: Onboarding tutorial system that persists completion/cancellation state to localStorage - tours auto-start on page navigation when incomplete
source: auto-skill
extracted_at: '2026-06-11T00:05:00.000Z'
---

# Onboarding Tour Cancel & Persistence System

## Problem Solved

Users navigating between app pages would see the same tours repeatedly because:
1. ESC key just closed the tour without saving state
2. No distinction between "completed" vs "cancelled" tours
3. Tours didn't auto-start when switching to new pages
4. No way to reset tour progress for returning users

## Solution Approach

Enhanced the onboarding system to:
- Persist tour state to localStorage on any exit action (complete, cancel, ESC)
- Auto-start tours when navigating to pages with incomplete tours
- Add confirmation before stopping mid-tour
- Provide settings UI to reset all tour progress

## Implementation

### 1. Enhanced Tour Engine (`components/onboarding/useOnboardingEngine.ts`)

**Added resetTours function:**
```typescript
const resetTours = useCallback(() => {
  setCompletedTours([]);
  try {
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}completed_tours`);
  } catch (error) {
    console.error('Failed to reset onboarding state:', error);
  }
}, []);

return {
  // ...existing
  resetTours,
  totalSteps: tourSteps.length,
};
```

**Storage key format:**
```typescript
const STORAGE_KEY_PREFIX = 'jasper_onboarding_';
// Stored: localStorage['jasper_onboarding_completed_tours'] = ["dashboard", "settings"]
```

### 2. Updated Tour Overlay (`components/onboarding/OnboardingTour.tsx`)

**Auto-start tours on page navigation:**
```typescript
useEffect(() => {
  if (!enabled || isTourActive) return;
  
  const tourKey = activePage.toLowerCase();
  const tourSteps = TOUR_MAP[tourKey];
  
  // Auto-start if tour exists and is incomplete
  if (tourSteps && !isTourComplete(tourKey)) {
    const timer = setTimeout(() => {
      startTour(tourSteps);
    }, 300);
    return () => clearTimeout(timer);
  }
}, [activePage, enabled, isTourActive, isTourComplete, startTour]);
```

**ESC key saves state before closing:**
```typescript
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (!isTourActive && e.key === 'Escape') {
      e.preventDefault();
      markTourComplete(currentTourKey); // Save state first
      endTour();
    }
  };
  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [isTourActive, endTour, markTourComplete, currentTourKey]);
```

### 3. Interactive Tooltip with Confirmation (`components/onboarding/InteractiveTooltip.tsx`)

**Added cancel confirmation dialog:**
```typescript
const [showCancelConfirm, setShowCancelConfirm] = useState(false);

// Show confirmation instead of immediate close
if (showCancelConfirm) {
  return (
    <div className="fixed z-[9999] ...">
      <h3>Stop this tour?</h3>
      <p>You can restart it anytime from the Help menu.</p>
      <div className="flex gap-2">
        <button onClick={() => setShowCancelConfirm(false)}>Continue</button>
        <button onClick={handleCancelTour}>Stop Tour</button>
      </div>
    </div>
  );
}
```

**Handle tour cancellation:**
```typescript
const handleCancelTour = () => {
  const tourKey = getTourKeyFromPath();
  markTourComplete(tourKey); // Persist state
  endTour();
};
```

**Show Finish button on last step:**
```typescript
const isLastStep = currentStepIndex === totalSteps;

{isLastStep ? (
  <button onClick={handleFinishTour} className="bg-[#10B981]">
    ✓ Finish Tour
  </button>
) : (
  <button onClick={nextStep}>Next →</button>
)}
```

### 4. Settings Page Reset Button (`components/SettingsTab.tsx`)

**Added reset tours button:**
```typescript
import { useOnboarding } from '@/components/onboarding/OnboardingProvider';
import { Plane } from 'lucide-react';

const { resetTours } = useOnboarding();

<button
  onClick={() => {
    resetTours();
    triggerToast('success', 'Tours Reset', 'Onboarding tours will show again');
  }}
  className="px-4 py-2 border border-[#475569] ..."
>
  <Plane className="w-4 h-4" /> Reset Onboarding Tours
</button>
```

### 5. Updated Provider Context (`components/onboarding/OnboardingProvider.tsx`)

**Added resetTours to context type:**
```typescript
interface OnboardingContextType {
  // ...existing
  resetTours: () => void;
  totalSteps: number;
}
```

## User Flow

```
First-time user → Visits Dashboard
    ↓
Tour auto-starts (not marked complete)
    ↓
User presses ESC → "Stop this tour?" confirmation
    ↓
Clicks "Stop Tour" → Marked complete in localStorage
    ↓
User navigates to Settings → Settings tour auto-starts
    ↓
User completes all steps → Clicks "Finish Tour" → Saved
    ↓
User reloads app → No tours (all marked complete)
    ↓
User wants tours again → Settings → "Reset Onboarding Tours"
```

## Key Learnings

1. **ESC key must persist state**: Don't just close - save to localStorage first
2. **Confirmation prevents accidental cancels**: Users might press ESC reflexively
3. **Auto-start on navigation**: Each page's tour triggers independently
4. **Finish button on last step**: Clear call-to-action vs ambiguous "Next"
5. **Reset functionality**: Power users may want to see tours again
6. **localStorage is sufficient**: No backend storage needed for UI state

## Storage Format

```javascript
localStorage.setItem('jasper_onboarding_completed_tours', JSON.stringify([
  "dashboard",
  "settings",
  "portfolio"
]));
```

**Check if complete:**
```javascript
const completed = JSON.parse(localStorage.getItem('jasper_onboarding_completed_tours') || '[]');
const isComplete = completed.includes(tourKey); // true/false
```

## When to Use This Pattern

- ✅ Multi-page apps with page-specific tutorials
- ✅ Users should see each tour once (not every visit)
- ✅ Need distinction between "completed" vs "skipped"
- ✅ Want tours to auto-start on relevant pages
- ✅ Users need ability to reset and replay tours

**Don't use for:**
- ❌ Tours that should show every session
- ❌ Complex multi-step wizards requiring backend state
- ❌ Accessibility-critical onboarding (need ARIA announcements)