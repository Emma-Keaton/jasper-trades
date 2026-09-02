'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { loadOnboardingPrefs, saveOnboardingPrefs, resetOnboarding } from '@/lib/preferences';

const ONBOARDING_STORAGE_KEY = 'jasper_onboarding_state';

function loadLocalOnboarding(): { completed_tours: string[]; onboarding_completed: boolean; welcome_done: boolean } {
  try {
    const raw = localStorage.getItem(ONBOARDING_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { completed_tours: [], onboarding_completed: false, welcome_done: false };
}

function saveLocalOnboarding(data: { completed_tours: string[]; onboarding_completed: boolean; welcome_done: boolean }) {
  try { localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(data)); } catch { /* ignore */ }
}

export interface TourStep {
  id: string;
  targetElement: string; // CSS selector or data-onboarding attribute
  title: string;
  description: string;
  tip?: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  skipAction?: boolean;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export interface TargetElementInfo {
  id: string;
  selector: string;
  element: HTMLElement | null;
  rect: DOMRect | null;
}

interface UseOnboardingEngineReturn {
  currentStepIndex: number;
  currentStep: TourStep | null;
  targetElement: TargetElementInfo | null;
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
  resetTours: () => void;
  totalSteps: number;
}

export function useOnboardingEngine(): UseOnboardingEngineReturn {
  const [tourSteps, setTourSteps] = useState<TourStep[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(-1);
  const [targetElements, setTargetElements] = useState<TargetElementInfo[]>([]);
  const [completedTours, setCompletedTours] = useState<string[]>([]);
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean>(false);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const [welcomeDone, setWelcomeDone] = useState<boolean>(false);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Load completed tours from the DB (per device) with localStorage fallback
  useEffect(() => {
    let cancelled = false;

    // Immediately load from localStorage so tours don't flash on refresh
    const local = loadLocalOnboarding();
    if (local.completed_tours.length > 0) {
      setCompletedTours(local.completed_tours);
    }
    if (local.onboarding_completed) {
      setOnboardingCompleted(true);
    }
    if (local.welcome_done) {
      setWelcomeDone(true);
    }

    // Then sync from backend (may override with more recent data)
    loadOnboardingPrefs().then((prefs) => {
      if (cancelled) return;
      const tours = Array.isArray(prefs.completed_tours) ? (prefs.completed_tours as string[]) : local.completed_tours;
      const completed = prefs.onboarding_completed === true || local.onboarding_completed;
      const welcomeDone = prefs.welcome_done === true || local.welcome_done;
      setCompletedTours(tours);
      setOnboardingCompleted(completed);
      setWelcomeDone(welcomeDone);
      saveLocalOnboarding({ completed_tours: tours, onboarding_completed: completed, welcome_done: welcomeDone });
      setIsLoaded(true);
    }).catch((error) => {
      console.error('Failed to load onboarding state:', error);
      setIsLoaded(true);
    });
    return () => { cancelled = true; };
  }, []);

  // Scan DOM for target elements
  const scanElements = useCallback(() => {
    if (tourSteps.length === 0) return;

    const elements = tourSteps.map((step) => {
      // Support both data-onboarding attributes and regular CSS selectors
      let selector = step.targetElement;
      if (step.targetElement.startsWith('[data-onboarding="')) {
        selector = step.targetElement;
      } else if (!step.targetElement.startsWith('[data-onboarding=')) {
        // Try data-onboarding first, then fall back to regular selector
        selector = `[data-onboarding="${step.id}"]`;
      }
      
      const element = document.querySelector(selector) as HTMLElement;
      return {
        id: step.id,
        selector,
        element,
        rect: element?.getBoundingClientRect() || null,
      };
    });

    setTargetElements(elements);
  }, [tourSteps]);

  // Set up ResizeObserver to track element position changes
  // Decouple rect updates from element list to avoid infinite re-subscribe loop
  const [targetRects, setTargetRects] = useState<Record<string, DOMRect | null>>({});
  const targetElementsRef = useRef(targetElements);
  targetElementsRef.current = targetElements;

  const updateRects = useCallback(() => {
    const rects: Record<string, DOMRect | null> = {};
    for (const t of targetElementsRef.current) {
      rects[t.id] = t.element?.getBoundingClientRect() || null;
    }
    setTargetRects(rects);
  }, []);

  const updateRectsRef = useRef(updateRects);
  updateRectsRef.current = updateRects;

  useEffect(() => {
    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect();
    }

    resizeObserverRef.current = new ResizeObserver(() => {
      updateRectsRef.current();
    });

    targetElements.forEach((target) => {
      if (target.element) {
        resizeObserverRef.current?.observe(target.element);
      }
    });

    // Initial scan
    updateRectsRef.current();

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, [targetElements]);

  // Get current step
  const currentStep = currentStepIndex >= 0 && currentStepIndex < tourSteps.length
    ? tourSteps[currentStepIndex]
    : null;

  // Get current target element info (merges live rect from ResizeObserver)
  const currentTargetElement = currentStep
    ? (() => {
        const base = targetElements.find((t) => t.id === currentStep.id);
        if (!base) return null;
        return { ...base, rect: targetRects[base.id] ?? base.rect };
      })()
    : null;

  // Start tour
  const startTour = useCallback((steps: TourStep[]) => {
    setTourSteps(steps);
    setCurrentStepIndex(0);
  }, []);

  // Scan elements whenever tourSteps change (replaces stale setTimeout)
  useEffect(() => {
    if (tourSteps.length > 0) {
      const t = setTimeout(() => scanElements(), 50);
      return () => clearTimeout(t);
    }
  }, [tourSteps, scanElements]);

  // Go to specific step
  const goToStep = useCallback((index: number) => {
    if (index >= 0 && index < tourSteps.length) {
      setCurrentStepIndex(index);
      setTimeout(() => scanElements(), 50);
    }
  }, [tourSteps.length, scanElements]);

  // Next step
  const nextStep = useCallback(() => {
    if (currentStepIndex < tourSteps.length - 1) {
      setCurrentStepIndex(prev => prev + 1);
      setTimeout(() => scanElements(), 50);
    }
  }, [currentStepIndex, tourSteps.length, scanElements]);

  // Previous step
  const prevStep = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(prev => prev - 1);
      setTimeout(() => scanElements(), 50);
    }
  }, [currentStepIndex, scanElements]);

  // End tour
  const endTour = useCallback(() => {
    setTourSteps([]);
    setCurrentStepIndex(-1);
    setTargetElements([]);
  }, []);

  // Mark tour as complete
  const markTourComplete = useCallback((tourId: string) => {
    setCompletedTours(prev => {
      if (!prev.includes(tourId)) {
        const updated = [...prev, tourId];
        const local = loadLocalOnboarding();
        saveLocalOnboarding({ completed_tours: updated, onboarding_completed: local.onboarding_completed, welcome_done: local.welcome_done });
        saveOnboardingPrefs({ completed_tours: updated }).catch((error) => {
          console.error('Failed to save onboarding state:', error);
        });
        return updated;
      }
      return prev;
    });
  }, []);

  // Check if tour is complete
  const isTourComplete = useCallback((tourId: string) => {
    return completedTours.includes(tourId);
  }, [completedTours]);

  // Flag the whole onboarding as completed once (persists across visits)
  const completeOnboarding = useCallback(() => {
    setOnboardingCompleted(true);
    setWelcomeDone(true);
    setCompletedTours((prev) => {
      saveLocalOnboarding({ completed_tours: prev, onboarding_completed: true, welcome_done: true });
      saveOnboardingPrefs({ onboarding_completed: true, welcome_done: true, completed_tours: prev }).catch((error) => {
        console.error('Failed to save onboarding state:', error);
      });
      return prev;
    });
  }, []);

  const isOnboardingComplete = useCallback(() => {
    return onboardingCompleted || welcomeDone;
  }, [onboardingCompleted, welcomeDone]);

  // Reset all tour progress (also clears the DB via the settings endpoint)
  const resetTours = useCallback(() => {
    setCompletedTours([]);
    setOnboardingCompleted(false);
    setWelcomeDone(false);
    saveLocalOnboarding({ completed_tours: [], onboarding_completed: false, welcome_done: false });
    saveOnboardingPrefs({ onboarding_completed: false, welcome_done: false, completed_tours: [] }).catch((error) => {
      console.error('Failed to reset onboarding state:', error);
    });
    resetOnboarding().catch(() => undefined);
  }, []);

  return {
    currentStepIndex: currentStepIndex + 1, // 1-indexed for display
    currentStep,
    targetElement: currentTargetElement,
    goToStep,
    nextStep,
    prevStep,
    startTour,
    endTour,
    scanElements,
    isTourActive: currentStepIndex >= 0 && currentStepIndex < tourSteps.length,
    isLoaded,
    completedTours,
    markTourComplete,
    isTourComplete,
    onboardingCompleted,
    welcomeDone,
    completeOnboarding,
    isOnboardingComplete,
    resetTours,
    totalSteps: tourSteps.length,
  };
}