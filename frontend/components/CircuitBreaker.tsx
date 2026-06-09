'use client';

import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  Power,
  RefreshCcw,
  AlertOctagon
} from 'lucide-react';

interface CircuitBreakerStatus {
  state: 'idle' | 'warning' | 'halted';
  triggered_at: string | null;
  trigger_reason: string | null;
  halted_by: 'auto' | 'manual';
  can_trade: boolean;
  time_halted_seconds: number;
}

export default function CircuitBreakerWidget() {
  const [status, setStatus] = useState<CircuitBreakerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmingResume, setConfirmingResume] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/circuit-breaker/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch circuit breaker status:', error);
    } finally {
      setLoading(false);
    }
  };

  const triggerHalt = async () => {
    const reason = prompt('Enter reason for trading halt:');
    if (!reason) return;

    try {
      const res = await fetch(`${API_URL}/api/v1/circuit-breaker/halt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      });

      if (res.ok) {
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to halt trading:', error);
    }
  };

  const resumeTrading = async () => {
    if (!confirmingResume) {
      setConfirmingResume(true);
      setTimeout(() => setConfirmingResume(false), 5000);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/circuit-breaker/resume`, {
        method: 'POST',
      });

      if (res.ok) {
        setConfirmingResume(false);
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to resume trading:', error);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStateConfig = () => {
    if (!status) return { color: 'gray', icon: Shield, label: 'Unknown' };

    switch (status.state) {
      case 'idle':
        return { color: 'green', icon: CheckCircle, label: '正常' };
      case 'warning':
        return { color: 'yellow', icon: AlertTriangle, label: 'Warning' };
      case 'halted':
        return { color: 'red', icon: XCircle, label: 'HALTED' };
      default:
        return { color: 'gray', icon: Shield, label: 'Unknown' };
    }
  };

  const config = getStateConfig();
  const Icon = config.icon;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <RefreshCcw className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-6 h-6 text-blue-500" />
          <h3 className="text-lg font-bold text-white">Circuit Breaker</h3>
        </div>
        <button
          onClick={fetchStatus}
          className="p-1.5 hover:bg-gray-700 rounded-lg transition"
        >
          <RefreshCcw className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* Status Indicator */}
      <div className={`rounded-lg p-4 border-2 border-${config.color}-500 bg-${config.color}-500/10`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Icon className={`w-8 h-8 text-${config.color}-500`} />
            <div>
              <div className={`text-2xl font-bold text-${config.color}-500`}>
                {config.label}
              </div>
              <div className="text-xs text-gray-400">
                {status?.can_trade ? 'Trading allowed' : 'Trading blocked'}
              </div>
            </div>
          </div>
          <div className="text-right">
            {status?.state === 'halted' && (
              <>
                <div className="text-xs text-gray-400">Halted for</div>
                <div className="text-lg font-mono text-white">
                  {Math.floor(status.time_halted_seconds / 60)}m {status.time_halted_seconds % 60}s
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Trigger Reason */}
      {status?.trigger_reason && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <AlertOctagon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-bold text-red-400 uppercase">Trigger Reason</div>
              <div className="text-sm text-gray-300 mt-1">{status.trigger_reason}</div>
              <div className="text-xs text-gray-500 mt-2">
                Triggered by: {status.halted_by} • {status.triggered_at ? new Date(status.triggered_at).toLocaleString() : 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="space-y-2">
        {status?.state === 'halted' ? (
          <button
            onClick={resumeTrading}
            className={`w-full py-2.5 rounded-lg font-bold flex items-center justify-center gap-2 transition ${
              confirmingResume
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
            }`}
          >
            <Power className="w-5 h-5" />
            {confirmingResume ? 'Click again to confirm' : 'Resume Trading'}
          </button>
        ) : (
          <button
            onClick={triggerHalt}
            className="w-full py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold flex items-center justify-center gap-2 transition"
          >
            <AlertTriangle className="w-5 h-5" />
            Emergency Halt
          </button>
        )}
      </div>

      {/* Info */}
      <div className="text-xs text-gray-500 text-center">
        {status?.state === 'idle' 
          ? 'Trading is operating normally'
          : status?.state === 'warning'
          ? 'Elevated risk monitoring - trading still allowed'
          : 'All trading blocked - manual override required'}
      </div>
    </div>
  );
}