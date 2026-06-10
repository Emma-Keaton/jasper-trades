/**
 * Onboarding Tour Hook
 * Manages interactive tour state with localStorage persistence
 */
'use client';

import { useState, useEffect, useCallback } from 'react';

export interface TourStep {
  id: string;
  targetElement: string; // CSS selector
  title: string;
  description: string;
  position?: 'top' | 'bottom' | 'left' | 'right' | 'center';
  interactiveElement?: {
    type: 'button' | 'input' | 'checkbox';
    selector: string;
    action?: 'click' | 'focus' | 'highlight';
  };
}

export interface TourConfig {
  id: string;
  name: string;
  pages: string[]; // URL paths or tab names where this tour applies
  steps: TourStep[];
  autoStart?: boolean; // Start on first visit
}

interface TourState {
  active: boolean;
  currentStep: number;
  completedTours: string[];
  skippedTours: string[];
}

const STORAGE_KEY = 'jasper_onboarding';

export function useOnboarding() {
  const [tourState, setTourState] = useState<TourState>({
    active: false,
    currentStep: 0,
    completedTours: [],
    skippedTours: [],
  });

  const [currentTour, setCurrentTour] = useState<TourConfig | null>(null);

  // Load state from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setTourState(prev => ({
          ...prev,
          completedTours: parsed.completedTours || [],
          skippedTours: parsed.skippedTours || [],
        }));
      }
    } catch (error) {
      console.error('Failed to load onboarding state:', error);
    }
  }, []);

  // Save state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        completedTours: tourState.completedTours,
        skippedTours: tourState.skippedTours,
      }));
    } catch (error) {
      console.error('Failed to save onboarding state:', error);
    }
  }, [tourState.completedTours, tourState.skippedTours]);

  // Start a tour
  const startTour = useCallback((tour: TourConfig, step = 0) => {
    setCurrentTour(tour);
    setTourState(prev => ({
      ...prev,
      active: true,
      currentStep: step,
    }));
  }, []);

  // Go to next step
  const nextStep = useCallback(() => {
    setTourState(prev => {
      if (!currentTour) return prev;

      if (prev.currentStep >= currentTour.steps.length - 1) {
        // Tour completed
        return {
          ...prev,
          active: false,
          currentStep: 0,
          completedTours: [...prev.completedTours, currentTour.id],
        };
      }

      return {
        ...prev,
        currentStep: prev.currentStep + 1,
      };
    });
  }, [currentTour]);

  // Go to previous step
  const prevStep = useCallback(() => {
    setTourState(prev => ({
      ...prev,
      currentStep: Math.max(0, prev.currentStep - 1),
    }));
  }, []);

  // Skip tour
  const skipTour = useCallback(() => {
    if (!currentTour) return;

    setTourState(prev => ({
      ...prev,
      active: false,
      currentStep: 0,
      skippedTours: [...prev.skippedTours, currentTour.id],
    }));
    setCurrentTour(null);
  }, [currentTour]);

  // Close tour (without marking as completed)
  const closeTour = useCallback(() => {
    setTourState(prev => ({
      ...prev,
      active: false,
      currentStep: 0,
    }));
    setCurrentTour(null);
  }, []);

  // Restart a completed tour
  const restartTour = useCallback((tour: TourConfig) => {
    setTourState(prev => ({
      ...prev,
      completedTours: prev.completedTours.filter(id => id !== tour.id),
    }));
    startTour(tour, 0);
  }, [startTour]);

  // Check if tour is completed
  const isTourCompleted = useCallback((tourId: string) => {
    return tourState.completedTours.includes(tourId);
  }, [tourState.completedTours]);

  // Check if tour was skipped
  const isTourSkipped = useCallback((tourId: string) => {
    return tourState.skippedTours.includes(tourId);
  }, [tourState.skippedTours]);

  // Reset all onboarding progress (for testing)
  const resetOnboarding = useCallback(() => {
    setTourState({
      active: false,
      currentStep: 0,
      completedTours: [],
      skippedTours: [],
    });
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  // Get current step data
  const currentStepData = currentTour?.steps[tourState.currentStep];

  // Progress percentage
  const progress = currentTour && tourState.active
    ? ((tourState.currentStep + 1) / currentTour.steps.length) * 100
    : 0;

  return {
    // State
    active: tourState.active,
    currentTour,
    currentStep: tourState.currentStep,
    totalSteps: currentTour?.steps.length || 0,
    currentStepData,
    progress,

    // Actions
    startTour,
    nextStep,
    prevStep,
    skipTour,
    closeTour,
    restartTour,
    isTourCompleted,
    isTourSkipped,
    resetOnboarding,
  };
}