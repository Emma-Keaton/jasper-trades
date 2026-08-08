/**
 * Onboarding Tour Configurations
 * Defines tour steps for each page in Jasper Trades
 */

import { TourStep } from '@/components/onboarding/useOnboardingEngine';

export interface TourConfig {
  id: string;
  name: string;
  pages: string[];
  autoStart?: boolean;
  steps: Array<Partial<TourStep> & { [key: string]: any }>;
}

export const TOURS: Record<string, TourConfig> = {
  // ==================== DASHBOARD TOUR ====================
  dashboard: {
    id: 'dashboard',
    name: 'Dashboard Overview',
    pages: ['dashboard'],
    autoStart: true,
    steps: [
      {
        id: 'portfolio-value',
        targetElement: '[data-tour="portfolio-value"]',
        title: 'Your Portfolio Value',
        description: 'Real-time total value of your portfolio including cash and holdings. Updates every 30 seconds via silent background refresh.',
        position: 'bottom',
      },
      {
        id: 'holdings-list',
        targetElement: '[data-tour="holdings-list"]',
        title: 'Current Holdings',
        description: 'All your positions with live PnL. Click on any holding to see detailed analytics. Green = profit, Red = loss.',
        position: 'right',
      },
      {
        id: 'equity-curve',
        targetElement: '[data-tour="equity-curve"]',
        title: 'Equity Curve',
        description: 'Visual representation of your portfolio performance over time. Toggle between 1M, 3M, 1Y, and All timeframes.',
        position: 'top',
      },
      {
        id: 'agent-status',
        targetElement: '[data-tour="agent-status"]',
        title: 'AI Agent Status',
        description: '4-stage autonomous pipeline: Director → Quant → Risk → Execution. Green = Running, Gray = Stopped. Start agents to begin trading.',
        position: 'left',
      },
      {
        id: 'trade-history',
        targetElement: '[data-tour="trade-history"]',
        title: 'Recent Trades',
        description: 'Live execution log showing all trades. Click any trade to view details including entry price, current value, and PnL.',
        position: 'top',
      },
    ],
  },

  // ==================== AGENTS TOUR ====================
  agents: {
    id: 'agents',
    name: 'AI Agents Configuration',
    pages: ['agents'],
    autoStart: true,
    steps: [
      {
        id: 'agent-overview',
        targetElement: '[data-tour="agent-cards"]',
        title: '4-Stage AI Pipeline',
        description: 'Each agent has a specific role: Director (coordination), Quant (analysis), Risk (safety), Execution (trading). All must be running for full autonomy.',
        position: 'bottom',
      },
      {
        id: 'start-stop',
        targetElement: '[data-tour="agent-controls"]',
        title: 'Start/Stop Controls',
        description: 'Click Play to start an agent, Square to stop. Start order matters: Director first, then others. Stop in reverse order.',
        position: 'left',
        interactiveElement: {
          type: 'button',
          selector: '[data-tour="agent-controls"] button',
          action: 'highlight',
        },
      },
      {
        id: 'agent-metrics',
        targetElement: '[data-tour="agent-metrics"]',
        title: 'Performance Metrics',
        description: 'Live stats: Latency (response time), Success Rate (%), Uptime. Green = healthy (<500ms), Yellow = moderate, Red = slow (>2s).',
        position: 'top',
      },
      {
        id: 'model-config',
        targetElement: '[data-tour="model-config"]',
        title: 'NVIDIA Model Selection',
        description: 'Choose AI model per agent: Llama-3.2-3B (fast, $0.15/M tokens), Llama-3.3-70B (balanced, $0.65/M), Nemotron-120B (deep analysis, $2.00/M).',
        position: 'bottom',
      },
    ],
  },

  // ==================== SETTINGS TOUR ====================
  settings: {
    id: 'settings',
    name: 'Settings & Integrations',
    pages: ['settings'],
    autoStart: true,
    steps: [
      {
        id: 'api-keys',
        targetElement: '[data-tour="api-keys-section"]',
        title: 'API Keys (Required)',
        description: 'Start here! NVIDIA API key is required for AI features. Get free $25/month credits at catalog.ngc.nvidia.com. All keys are encrypted before storage.',
        position: 'bottom',
      },
      {
        id: 'exness-mt5',
        targetElement: '[data-tour="exness-section"]',
        title: 'Exness/MT5 Account',
        description: 'Link your Exness broker for Forex/CFD trading. Enter MT5 Login ID, select server (e.g., Exness-MT5-Real6), and trading password. Works on Windows (MT5 terminal) or cloud (REST API).',
        position: 'left',
      },
      {
        id: 'trading-caps',
        targetElement: '[data-tour="trading-caps-section"]',
        title: 'Trading Caps (Risk Management)',
        description: 'PROTECT YOUR PORTFOLIO: Set max position $ (e.g., $5,000), max % (e.g., 20%), daily loss limits. Hard Limit = block trades, Soft Limit = warn but allow.',
        position: 'top',
      },
      {
        id: 'market-data',
        targetElement: '[data-tour="market-data-section"]',
        title: 'Free Market Data',
        description: 'CoinGecko (crypto) works immediately - no key needed! Add Alpha Vantage (stocks/forex), Finnhub (real-time stocks), Twelve Data for more coverage. All free tiers!',
        position: 'bottom',
      },
      {
        id: 'sendgrid-email',
        targetElement: '[data-tour="email-section"]',
        title: 'Email Notifications',
        description: 'SendGrid: 100 FREE emails/day forever. Get trade confirmations, price alerts, daily summaries. Signup at sendgrid.com → Create API Key → Paste above.',
        position: 'left',
      },
      {
        id: 'discord-bot',
        targetElement: '[data-tour="discord-section"]',
        title: 'Discord Two-Way Bot',
        description: 'FREE unlimited! Commands: !portfolio, !trades, !help. Setup: discord.com/developers → New App → Bot → Copy Token → Get Server/Channel IDs (Developer Mode).',
        position: 'top',
      },
      {
        id: 'notifications',
        targetElement: '[data-tour="notifications-section"]',
        title: 'Notification Channels',
        description: 'Configure WhatsApp (embedded OpenWA), Slack, Telegram webhooks. Choose events: trade executions, signals, risk alerts. Set quiet hours to sleep peacefully.',
        position: 'bottom',
      },
      {
        id: 'save-button',
        targetElement: '[data-tour="save-settings"]',
        title: 'Save Your Settings',
        description: '⚠️ IMPORTANT: Click Save after configuring each section! Settings are encrypted and stored securely. Test connections before enabling.',
        position: 'right',
        interactiveElement: {
          type: 'button',
          selector: '[data-tour="save-settings"] button',
          action: 'highlight',
        },
      },
    ],
  },

  // ==================== PORTFOLIO TOUR ====================
  portfolio: {
    id: 'portfolio',
    name: 'Portfolio Management',
    pages: ['portfolio'],
    autoStart: true,
    steps: [
      {
        id: 'holdings-table',
        targetElement: '[data-tour="portfolio-holdings"]',
        title: 'Portfolio Holdings',
        description: 'All your positions across brokers. Shows symbol, quantity, avg price, current price, and PnL%. Click any row to add more or close position.',
        position: 'bottom',
      },
      {
        id: 'add-holding',
        targetElement: '[data-tour="add-holding-btn"]',
        title: 'Add Manual Position',
        description: 'Manually add holdings not from automated trading. Select broker, enter symbol, quantity, purchase price. Useful for importing existing portfolios.',
        position: 'left',
        interactiveElement: {
          type: 'button',
          selector: '[data-tour="add-holding-btn"]',
          action: 'highlight',
        },
      },
      {
        id: 'withdraw-button',
        targetElement: '[data-tour="withdraw-btn"]',
        title: 'Withdraw Profits',
        description: 'Auto-payout: 50% of daily profits (customizable in Settings). Choose destination: Crypto wallet (USDT), Bank (Alpaca), Exness account. Fees auto-calculated.',
        position: 'top',
        interactiveElement: {
          type: 'button',
          selector: '[data-tour="withdraw-btn"]',
          action: 'highlight',
        },
      },
      {
        id: 'pnl-display',
        targetElement: '[data-tour="portfolio-pnl"]',
        title: 'PnL Calculation',
        description: 'Realized PnL (closed trades) + Unrealized PnL (open positions). Portfolio resets to $0 PnL until first real trade to avoid phantom gains.',
        position: 'right',
      },
    ],
  },

  // ==================== SIGNALS TOUR ====================
  signals: {
    id: 'signals',
    name: 'Signals Feed',
    pages: ['signals'],
    autoStart: false,
    steps: [
      {
        id: 'signals-feed',
        targetElement: '[data-tour="signals-feed"]',
        title: 'AI Trading Signals',
        description: 'Live signal feed from AI agents. Each signal shows: Symbol, Action (BUY/SELL), Confidence, Reasoning. Click Execute to trade or Ignore to dismiss.',
        position: 'bottom',
      },
      {
        id: 'signal-filters',
        targetElement: '[data-tour="signal-filters"]',
        title: 'Filter & Sort',
        description: 'Filter by: Asset class, Confidence level, Agent source. Sort by: Time, Confidence, Expected return. Focus on high-confidence signals (>70%).',
        position: 'left',
      },
    ],
  },
  // ==================== BACKTEST TOUR ====================
  backtest: {
    id: 'backtest',
    name: 'Backtesting',
    pages: ['backtest'],
    autoStart: false,
    steps: [
      {
        id: 'backtest-config',
        targetElement: '[data-tour="backtest-config"]',
        title: 'Configure Backtest',
        description: 'Select strategy (alpha factors), date range, initial capital, benchmark. Click Run Backtest to start. Results show Sharpe, max drawdown, CAGR.',
        position: 'bottom',
        interactiveElement: {
          type: 'button',
          selector: '[data-tour="run-backtest"]',
          action: 'highlight',
        },
      },
      {
        id: 'results-chart',
        targetElement: '[data-tour="backtest-results"]',
        title: 'Performance Analytics',
        description: 'Equity curve vs benchmark, monthly returns heatmap, drawdown periods. Compare against Buy & Hold to see if alpha adds value.',
        position: 'top',
      },
    ],
  },

  // ==================== ALPHA ZOO TOUR ====================
  alphazoo: {
    id: 'alphazoo',
    name: 'Alpha Factors',
    pages: ['alphazoo'],
    autoStart: false,
    steps: [
      {
        id: 'alpha-browser',
        targetElement: '[data-tour="alpha-browser"]',
        title: '452 Alpha Factors',
        description: 'Quantitative signals library: Momentum, Mean Reversion, Volatility, Volume, ML-based. Click any factor to see description, Sharpe ratio, and correlation.',
        position: 'bottom',
      },
      {
        id: 'factor-selection',
        targetElement: '[data-tour="factor-selection"]',
        title: 'Build Your Strategy',
        description: 'Select multiple factors (hold Ctrl/Cmd). System auto-calculates combined Sharpe and correlation matrix. Aim for low correlation (<0.5) for diversification.',
        position: 'left',
      },
    ],
  },
};

// Helper to get tour by page name
export function getTourByPage(pageName: string): TourConfig | null {
  const tour = Object.values(TOURS).find(tour =>
    tour.pages.includes(pageName.toLowerCase())
  );
  return tour || null;
}

// Helper to check if a page has a tour
export function pageHasTour(pageName: string): boolean {
  return getTourByPage(pageName) !== null;
}
