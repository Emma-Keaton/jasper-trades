'use client';

import React, { useState } from 'react';
import { quantlibAPI } from '@/lib/api-client';
import { Loader2 } from 'lucide-react';

export function QuantLibPanel() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [activeTool, setActiveTool] = useState<string>('black-scholes');

  const handleCalculate = async (tool: string, data: any) => {
    setLoading(true);
    let response;

    try {
      switch (tool) {
        case 'black-scholes':
          response = await quantlibAPI.getBlackScholes(data);
          break;
        case 'greeks':
          response = await quantlibAPI.getGreeks(data);
          break;
        case 'var-mc':
          response = await quantlibAPI.getMonteCarloVaR(data);
          break;
        case 'var-hist':
          response = await quantlibAPI.getHistoricalVaR(data);
          break;
        case 'sharpe':
          response = await quantlibAPI.getSharpe(data);
          break;
        default:
          return;
      }

      if (response.data) {
        setResult(response.data);
      } else if (response.error) {
        setResult({ error: response.error });
      }
    } catch (err) {
      setResult({ error: err instanceof Error ? err.message : 'Unknown error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Tool Selector */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveTool('black-scholes')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition ${
            activeTool === 'black-scholes'
              ? 'bg-[#3B82F6] text-white'
              : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
          }`}
        >
          Black-Scholes
        </button>
        <button
          onClick={() => setActiveTool('greeks')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition ${
            activeTool === 'greeks'
              ? 'bg-[#3B82F6] text-white'
              : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
          }`}
        >
          Greeks
        </button>
        <button
          onClick={() => setActiveTool('var-mc')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition ${
            activeTool === 'var-mc'
              ? 'bg-[#3B82F6] text-white'
              : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
          }`}
        >
          Monte Carlo VaR
        </button>
        <button
          onClick={() => setActiveTool('var-hist')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition ${
            activeTool === 'var-hist'
              ? 'bg-[#3B82F6] text-white'
              : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
          }`}
        >
          Historical VaR
        </button>
        <button
          onClick={() => setActiveTool('sharpe')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition ${
            activeTool === 'sharpe'
              ? 'bg-[#3B82F6] text-white'
              : 'bg-[#1E293B] text-[#94A3B8] hover:bg-[#334155]'
          }`}
        >
          Sharpe Ratio
        </button>
      </div>

      {/* Simple Input Form */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <input
          type="number"
          placeholder="Spot Price (S)"
          className="bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
          id="spot"
          defaultValue={100}
        />
        <input
          type="number"
          placeholder="Strike (K)"
          className="bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
          id="strike"
          defaultValue={100}
        />
        <input
          type="number"
          placeholder="Time (years)"
          className="bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
          id="time"
          defaultValue={1}
          step={0.01}
        />
        <input
          type="number"
          placeholder="Volatility (%)"
          className="bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
          id="volatility"
          defaultValue={20}
        />
        <input
          type="number"
          placeholder="Risk-free Rate (%)"
          className="bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-xs text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
          id="rate"
          defaultValue={5}
        />
      </div>

      {/* Calculate Button */}
      <button
        onClick={() => {
          const data = {
            spot: Number((document.getElementById('spot') as HTMLInputElement).value),
            strike: Number((document.getElementById('strike') as HTMLInputElement).value),
            time: Number((document.getElementById('time') as HTMLInputElement).value),
            volatility: Number((document.getElementById('volatility') as HTMLInputElement).value) / 100,
            rate: Number((document.getElementById('rate') as HTMLInputElement).value) / 100,
          };
          handleCalculate(activeTool, data);
        }}
        disabled={loading}
        className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 h-11"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? 'Calculating...' : 'Calculate'}
      </button>

      {/* Results Display */}
      {result && (
        <div className={`p-3 rounded-lg border ${
          result.error 
            ? 'bg-[#EF4444]/10 border-[#EF4444]/30' 
            : 'bg-[#10B981]/10 border-[#10B981]/30'
        }`}>
          <pre className="text-xs text-[#F8FAFC] font-mono whitespace-pre-wrap">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}