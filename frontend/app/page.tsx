'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  Bot,
  Radio,
  Users,
  TrendingUp,
  Compass,
  Briefcase,
  Settings,
  Search,
  Bell,
  Menu,
  ChevronLeft,
  ChevronRight,
  X,
  Sparkles,
  Check,
  AlertTriangle,
  Info
} from 'lucide-react';

// Types
export interface Holding {
  symbol: string;
  name: string;
  type: 'Stock' | 'Crypto' | 'Cash';
  shares: number;
  avgPrice: number;
  currentPrice: number;
  pnlPercent: number;
}

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

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
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

import { usePriceStream } from '@/hooks/usePriceStream';
import { websocketClient, ConnectionStatus } from '@/lib/websocket';
import ChatWidget from '@/components/ChatWidget';

// Import tab components
import DashboardTab from '@/components/DashboardTab';
import AgentsTab from '@/components/AgentsTab';
import SignalsTab from '@/components/SignalsTab';
import CopyTradeTab from '@/components/CopyTradeTab';
import BacktestTab from '@/components/BacktestTab';
import AlphaZooTab from '@/components/AlphaZooTab';
import PortfolioTab from '@/components/PortfolioTab';
import SettingsTab from '@/components/SettingsTab';

// API utility
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<{ data?: T; error?: string }> {
  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options?.headers },
    });
    const data = await response.json();
    if (!response.ok) {
      return { error: data.detail || data.error || `HTTP ${response.status}` };
    }
    return { data };
  } catch (e) {
    return { error: e instanceof Error ? e.message : 'Network error' };
  }
}

export default function Home() {
  // Navigation state
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [sidebarExpanded, setSidebarExpanded] = useState<boolean>(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [currentSettingsTab, setCurrentSettingsTab] = useState<string>('api');

  // Search state
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showCommandPalette, setShowCommandPalette] = useState<boolean>(false);

  // Backend sync state - starts with defaults, syncs to backend
  const [cash, setCash] = useState<number>(0); // Start at $0 until loaded from backend
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [tradeHistory, setTradeHistory] = useState<TradeHistoryItem[]>([]);
  const [portfolioLoaded, setPortfolioLoaded] = useState<boolean>(false);
  const [portfolioInitialized, setPortfolioInitialized] = useState<boolean>(false); // Track if portfolio has real trading activity
  const [agents, setAgents] = useState<AgentState[]>([
    { id: 'director', name: 'Director', status: 'Stopped', latency: '-', successRate: '-', uptime: '-' },
    { id: 'quant', name: 'Quant', status: 'Stopped', latency: '-', successRate: '-', uptime: '-' },
    { id: 'risk', name: 'Risk', status: 'Stopped', latency: '-', successRate: '-', uptime: '-' },
    { id: 'execution', name: 'Execution', status: 'Stopped', latency: '-', successRate: '-', uptime: '-' },
  ]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [selectedAlphaFactors, setSelectedAlphaFactors] = useState<string[]>([]);

  // Toast state
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Connection state
  const [backendConnected, setBackendConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [currentTimeStr, setCurrentTimeStr] = useState<string>('00:00:00');
  const [wsStatus, setWsStatus] = useState<ConnectionStatus>('disconnected');

  // WebSocket price stream
  const { isConnected: wsConnected, status: priceStreamStatus } = usePriceStream({
    onPriceUpdate: (update) => {
      // Update holding prices in real-time
      setHoldings(prev => prev.map(h => 
        h.symbol === update.symbol
          ? { ...h, currentPrice: update.price, pnlPercent: ((update.price - h.avgPrice) / h.avgPrice) * 100 }
          : h
      ));
    },
    onStatusChange: setWsStatus,
  });

  // Auto-redirect to /settings when Settings tab is selected
  useEffect(() => {
    if (activeTab === 'settings') {
      setCurrentSettingsTab('api');
    }
  }, [activeTab]);

  // Kronos memory monitoring state (4GB RAM optimization)
  const [memoryUsage, setMemoryUsage] = useState<{
    rss_mb: number;
    system_percent: number;
    is_safe_for_inference: boolean;
  } | null>(null);

  // Clock effect
  useEffect(() => {
    const updateTime = () => setCurrentTimeStr(new Date().toISOString().slice(11, 19));
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch initial data from backend
  const fetchBackendData = useCallback(async () => {
    setLoading(true);

    // Fetch system status
    const statusResult = await apiRequest<any>('/api/v1/status');
    if (statusResult.data) {
      setBackendConnected(true);
      // Update agents from backend
      if (statusResult.data.agents) {
        setAgents(prev => prev.map(a => ({
          ...a,
          status: statusResult.data.agents.includes(a.id.toUpperCase()) ? 'Running' : 'Stopped'
        })));
      }
    } else {
      setBackendConnected(false);
    }

    // Fetch memory status (Kronos 4GB monitoring)
    const memoryResult = await apiRequest<any>('/api/v1/system/memory');
    if (memoryResult.data) {
      setMemoryUsage({
        rss_mb: memoryResult.data.rss_mb || 0,
        system_percent: memoryResult.data.system_percent || 0,
        is_safe_for_inference: memoryResult.data.is_safe_for_inference ?? true,
      });
    }

    // Fetch portfolio data
    const portfoliosResult = await apiRequest<any[]>('/api/v1/portfolio');
    if (portfoliosResult.data && portfoliosResult.data.length > 0) {
      const portfolio = portfoliosResult.data[0];
      const portfolioId = portfolio.id;

      // Fetch initialization status to determine if PnL should be shown
      const initStatusResult = await apiRequest<any>(`/api/v1/portfolio/${portfolioId}/initialization-status`);
      if (initStatusResult.data) {
        setPortfolioInitialized(initStatusResult.data.is_initialized);
      }

      setCash(portfolio.cash || 0);
      setPortfolioLoaded(true);

      // Fetch holdings
      const holdingsResult = await apiRequest<any[]>(`/api/v1/portfolio/${portfolioId}/holdings`);
      if (holdingsResult.data) {
        setHoldings(holdingsResult.data.map((h: any) => ({
          symbol: h.symbol,
          name: h.name || h.symbol,
          type: h.type || 'Stock',
          shares: h.shares,
          avgPrice: h.avg_price || 0,
          currentPrice: h.current_price || h.avg_price || 0,
          pnlPercent: h.pnl_percent || 0
        })));
      }

      // Fetch trades
      const tradesResult = await apiRequest<any[]>(`/api/v1/portfolio/${portfolioId}/trades`);
      if (tradesResult.data) {
        setTradeHistory(tradesResult.data.map((t: any) => ({
          id: t.id,
          date: new Date(t.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
          type: t.type,
          symbol: t.symbol,
          side: 'Long',
          shares: t.shares,
          price: t.price,
          total: t.total,
          agent: 'Director'
        })));
      }
    }

    setLoading(false);
  }, []);

  // Initial load and poll for updates (WebSocket handles real-time prices)
  useEffect(() => {
    fetchBackendData();
    // Poll every 30s for non-price data (WebSocket handles prices)
    const interval = setInterval(fetchBackendData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Toast helpers
  const triggerToast = useCallback((type: Toast['type'], title: string, message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, type, title, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Trade execution
  const executeTradeFromSignal = useCallback(async (
    symbol: string,
    type: 'BUY' | 'SELL',
    shares: number,
    price: number,
    total: number,
    agentName: string
  ) => {
    if (type === 'BUY' && total > cash) {
      triggerToast('error', 'Insufficient Cash', `Required: $${total.toLocaleString()}. Available: $${cash.toLocaleString()}.`);
      return;
    }

    const portfolioResult = await apiRequest<any[]>('/api/v1/portfolio');
    if (!portfolioResult.data || portfolioResult.data.length === 0) {
      triggerToast('error', 'No Portfolio', 'Please create a portfolio first.');
      return;
    }
    const portfolioId = portfolioResult.data[0].id;

    // Execute via backend API
    const tradeResult = await apiRequest<any>('/api/v1/trading/execute', {
      method: 'POST',
      body: JSON.stringify({
        portfolio_id: portfolioId,
        symbol,
        type,
        shares,
        order_type: 'MARKET',
      }),
    });

    if (tradeResult.error) {
      triggerToast('error', 'Trade Failed', tradeResult.error);
      return;
    }

    triggerToast('success', 'Trade Executed', `${type} ${shares} ${symbol} @ $${price.toLocaleString()}`);

    // Refresh data after trade
    setTimeout(fetchBackendData, 1000);
  }, [cash, fetchBackendData, triggerToast]);

  // Alpha factor management
  const addAlphaFactorToStrategy = useCallback((factorName: string) => {
    setSelectedAlphaFactors(prev => {
      if (prev.includes(factorName)) {
        triggerToast('info', 'Already Added', `${factorName} is already in your strategy.`);
        return prev;
      }
      triggerToast('success', 'Factor Added', `${factorName} added to backtest strategy.`);
      return [...prev, factorName];
    });
  }, [triggerToast]);

  const removeAlphaFactorFromStrategy = useCallback((factorName: string) => {
    setSelectedAlphaFactors(prev => {
      triggerToast('info', 'Factor Removed', `${factorName} removed from strategy.`);
      return prev.filter(f => f !== factorName);
    });
  }, [triggerToast]);

  // Calculate portfolio value
  const portfolioValue = holdings.reduce((sum, h) => sum + (h.shares * h.currentPrice), 0) + cash;
  const activeAgentsCount = agents.filter(a => a.status === 'Running').length;

  // Connection status indicator
  const connectionColor = backendConnected ? '#10B981' : '#EF4444';
  const connectionText = backendConnected ? 'Connected' : 'Disconnected';
  const wsColor = wsConnected ? '#10B981' : '#F59E0B';
  const wsText = wsConnected ? 'Live' : 'Connecting';

  return (
    <div className="min-h-screen bg-[#0F172A] text-[#F8FAFC] font-sans flex flex-col selection:bg-[#3B82F6] selection:text-white pb-8 md:pb-0">

      {/* TOP HEADER */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-[#1E293B] border-b border-[#475569] px-4 flex items-center justify-between z-50">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMobileMenuOpen(prev => !prev)}
            className="p-1.5 hover:bg-[#334155] rounded-md transition md:hidden text-[#94A3B8]"
          >
            <Menu className="w-6 h-6" />
          </button>

          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
            <span className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#3B82F6] to-[#10B981] flex items-center justify-center shadow-lg">
              <Sparkles className="w-5 h-5 text-white" />
            </span>
            <div className="flex flex-col">
              <span className="font-extrabold text-[#F8FAFC] text-md tracking-tight">JASPER</span>
              <span className="text-[10px] text-[#10B981] font-mono leading-none font-semibold">TRADES</span>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="hidden md:flex items-center relative w-[320px] lg:w-[450px]">
          <Search className="w-4 h-4 text-[#94A3B8] absolute left-3" />
          <input
            type="text"
            placeholder="Search commands, symbols, agents..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setShowCommandPalette(true); }}
            onFocus={() => setShowCommandPalette(true)}
            className="w-full bg-[#0F172A] border border-[#475569] rounded-lg h-9 pl-10 pr-12 text-sm focus:outline-none focus:border-[#3B82F6] text-[#F8FAFC] placeholder-[#94A3B8] font-mono"
          />
          <span className="absolute right-3 text-[10px] font-mono border border-[#475569] px-1.5 py-0.5 rounded text-[#94A3B8] bg-[#1E293B]">⌘K</span>
        </div>

        {/* Connection status & Profile */}
        <div className="flex items-center gap-3">
          {/* API Connection */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: connectionColor }} />
            <span className="hidden lg:inline text-[#94A3B8]">{connectionText}</span>
          </div>

          {/* WebSocket Status */}
          <div className="flex items-center gap-2 text-xs font-mono border-l border-[#475569] pl-2">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: wsColor }} />
            <span className="hidden lg:inline text-[#94A3B8]">Price Stream: <span style={{ color: wsColor }}>{wsText}</span></span>
          </div>

          <div className="flex items-center gap-2 pl-2 border-l border-[#475569]">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#3B82F6] to-pink-500 flex items-center justify-center font-extrabold text-sm text-white">
              ET
            </div>
            <div className="hidden lg:flex flex-col text-left">
              <span className="text-xs font-bold text-[#F8FAFC] leading-none">Trader Account</span>
              <span className="text-[10px] text-[#10B981] font-mono font-semibold">Verified</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <div className="pt-16 flex flex-1 h-full relative">

        {/* SIDEBAR */}
        <aside className={`hidden md:flex flex-col bg-[#1E293B] border-r border-[#475569] fixed top-16 bottom-8 z-30 transition-all ${sidebarExpanded ? 'w-60' : 'w-16'}`}>
          <div className="p-3 flex justify-end border-b border-[#475569]">
            <button onClick={() => setSidebarExpanded(prev => !prev)} className="p-1 hover:bg-[#334155] rounded-md text-[#94A3B8]">
              {sidebarExpanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
          </div>

          <nav className="flex-1 p-2 flex flex-col gap-1 overflow-y-auto">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
              { id: 'agents', label: 'Agents config', icon: Bot, badge: `${activeAgentsCount}/4` },
              { id: 'signals', label: 'Signals Feed', icon: Radio, badge: 'Live' },
              { id: 'copytrade', label: 'Copy Trading', icon: Users },
              { id: 'backtest', label: 'Backtests', icon: TrendingUp },
              { id: 'alphazoo', label: 'Alpha Factor Zoo', icon: Compass, badge: '452' },
              { id: 'portfolio', label: 'Portfolio', icon: Briefcase },
              { id: 'settings', label: 'Settings', icon: Settings },
            ].map(item => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => { setActiveTab(item.id); setMobileMenuOpen(false); }}
                  className={`flex items-center h-11 px-3 rounded-lg text-sm transition ${
                    isActive
                      ? 'bg-[#3B82F6]/10 text-[#3B82F6] font-semibold border-l-2 border-[#3B82F6]'
                      : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#334155]'
                  }`}
                >
                  <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-[#3B82F6]' : 'text-[#94A3B8]'}`} />
                  {sidebarExpanded && (
                    <div className="flex-1 flex items-center justify-between ml-3">
                      <span>{item.label}</span>
                      {item.badge && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#0F172A] text-[#94A3B8]">{item.badge}</span>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Mobile menu overlay */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-40 bg-[#0F172A]/80 flex md:hidden" onClick={() => setMobileMenuOpen(false)}>
            <div className="w-64 bg-[#1E293B] border-r border-[#475569] p-4 flex flex-col gap-4" onClick={e => e.stopPropagation()}>
              <div className="flex justify-between items-center pb-3 border-b border-[#475569]">
                <span className="font-bold font-mono text-[#F8FAFC]">Navigation</span>
                <button onClick={() => setMobileMenuOpen(false)}><X className="w-5 h-5 text-[#94A3B8]" /></button>
              </div>
              {[
                { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
                { id: 'agents', label: 'Agents', icon: Bot },
                { id: 'signals', label: 'Signals', icon: Radio },
                { id: 'copytrade', label: 'Copy Trading', icon: Users },
                { id: 'backtest', label: 'Backtests', icon: TrendingUp },
                { id: 'alphazoo', label: 'Alpha Zoo', icon: Compass },
                { id: 'portfolio', label: 'Portfolio', icon: Briefcase },
                { id: 'settings', label: 'Settings', icon: Settings },
              ].map(item => (
                <button
                  key={item.id}
                  onClick={() => { setActiveTab(item.id); setMobileMenuOpen(false); }}
                  className="flex items-center gap-3 p-3 text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#334155] rounded-lg"
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Main Content */}
        <main className={`flex-1 transition-all ${sidebarExpanded ? 'md:pl-60' : 'md:pl-16'} pb-12`}>
          <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto flex flex-col gap-6">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <div className="w-8 h-8 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-[#94A3B8] font-mono text-sm">Loading dashboard...</p>
                </div>
              </div>
            ) : (
              <>
                {activeTab === 'dashboard' && (
                  <DashboardTab cash={cash} holdings={holdings} agents={agents} tradeHistory={tradeHistory} triggerToast={triggerToast} loading={loading} portfolioInitialized={portfolioInitialized} />
                )}
                {activeTab === 'agents' && (
                  <AgentsTab agents={agents} setAgents={setAgents} triggerToast={triggerToast} />
                )}
                {activeTab === 'signals' && (
                  <SignalsTab executeTrade={executeTradeFromSignal} triggerToast={triggerToast} />
                )}
                {activeTab === 'copytrade' && (
                  <CopyTradeTab triggerToast={triggerToast} />
                )}
                {activeTab === 'backtest' && (
                  <BacktestTab selectedAlphaFactors={selectedAlphaFactors} removeAlphaFactor={removeAlphaFactorFromStrategy} triggerToast={triggerToast} setActiveTab={setActiveTab} />
                )}
                {activeTab === 'alphazoo' && (
                  <AlphaZooTab addAlphaFactor={addAlphaFactorToStrategy} triggerToast={triggerToast} />
                )}
                {activeTab === 'portfolio' && (
                  <PortfolioTab cash={cash} setCash={setCash} holdings={holdings} setHoldings={setHoldings} tradeHistory={tradeHistory} triggerToast={triggerToast} />
                )}
                {activeTab === 'settings' && (
                  <SettingsTab onNavigate={setCurrentSettingsTab} initialTab={currentSettingsTab} triggerToast={triggerToast} />
                )}
              </>
            )}
          </div>
        </main>
      </div>

      {/* Footer Status Bar */}
      <footer className="fixed bottom-0 left-0 right-0 h-8 bg-[#0F172A] border-t border-[#475569] px-4 flex items-center justify-between text-xs text-[#94A3B8] font-mono z-40">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: connectionColor }} />
          <span>System: {connectionText}</span>
        </div>
        <div className="hidden md:flex items-center gap-4">
          <span>Agents: {activeAgentsCount} Running</span>
          <span className="border-l border-[#475569] h-3" />
          <span className="text-[#3B82F6]">UTC: {currentTimeStr}</span>
        </div>
        <div>
          <span>Portfolio: </span>
          <span className="font-bold text-[#F8FAFC]">${portfolioValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
      </footer>

      {/* Mobile Bottom Nav */}
      <div className="md:hidden fixed bottom-8 left-4 right-4 h-14 bg-[#1E293B] border border-[#475569] rounded-xl flex items-center justify-around z-40">
        {[
          { id: 'dashboard', label: 'Dash', icon: LayoutDashboard },
          { id: 'agents', label: 'AI', icon: Bot },
          { id: 'signals', label: 'Signals', icon: Radio },
          { id: 'portfolio', label: 'Holdings', icon: Briefcase },
          { id: 'settings', label: 'Config', icon: Settings },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex flex-col items-center justify-center flex-1 h-full ${activeTab === tab.id ? 'text-[#3B82F6]' : 'text-[#94A3B8]'}`}
          >
            <tab.icon className="w-5 h-5 mb-0.5" />
            <span className="text-[10px]">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Toast Notifications */}
      <div className="fixed bottom-10 right-4 flex flex-col gap-2 z-50 max-w-sm w-full pointer-events-none p-4">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-4 rounded-lg shadow-xl flex items-start gap-3 border ${
              toast.type === 'success' ? 'bg-[#1E293B] border-[#10B981] text-white' :
              toast.type === 'error' ? 'bg-[#1E293B] border-[#EF4444] text-white' :
              toast.type === 'warning' ? 'bg-[#1E293B] border-[#F59E0B] text-white' :
              'bg-[#1E293B] border-[#3B82F6] text-white'
            }`}
          >
            <div className="mt-0.5">
              {toast.type === 'success' && <Check className="w-5 h-5 text-[#10B981]" />}
              {toast.type === 'error' && <AlertTriangle className="w-5 h-5 text-[#EF4444]" />}
              {toast.type === 'warning' && <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />}
              {toast.type === 'info' && <Info className="w-5 h-5 text-[#3B82F6]" />}
            </div>
            <div className="flex-1">
              <h4 className="font-bold text-xs uppercase font-mono mb-0.5">{toast.title}</h4>
              <p className="text-xs text-[#94A3B8]">{toast.message}</p>
            </div>
            <button onClick={() => removeToast(toast.id)} className="p-1 hover:bg-[#334155] rounded text-[#94A3B8]">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* AI Chat Widget */}
      <ChatWidget />
    </div>
  );
}