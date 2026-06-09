export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
}

/**
 * Callback props for child components to communicate with parent
 */
export interface HomeCallbacks {
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
  executeTrade: (
    symbol: string,
    type: 'BUY' | 'SELL',
    shares: number,
    price: number,
    total: number,
    agentName: string
  ) => void;
  addAlphaFactor: (factorName: string) => void;
  removeAlphaFactor: (factorName: string) => void;
  setActiveTab: (tab: string) => void;
}

/**
 * Main home page state interface
 */
export interface HomeState {
  cash: number;
  holdings: Holding[];
  tradeHistory: TradeHistoryItem[];
  agents: AgentState[];
  notifications: NotificationItem[];
  selectedAlphaFactors: string[];
}

/**
 * A single position held in the portfolio
 */
export interface Holding {
  symbol: string;
  name: string;
  type: 'Stock' | 'Crypto' | 'Cash';
  shares: number;
  avgPrice: number;
  currentPrice: number;
  pnlPercent: number;
}

/**
 * A historical trade execution
 */
export interface TradeHistoryItem {
  id: string;
  date: string;
  type: 'BUY' | 'SELL';
  symbol: string;
  side: 'Long' | 'Short';
  shares: number;
  price: number;
  total: number;
  agent: string;
}

export interface AgentState {
  id: string;
  name: string;
  status: 'Running' | 'Stopped' | 'Error';
  latency: string;
  successRate: string;
  uptime: string;
}

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  time: string;
  unread: boolean;
}