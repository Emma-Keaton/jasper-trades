'use client';

import React, { useState } from 'react';
import { checkpointAPI, debateAPI } from '@/lib/api-client';
import { Loader2, Save, GitCompare } from 'lucide-react';

export function CheckpointPanel() {
  const [loading, setLoading] = useState(false);
  const [checkpoints, setCheckpoints] = useState<any[]>([]);
  const [ticker, setTicker] = useState('AAPL');

  const loadCheckpoints = async () => {
    setLoading(true);
    const response = await checkpointAPI.list();
    if (response.data) {
      setCheckpoints(Array.isArray(response.data) ? response.data : []);
    }
    setLoading(false);
  };

  const saveCheckpoint = async () => {
    setLoading(true);
    await checkpointAPI.save({ ticker, timestamp: new Date().toISOString() });
    await loadCheckpoints();
    setLoading(false);
  };

  const clearCheckpoint = async (t: string) => {
    setLoading(true);
    await checkpointAPI.clear(t);
    await loadCheckpoints();
    setLoading(false);
  };

  React.useEffect(() => {
    loadCheckpoints();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-4">
        <Save className="w-6 h-6 text-[#F59E0B]" />
        <div>
          <h4 className="text-sm font-bold text-[#F8FAFC]">Checkpoint System</h4>
          <p className="text-xs text-[#94A3B8]">Save and restore trading states</p>
        </div>
      </div>

      {/* Save New Checkpoint */}
      <div className="flex gap-2">
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker (e.g., AAPL)"
          className="flex-1 bg-[#0F172A] border border-[#475569] rounded-lg px-3 py-2 text-sm text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
        />
        <button
          onClick={saveCheckpoint}
          disabled={loading || !ticker}
          className="bg-[#F59E0B] hover:bg-[#D97706] text-black font-bold px-4 py-2 rounded-lg text-sm transition disabled:opacity-50 h-11 flex items-center gap-2"
        >
          <Save className="w-4 h-4" />
          Save
        </button>
      </div>

      {/* Checkpoints List */}
      {loading ? (
        <div className="flex items-center justify-center py-4 text-[#94A3B8]">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          <span>Loading checkpoints...</span>
        </div>
      ) : checkpoints.length > 0 ? (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {checkpoints.map((cp: any, idx: number) => (
            <div
              key={cp.id || cp.ticker || idx}
              className="p-3 bg-[#1E293B] border border-[#475569] rounded-lg flex items-center justify-between"
            >
              <div>
                <div className="font-mono text-sm font-bold text-[#F8FAFC]">
                  {cp.ticker || cp.symbol || 'Unknown'}
                </div>
                <div className="text-xs text-[#94A3B8]">
                  {cp.timestamp || cp.saved_at ? new Date(cp.timestamp || cp.saved_at).toLocaleString() : 'Unknown date'}
                </div>
              </div>
              <button
                onClick={() => clearCheckpoint(cp.ticker || cp.symbol)}
                className="text-xs px-3 py-1.5 bg-[#EF4444]/20 text-[#EF4444] rounded hover:bg-[#EF4444]/30 transition"
              >
                Clear
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-4 text-[#94A3B8] text-sm">
          No checkpoints saved
        </div>
      )}
    </div>
  );
}

export function DebatePanel() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const runDebate = async () => {
    setLoading(true);
    const response = await debateAPI.analyze({
      signal: 'sample_signal',
      participants: ['bull', 'bear'],
    });
    if (response.data) setResult(response.data);
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-4">
        <GitCompare className="w-6 h-6 text-[#EC4899]" />
        <div>
          <h4 className="text-sm font-bold text-[#F8FAFC]">Agent Debate Protocol</h4>
          <p className="text-xs text-[#94A3B8]">Multi-agent signal analysis</p>
        </div>
      </div>

      <button
        onClick={runDebate}
        disabled={loading}
        className="w-full bg-[#EC4899] hover:bg-[#DB2777] text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50 h-11 flex items-center justify-center gap-2"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? 'Debating...' : 'Run Signal Debate'}
      </button>

      {result && (
        <div className="p-3 bg-[#EC4899]/10 border border-[#EC4899]/30 rounded-lg">
          <pre className="text-xs text-[#F8FAFC] font-mono whitespace-pre-wrap">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}