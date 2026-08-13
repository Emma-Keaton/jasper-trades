'use client';

import React, { createContext, useContext, ReactNode } from 'react';
import { useOnboardingEngine, TourStep } from './useOnboardingEngine';
import { loadOnboardingPrefs } from '@/lib/preferences';

interface OnboardingContextType {
  currentStepIndex: number;
  currentStep: TourStep | null;
  targetElement: {
    id: string;
    selector: string;
    element: HTMLElement | null;
    rect: DOMRect | null;
  } | null;
  goToStep: (index: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  startTour: (steps: TourStep[]) => void;
  endTour: () => void;
  scanElements: () => void;
  isTourActive: boolean;
  completedTours: string[];
  markTourComplete: (tourId: string) => void;
  isTourComplete: (tourId: string) => boolean;
  onboardingCompleted: boolean;
  completeOnboarding: () => void;
  isOnboardingComplete: () => boolean;
  showWelcome: boolean;
  setShowWelcome: (show: boolean) => void;
  totalSteps: number;
  resetTours: () => void;
}

const OnboardingContext = createContext<OnboardingContextType | undefined>(undefined);

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const engine = useOnboardingEngine();

  // Initial hidden if the welcome was already dismissed or onboarding completed once
  const [showWelcome, setShowWelcome] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    loadOnboardingPrefs().then((prefs) => {
      if (cancelled) return;
      const completed = prefs.onboarding_completed === true;
      const dismissed = prefs.welcome_done === true;
      setShowWelcome(!completed && !dismissed);
    }).catch(() => {
      setShowWelcome(true);
    });
    return () => { cancelled = true; };
  }, []);

  const value = {
    ...engine,
    showWelcome,
    setShowWelcome,
  };

  return (
    <OnboardingContext.Provider value={value}>
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const context = useContext(OnboardingContext);
  if (context === undefined) {
    throw new Error('useOnboarding must be used within OnboardingProvider');
  }
  return context;
}