'use client';

import React, { useEffect } from 'react';
import { useOnboarding } from './OnboardingProvider';
import { TourStep } from './useOnboardingEngine';
import TourOverlay from './TourOverlay';
import InteractiveTooltip from './InteractiveTooltip';
import { dashboardTour } from './tours/dashboard-tour';
import { agentsTour } from './tours/agents-tour';
import { signalsTour } from './tours/signals-tour';
import { copyTradeTour } from './tours/copytrade-tour';
import { backtestTour } from './tours/backtest-tour';
import { alphaZooTour } from './tours/alphazoo-tour';
import { portfolioTour } from './tours/portfolio-tour';
import { settingsTour } from './tours/settings-tour';

interface OnboardingTourProps {
  activePage: string;
  enabled?: boolean;
}

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

export default function OnboardingTour({ activePage, enabled = true }: OnboardingTourProps) {
  const {
    startTour,
    endTour,
    isTourActive,
    currentStep,
    targetElement,
    markTourComplete,
    isTourComplete,
    showWelcome,
    setShowWelcome,
    completedTours,
  } = useOnboarding();

  // Get current tour key from activePage
  const currentTourKey = PATH_TO_TOUR_KEY[activePage.toLowerCase()] || activePage.toLowerCase();
  const hasAnyIncompleteTours = Object.keys(TOUR_MAP).some((key) => !isTourComplete(key));

  // Keyboard handler for ESC
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

  // Start tour when page changes (auto-start for incomplete tours)
  useEffect(() => {
    if (!enabled || isTourActive) return;

    const tourKey = activePage.toLowerCase();
    const tourSteps = TOUR_MAP[tourKey];

    // Auto-start tour if:
    // 1. Tour exists for this page
    // 2. User hasn't completed or explicitly cancelled this tour
    // 3. User hasn't dismissed the welcome modal (showWelcome is still true means they haven't decided yet)
    if (tourSteps && !isTourComplete(tourKey)) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(() => {
        startTour(tourSteps);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [activePage, enabled, isTourActive, isTourComplete, startTour, showWelcome]);

  // Render tour overlay and tooltip when active
  if (isTourActive) {
    return (
      <TourOverlay>
        <InteractiveTooltip
          position={currentStep?.position}
          targetRect={targetElement?.rect || null}
        />
      </TourOverlay>
    );
  }

  return null;
}