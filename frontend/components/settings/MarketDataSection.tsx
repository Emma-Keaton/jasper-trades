'use client';

import { useState } from 'react';
import { TrendingUp, Check, Info, ExternalLink } from 'lucide-react';
import { Toast } from '@/app/types';
import InfoModal from './InfoModal';
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';
import { apiFetch } from '@/lib/api-client';

interface MarketDataSettings {
  alphavantage_key: string;
  finnhub_key: string;
  twelvedata_key: string;
  polygon_key: string;
  fred_key: string;
  coingecko_enabled: boolean;
}

interface MarketDataSectionProps {
  marketData: MarketDataSettings;
  setMarketData: (settings: MarketDataSettings) => void;
  triggerToast: (type: Toast['type'], title: string, message: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function MarketDataSection({ marketData, setMarketData, triggerToast }: MarketDataSectionProps) {
  const [showAlphavantageModal, setShowAlphavantageModal] = useState(false);
  const [showFinnhubModal, setShowFinnhubModal] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { valid: boolean; message: string }>>({});

  const saveMarketDataKeys = async () => {
    try {
      const deviceId = getOrCreateDeviceId();
      const res = await apiFetch(`${API_URL}/api/v1/settings/market-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(marketData),
      });

      if (res.ok) {
        triggerToast('success', 'Market Data Saved', 'Your API keys have been configured');
      } else {
        const data = await res.json();
        triggerToast('error', 'Save Failed', data.detail || 'Could not save settings');
      }
    } catch {
      triggerToast('error', 'Save Failed', 'Could not save market data settings');
    }
  };

  const testConnection = async (service: string) => {
    setTesting(service);
    try {
      const key = service === 'alphavantage' ? marketData.alphavantage_key :
                  service === 'finnhub' ? marketData.finnhub_key :
                  service === 'twelvedata' ? marketData.twelvedata_key :
                  service === 'polygon' ? marketData.polygon_key :
                  service === 'fred' ? marketData.fred_key : '';

      const res = await apiFetch(`${API_URL}/api/v1/settings/market-data/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service, key }),
      });

      const result = await res.json();
      setTestResults(prev => ({
        ...prev,
        [service]: { valid: result.valid, message: result.message }
      }));

      if (result.valid) {
        triggerToast('success', 'Connection OK', result.message);
      } else {
        triggerToast('error', 'Connection Failed', result.message);
      }
    } catch {
      setTestResults(() => ({
        [service]: { valid: false, message: 'Connection failed' }
      }));
      triggerToast('error', 'Test Failed', 'Could not test connection');
    } finally {
      setTesting(null);
    }
  };

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Market Data Providers</h2>
        </div>
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Configure free market data APIs for real-time prices, news, and sentiment.
        CoinGecko works immediately - no API key needed!
      </p>

      {/* CoinGecko - Always Available */}
      <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-500" />
            <h3 className="text-sm font-semibold text-white">CoinGecko</h3>
          </div>
          <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">
            ✓ Active (Free, No Key)
          </span>
        </div>
        <p className="text-xs text-gray-400">
          Real-time cryptocurrency prices, market caps, volume, gainers/losers, and trending coins.
        </p>
      </div>

      {/* Alpha Vantage */}
      <div className="border-t border-[#475569] pt-4 mt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">Alpha Vantage</span>
            <button onClick={() => setShowAlphavantageModal(true)} className="p-1 hover:bg-[#334155] rounded text-[#94A3B8]">
              <Info className="w-4 h-4" />
            </button>
          </div>
          {testResults.alphavantage && (
            <span className={`text-xs px-2 py-1 rounded ${testResults.alphavantage.valid ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
              {testResults.alphavantage.valid ? 'Connected' : 'Failed'}
            </span>
          )}
        </div>
        <input
          type="password"
          value={marketData.alphavantage_key}
          onChange={(e) => setMarketData({...marketData, alphavantage_key: e.target.value})}
          placeholder="Enter API key..."
          className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm mb-2"
        />
        <div className="flex gap-2">
          <button
            onClick={() => testConnection('alphavantage')}
            disabled={!marketData.alphavantage_key || testing === 'alphavantage'}
            className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] disabled:opacity-50 text-white rounded-md text-sm"
          >
            {testing === 'alphavantage' ? 'Testing...' : 'Test'}
          </button>
        </div>

        <InfoModal title="Alpha Vantage - Setup Guide" open={showAlphavantageModal} onClose={() => setShowAlphavantageModal(false)}>
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold text-white mb-2">What is Alpha Vantage?</h4>
              <p className="text-gray-300">
                Free financial data API providing real-time stock quotes, forex rates, crypto prices, 
                and news sentiment. Perfect for expanding Jasper&apos;s market data beyond CoinGecko.
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-2">Free Tier Limits</h4>
              <ul className="text-gray-300 space-y-1">
                <li>• 5 API calls per minute</li>
                <li>• 500 API calls per day</li>
                <li>• Stocks, forex, crypto, indicators</li>
                <li>• News sentiment analysis</li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-2">How to Get Your API Key</h4>
              <div className="space-y-3">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">1</div>
                  <div>
                    Go to{' '}
                    <a href="https://www.alphavantage.co/support/#api-key" target="_blank" className="text-blue-400 hover:underline flex items-center gap-1">
                      Alpha Vantage API Key Page
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">2</div>
                  <div>Enter your email address (no credit card required)</div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">3</div>
                  <div>Click &quot;Get API Key&quot; - you&apos;ll receive it instantly on screen</div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">4</div>
                  <div>Copy the key and paste it above</div>
                </div>
              </div>
            </div>

            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
              <h4 className="font-semibold text-blue-400 mb-2">What You Get:</h4>
              <ul className="text-gray-300 space-y-1 text-xs">
                <li>• Real-time US stock prices</li>
                <li>• Forex exchange rates (150+ currencies)</li>
                <li>• Crypto prices (Bitcoin, Ethereum, etc.)</li>
                <li>• News sentiment analysis (bullish/bearish)</li>
                <li>• Technical indicators (RSI, MACD, etc.)</li>
              </ul>
            </div>
          </div>
        </InfoModal>
      </div>

      {/* Finnhub */}
      <div className="border-t border-[#475569] pt-4 mt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">Finnhub</span>
            <button onClick={() => setShowFinnhubModal(true)} className="p-1 hover:bg-[#334155] rounded text-[#94A3B8]">
              <Info className="w-4 h-4" />
            </button>
          </div>
          {testResults.finnhub && (
            <span className={`text-xs px-2 py-1 rounded ${testResults.finnhub.valid ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
              {testResults.finnhub.valid ? 'Connected' : 'Failed'}
            </span>
          )}
        </div>
        <input
          type="password"
          value={marketData.finnhub_key}
          onChange={(e) => setMarketData({...marketData, finnhub_key: e.target.value})}
          placeholder="Enter API key..."
          className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm mb-2"
        />
        <div className="flex gap-2">
          <button
            onClick={() => testConnection('finnhub')}
            disabled={!marketData.finnhub_key || testing === 'finnhub'}
            className="flex-1 py-2 bg-[#1E293B] border border-[#475569] hover:bg-[#334155] disabled:opacity-50 text-white rounded-md text-sm"
          >
            {testing === 'finnhub' ? 'Testing...' : 'Test'}
          </button>
        </div>

        <InfoModal title="Finnhub - Setup Guide" open={showFinnhubModal} onClose={() => setShowFinnhubModal(false)}>
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold text-white mb-2">What is Finnhub?</h4>
              <p className="text-gray-300">
                Real-time stock market data API with institutional-grade quality. 
                Provides stock quotes, company news, insider transactions, and social sentiment.
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-2">Free Tier Limits</h4>
              <ul className="text-gray-300 space-y-1">
                <li>• 60 API calls per minute</li>
                <li>• Real-time stock quotes</li>
                <li>• Company news & filings</li>
                <li>• Insider transactions</li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-2">How to Get Your API Key</h4>
              <div className="space-y-3">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">1</div>
                  <div>
                    Go to{' '}
                    <a href="https://finnhub.io/dashboard" target="_blank" className="text-blue-400 hover:underline flex items-center gap-1">
                      Finnhub Dashboard
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">2</div>
                  <div>Sign up for free (email + password)</div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">3</div>
                  <div>Your API key is shown on the dashboard immediately</div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">4</div>
                  <div>Copy the key and paste it above</div>
                </div>
              </div>
            </div>

            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
              <h4 className="font-semibold text-blue-400 mb-2">What You Get:</h4>
              <ul className="text-gray-300 space-y-1 text-xs">
                <li>• Real-time US stock quotes (NYSE, NASDAQ)</li>
                <li>• Company news feed</li>
                <li>• SEC filings (10-K, 10-Q, 8-K)</li>
                <li>• Insider transactions</li>
                <li>• Social sentiment from Reddit/Twitter</li>
              </ul>
            </div>
          </div>
        </InfoModal>
      </div>

      {/* Twelve Data -->
      <div className="border-t border-[#475569] pt-4 mt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">Twelve Data</span>
            <button onClick={() => setShowTwelveDataModal(true)} className="p-1 hover:bg-[#334155] rounded text-[#94A3B8]">
              <Info className="w-4 h-4" />
            </button>
          </div>
        </div>
        <input
          type="password"
          value={marketData.twelvedata_key}
          onChange={(e) => setMarketData({...marketData, twelvedata_key: e.target.value})}
          placeholder="Enter API key..."
          className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm mb-2"
        />

        <InfoModal title="Twelve Data - Setup Guide" open={showTwelveDataModal} onClose={() => setShowTwelveDataModal(false)}>
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold text-white mb-2">What is Twelve Data?</h4>
              <p className="text-gray-300">
                Comprehensive market data API covering stocks, forex, cryptocurrencies, and ETFs.
                Includes real-time prices, historical data, and technical indicators.
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-2">Free Tier Limits</h4>
              <ul className="text-gray-300 space-y-1">
                <li>• 800 API calls per day</li>
                <li>• 8 API calls per minute</li>
                <li>• Stocks, forex, crypto</li>
                <li>• 60+ technical indicators</li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold text-white mb-2">How to Get Your API Key</h4>
              <div className="space-y-3">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">1</div>
                  <div>
                    Go to{' '}
                    <a href="https://twelvedata.com/pricing" target="_blank" className="text-blue-400 hover:underline flex items-center gap-1">
                      Twelve Data Pricing
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">2</div>
                  <div>Click "Start Free" - no credit card required</div>
                </div>
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">3</div>
                  <div>API key available in dashboard after signup</div>
                </div>
              </div>
            </div>
          </div>
        </InfoModal>
      </div>

      {/* Save Button */}
      <div className="mt-6">
        <button
          onClick={saveMarketDataKeys}
          className="w-full py-2.5 bg-[#10B981] hover:bg-[#059669] text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Check className="w-4 h-4" />
          Save Market Data Settings
        </button>
      </div>

      <div className="mt-3 p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg">
        <p className="text-xs text-[#10B981]">
          💡 <strong>CoinGecko is always active</strong> - no setup required. 
          Add other providers for more data coverage and higher rate limits.
        </p>
      </div>
    </section>
  );
}
