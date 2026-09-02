/**
 * Backend-persisted frontend preferences (per device).
 *
 * Values that used to live in localStorage (trading mode, ai running state,
 * agent configs, collapsible sections, onboarding progress) are now stored in
 * the database keyed by the X-Device-ID fingerprint. The device id and the
 * light/dark theme intentionally stay client-side.
 */
import { API_URL, DEFAULT_DEVICE_ID } from '@/lib/constants';
import { getOrCreateDeviceId, deviceHeaders } from '@/lib/deviceFingerprint';

export interface OnboardingPrefs {
  welcome_done?: boolean;
  onboarding_completed?: boolean;
  completed_tours?: string[];
}

export interface Preferences {
  ai_running?: boolean;
  agent_configs?: Record<string, AgentConfigMap>;
  collapsible_sections?: Record<string, boolean>;
  onboarding?: OnboardingPrefs;
}

// ---------------------------------------------------------------------------
// Trading mode (paper | live)
// ---------------------------------------------------------------------------

export async function fetchTradingMode(): Promise<'practice' | 'live'> {
  try {
    const res = await fetch(`${API_URL}/api/v1/settings/trading-mode`, { headers: deviceHeaders() });
    if (!res.ok) return 'practice';
    const data = await res.json();
    return data.trading_mode === 'live' ? 'live' : 'practice';
  } catch {
    return 'practice';
  }
}

export async function saveTradingMode(mode: 'practice' | 'live'): Promise<void> {
  try {
    await fetch(`${API_URL}/api/v1/settings/trading-mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...deviceHeaders() },
      body: JSON.stringify({ trading_mode: mode }),
    });
  } catch {
    /* offline - caller still updates local state */
  }
}

// ---------------------------------------------------------------------------
// Generic preferences (shallow-merged server-side)
// ---------------------------------------------------------------------------

export interface AgentConfigMap {
  agent_id?: string;
  agent_name?: string;
  director?: Record<string, unknown>;
  quant?: Record<string, unknown>;
  risk?: Record<string, unknown>;
  execution?: Record<string, unknown>;
}

export async function saveAgentConfig(agentId: string, config: AgentConfigMap): Promise<void> {
  const current = await fetchPreferences();
  const agent_configs = { ...(current.agent_configs || {}), [agentId]: config };
  await savePreferences({ agent_configs });
}

export async function loadAgentConfig(agentId: string): Promise<AgentConfigMap | null> {
  const prefs = await fetchPreferences();
  return prefs.agent_configs?.[agentId] ?? null;
}

export async function saveCollapsibleState(key: string, isOpen: boolean): Promise<void> {
  const current = await fetchPreferences();
  const collapsible_sections = { ...(current.collapsible_sections || {}), [key]: isOpen };
  await savePreferences({ collapsible_sections });
}

export async function loadCollapsibleState(key: string): Promise<boolean | null> {
  const prefs = await fetchPreferences();
  const stored = prefs.collapsible_sections?.[key];
  return typeof stored === 'boolean' ? stored : null;
}

export async function saveOnboardingPrefs(patch: OnboardingPrefs): Promise<void> {
  const current = await fetchPreferences();
  const onboarding = { ...(current.onboarding || {}), ...patch };
  await savePreferences({ onboarding });
}

export async function loadOnboardingPrefs(): Promise<OnboardingPrefs> {
  const prefs = await fetchPreferences();
  return prefs.onboarding || {};
}

/** Settings-triggered reset: zeroes the persisted onboarding block in the DB. */
export async function resetOnboarding(): Promise<void> {
  try {
    await fetch(`${API_URL}/api/v1/settings/onboarding/reset`, {
      method: 'POST',
      headers: deviceHeaders(),
    });
  } catch {
    /* offline - caller still clears local state */
  }
}

export async function fetchPreferences(): Promise<Preferences> {
  try {
    const res = await fetch(`${API_URL}/api/v1/settings/preferences`, { headers: deviceHeaders() });
    if (!res.ok) return {};
    const data = await res.json();
    return data.preferences || {};
  } catch {
    return {};
  }
}

export async function savePreferences(patch: Partial<Preferences>): Promise<void> {
  try {
    await fetch(`${API_URL}/api/v1/settings/preferences`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...deviceHeaders() },
      body: JSON.stringify({ preferences: patch }),
    });
  } catch {
    /* offline */
  }
}
