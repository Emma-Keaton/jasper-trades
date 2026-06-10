import { TourStep } from '../useOnboardingEngine';

export const alphaZooTour: TourStep[] = [
  {
    id: 'search-bar',
    targetElement: '[data-onboarding="search-bar"]',
    title: 'Search Factors',
    description: 'Find alpha factors by name, category, or formula type. Type keywords like "momentum", "RSI", "mean reversion".',
    action: {
      label: 'Try Searching',
      onClick: () => {
        const input = document.querySelector('[data-onboarding="search-bar"] input') as HTMLElement;
        input?.focus();
      },
    },
    skipAction: false,
    position: 'bottom',
  },
  {
    id: 'category-filters',
    targetElement: '[data-onboarding="category-filters"]',
    title: 'Category Filters',
    description: 'Filter factors by type: Momentum, Mean-Reversion, Volume, Volatility. Each category captures different market patterns.',
    action: {
      label: 'Select Category',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="category-filters"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'difficulty-badge',
    targetElement: '[data-onboarding="difficulty-badge"]',
    title: 'Difficulty Level',
    description: 'Basic = simple indicators (RSI, MA), Intermediate = composite signals, Advanced = ML-ensemble factors.',
    tip: 'Start with Basic/Intermediate for backtesting',
    position: 'right',
  },
  {
    id: 'win-rate',
    targetElement: '[data-onboarding="win-rate"]',
    title: 'Win Rate',
    description: 'Historical accuracy percentage. 55%+ is good, 60%+ is excellent. Always check sample size.',
    tip: 'High win rate + low trades = potential overfitting',
    position: 'bottom',
  },
  {
    id: 'sharpe-ratio',
    targetElement: '[data-onboarding="sharpe-ratio"]',
    title: 'Sharpe Ratio',
    description: 'Risk-adjusted return metric. Higher = better returns per unit of risk. Look for 1.5+ for quality factors.',
    position: 'left',
  },
  {
    id: 'formula-preview',
    targetElement: '[data-onboarding="formula-preview"]',
    title: 'Formula Preview',
    description: 'Click to see the mathematical formula behind the factor. Useful for understanding the calculation logic.',
    action: {
      label: 'View Formula',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="formula-preview"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'code-snippet',
    targetElement: '[data-onboarding="code-snippet"]',
    title: 'Python Code',
    description: 'Full Python implementation of the factor. Copy/paste into your own scripts or study for learning.',
    tip: 'Code is production-ready and tested',
    skipAction: true,
    position: 'bottom',
  },
  {
    id: 'add-to-strategy',
    targetElement: '[data-onboarding="add-to-strategy"]',
    title: 'Add to Strategy',
    description: 'Star this factor to use it in backtests. Starred factors appear in your Backtest tab strategy builder.',
    action: {
      label: 'Star a Factor',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="add-to-strategy"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
];