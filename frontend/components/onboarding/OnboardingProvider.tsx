'use client';

import type { ReactNode } from 'react';
import React, { createContext, useContext } from 'react';
import type { TourStep } from './useOnboardingEngine';
import { useOnboardingEngine } from './useOnboardingEngine';

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

  // Sync showWelcome with engine state without an effect
  const [prevLoaded, setPrevLoaded] = React.useState(engine.isLoaded);
  const [prevWelcomeDone, setPrevWelcomeDone] = React.useState(engine.welcomeDone);
  if (engine.isLoaded !== prevLoaded || engine.welcomeDone !== prevWelcomeDone) {
    setPrevLoaded(engine.isLoaded);
    setPrevWelcomeDone(engine.welcomeDone);
    setShowWelcome(engine.isLoaded && !engine.welcomeDone);
  }

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