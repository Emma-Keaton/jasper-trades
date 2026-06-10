import { TourStep } from '../useOnboardingEngine';

export const dashboardTour: TourStep[] = [
  {
    id: 'portfolio-value',
    targetElement: '[data-onboarding="portfolio-value"]',
    title: 'Total Portfolio Value',
    description: 'This shows your total account value including cash and holdings. Updates in real-time as trades execute.',
    tip: 'Click any card to see detailed breakdown by asset type',
    position: 'bottom',
  },
  {
    id: 'pnl-chart',
    targetElement: '[data-onboarding="pnl-chart"]',
    title: 'Profit & Loss Chart',
    description: 'Visual track of your portfolio performance over time. Green line = gains, red line = losses. Hover to see exact values at any point.',
    tip: 'Change timeframe (1D, 1W, 1M, ALL) to zoom into specific periods',
    position: 'top',
  },
  {
    id: 'holdings-table',
    targetElement: '[data-onboarding="holdings-table"]',
    title: 'Your Holdings',
    description: 'List of all assets you own. Shows symbol, shares, average buy price, current price, and P&L percentage. Click any row to see detailed analytics.',
    position: 'right',
  },
  {
    id: 'trade-history',
    targetElement: '[data-onboarding="trade-history"]',
    title: 'Trade History Console',
    description: 'Real-time feed of all executed trades. Shows agent name, entry price, shares, and total value. This is your audit trail.',
    tip: 'Trades are color-coded: Green = BUY, Red = SELL',
    skipAction: true,
    position: 'left',
  },
];
