'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import {
  Home as HomeIcon, Briefcase, TrendingUp, Radio, Settings as SettingsIcon,
  Compass, Microscope, Sun, Moon, Coins, Bell, X, Menu,
} from 'lucide-react';
import { usePriceStream } from '@/hooks/usePriceStream';
import { usePortfolioHistory } from '@/hooks/usePortfolioHistory';

import { useCurrency } from '@/lib/currencyContext';
import { fetchTradingMode } from '@/lib/preferences';
import { useTheme } from '@/lib/theme';
import { Holding, TradeHistoryItem, Toast, WatchedEntry } from '@/app/types';
import { Badge } from '@/components/ui';
import ChatWidget from '@/components/ChatWidget';
import { OnboardingProvider } from '@/components/onboarding/OnboardingProvider';
import OnboardingTour from '@/components/onboarding/OnboardingTour';
import WelcomeWizard from '@/components/onboarding/WelcomeWizard';
import HomeScreen from '@/components/screens/HomeScreen';
import TradesScreen from '@/components/screens/TradesScreen';
import MarketsScreen from '@/components/screens/MarketsScreen';
import SignalsScreen from '@/components/screens/SignalsScreen';
import SettingsScreen, { StepId } from '@/components/screens/SettingsScreen';
import BacktestScreen from '@/components/screens/BacktestScreen';
import AlphaZooScreen from '@/components/screens/AlphaZooScreen';

import { apiRequest } from '@/lib/api-client';

const PRIMARY_TABS = [
  { id: 'home', label: 'Home', icon: HomeIcon },
  { id: 'trades', label: 'Trades', icon: Briefcase },
  { id: 'markets', label: 'Markets', icon: TrendingUp },
  { id: 'signals', label: 'Signals', icon: Radio },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
] as const;

const ADVANCED_TABS = [
  { id: 'backtest', label: 'Backtesting', icon: Microscope },
  { id: 'alphazoo', label: 'Alpha Zoo', icon: Compass },
] as const;

export default function Home() {
  const [activeTab, setActiveTab] = useState<string>('home');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsDefaultOpen, setSettingsDefaultOpen] = useState<StepId | null>(null);
  const [tradingMode, setTradingMode] = useState<'practice' | 'live' | null>(null);

const [cash, setCash] = useState<number>(0);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [tradeHistory, setTradeHistory] = useState<TradeHistoryItem[]>([]);
  const [watched, setWatched] = useState<WatchedEntry[]>([]);
  const [factorStats, setFactorStats] = useState<{ traded: number; watching: number }>({ traded: 0, watching: 0 });
  const [portfolioInitialized, setPortfolioInitialized] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [backendConnected, setBackendConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
const [, setWsStatus] = useState<string>('disconnected');
  const [selectedAlphaFactors, setSelectedAlphaFactors] = useState<{id: string; name: string}[]>([]);
  const [portfolioId, setPortfolioId] = useState<number | null>(null);

  usePriceStream({
    onPriceUpdate: (update) => {
      setHoldings(prev => prev.map(h =>
        h.symbol === update.symbol
          ? { ...h, currentPrice: update.price, pnlPercent: ((update.price - h.avgPrice) / h.avgPrice) * 100 }
          : h
      ));
    },
    onStatusChange: setWsStatus,
  });

  const { data: portfolioHistory } = usePortfolioHistory({ portfolioId: portfolioId || 1, period: '1m', refreshInterval: 30000 });

  const triggerToast = useCallback((type: Toast['type'], title: string, message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, type, title, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const removeToast = useCallback((id: string) => setToasts(prev => prev.filter(t => t.id !== id)), []);

  useEffect(() => {
    fetchTradingMode().then(setTradingMode);
  }, [activeTab, settingsDefaultOpen]);

  const fetchFactorData = useCallback(async () => {
    try {
      const [signalsRes, statsRes] = await Promise.all([
        apiRequest<any>('/api/v1/factor-trading/signals'),
        apiRequest<any>('/api/v1/factor-trading/stats'),
      ]);
      if (signalsRes.data?.watching) setWatched(signalsRes.data.watching as WatchedEntry[]);
      if (statsRes.data) {
        setFactorStats({
          traded: statsRes.data.trades_taken ?? 0,
          watching: statsRes.data.watching ?? watched.length,
        });
      }
    } catch {
      // Silently ignore — non-critical data
    }
  }, [watched.length]);

const fetchBackendData = useCallback(async () => {
    setLoading(true);
    try {
      // Try status endpoint first, fall back to health if it fails
      const statusResult = await apiRequest<any>('/api/v1/status');
      if (!statusResult.data) {
        const healthResult = await apiRequest<any>('/api/v1/health');
        setBackendConnected(!!healthResult.data);
      } else {
        setBackendConnected(true);
      }

      // Backend returns a single portfolio summary object (not an array).
      const portfolioResult = await apiRequest<any>('/api/v1/portfolio');
      if (portfolioResult.data && portfolioResult.data.id) {
        const pid = portfolioResult.data.id;
        setPortfolioId(pid);
        setCash(portfolioResult.data.cash || 0);

        const initRes = await apiRequest<any>(`/api/v1/portfolio/${pid}/initialization-status`);
        if (initRes.data) setPortfolioInitialized(!!initRes.data.is_initialized);

        const hRes = await apiRequest<any>(`/api/v1/portfolio/${pid}/holdings`);
        if (hRes.data) {
          const arr = Array.isArray(hRes.data) ? hRes.data : (hRes.data.holdings || []);
          setHoldings(arr.map((h: any) => ({
            symbol: h.symbol, name: h.name || h.symbol, type: h.type || 'Stock',
            shares: h.shares || h.quantity || 0, avgPrice: h.avg_price || 0,
            currentPrice: h.current_price || h.avg_price || 0, pnlPercent: h.pnl_percent || h.unrealized_pnl_percent || 0,
          })));
        }
        const tRes = await apiRequest<any>(`/api/v1/trading/history?limit=30`);
        if (tRes.data) {
          const trades = tRes.data.trades || tRes.data || [];
          setTradeHistory(trades.map((t: any) => ({
            id: t.id, date: new Date(t.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
            type: (t.side || t.type || '').toUpperCase(), symbol: t.symbol, side: (t.side === 'buy' ? 'Long' : 'Short') as 'Long' | 'Short', shares: t.quantity || t.shares || 0, price: t.price || 0, total: t.pnl != null ? t.pnl : ((t.quantity || 0) * (t.price || 0)), agent: t.agent_name || 'System',
          })));
        }
      }
    } catch {
      setBackendConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshBackendData = useCallback(async () => {
    try {
      const pid = portfolioId;
      if (!pid) {
        const portfolioResult = await apiRequest<any>('/api/v1/portfolio');
        if (portfolioResult.data?.id) {
          setPortfolioId(portfolioResult.data.id);
          setCash(portfolioResult.data.cash || 0);
        }
        return;
      }
      const fresh = await apiRequest<any>(`/api/v1/portfolio/${pid}`);
      if (fresh.data) setCash(prev => Math.abs(prev - (fresh.data.cash || 0)) > 0.01 ? (fresh.data.cash || 0) : prev);
      const hRes = await apiRequest<any>(`/api/v1/portfolio/${pid}/holdings`);
      const arr = hRes.data ? (Array.isArray(hRes.data) ? hRes.data : (hRes.data.holdings || [])) : [];
      const next = arr.map((h: any) => ({
        symbol: h.symbol, name: h.name || h.symbol, type: h.type || 'Stock',
        shares: h.shares || h.quantity || 0, avgPrice: h.avg_price || 0,
        currentPrice: h.current_price || h.avg_price || 0, pnlPercent: h.pnl_percent || h.unrealized_pnl_percent || 0,
      }));
      setHoldings(prev => JSON.stringify(prev) !== JSON.stringify(next) ? next : prev);
      const tRes = await apiRequest<any>(`/api/v1/trading/history?limit=30`);
      if (tRes.data) {
        const trades = (tRes.data.trades || tRes.data) || [];
        const next = trades.slice(0, 30).map((t: any) => ({
          id: t.id, date: new Date(t.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
          type: (t.side || t.type || '').toUpperCase(), symbol: t.symbol, side: (t.side === 'buy' ? 'Long' : 'Short') as 'Long' | 'Short', shares: t.quantity || t.shares || 0, price: t.price || 0, total: t.pnl || t.total || 0, agent: t.agent_name || 'System',
        }));
        setTradeHistory(prev => JSON.stringify(prev) !== JSON.stringify(next) ? next : prev);
      }
      const statusResult = await apiRequest<any>('/api/v1/status');
      setBackendConnected(!!statusResult.data);
    } catch {
      /* silent */
    }
  }, [portfolioId]);

  useEffect(() => {
    fetchBackendData();
    fetchFactorData();
    const t = setInterval(() => { refreshBackendData(); fetchFactorData(); }, 15000);
    return () => clearInterval(t);
  }, [fetchBackendData, refreshBackendData, fetchFactorData]);

const addAlphaFactor = useCallback((factor: {id: string; name: string}) => {
    setSelectedAlphaFactors(prev => {
      if (prev.some(f => f.id === factor.id)) { triggerToast('info', 'Already added', `${factor.name} is in your strategy.`); return prev; }
      triggerToast('success', 'Factor added', `${factor.name} added to backtest strategy.`);
      return [...prev, factor];
    });
  }, [triggerToast]);

  const removeAlphaFactor = useCallback((id: string) => {
    setSelectedAlphaFactors(prev => { const f = prev.find(x => x.id === id); triggerToast('info', 'Factor removed', `${f?.name || id} removed.`); return prev.filter(x => x.id !== id); });
  }, [triggerToast]);


  const { currency, toggleCurrency } = useCurrency();
  const { theme, toggleTheme } = useTheme();

  const nav = (t: string, opts?: { defaultOpen?: StepId }) => {
    if (t === 'settings' && opts?.defaultOpen) setSettingsDefaultOpen(opts.defaultOpen);
    setActiveTab(t);
    setSidebarOpen(false);
  };

  // Handle cTrader OAuth callback redirect (?ctrader_connected=true&id=… / ?ctrader_error=…)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const connected = params.get('ctrader_connected');
    const error = params.get('ctrader_error');
    const id = params.get('id');
    if (connected === 'true') {
      triggerToast('success', 'cTrader Connected', `Account connected for auto-trading${id ? ` (id ${id})` : ''}.`);
      setActiveTab('settings');
      setSettingsDefaultOpen('wallet');
    } else if (error) {
      triggerToast('error', 'cTrader Connection Failed', decodeURIComponent(error));
    }
    if (connected || error) {
      window.history.replaceState({}, '', window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  let content: React.ReactNode;
  switch (activeTab) {
case 'trades':
      content = <TradesScreen cash={cash} holdings={holdings} tradeHistory={tradeHistory} watched={watched} factorStats={factorStats} loading={loading} portfolioInitialized={portfolioInitialized} onNavigate={nav} triggerToast={triggerToast} />;
      break;
    case 'markets':
      content = <MarketsScreen onNavigate={nav} triggerToast={triggerToast} />;
      break;
    case 'signals':
      content = <SignalsScreen triggerToast={triggerToast} />;
      break;
    case 'settings':
      content = <SettingsScreen triggerToast={triggerToast} onNavigate={nav} defaultOpen={settingsDefaultOpen} onDefaultOpenConsumed={() => setSettingsDefaultOpen(null)} />;
      break;
    case 'backtest':
      content = <BacktestScreen selectedAlphaFactors={selectedAlphaFactors} removeAlphaFactor={removeAlphaFactor} triggerToast={triggerToast} onNavigate={nav} />;
      break;
    case 'alphazoo':
      content = <AlphaZooScreen addAlphaFactor={addAlphaFactor} triggerToast={triggerToast} />;
      break;
    case 'home':
    default:
      content = (
        <HomeScreen
          cash={cash}
          holdings={holdings}
          tradeHistory={tradeHistory}
          equityData={portfolioHistory?.equity || []}
          portfolioInitialized={portfolioInitialized}
          loading={loading}
          triggerToast={triggerToast}
          onNavigate={nav}
        />
      );
  }

  return (
    <OnboardingProvider>
      <div className="min-h-dvh bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        {/* ===== Mobile top bar ===== */}
<header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-slate-200 bg-white/85 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/85 md:hidden">
          <div className="flex items-center gap-2">
            <button onClick={() => setSidebarOpen(true)} aria-label="Open menu" className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
              <Menu className="h-5 w-5" />
            </button>
            <Image src="/logo.png" alt="Jasper" width={28} height={28} className="h-7 w-7 object-contain" />
            <span className="font-display text-base font-bold tracking-tight">Jasper</span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={toggleTheme} aria-label="Toggle theme" className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
              {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            <button onClick={toggleCurrency} className="rounded-full px-2.5 py-1.5 text-xs font-semibold text-brand-600 dark:text-brand-300">{currency}</button>
          </div>
</header>

        {/* ===== Mobile sidebar drawer ===== */}
        <div className={`fixed inset-0 z-[60] md:hidden ${sidebarOpen ? '' : 'pointer-events-none'}`}>
          <div
            className={`absolute inset-0 bg-slate-950/50 transition-opacity duration-200 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
          <aside
            className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col border-r border-slate-200 bg-white shadow-card transition-transform duration-200 dark:border-slate-800 dark:bg-slate-900 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
          >
            <div className="flex items-center justify-between px-5 pb-4 pt-5">
              <div className="flex items-center gap-2.5">
                <Image src="/logo.png" alt="Jasper" width={32} height={32} className="h-8 w-8 object-contain" />
                <div>
                  <p className="font-display text-base font-bold leading-none tracking-tight">Jasper</p>
                  <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300">AI Trader</p>
                </div>
              </div>
              <button onClick={() => setSidebarOpen(false)} aria-label="Close menu" className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
              <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Main</p>
              {PRIMARY_TABS.map(t => {
                const active = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => nav(t.id)}
                    className={`flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition ${
                      active
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    <t.icon className="h-[18px] w-[18px]" />
                    {t.label}
                  </button>
                );
              })}

              <div className="pt-4">
                <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">For pros</p>
                {ADVANCED_TABS.map(t => {
                  const active = activeTab === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => nav(t.id)}
                      className={`flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition ${
                        active
                          ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                          : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                      }`}
                    >
                      <t.icon className="h-[18px] w-[18px]" />
                      {t.label}
                    </button>
                  );
                })}
              </div>

              <div className="space-y-1 border-t border-slate-100 pt-3 dark:border-slate-800">
                <button onClick={toggleTheme} className="flex w-full items-center justify-between rounded-control px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
                  <span className="flex items-center gap-2">{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />} Theme</span>
                  <span className="text-xs capitalize text-slate-400">{theme}</span>
                </button>
                <button onClick={toggleCurrency} className="flex w-full items-center justify-between rounded-control px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
                  <span className="flex items-center gap-2"><Coins className="h-4 w-4" /> Currency</span>
                  <span className="text-xs font-semibold text-brand-600 dark:text-brand-300">{currency}</span>
                </button>
              </div>
            </nav>
          </aside>
        </div>

        <div className="mx-auto flex w-full max-w-shell">
          {/* ===== Desktop sidebar ===== */}
          <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 md:flex">
            <div className="flex items-center gap-2.5 px-6 pb-6 pt-6">
              <Image src="/logo.png" alt="Jasper" width={36} height={36} className="h-9 w-9 object-contain" />
              <div>
                <p className="font-display text-lg font-bold leading-none tracking-tight">Jasper</p>
                <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.18em] text-brand-600 dark:text-brand-300">AI Trader</p>
              </div>
            </div>

            <nav className="flex-1 space-y-1 overflow-y-auto px-3">
              <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Main</p>
              {PRIMARY_TABS.map(t => {
                const active = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => nav(t.id)}
                    className={`flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition ${
                      active
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    <t.icon className="h-[18px] w-[18px]" />
                    {t.label}
                  </button>
                );
              })}

              <div className="pt-4">
                <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">For pros</p>
                {ADVANCED_TABS.map(t => {
                  const active = activeTab === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => nav(t.id)}
                      className={`flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition ${
                        active
                          ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                          : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                      }`}
                    >
                      <t.icon className="h-[18px] w-[18px]" />
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </nav>

            <div className="space-y-2 border-t border-slate-100 px-4 py-4 dark:border-slate-800">
              <button onClick={toggleTheme} className="flex w-full items-center justify-between rounded-control px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
                <span className="flex items-center gap-2">{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />} Theme</span>
                <span className="text-xs capitalize text-slate-400">{theme}</span>
              </button>
              <button onClick={toggleCurrency} className="flex w-full items-center justify-between rounded-control px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">
                <span className="flex items-center gap-2"><Coins className="h-4 w-4" /> Currency</span>
                <span className="text-xs font-semibold text-brand-600 dark:text-brand-300">{currency}</span>
              </button>
            </div>
          </aside>

          {/* ===== Main column ===== */}
          <div className="flex min-w-0 flex-1 flex-col">
            {/* Desktop top bar */}
            <header className="sticky top-0 z-30 hidden h-14 items-center justify-between border-b border-slate-200 bg-white/85 px-8 backdrop-blur dark:border-slate-800 dark:bg-slate-900/85 md:flex">
              <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                <Bell className="h-4 w-4" />
                <span>Jasper keeps you updated in the chat bubble.</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  <span className={`h-1.5 w-1.5 rounded-full ${backendConnected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  {backendConnected ? 'Connected' : 'Offline'}
                </span>
                <Badge tone={tradingMode === 'live' ? 'accent' : 'up'}>
                  {tradingMode === 'live' ? 'Live' : 'Practice'}
                </Badge>
              </div>
            </header>

            <main className="flex-1 px-4 py-6 sm:px-6 md:px-8 md:py-8">
              <div className="mx-auto w-full max-w-5xl">
                {content}
              </div>
            </main>
          </div>
        </div>

        {/* ===== Mobile bottom nav ===== */}
        <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur dark:border-slate-800 dark:bg-slate-900/95 md:hidden">
          <div className="grid grid-cols-5">
            {PRIMARY_TABS.map(t => {
              const active = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => nav(t.id)}
                  className={`flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium transition ${active ? 'text-brand-600 dark:text-brand-300' : 'text-slate-400 dark:text-slate-500'}`}
                >
                  <t.icon className="h-5 w-5" />
                  {t.label}
                </button>
              );
            })}
          </div>
        </nav>

        {/* ===== Mobile advanced drawer trigger ===== */}
        {(activeTab === 'backtest' || activeTab === 'alphazoo') && (
          <button
            onClick={() => nav('settings')}
            className="fixed bottom-20 right-4 z-30 rounded-full bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white shadow-card dark:bg-slate-800 md:hidden"
          >
            Back to app
          </button>
        )}

        {/* ===== Toasts ===== */}
        <div className="pointer-events-none fixed inset-x-0 top-0 z-[70] flex flex-col items-center gap-2 p-4 sm:items-end sm:pr-6">
          {toasts.map(t => (
            <div
              key={t.id}
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-card border bg-white px-4 py-3 shadow-pop dark:bg-slate-900 animate-fade-up"
              style={{ borderColor: t.type === 'success' ? '#10b981' : t.type === 'error' ? '#e11d48' : t.type === 'warning' ? '#f59e0b' : '#14b8a6' }}
            >
              <p className="mt-0.5 text-sm font-semibold text-slate-900 dark:text-slate-50">{t.title}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{t.message}</p>
              <button onClick={() => removeToast(t.id)} className="ml-auto rounded-full p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"><X className="h-4 w-4" /></button>
            </div>
          ))}
        </div>

        <ChatWidget />
        <WelcomeWizard />
        <OnboardingTour activePage={activeTab} enabled />
      </div>
    </OnboardingProvider>
  );
}
