'use client';

import { useState, useEffect } from 'react';
import { Key, CheckCircle, AlertCircle, Loader2, ExternalLink, Shield } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface TroveSettingsState {
  trove_enabled: boolean;
  trove_base_url: string | null;
  trove_sandbox: boolean;
  trove_account_id: string | null;
  is_connected: boolean;
}

interface TroveSettingsProps {
  triggerToast: (type: 'success' | 'error' | 'info', title: string, message: string) => void;
}

export default function TroveSettings({ triggerToast }: TroveSettingsProps) {
  const [formData, setFormData] = useState({
    trove_api_key: '',
    trove_base_url: 'https://sandbox.api.trovefinance.com/v1',
    trove_enabled: false,
    trove_sandbox: true,
  });
  const [settings, setSettings] = useState<TroveSettingsState | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  const getDeviceId = () => {
    let deviceId = localStorage.getItem('device_id');
    if (!deviceId) {
      deviceId = 'dev_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('device_id', deviceId);
    }
    return deviceId;
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const deviceId = getDeviceId();
      const res = await fetch(`${API_URL}/api/v1/settings/trove`, {
        headers: { 'X-Device-ID': deviceId },
      });

      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setFormData(prev => ({
          ...prev,
          trove_enabled: data.trove_enabled || false,
          trove_sandbox: data.trove_sandbox ?? true,
          trove_base_url: data.trove_base_url || 'https://sandbox.api.trovefinance.com/v1',
        }));
      }
    } catch (e) {
      console.error('Failed to load Trove settings:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!formData.trove_api_key) {
      triggerToast('error', 'API Key Required', 'Please enter your Trove API key');
      return;
    }

    setSaving(true);
    try {
      const deviceId = getDeviceId();
      const res = await fetch(`${API_URL}/api/v1/settings/trove`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(formData),
      });

      if (res.ok) {
        triggerToast('success', 'Settings Saved', 'Trove API configuration saved');
        loadSettings();
      } else {
        const error = await res.json();
        triggerToast('error', 'Save Failed', error.detail || 'Failed to save settings');
      }
    } catch (e) {
      triggerToast('error', 'Save Failed', 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!formData.trove_api_key) {
      triggerToast('error', 'API Key Required', 'Please enter your Trove API key first');
      return;
    }

    setTesting(true);
    try {
      const deviceId = getDeviceId();

      // First save the settings
      await fetch(`${API_URL}/api/v1/settings/trove`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Device-ID': deviceId,
        },
        body: JSON.stringify(formData),
      });

      // Then test connection
      const res = await fetch(`${API_URL}/api/v1/settings/trove/test`, {
        headers: { 'X-Device-ID': deviceId },
      });

      const data = await res.json();

      if (data.valid) {
        triggerToast(
          'success',
          'Connection Successful',
          `Connected to Trove API - Account: ${data.account_id || 'N/A'}`,
        );
        loadSettings();
      } else {
        triggerToast('error', 'Connection Failed', data.message || 'Failed to connect');
      }
    } catch (e) {
      triggerToast('error', 'Connection Failed', 'Failed to test connection');
    } finally {
      setTesting(false);
    }
  };

  const toggleEnabled = () => {
    setFormData(prev => ({ ...prev, trove_enabled: !prev.trove_enabled }));
  };

  const toggleSandbox = () => {
    const newSandbox = !formData.trove_sandbox;
    setFormData(prev => ({
      ...prev,
      trove_sandbox: newSandbox,
      trove_base_url: newSandbox
        ? 'https://sandbox.api.trovefinance.com/v1'
        : 'https://api.trovefinance.com/v1',
    }));
  };

  if (loading) {
    return (
      <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]">
        <div className="flex items-center gap-2 mb-3">
          <Key className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Trove API (US & Nigerian Stocks)</h2>
        </div>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-[#334155] rounded w-3/4"></div>
          <div className="h-10 bg-[#334155] rounded"></div>
          <div className="h-4 bg-[#334155] rounded w-1/2"></div>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-[#1E293B] rounded-lg p-4 border border-[#475569]" data-tour="trove-section">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Key className="w-5 h-5 text-[#10B981]" />
          <h2 className="text-lg font-semibold text-white">Trove API (US & Nigerian Stocks)</h2>
        </div>
        <div className="flex items-center gap-2">
          {settings?.is_connected && (
            <span className="flex items-center gap-1 text-xs text-green-400">
              <CheckCircle className="w-3 h-3" />
              Connected
            </span>
          )}
          <a
            href="https://sandbox.api.trovefinance.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[#3B82F6] hover:underline flex items-center gap-1"
          >
            Get API Key <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Trade US stocks (AAPL, TSLA) and Nigerian NGX stocks (DANGCEM, MTNN) with fractional shares.
        Supports multi-currency (USD/NGN) and real-time forex conversion.
      </p>

      {/* API Key Input */}
      <div className="mb-4">
        <label className="block text-sm text-gray-300 mb-2">Trove API Key</label>
        <input
          type="password"
          value={formData.trove_api_key}
          onChange={(e) => setFormData({ ...formData, trove_api_key: e.target.value })}
          placeholder="trv_sk_..."
          className="w-full bg-[#0F172A] border border-[#475569] rounded-md px-3 py-2 text-white text-sm focus:outline-none focus:border-[#10B981]"
        />
      </div>

      {/* Environment Toggle */}
      <div className="mb-4">
        <label className="block text-sm text-gray-300 mb-2">Environment</label>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleSandbox}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              formData.trove_sandbox
                ? 'bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30'
                : 'bg-[#334155] text-gray-400 border border-[#475569]'
            }`}
          >
            Sandbox (Demo)
          </button>
          <button
            onClick={toggleSandbox}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              !formData.trove_sandbox
                ? 'bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/30'
                : 'bg-[#334155] text-gray-400 border border-[#475569]'
            }`}
          >
            Live (Real Money)
          </button>
          <span className="text-xs text-gray-500">
            {formData.trove_base_url}
          </span>
        </div>
      </div>

      {/* Enable/Disable Toggle */}
      <div className="mb-4">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={formData.trove_enabled}
            onChange={toggleEnabled}
            className="w-4 h-4 rounded border-gray-600 text-[#10B981] focus:ring-[#10B981]"
          />
          <span className="text-sm text-gray-300">
            Enable Trove API for stock trading
          </span>
        </label>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleTestConnection}
          disabled={testing || !formData.trove_api_key}
          className="flex-1 py-2 bg-[#10B981]/20 border border-[#10B981]/30 hover:bg-[#10B981]/30 text-[#10B981] rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {testing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Testing...
            </>
          ) : (
            <>
              <Shield className="w-4 h-4" />
              Test Connection
            </>
          )}
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 py-2 bg-[#3B82F6] hover:bg-[#2563EB] text-white rounded-md text-sm disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <CheckCircle className="w-4 h-4" />
              Save Settings
            </>
          )}
        </button>
      </div>

      {/* Info Box */}
      <div className="mt-4 p-3 bg-[#10B981]/10 border border-[#10B981]/30 rounded-md">
        <p className="text-xs text-[#10B981]">
          <strong className="font-semibold">✓ Fractional Trading:</strong> Buy stocks by dollar amount (e.g., $50 AAPL)
          <br />
          <strong className="font-semibold">✓ Multi-Currency:</strong> Trade in USD or NGN with auto conversion
          <br />
          <strong className="font-semibold">✓ Markets:</strong> US Stocks + Nigerian NGX (DANGCEM, MTNN, GTCO)
        </p>
      </div>

      {/* Account Info */}
      {settings?.trove_account_id && (
        <div className="mt-3 p-3 bg-[#3B82F6]/10 border border-[#3B82F6]/30 rounded-md">
          <p className="text-xs text-[#3B82F6]">
            <strong>Connected Account:</strong> {settings.trove_account_id}
          </p>
        </div>
      )}
    </section>
  );
}