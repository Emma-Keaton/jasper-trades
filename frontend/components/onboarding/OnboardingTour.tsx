'use client';

import React, { useEffect } from 'react';
import { useOnboarding } from './OnboardingProvider';
import { TourStep } from './useOnboardingEngine';
import TourOverlay from './TourOverlay';
import InteractiveTooltip from './InteractiveTooltip';

interface OnboardingTourProps {
  activePage: string;
  enabled?: boolean;
}

const T = (
  id: string,
  title: string,
  description: string,
  position: 'top' | 'bottom' | 'left' | 'right',
  tip?: string
): TourStep => ({ id, targetElement: `[data-onboarding="${id}"]`, title, description, position, tip });

const TOUR_MAP: Record<string, TourStep[]> = {
  home: [
    T('home-start', 'Press Start', 'This is the only button you need. Jasper begins watching markets and trading with practice money.', 'bottom', 'Practice money only. Nothing real.'),
    T('home-stats', 'Your balance', 'Here is your practice money and how you are doing today.', 'left', 'Green means you are up today.'),
    T('recent-trades', 'Recent AI trades', 'Every trade Jasper places appears here, in plain English.', 'top', 'See the full list in Trades.'),
  ],
  trades: [
    T('trades-holdings', 'What you own', 'Everything Jasper has bought, with its current value and a plain-English trend line.', 'bottom', 'Holdings update in real time.'),
  ],
  markets: [
    T('markets-recs', 'Trending right now', 'What is hot in crypto right now — tap a star to add it to your watchlist.', 'bottom', 'Add symbols for the AI to trade.'),
  ],
  signals: [
    T('signals-sources', 'Signal sources', 'Plug in feeds, Reddit, StockTwits or Telegram so Jasper has places to look for ideas.', 'bottom', 'Results are ranked for you.'),
    T('position-size', 'Position size', 'Every signal buys a slice of your equity - here is how big that slice is. Slide it to 5% and let Jasper size its own trades.', 'top', 'Capped by Trading Caps in Settings.'),
  ],
  settings: [
    T('settings-checklist', 'Set up Jasper', 'A simple checklist to make everything work the way you want. Tap any row to open it.', 'right', 'Start with practice mode.'),
  ],
};

export default function OnboardingTour({ activePage, enabled = true }: OnboardingTourProps) {
  const {
    startTour, endTour, isTourActive, currentStep, targetElement,
    markTourComplete, isTourComplete, showWelcome, isOnboardingComplete, isLoaded,
    onboardingCompleted, welcomeDone,
  } = useOnboarding();

  const tourKey = activePage.toLowerCase();
  const hasTours = Object.prototype.hasOwnProperty.call(TOUR_MAP, tourKey);
  const onboardingDone = onboardingCompleted || welcomeDone;

  // ESC to stop the current tour
  useEffect(() => {
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isTourActive) { e.preventDefault(); markTourComplete(tourKey); endTour(); }
    };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [isTourActive, endTour, markTourComplete, tourKey]);

  // Auto-start once per screen after the welcome modal has been dismissed
  useEffect(() => {
    if (!enabled || !hasTours || showWelcome) return;
    if (!isLoaded) return;
    if (onboardingDone) return;
    if (isTourActive || isTourComplete(tourKey)) return;
    const t = setTimeout(() => startTour(TOUR_MAP[tourKey]), 350);
    return () => clearTimeout(t);
  }, [activePage, enabled, hasTours, showWelcome, isLoaded, onboardingDone, isTourActive, isTourComplete, startTour, tourKey]);

  if (isTourActive) {
    return (
      <TourOverlay>
        <InteractiveTooltip position={currentStep?.position} targetRect={targetElement?.rect || null} tourKey={tourKey} />
      </TourOverlay>
    );
  }

  return null;
}
