import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { API_URL } from '../../lib/api-client';
import { getOrCreateDeviceId } from '../../lib/deviceFingerprint';

interface AKShareSettingsProps {
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
  paperTradingConfig?: { enabled: boolean; capital: number; currency: string };
  onUpdatePaperTrading?: (updates: Partial<{enabled: boolean; capital: number; currency: string}>) => void;
  onSave?: () => void;
}

interface AKShareConfig {
  enabled: boolean;
  paper_trading: boolean;
  initial_capital: string;
  currency: string;
  connected: boolean;
}

const AKShareSettings: React.FC<AKShareSettingsProps> = ({ triggerToast }) => {
  const [config, setConfig] = useState<AKShareConfig>({
    enabled: false,
    paper_trading: true,
    initial_capital: '1000000',
    currency: 'CNY',
    connected: false,
  });
  const [loading, setLoading] = useState(false);
  const [marketData, setMarketData] = useState<any>(null);
  const [testSymbol, setTestSymbol] = useState('600000');
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'checking' | 'connected'>('disconnected');

  // Load config from backend on mount and poll every 5 seconds
  useEffect(() => {
    loadConfig();
    const interval = setInterval(loadConfig, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadConfig = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const response = await fetch(`${API_URL}/api/v1/settings/akshare`, {
        headers: { 'X-Device-ID': deviceId },
      });

      if (response.ok) {
        const data = await response.json();
        setConfig(data);

        // Check backend connectivity when enabled
        if (data.enabled) {
          setConnectionStatus('checking');
          try {
            const statusResponse = await fetch(`${API_URL}/api/v1/akshare/status`);
            if (statusResponse.ok) {
              const status = await statusResponse.json();
              setConnectionStatus(status.connected ? 'connected' : 'disconnected');
            } else {
              setConnectionStatus('disconnected');
            }
          } catch {
            setConnectionStatus('disconnected');
          }
        } else {
          setConnectionStatus('disconnected');
        }
      }
    } catch (error) {
      console.error('Failed to load AKShare settings:', error);
      setConnectionStatus('disconnected');
    }
  };

  const saveConfig = async () => {
    setLoading(true);
    try {
      const deviceId = getOrCreateDeviceId();
      const response = await fetch(`${API_URL}/api/v1/settings/akshare`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(config),
      });

      if (response.ok) {
        triggerToast('success', 'AKShare Saved', 'Chinese stock trading configured');
        setConfig({ ...config, connected: true });
        setTimeout(loadConfig, 1000);
      } else {
        triggerToast('error', 'Failed', 'Could not save AKShare settings');
      }
    } catch {
      triggerToast('error', 'Failed', 'Error saving AKShare settings');
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/akshare/market-data?symbol=${testSymbol}&exchange=SSE`
      );

      if (response.ok) {
        const data = await response.json();
        setMarketData(data);
        triggerToast('success', 'Connection OK', `Fetched data for ${testSymbol}`);
      } else {
        triggerToast('error', 'Failed', 'Could not fetch market data');
      }
    } catch {
      triggerToast('error', 'Failed', 'Error testing AKShare connection');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with Live Connection Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-[#DC143C]" />
          <h3 className="text-md font-semibold text-white">Chinese Stocks (AKShare)</h3>
        </div>
        <div className="flex items-center gap-2">
          {connectionStatus === 'checking' && (
            <>
              <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
              <span className="text-xs px-2 py-1 rounded bg-yellow-500/20 text-yellow-400">Checking...</span>
            </>
          )}
          {connectionStatus === 'connected' && (
            <>
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">Connected</span>
            </>
          )}
          {connectionStatus === 'disconnected' && (
            <>
              <XCircle className="w-4 h-4 text-red-400" />
              <span className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400">Disconnected</span>
            </>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="p-3 bg-[#DC143C]/10 rounded-lg border border-[#DC143C]/30">
        <div className="flex items-start gap-3">
          <div className="text-2xl">🇨🇳</div>
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-white mb-1">China A-Shares & B-Shares Trading</h4>
            <p className="text-xs text-gray-400">
              Access Shanghai (SSE) and Shenzhen (SZSE) stock exchanges. Paper trading enabled by default.
            </p>
            {connectionStatus === 'connected' && (
              <p className="text-xs text-green-400 mt-2 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Backend AKShare service is running and reachable
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Settings Form */}
      <div className="space-y-3">
        {/* Enable AKShare */}
        <div className="flex items-center justify-between">
          <label htmlFor="akshareEnabled" className="text-sm text-gray-300">Enable Chinese Stock Trading</label>
          <button
            id="akshareEnabled"
            onClick={() => setConfig({ ...config, enabled: !config.enabled })}
            className={`relative w-12 h-6 rounded-full transition-colors ${config.enabled ? 'bg-[#DC143C]' : 'bg-gray-600'}`}
          >
            <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${config.enabled ? 'left-7' : 'left-1'}`} />
          </button>
        </div>

        {/* Paper Trading Toggle */}
        <div className="flex items-center justify-between">
          <label htmlFor="aksharePaperTrading" className="text-sm text-gray-300">Paper Trading Mode</label>
          <button
            id="aksharePaperTrading"
            onClick={() => setConfig({ ...config, paper_trading: !config.paper_trading })}
            className={`relative w-12 h-6 rounded-full transition-colors ${config.paper_trading ? 'bg-[#DC143C]' : 'bg-gray-600'}`}
          >
            <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${config.paper_trading ? 'left-7' : 'left-1'}`} />
          </button>
        </div>

        {/* Initial Capital */}
        <div>
          <label htmlFor="akshareCapital" className="text-sm text-gray-300 block mb-1">Paper Trading Capital (CNY)</label>
          <input
            id="akshareCapital"
            type="number"
            value={config.initial_capital}
            onChange={(e) => setConfig({ ...config, initial_capital: e.target.value })}
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:border-[#DC143C] focus:ring-1 focus:ring-[#DC143C]"
            placeholder="1000000"
          />
          <p className="text-xs text-gray-500 mt-1">
            {config.initial_capital && parseInt(config.initial_capital) > 0 ? (
              <span className="text-green-400">✓ Value set: ¥{parseInt(config.initial_capital).toLocaleString()} CNY</span>
            ) : (
              'Enter initial capital for paper trading'
            )}
          </p>
        </div>

        {/* Currency */}
        <div>
          <label htmlFor="akshareCurrency" className="text-sm text-gray-300 block mb-1">Trading Currency</label>
          <select
            id="akshareCurrency"
            value={config.currency}
            onChange={(e) => setConfig({ ...config, currency: e.target.value })}
            className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:border-[#DC143C] focus:ring-1 focus:ring-[#DC143C]"
          >
            <option value="CNY">CNY (Chinese Yuan) - A-shares</option>
            <option value="USD">USD (US Dollar) - B-shares SSE</option>
            <option value="HKD">HKD (HK Dollar) - B-shares SZSE</option>
          </select>
          <p className="text-xs text-gray-500 mt-1">
            {config.currency === 'CNY' && '✓ A-shares traded in Chinese Yuan'}
            {config.currency === 'USD' && '✓ B-shares (Shanghai) traded in USD'}
            {config.currency === 'HKD' && '✓ B-shares (Shenzhen) traded in HKD'}
          </p>
        </div>
      </div>

      {/* Test Connection */}
      <div className="pt-3 border-t border-[#475569]">
        <label htmlFor="akshareTestSymbol" className="text-sm text-gray-300 block mb-2">Test Market Data Connection</label>
        <div className="flex gap-2 mb-2">
          <input
            id="akshareTestSymbol"
            type="text"
            value={testSymbol}
            onChange={(e) => setTestSymbol(e.target.value)}
            className="flex-1 bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:border-[#DC143C] focus:ring-1 focus:ring-[#DC143C]"
            placeholder="600000"
          />
          <button
            onClick={testConnection}
            disabled={loading || connectionStatus !== 'connected'}
            className="px-4 py-2 bg-[#DC143C] hover:bg-[#C41230] text-white rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            Test
          </button>
        </div>

        {marketData && (
          <div className="mt-2 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-white">{marketData.name} ({marketData.symbol})</h4>
              <span className={`text-sm font-bold ${marketData.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ¥{marketData.current?.toFixed(2)} ({marketData.change >= 0 ? '+' : ''}{marketData.change_pct?.toFixed(2)}%)
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div><span className="text-gray-400">Open:</span><span className="text-white ml-2">¥{marketData.open?.toFixed(2)}</span></div>
              <div><span className="text-gray-400">High:</span><span className="text-white ml-2">¥{marketData.high?.toFixed(2)}</span></div>
              <div><span className="text-gray-400">Low:</span><span className="text-white ml-2">¥{marketData.low?.toFixed(2)}</span></div>
              <div><span className="text-gray-400">Prev Close:</span><span className="text-white ml-2">¥{marketData.close?.toFixed(2)}</span></div>
              <div><span className="text-gray-400">Volume:</span><span className="text-white ml-2">{marketData.volume?.toLocaleString()}</span></div>
              <div><span className="text-gray-400">Turnover:</span><span className="text-white ml-2">¥{marketData.amount?.toLocaleString()}</span></div>
            </div>
            <p className="text-xs text-green-400 mt-2 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Live data fetched successfully
            </p>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 pt-3 border-t border-[#475569]">
        <button
          onClick={saveConfig}
          disabled={loading}
          className="flex-1 py-2 bg-[#DC143C] hover:bg-[#C41230] text-white rounded-md text-sm disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          Save Settings
        </button>
      </div>

      {/* Quick Reference */}
      <div className="mt-3 p-3 bg-[#0F172A] rounded-lg border border-[#475569]">
        <h5 className="text-white font-semibold mb-2 text-sm flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Popular Chinese Stocks:
        </h5>
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
          <div className="flex justify-between"><span>600000</span><span className="text-gray-300">Shanghai Pudong Dev Bank</span></div>
          <div className="flex justify-between"><span>600036</span><span className="text-gray-300">China Merchants Bank</span></div>
          <div className="flex justify-between"><span>000001</span><span className="text-gray-300">Ping An Bank</span></div>
          <div className="flex justify-between"><span>000002</span><span className="text-gray-300">China Vanke</span></div>
          <div className="flex justify-between"><span>688981</span><span className="text-gray-300">SMIC (Semiconductor)</span></div>
          <div className="flex justify-between"><span>300750</span><span className="text-gray-300">CATL (Batteries)</span></div>
        </div>
      </div>
    </div>
  );
};

export default AKShareSettings;