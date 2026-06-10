import { TourStep } from '../useOnboardingEngine';

export const backtestTour: TourStep[] = [
  {
    id: 'strategy-form',
    targetElement: '[data-onboarding="strategy-form"]',
    title: 'Strategy Configurator',
    description: 'Name your strategy, select a backtest engine, set date range, and initial capital. This defines your test parameters.',
    tip: 'Use at least 1 year of data for statistically significant results',
    position: 'bottom',
  },
  {
    id: 'alpha-factors',
    targetElement: '[data-onboarding="alpha-factors"]',
    title: 'Alpha Factors',
    description: 'Selected factors from Alpha Zoo that your strategy will use. Each factor adds a predictive signal to your model.',
    action: {
      label: 'Add a Factor',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="alpha-factors"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'right',
  },
  {
    id: 'run-backtest',
    targetElement: '[data-onboarding="run-backtest"]',
    title: 'Run Backtest',
    description: 'Start historical simulation. The engine tests your strategy against past market data to estimate performance.',
    action: {
      label: 'Start Backtest',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="run-backtest"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
  {
    id: 'progress-bar',
    targetElement: '[data-onboarding="progress-bar"]',
    title: 'Progress Tracker',
    description: 'Real-time execution status. Backtesting runs server-side - you can navigate away and return when complete.',
    tip: 'Complex strategies may take 30-60 seconds',
    position: 'bottom',
  },
  {
    id: 'heatmap',
    targetElement: '[data-onboarding="heatmap"]',
    title: 'Returns Heatmap',
    description: 'Monthly returns visualization. Green = profit, Red = loss. Look for consistent green across seasons.',
    skipAction: true,
    position: 'left',
  },
  {
    id: 'performance-metrics',
    targetElement: '[data-onboarding="performance-metrics"]',
    title: 'Performance Metrics',
    description: 'Key stats: Sharpe ratio (risk-adjusted return), Sortino (downside risk), Max Drawdown (worst peak-to-trough), Total Return.',
    tip: 'Sharpe > 1.5 is good, > 2 is excellent',
    position: 'top',
  },
  {
    id: 'equity-curve',
    targetElement: '[data-onboarding="equity-curve"]',
    title: 'Equity Curve',
    description: 'Compare your strategy vs benchmark (SPY). Smooth upward slope = consistent returns. Volatile = higher risk.',
    skipAction: true,
    position: 'bottom',
  },
  {
    id: 'save-strategy',
    targetElement: '[data-onboarding="save-strategy"]',
    title: 'Save Strategy',
    description: 'Store this configuration for reuse. Saved strategies appear in your library for quick re-testing.',
    action: {
      label: 'Save Strategy',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="save-strategy"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
];