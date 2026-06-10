import { TourStep } from '../useOnboardingEngine';

export const signalsTour: TourStep[] = [
  {
    id: 'signal-cards',
    targetElement: '[data-onboarding="signal-cards"]',
    title: 'Signal Cards',
    description: 'AI-generated trading recommendations. Each card shows BUY/SELL/HOLD, confidence %, target price, and stop loss.',
    tip: 'Look for 70%+ confidence signals with clear thesis',
    position: 'bottom',
  },
  {
    id: 'signal-filters',
    targetElement: '[data-onboarding="signal-filters"]',
    title: 'Signal Filters',
    description: 'Filter by agent, asset type, signal type, and minimum confidence. Narrow down to highest-quality opportunities.',
    action: {
      label: 'Try Filtering',
      onClick: () => {
        const select = document.querySelector('[data-onboarding="signal-filters"] select') as HTMLElement;
        select?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'execute-button',
    targetElement: '[data-onboarding="execute-button"]',
    title: 'Execute Trade',
    description: 'One-click trade execution from this signal. Automatically fills shares, price, and total based on signal parameters.',
    action: {
      label: 'View Execution',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="execute-button"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'right',
  },
  {
    id: 'thesis-reason',
    targetElement: '[data-onboarding="thesis-reason"]',
    title: 'AI Thesis',
    description: 'Natural language explanation of why the signal was generated. Shows key factors influencing the decision.',
    tip: 'Read the thesis to understand the trade rationale',
    position: 'left',
  },
  {
    id: 'watchlist-star',
    targetElement: '[data-onboarding="watchlist-star"]',
    title: 'Add to Watchlist',
    description: 'Star symbols to monitor them closely. Watchlisted symbols appear in your dedicated watchlist panel.',
    action: {
      label: 'Star a Symbol',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="watchlist-star"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'target-stop',
    targetElement: '[data-onboarding="target-stop"]',
    title: 'Target & Stop Prices',
    description: 'Suggested exit points for risk management. Target = take profit, Stop = cut loss. Based on ATR and support/resistance.',
    tip: 'Always set stops before entering a trade',
    position: 'bottom',
  },
  {
    id: 'time-filter',
    targetElement: '[data-onboarding="time-filter"]',
    title: 'Time Filter',
    description: 'Show signals from last 24h, 7d, or 30d. Fresh signals have higher relevance.',
    skipAction: true,
    position: 'top',
  },
];