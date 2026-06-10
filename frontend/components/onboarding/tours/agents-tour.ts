import { TourStep } from '../useOnboardingEngine';

export const agentsTour: TourStep[] = [
  {
    id: 'director-agent',
    targetElement: '[data-onboarding="agent-director"]',
    title: 'Director Agent',
    description: 'The brain of the operation. Analyzes market conditions and coordinates all other agents. Makes high-level trading decisions.',
    tip: 'Director uses Llama-3.3-70B for complex market analysis',
    position: 'bottom',
  },
  {
    id: 'quant-agent',
    targetElement: '[data-onboarding="agent-quant"]',
    title: 'Quant Agent',
    description: 'Runs quantitative analysis on potential trades. Calculates expected returns, risk metrics, and optimal position sizes.',
    tip: 'Processes 452 alpha factors from the Alpha Zoo',
    position: 'bottom',
  },
  {
    id: 'risk-agent',
    targetElement: '[data-onboarding="agent-risk"]',
    title: 'Risk Agent',
    description: 'Your safety net. Reviews every trade against risk limits, VaR constraints, and circuit breaker rules before execution.',
    tip: 'Can halt all trading if drawdown exceeds 5%',
    position: 'bottom',
  },
  {
    id: 'execution-agent',
    targetElement: '[data-onboarding="agent-execution"]',
    title: 'Execution Agent',
    description: 'Handles actual order placement. Routes to best broker (Alpaca/Binance), manages slippage, and confirms fills.',
    tip: 'Uses Llama-3.2-3B for ultra-low latency execution',
    position: 'bottom',
  },
  {
    id: 'agent-status',
    targetElement: '[data-onboarding="agent-status"]',
    title: 'Status Indicators',
    description: 'Green = Running, Gray = Stopped, Red = Error. Click the play/stop buttons to control individual agents.',
    action: {
      label: 'Toggle an Agent',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="agent-status"] button') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'right',
  },
  {
    id: 'agent-latency',
    targetElement: '[data-onboarding="agent-latency"]',
    title: 'Latency Badge',
    description: 'Shows response time from NVIDIA NIM API. Lower is better. Typically 50-600ms depending on model size.',
    tip: '3B models ~50ms, 70B models ~300ms, 120B models ~600ms',
    position: 'left',
  },
  {
    id: 'model-config',
    targetElement: '[data-onboarding="model-config"]',
    title: 'Model Configuration',
    description: 'Click any agent to see detailed settings: model selection, temperature, max tokens. Fine-tune AI behavior per agent.',
    skipAction: true,
    position: 'top',
  },
  {
    id: 'test-connection',
    targetElement: '[data-onboarding="test-connection"]',
    title: 'Test Connection',
    description: 'Verify your NVIDIA API key is working. Sends a ping to test model responses.',
    action: {
      label: 'Run Test',
      onClick: () => {
        const btn = document.querySelector('[data-onboarding="test-connection"]') as HTMLElement;
        btn?.click();
      },
    },
    skipAction: false,
    position: 'top',
  },
];