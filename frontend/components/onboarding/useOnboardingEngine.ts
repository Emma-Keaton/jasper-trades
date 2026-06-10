import { useState, useEffect, useCallback, useRef } from 'react';

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
  completedTours: string[];
  markTourComplete: (tourId: string) => void;
  isTourComplete: (tourId: string) => boolean;
  resetTours: () => void;
  totalSteps: number;
}

const STORAGE_KEY_PREFIX = 'jasper_onboarding_';

export function useOnboardingEngine(): UseOnboardingEngineReturn {
  const [tourSteps, setTourSteps] = useState<TourStep[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(-1);
  const [targetElements, setTargetElements] = useState<TargetElementInfo[]>([]);
  const [completedTours, setCompletedTours] = useState<string[]>([]);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Load completed tours from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}completed_tours`);
      if (stored) {
        setCompletedTours(JSON.parse(stored));
      }
    } catch (error) {
      console.error('Failed to load onboarding state:', error);
    }
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
  useEffect(() => {
    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect();
    }

    resizeObserverRef.current = new ResizeObserver(() => {
      scanElements();
    });

    targetElements.forEach((target) => {
      if (target.element) {
        resizeObserverRef.current?.observe(target.element);
      }
    });

    // Initial scan
    scanElements();

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, [targetElements.map(t => t.selector).join(','), scanElements]);

  // Get current step
  const currentStep = currentStepIndex >= 0 && currentStepIndex < tourSteps.length
    ? tourSteps[currentStepIndex]
    : null;

  // Get current target element info
  const currentTargetElement = currentStep
    ? targetElements.find((t) => t.id === currentStep.id) || null
    : null;

  // Start tour
  const startTour = useCallback((steps: TourStep[]) => {
    setTourSteps(steps);
    setCurrentStepIndex(0);
    // Wait for DOM to update, then scan elements
    setTimeout(() => scanElements(), 100);
  }, [scanElements]);

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
        try {
          localStorage.setItem(`${STORAGE_KEY_PREFIX}completed_tours`, JSON.stringify(updated));
        } catch (error) {
          console.error('Failed to save onboarding state:', error);
        }
        return updated;
      }
      return prev;
    });
  }, []);

  // Check if tour is complete
  const isTourComplete = useCallback((tourId: string) => {
    return completedTours.includes(tourId);
  }, [completedTours]);

  // Reset all tour progress
  const resetTours = useCallback(() => {
    setCompletedTours([]);
    try {
      localStorage.removeItem(`${STORAGE_KEY_PREFIX}completed_tours`);
    } catch (error) {
      console.error('Failed to reset onboarding state:', error);
    }
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
    completedTours,
    markTourComplete,
    isTourComplete,
    resetTours,
    totalSteps: tourSteps.length,
  };
}