import { TourStep } from '../useOnboardingEngine';

export const settingsTour: TourStep[] = [
  {
    id: 'api-keys',
    targetElement: '[data-onboarding="api-keys"]',
    title: 'API Keys Section',
    description: 'Configure your NVIDIA NIM API key (for AI models), Alpaca (stocks), and Binance (crypto) credentials. Stored encrypted locally.',
    tip: 'Start with paper trading keys, switch to live when ready',
    position: 'bottom',
  },
  {
    id: 'exness-integration',
    targetElement: '[data-onboarding="exness-integration"]',
    title: 'Exness/MT5 Integration',
    description: 'Connect your Exness MetaTrader 5 account for live forex/CFD trading. Requires login ID, server, and passwords.',
    skipAction: true,
    position: 'right',
  },
  {
    id: 'trading-caps',
    targetElement: '[data-onboarding="trading-caps"]',
    title: 'Trading Caps',
    description: 'Set daily loss limits, maximum position size, and max trades per day. Risk management guardrails to prevent overtrading.',
    action: {
      label: 'Set a Limit',
      onClick: () => {
        const input = document.querySelector('[data-onboarding="trading-caps"] input') as HTMLElement;
        input?.focus();
      },
    },
    skipAction: false,
    position: 'left',
  },
  {
    id: 'payout-settings',
    targetElement: '[data-onboarding="payout-settings"]',
    title: 'Payout Configuration',
    description: '50% daily profit auto-withdrawal rule. Protects your capital by withdrawing half of daily gains automatically.',
    tip: 'Compound the other 50% for growth',
    position: 'top',
  },
  {
    id: 'notifications',
    targetElement: '[data-onboarding="notifications"]',
    title: 'Notification Services',
    description: 'Configure WhatsApp, Discord, Slack, or Email alerts. Get notified when trades execute, circuit breaks trigger, or targets hit.',
    skipAction: true,
    position: 'bottom',
  },
  {
    id: 'market-data',
    targetElement: '[data-onboarding="market-data"]',
    title: 'Market Data Sources',
    description: 'Select your data providers: Polygon, TwelveData, Yahoo Finance. Determines which feeds power your analytics and signals.',
    tip: 'Yahoo Finance is free but delayed; Polygon is real-time',
    position: 'right',
  },
  {
    id: 'device-fingerprint',
    targetElement: '[data-onboarding="device-fingerprint"]',
    title: 'Device Fingerprint',
    description: 'Your settings persist across app updates via device fingerprinting. No account needed - your browser ID stores preferences.',
    skipAction: true,
    position: 'top',
  },
  {
    id: 'save-reset',
    targetElement: '[data-onboarding="save-reset"]',
    title: 'Save & Reset',
    description: 'Apply your changes or restore all defaults. Always click "Save" after modifying settings.',
    action: {
      label: 'Save Settings',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="save-reset"] button[type="submit"]') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'bottom',
  },
];