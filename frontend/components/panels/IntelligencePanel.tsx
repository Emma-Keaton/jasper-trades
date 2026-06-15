'use client';

import React, { useState } from 'react';
import { swarmAPI, learningAPI, ensembleAPI } from '@/lib/api-client';
import { Loader2, Brain, Network } from 'lucide-react';

export function SwarmPanel() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const runSwarm = async () => {
    setLoading(true);
    const response = await swarmAPI.run({
      task: 'market_analysis',
      agents: ['quant', 'risk', 'sentiment'],
    });
    if (response.data) setResult(response.data);
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-4">
        <Network className="w-6 h-6 text-[#3B82F6]" />
        <div>
          <h4 className="text-sm font-bold text-[#F8FAFC]">Swarm Intelligence</h4>
          <p className="text-xs text-[#94A3B8]">Multi-agent collaborative analysis</p>
        </div>
      </div>

      <button
        onClick={runSwarm}
        disabled={loading}
        className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50 h-11 flex items-center justify-center gap-2"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? 'Running Swarm...' : 'Run Swarm Analysis'}
      </button>

      {result && (
        <div className="p-3 bg-[#1E293B] border border-[#475569] rounded-lg">
          <pre className="text-xs text-[#F8FAFC] font-mono whitespace-pre-wrap">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function LearningPanel() {
  const [loading, setLoading] = useState(false);
  const [patterns, setPatterns] = useState<any>(null);

  const loadPatterns = async () => {
    setLoading(true);
    const [winning, losing] = await Promise.all([
      learningAPI.getWinningPatterns(),
      learningAPI.getLosingPatterns(),
    ]);
    setPatterns({ winning: winning.data, losing: losing.data });
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-4">
        <Brain className="w-6 h-6 text-[#10B981]" />
        <div>
          <h4 className="text-sm font-bold text-[#F8FAFC]">RL Learning Patterns</h4>
          <p className="text-xs text-[#94A3B8]">Reinforcement learning insights</p>
        </div>
      </div>

      <button
        onClick={loadPatterns}
        disabled={loading}
        className="w-full bg-[#10B981] hover:bg-[#059669] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50 h-11 flex items-center justify-center gap-2"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? 'Loading...' : 'Load Patterns'}
      </button>

      {patterns && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg">
            <h5 className="text-xs font-bold text-[#10B981] mb-2">Winning Patterns</h5>
            <pre className="text-xs text-[#F8FAFC] font-mono whitespace-pre-wrap">
              {JSON.stringify(patterns.winning, null, 2)}
            </pre>
          </div>
          <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg">
            <h5 className="text-xs font-bold text-[#EF4444] mb-2">Losing Patterns</h5>
            <pre className="text-xs text-[#F8FAFC] font-mono whitespace-pre-wrap">
              {JSON.stringify(patterns.losing, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function EnsemblePanel() {
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<any>(null);

  const getPrediction = async () => {
    setLoading(true);
    const response = await ensembleAPI.predict({ symbols: ['AAPL', 'NVDA'] });
    if (response.data) setPrediction(response.data);
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-4">
        <Network className="w-6 h-6 text-[#8B5CF6]" />
        <div>
          <h4 className="text-sm font-bold text-[#F8FAFC]">Ensemble Predictions</h4>
          <p className="text-xs text-[#94A3B8]">Multi-model consensus</p>
        </div>
      </div>

      <button
        onClick={getPrediction}
        disabled={loading}
        className="w-full bg-[#8B5CF6] hover:bg-[#7C3AED] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50 h-11 flex items-center justify-center gap-2"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? 'Predicting...' : 'Get Ensemble Prediction'}
      </button>

      {prediction && (
        <div className="p-3 bg-[#8B5CF6]/10 border border-[#8B5CF6]/30 rounded-lg">
          <pre className="text-xs text-[#F8FAFC] font-mono whitespace-pre-wrap">
            {JSON.stringify(prediction, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}