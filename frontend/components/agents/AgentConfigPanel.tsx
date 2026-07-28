'use client';

import React, { useState, useEffect } from 'react';
import { Save, RotateCcw, Settings, Zap, Shield, Play, AlertTriangle, Info } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DirectorConfig {
  temperature: number;
  maxThinkTime: number;
  confidenceThreshold: number;
  maxTradesPerDay: number;
  marketRegimeSensitivity: number;
}

interface QuantConfig {
  macdThreshold: number;
  rsiOverbought: number;
  rsiOversold: number;
  bollingerSTD: number;
  maShortPeriod: number;
  maLongPeriod: number;
  momentumWeight: number;
  volatilityWeight: number;
}

interface RiskConfig {
  maxPositionSize: number;
  maxPortfolioRisk: number;
  maxDrawdown: number;
  minStopLoss: number;
  maxStopLoss: number;
  minTakeProfit: number;
  maxTakeProfit: number;
  useStopLoss: boolean;
  useTakeProfit: boolean;
}

interface ExecutionConfig {
  maxSlippage: number;
  orderTimeout: number;
  retryAttempts: number;
  useLimitOrders: boolean;
}

interface AgentConfigPanelProps {
  agentId: string;
  agentName: string;
  toast: (type: 'success' | 'error' | 'info', title: string, msg: string) => void;
}

export default function AgentConfigPanel({ agentId, agentName, toast }: AgentConfigPanelProps) {
  const [loading, setLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Director Config
  const [directorConfig, setDirectorConfig] = useState<DirectorConfig>({
    temperature: 0.5,
    maxThinkTime: 30,
    confidenceThreshold: 0.7,
    maxTradesPerDay: 10,
    marketRegimeSensitivity: 0.6,
  });

  // Quant Config
  const [quantConfig, setQuantConfig] = useState<QuantConfig>({
    macdThreshold: 0.005,
    rsiOverbought: 70,
    rsiOversold: 30,
    bollingerSTD: 2.0,
    maShortPeriod: 20,
    maLongPeriod: 50,
    momentumWeight: 0.4,
    volatilityWeight: 0.3,
  });

  // Risk Config
  const [riskConfig, setRiskConfig] = useState<RiskConfig>({
    maxPositionSize: 0.1,
    maxPortfolioRisk: 0.02,
    maxDrawdown: 0.15,
    minStopLoss: 0.02,
    maxStopLoss: 0.10,
    minTakeProfit: 0.05,
    maxTakeProfit: 0.30,
    useStopLoss: true,
    useTakeProfit: true,
  });

  // Execution Config
  const [executionConfig, setExecutionConfig] = useState<ExecutionConfig>({
    maxSlippage: 0.005,
    orderTimeout: 10000,
    retryAttempts: 3,
    useLimitOrders: false,
  });

  // Load config on mount
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const stored = localStorage.getItem(`agent_config_${agentId}`);
      if (stored) {
        const config = JSON.parse(stored);
        if (config.director) setDirectorConfig(config.director);
        if (config.quant) setQuantConfig(config.quant);
        if (config.risk) setRiskConfig(config.risk);
        if (config.execution) setExecutionConfig(config.execution);
      }
    } catch (err) {
      console.error('Failed to load config:', err);
    }
  };

  const saveConfig = async () => {
    setLoading(true);
    try {
      const config = {
        agent_id: agentId,
        agent_name: agentName,
        director: directorConfig,
        quant: quantConfig,
        risk: riskConfig,
        execution: executionConfig,
      };

      // Save to localStorage
      localStorage.setItem(`agent_config_${agentId}`, JSON.stringify(config));

      // Also try to save to backend (non-blocking)
      try {
        await fetch(`${API_URL}/api/v1/agents/${agentId}/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        });
      } catch (err) {
        console.warn('Failed to save to backend (localStorage only):', err);
      }

      setSaveSuccess(true);
      toast('success', 'Configuration Saved', `${agentName} parameters updated successfully`);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      toast('error', 'Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const resetToDefaults = () => {
    if (window.confirm('Reset all settings to defaults? This cannot be undone.')) {
      setDirectorConfig({
        temperature: 0.5,
        maxThinkTime: 30,
        confidenceThreshold: 0.7,
        maxTradesPerDay: 10,
        marketRegimeSensitivity: 0.6,
      });
      setQuantConfig({
        macdThreshold: 0.005,
        rsiOverbought: 70,
        rsiOversold: 30,
        bollingerSTD: 2.0,
        maShortPeriod: 20,
        maLongPeriod: 50,
        momentumWeight: 0.4,
        volatilityWeight: 0.3,
      });
      setRiskConfig({
        maxPositionSize: 0.1,
        maxPortfolioRisk: 0.02,
        maxDrawdown: 0.15,
        minStopLoss: 0.02,
        maxStopLoss: 0.10,
        minTakeProfit: 0.05,
        maxTakeProfit: 0.30,
        useStopLoss: true,
        useTakeProfit: true,
      });
      setExecutionConfig({
        maxSlippage: 0.005,
        orderTimeout: 10000,
        retryAttempts: 3,
        useLimitOrders: false,
      });
      toast('info', 'Reset to Defaults', 'Configuration restored to safe defaults');
    }
  };

  const formatPercent = (val: number) => `${(val * 100).toFixed(1)}%`;
  const formatMs = (val: number) => `${val}ms`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-[#3B82F6]" />
            {agentName} Configuration
          </h3>
          <p className="text-sm text-gray-400">Adjust parameters to control agent behavior</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={resetToDefaults}
            className="flex items-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={saveConfig}
            disabled={loading}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
              saveSuccess
                ? 'bg-green-600 text-white'
                : 'bg-[#3B82F6] hover:bg-[#2563EB] text-white'
            } disabled:opacity-50`}
          >
            <Save className="w-4 h-4" />
            {loading ? 'Saving...' : saveSuccess ? 'Saved!' : 'Save Config'}
          </button>
        </div>
      </div>

      {/* Director Agent Settings */}
      {(agentId === 'director' || agentId === 'all') && (
        <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-4 space-y-4">
          <h4 className="text-md font-bold text-[#3B82F6] flex items-center gap-2">
            <Play className="w-4 h-4" />
            Director Agent - Strategy & Coordination
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Temperature (Creativity vs Precision)</span>
                <span className="text-[#3B82F6] font-bold">{directorConfig.temperature.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0.3"
                max="0.8"
                step="0.05"
                value={directorConfig.temperature}
                onChange={(e) => setDirectorConfig({ ...directorConfig, temperature: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#3B82F6]"
              />
              <p className="text-[10px] text-gray-500">
                Lower = precise & deterministic | Higher = creative & exploratory
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Max Think Time</span>
                <span className="text-[#3B82F6] font-bold">{directorConfig.maxThinkTime}s</span>
              </label>
              <input
                type="range"
                min="5"
                max="60"
                step="5"
                value={directorConfig.maxThinkTime}
                onChange={(e) => setDirectorConfig({ ...directorConfig, maxThinkTime: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#3B82F6]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Confidence Threshold</span>
                <span className="text-[#3B82F6] font-bold">{formatPercent(directorConfig.confidenceThreshold)}</span>
              </label>
              <input
                type="range"
                min="0.5"
                max="0.95"
                step="0.05"
                value={directorConfig.confidenceThreshold}
                onChange={(e) => setDirectorConfig({ ...directorConfig, confidenceThreshold: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#3B82F6]"
              />
              <p className="text-[10px] text-gray-500">Min confidence required to execute trade</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Max Trades Per Day</span>
                <span className="text-[#3B82F6] font-bold">{directorConfig.maxTradesPerDay}</span>
              </label>
              <input
                type="range"
                min="1"
                max="50"
                step="1"
                value={directorConfig.maxTradesPerDay}
                onChange={(e) => setDirectorConfig({ ...directorConfig, maxTradesPerDay: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#3B82F6]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Market Regime Sensitivity</span>
                <span className="text-[#3B82F6] font-bold">{directorConfig.marketRegimeSensitivity.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.1"
                value={directorConfig.marketRegimeSensitivity}
                onChange={(e) => setDirectorConfig({ ...directorConfig, marketRegimeSensitivity: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#3B82F6]"
              />
              <p className="text-[10px] text-gray-500">
                How quickly to adapt to market changes
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Quant Agent Settings */}
      {(agentId === 'quant' || agentId === 'all') && (
        <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-4 space-y-4">
          <h4 className="text-md font-bold text-[#10B981] flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Quant Agent - Technical Analysis
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>MACD Signal Threshold</span>
                <span className="text-[#10B981] font-bold">{quantConfig.macdThreshold}</span>
              </label>
              <input
                type="range"
                min="0.001"
                max="0.01"
                step="0.001"
                value={quantConfig.macdThreshold}
                onChange={(e) => setQuantConfig({ ...quantConfig, macdThreshold: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
              <p className="text-[10px] text-gray-500">MACD crossover significance</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>RSI Overbought Level</span>
                <span className="text-[#10B981] font-bold">{quantConfig.rsiOverbought}</span>
              </label>
              <input
                type="range"
                min="60"
                max="90"
                step="5"
                value={quantConfig.rsiOverbought}
                onChange={(e) => setQuantConfig({ ...quantConfig, rsiOverbought: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>RSI Oversold Level</span>
                <span className="text-[#10B981] font-bold">{quantConfig.rsiOversold}</span>
              </label>
              <input
                type="range"
                min="10"
                max="40"
                step="5"
                value={quantConfig.rsiOversold}
                onChange={(e) => setQuantConfig({ ...quantConfig, rsiOversold: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Bollinger Bands STD</span>
                <span className="text-[#10B981] font-bold">{quantConfig.bollingerSTD}</span>
              </label>
              <input
                type="range"
                min="1.5"
                max="3.0"
                step="0.5"
                value={quantConfig.bollingerSTD}
                onChange={(e) => setQuantConfig({ ...quantConfig, bollingerSTD: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>MA Short Period</span>
                <span className="text-[#10B981] font-bold">{quantConfig.maShortPeriod}</span>
              </label>
              <input
                type="range"
                min="10"
                max="50"
                step="5"
                value={quantConfig.maShortPeriod}
                onChange={(e) => setQuantConfig({ ...quantConfig, maShortPeriod: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>MA Long Period</span>
                <span className="text-[#10B981] font-bold">{quantConfig.maLongPeriod}</span>
              </label>
              <input
                type="range"
                min="50"
                max="200"
                step="10"
                value={quantConfig.maLongPeriod}
                onChange={(e) => setQuantConfig({ ...quantConfig, maLongPeriod: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Momentum Weight</span>
                <span className="text-[#10B981] font-bold">{formatPercent(quantConfig.momentumWeight)}</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.1"
                value={quantConfig.momentumWeight}
                onChange={(e) => setQuantConfig({ ...quantConfig, momentumWeight: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Volatility Weight</span>
                <span className="text-[#10B981] font-bold">{formatPercent(quantConfig.volatilityWeight)}</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.1"
                value={quantConfig.volatilityWeight}
                onChange={(e) => setQuantConfig({ ...quantConfig, volatilityWeight: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#10B981]"
              />
            </div>
          </div>
        </div>
      )}

      {/* Risk Agent Settings */}
      {(agentId === 'risk' || agentId === 'all') && (
        <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-4 space-y-4">
          <h4 className="text-md font-bold text-[#F59E0B] flex items-center gap-2">
            <Shield className="w-4 h-4" />
            Risk Agent - Portfolio Protection
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Max Position Size</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.maxPositionSize)}</span>
              </label>
              <input
                type="range"
                min="0.01"
                max="0.20"
                step="0.01"
                value={riskConfig.maxPositionSize}
                onChange={(e) => setRiskConfig({ ...riskConfig, maxPositionSize: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
              <p className="text-[10px] text-gray-500">Max % of portfolio per trade</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Max Portfolio Risk</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.maxPortfolioRisk)}</span>
              </label>
              <input
                type="range"
                min="0.01"
                max="0.05"
                step="0.005"
                value={riskConfig.maxPortfolioRisk}
                onChange={(e) => setRiskConfig({ ...riskConfig, maxPortfolioRisk: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
              <p className="text-[10px] text-gray-500">Max total exposure risk</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Max Drawdown Limit</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.maxDrawdown)}</span>
              </label>
              <input
                type="range"
                min="0.05"
                max="0.25"
                step="0.01"
                value={riskConfig.maxDrawdown}
                onChange={(e) => setRiskConfig({ ...riskConfig, maxDrawdown: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
              <p className="text-[10px] text-gray-500">Force halt if portfolio drops this much</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Stop-Loss: Min</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.minStopLoss)}</span>
              </label>
              <input
                type="range"
                min="0.01"
                max="0.10"
                step="0.01"
                value={riskConfig.minStopLoss}
                onChange={(e) => setRiskConfig({ ...riskConfig, minStopLoss: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Stop-Loss: Max</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.maxStopLoss)}</span>
              </label>
              <input
                type="range"
                min="0.05"
                max="0.30"
                step="0.01"
                value={riskConfig.maxStopLoss}
                onChange={(e) => setRiskConfig({ ...riskConfig, maxStopLoss: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Take-Profit: Min</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.minTakeProfit)}</span>
              </label>
              <input
                type="range"
                min="0.02"
                max="0.20"
                step="0.01"
                value={riskConfig.minTakeProfit}
                onChange={(e) => setRiskConfig({ ...riskConfig, minTakeProfit: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Take-Profit: Max</span>
                <span className="text-[#F59E0B] font-bold">{formatPercent(riskConfig.maxTakeProfit)}</span>
              </label>
              <input
                type="range"
                min="0.10"
                max="1.00"
                step="0.05"
                value={riskConfig.maxTakeProfit}
                onChange={(e) => setRiskConfig({ ...riskConfig, maxTakeProfit: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#F59E0B]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400">Stop-Loss Enabled</label>
              <button
                onClick={() => setRiskConfig({ ...riskConfig, useStopLoss: !riskConfig.useStopLoss })}
                className={`w-full py-2 rounded-lg font-bold text-xs transition ${
                  riskConfig.useStopLoss
                    ? 'bg-green-600 text-white'
                    : 'bg-red-600 text-white'
                }`}
              >
                {riskConfig.useStopLoss ? 'ON' : 'OFF'}
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400">Take-Profit Enabled</label>
              <button
                onClick={() => setRiskConfig({ ...riskConfig, useTakeProfit: !riskConfig.useTakeProfit })}
                className={`w-full py-2 rounded-lg font-bold text-xs transition ${
                  riskConfig.useTakeProfit
                    ? 'bg-green-600 text-white'
                    : 'bg-red-600 text-white'
                }`}
              >
                {riskConfig.useTakeProfit ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>

          {riskConfig.maxPositionSize > 0.15 && (
            <div className="bg-orange-500/10 border border-orange-500/30 p-3 rounded flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-orange-300">
                High position size risk: Position sizes over 15% significantly increase portfolio volatility
              </p>
            </div>
          )}
        </div>
      )}

      {/* Execution Agent Settings */}
      {(agentId === 'execution' || agentId === 'all') && (
        <div className="bg-[#0F172A] border border-[#475569] rounded-lg p-4 space-y-4">
          <h4 className="text-md font-bold text-[#6366F1] flex items-center gap-2">
            <Play className="w-4 h-4" />
            Execution Agent - Order Management
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Max Slippage Tolerance</span>
                <span className="text-[#6366F1] font-bold">{formatPercent(executionConfig.maxSlippage)}</span>
              </label>
              <input
                type="range"
                min="0.001"
                max="0.02"
                step="0.001"
                value={executionConfig.maxSlippage}
                onChange={(e) => setExecutionConfig({ ...executionConfig, maxSlippage: parseFloat(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#6366F1]"
              />
              <p className="text-[10px] text-gray-500">Cancel if price moves this much</p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Order Timeout</span>
                <span className="text-[#6366F1] font-bold">{formatMs(executionConfig.orderTimeout)}</span>
              </label>
              <input
                type="range"
                min="5000"
                max="60000"
                step="5000"
                value={executionConfig.orderTimeout}
                onChange={(e) => setExecutionConfig({ ...executionConfig, orderTimeout: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#6366F1]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400 flex justify-between">
                <span>Retry Attempts</span>
                <span className="text-[#6366F1] font-bold">{executionConfig.retryAttempts}</span>
              </label>
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={executionConfig.retryAttempts}
                onChange={(e) => setExecutionConfig({ ...executionConfig, retryAttempts: parseInt(e.target.value) })}
                className="w-full h-1 bg-gray-700 rounded-lg accent-[#6366F1]"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs text-gray-400">Use Limit Orders</label>
              <button
                onClick={() => setExecutionConfig({ ...executionConfig, useLimitOrders: !executionConfig.useLimitOrders })}
                className={`w-full py-2 rounded-lg font-bold text-xs transition ${
                  executionConfig.useLimitOrders
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-600 text-white'
                }`}
              >
                {executionConfig.useLimitOrders ? 'LIMIT' : 'MARKET'}
              </button>
              <p className="text-[10px] text-gray-500 text-center">
                {executionConfig.useLimitOrders ? 'Prefer price control' : 'Prioritize speed'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/30 p-4 rounded-lg flex items-start gap-2">
        <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
        <div className="text-xs text-blue-300 space-y-1">
          <p><strong>Pro Tip:</strong> Start with conservative settings and gradually adjust based on performance.</p>
          <p>Settings are saved to local storage and automatically loaded on next visit.</p>
        </div>
      </div>
    </div>
  );
}