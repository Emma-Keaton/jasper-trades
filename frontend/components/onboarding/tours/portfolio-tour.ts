import { TourStep } from '../useOnboardingEngine';

export const portfolioTour: TourStep[] = [
  {
    id: 'allocation-chart',
    targetElement: '[data-onboarding="allocation-chart"]',
    title: 'Allocation Chart',
    description: 'Visual breakdown of your portfolio weights. Switch between donut and treemap views. Shows diversification across assets.',
    tip: 'Hover segments to see exact percentages',
    position: 'bottom',
  },
  {
    id: 'cash-balance',
    targetElement: '[data-onboarding="cash-balance"]',
    title: 'Cash Balance',
    description: 'Liquid capital available for new trades. Increases when you sell or receive profits, decreases when you buy.',
    tip: 'Keep 10-20% cash for opportunities and margin of safety',
    position: 'right',
  },
  {
    id: 'position-cards',
    targetElement: '[data-onboarding="position-cards"]',
    title: 'Position Cards',
    description: 'Each holding shows: entry price, current price, P&L, and P&L%. Click any card for detailed analytics on that position.',
    skipAction: true,
    position: 'left',
  },
  {
    id: 'sync-broker',
    targetElement: '[data-onboarding="sync-broker"]',
    title: 'Sync Broker',
    description: 'Pull live positions from your connected broker (Alpaca/Binance). Keeps your portfolio in sync with external accounts.',
    action: {
      label: 'Trigger Sync',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="sync-broker"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'export-csv',
    targetElement: '[data-onboarding="export-csv"]',
    title: 'Export CSV',
    description: 'Download your complete trade history for tax reporting or personal accounting. Includes dates, prices, P&L.',
    action: {
      label: 'Export Data',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="export-csv"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'bottom',
  },
  {
    id: 'withdraw-button',
    targetElement: '[data-onboarding="withdraw-button"]',
    title: 'Withdraw Profits',
    description: 'Initiate a withdrawal. Following the 50% daily profit rule: half of profits are automatically withdrawn to protect capital.',
    action: {
      label: 'View Withdraw',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="withdraw-button"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'rebalance-tool',
    targetElement: '[data-onboarding="rebalance-tool"]',
    title: 'Rebalance Tool',
    description: 'Adjust your portfolio allocation percentages. Rebalance to target weights periodically to maintain risk profile.',
    skipAction: true,
    position: 'bottom',
  },
];