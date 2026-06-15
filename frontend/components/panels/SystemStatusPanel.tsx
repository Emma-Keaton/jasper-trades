'use client';

import React, { useState, useEffect } from 'react';
import { systemAPI } from '@/lib/api-client';
import { Loader2, Server, Database, Activity } from 'lucide-react';

export function SystemStatusPanel() {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<{
    kronos?: any;
    system?: any;
    marketData?: any;
  }>({});

  const loadStatus = async () => {
    setLoading(true);
    const [kronosRes, systemRes, marketDataRes] = await Promise.all([
      systemAPI.getKronosStats(),
      systemAPI.getStatus(),
      systemAPI.getMarketData(),
    ]);

    setStatus({
      kronos: kronosRes.data,
      system: systemRes.data,
      marketData: marketDataRes.data,
    });
    setLoading(false);
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-[#94A3B8]">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        <span>Loading system status...</span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Kronos Stats */}
      <div className="p-4 bg-[#1E293B] border border-[#475569] rounded-xl">
        <div className="flex items-center gap-2 mb-3">
          <Server className="w-5 h-5 text-[#3B82F6]" />
          <h4 className="text-sm font-bold text-[#F8FAFC]">Kronos Model</h4>
        </div>
        {status.kronos ? (
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#94A3B8]">Status:</span>
              <span className="text-[#10B981] font-mono">
                {status.kronos.status || 'online'}
              </span>
            </div>
            {status.kronos.last_prediction && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Last Prediction:</span>
                <span className="text-[#F8FAFC] font-mono">
                  {new Date(status.kronos.last_prediction).toLocaleString()}
                </span>
              </div>
            )}
            {status.kronos.accuracy && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Accuracy:</span>
                <span className="text-[#F59E0B] font-mono">
                  {(status.kronos.accuracy * 100).toFixed(1)}%
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-[#94A3B8]">No data</div>
        )}
      </div>

      {/* System Status */}
      <div className="p-4 bg-[#1E293B] border border-[#475569] rounded-xl">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-5 h-5 text-[#10B981]" />
          <h4 className="text-sm font-bold text-[#F8FAFC]">System Health</h4>
        </div>
        {status.system ? (
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#94A3B8]">Status:</span>
              <span className={`font-mono ${
                status.system.status === 'healthy' ? 'text-[#10B981]' :
                status.system.status === 'degraded' ? 'text-[#F59E0B]' :
                'text-[#EF4444]'
              }`}>
                {status.system.status || 'unknown'}
              </span>
            </div>
            {status.system.memory_usage && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Memory:</span>
                <span className="text-[#F8FAFC] font-mono">
                  {status.system.memory_usage}
                </span>
              </div>
            )}
            {status.system.active_agents && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Active Agents:</span>
                <span className="text-[#F8FAFC] font-mono">
                  {status.system.active_agents}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-[#94A3B8]">No data</div>
        )}
      </div>

      {/* Market Data */}
      <div className="p-4 bg-[#1E293B] border border-[#475569] rounded-xl">
        <div className="flex items-center gap-2 mb-3">
          <Database className="w-5 h-5 text-[#8B5CF6]" />
          <h4 className="text-sm font-bold text-[#F8FAFC]">Market Data</h4>
        </div>
        {status.marketData ? (
          <div className="space-y-2">
            {status.marketData.providers && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Providers:</span>
                <span className="text-[#F8FAFC] font-mono">
                  {status.marketData.providers.length || 0} active
                </span>
              </div>
            )}
            {status.marketData.last_update && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Last Update:</span>
                <span className="text-[#F8FAFC] font-mono">
                  {new Date(status.marketData.last_update).toLocaleString()}
                </span>
              </div>
            )}
            {status.marketData.cache_hit_rate && (
              <div className="flex justify-between text-xs">
                <span className="text-[#94A3B8]">Cache Hit Rate:</span>
                <span className="text-[#10B981] font-mono">
                  {(status.marketData.cache_hit_rate * 100).toFixed(1)}%
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-[#94A3B8]">No data</div>
        )}
      </div>
    </div>
  );
}