import { TourStep } from '../useOnboardingEngine';

export const copyTradeTour: TourStep[] = [
  {
    id: 'leaderboard-table',
    targetElement: '[data-onboarding="leaderboard-table"]',
    title: 'Trader Leaderboard',
    description: 'Top performers ranked by total return. Shows win rate, AUM, total trades, and copiers. Find traders whose style matches your goals.',
    tip: 'Sort by win rate for consistency, or return for aggression',
    position: 'bottom',
  },
  {
    id: 'follow-button',
    targetElement: '[data-onboarding="follow-button"]',
    title: 'Follow Trader',
    description: 'Start copying this trader\'s positions automatically. Their future trades will be mirrored in your account (proportional to your capital).',
    action: {
      label: 'Follow a Trader',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="follow-button"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'right',
  },
  {
    id: 'trader-profile',
    targetElement: '[data-onboarding="trader-profile"]',
    title: 'Trader Profile',
    description: 'Click any trader to see detailed stats: trading history, preferred assets, typical holding period, and strategy description.',
    skipAction: true,
    position: 'top',
  },
  {
    id: 'copied-positions',
    targetElement: '[data-onboarding="copied-positions"]',
    title: 'Copied Positions',
    description: 'Your active positions from copied traders. Shows Trader name, Symbol, Entry price, Current price, and P&L.',
    tip: 'Click unfollow to stop copying and optionally close the position',
    position: 'left',
  },
  {
    id: 'unfollow-button',
    targetElement: '[data-onboarding="unfollow-button"]',
    title: 'Unfollow Trader',
    description: 'Stop copying a trader. You can choose to close positions immediately or keep them and manage manually.',
    action: {
      label: 'View Unfollow',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="unfollow-button"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'bottom',
  },
  {
    id: 'active-follows',
    targetElement: '[data-onboarding="active-follows"]',
    title: 'Active Follows Count',
    description: 'Total number of traders you\'re currently copying. Diversify across multiple traders to spread risk.',
    tip: 'Recommended: Follow 3-5 traders with different styles',
    position: 'top',
  },
  {
    id: 'filter-search',
    targetElement: '[data-onboarding="filter-search"]',
    title: 'Search & Filter',
    description: 'Find traders by name, return %, asset type, or minimum win rate. Narrow down to traders matching your criteria.',
    skipAction: true,
    position: 'top',
  },
];