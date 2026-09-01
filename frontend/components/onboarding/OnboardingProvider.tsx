'use client';

import React, { createContext, useContext, ReactNode } from 'react';
import { useOnboardingEngine, TourStep } from './useOnboardingEngine';

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
  isLoaded: boolean;
  completedTours: string[];
  markTourComplete: (tourId: string) => void;
  isTourComplete: (tourId: string) => boolean;
  onboardingCompleted: boolean;
  welcomeDone: boolean;
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

  // Derive showWelcome from engine state — avoid a duplicate DB load
  const [showWelcome, setShowWelcome] = React.useState(false);

  React.useEffect(() => {
    if (!engine.isLoaded) return;
    // Show welcome only if welcome hasn't been dismissed yet
    setShowWelcome(!engine.welcomeDone);
  }, [engine.isLoaded, engine.welcomeDone]);

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