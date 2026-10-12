/**
 * Device Fingerprinting Service
 * Generates persistent device IDs that survive app updates
 * Stores in localStorage with metadata for recovery
 */

interface DeviceInfo {
  deviceId: string;
  createdAt: string;
  lastSeenAt: string;
  userAgent: string;
  screenResolution: string;
  platform: string;
  version: string;
  /** Pre-2.0 fingerprint, kept only so the migration is auditable. */
  legacyDeviceId?: string;
}

const DEVICE_KEY = 'jasper_device_id';
const DEVICE_INFO_KEY = 'jasper_device_info';

/**
 * Generate the device UUID.
 *
 * This UUID *is* the credential: there are no user accounts, and whoever
 * presents it is that device. It must therefore be unguessable, so it comes
 * from `crypto.randomUUID()` (122 bits of CSPRNG output).
 *
 * The previous generator was
 * `base64(platform + Date.now() + Math.random())` — a timestamp plus a
 * non-cryptographic PRNG. Anyone who knew roughly when a device first connected
 * could narrow the search space considerably. It also produced a 32-character
 * opaque string rather than a UUID, so the server could not validate the header
 * it was being sent.
 *
 * `crypto.randomUUID` requires a secure context (https, or localhost). If it is
 * unavailable the caller gets a clear error rather than a weaker identifier,
 * because a guessable device ID silently defeats the access model.
 */
function generateDeviceId(): string {
  if (
    typeof crypto === 'undefined' ||
    typeof crypto.randomUUID !== 'function'
  ) {
    throw new Error(
      'crypto.randomUUID() is unavailable. Jasper Trades requires a secure ' +
        'context (https, or localhost) because the device ID is the ' +
        'credential that authenticates this device.'
    );
  }
  return crypto.randomUUID();
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** True when `id` is a canonical UUID. */
function isUuid(id: string | null): boolean {
  return typeof id === 'string' && UUID_RE.test(id);
}

/**
 * Get existing device ID or create new one
 * Persists across app updates via localStorage.
 * SSR-safe: returns a throwaway id when not in the browser.
 */
export function getOrCreateDeviceId(): string {
  // Server-side rendering has no localStorage and no secure context. Callers
  // only read this into a header on a real request, so a placeholder is fine
  // here - but it is deliberately not a valid UUID so it can never be mistaken
  // for a real credential if it ever leaked into a request.
  if (typeof window === 'undefined') return 'ssr-not-a-uuid';

  // Try to get existing device ID
  let deviceId = localStorage.getItem(DEVICE_KEY);

  // A device ID stored by an older build is a 32-character opaque fingerprint,
  // not a UUID. The server now rejects those, so this device would lose access
  // to its own settings, portfolio and history on upgrade. Mint a UUID and keep
  // the old value in deviceInfo so the migration is visible rather than silent.
  if (deviceId && !isUuid(deviceId)) {
    console.warn(
      'Replacing legacy non-UUID device ID with a UUID. Previously stored: ' +
        deviceId
    );
    const legacy = deviceId;
    deviceId = null;
    try {
      const saved: DeviceInfo = JSON.parse(
        localStorage.getItem(DEVICE_INFO_KEY) || '{}'
      );
      saved.legacyDeviceId = legacy;
      localStorage.setItem(DEVICE_INFO_KEY, JSON.stringify(saved));
    } catch {
      // A corrupt deviceInfo must not block issuing a working credential.
    }
  }

  if (!deviceId) {
    // Check if we have device info to recover from
    const savedInfo = localStorage.getItem(DEVICE_INFO_KEY);
    if (savedInfo) {
      try {
        const info: DeviceInfo = JSON.parse(savedInfo);
        if (isUuid(info.deviceId)) {
          deviceId = info.deviceId;
          console.log('Recovered device UUID from backup info');
        }
      } catch (e) {
        console.error('Failed to recover device info:', e);
      }
    }

    // If still no device ID, generate new one
    if (!deviceId) {
      deviceId = generateDeviceId();
      console.log('Generated new device UUID:', deviceId);
    }

    // Save to localStorage
    localStorage.setItem(DEVICE_KEY, deviceId);

    // Save device metadata for recovery
    const deviceInfo: DeviceInfo = {
      deviceId,
      createdAt: new Date().toISOString(),
      lastSeenAt: new Date().toISOString(),
      userAgent: navigator.userAgent,
      screenResolution: `${screen.width}x${screen.height}`,
      platform: navigator.platform,
      version: '2.0.0', // device-ID format is UUID as of 2.0.0
    };

    localStorage.setItem(DEVICE_INFO_KEY, JSON.stringify(deviceInfo));
  } else {
    // Update last seen timestamp
    const savedInfo = localStorage.getItem(DEVICE_INFO_KEY);
    if (savedInfo) {
      try {
        const info: DeviceInfo = JSON.parse(savedInfo);
        info.lastSeenAt = new Date().toISOString();
        localStorage.setItem(DEVICE_INFO_KEY, JSON.stringify(info));
      } catch (e) {
        console.error('Failed to update last seen:', e);
      }
    }
  }
  
  return deviceId;
}

/**
 * Build common headers with the device ID attached.
 * Every request to the backend should carry X-Device-ID so
 * device-scoped routes (portfolio, watchlist, signals, brokers) work.
 */
export function deviceHeaders(
  extra?: Record<string, string>
): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Device-ID': getOrCreateDeviceId(),
    ...extra,
  };
}

/**
 * Get device metadata for debugging/support
 */
export function getDeviceInfo(): DeviceInfo | null {
  const infoStr = localStorage.getItem(DEVICE_INFO_KEY);
  if (!infoStr) return null;
  
  try {
    return JSON.parse(infoStr);
  } catch (e) {
    console.error('Failed to parse device info:', e);
    return null;
  }
}

/**
 * Export device data for backup/migration
 * Returns JSON string that can be saved or printed
 */
export function exportDeviceData(): string {
  const deviceId = localStorage.getItem(DEVICE_KEY);
  const deviceInfo = localStorage.getItem(DEVICE_INFO_KEY);
  
  let parsedInfo = null;
  try {
    parsedInfo = deviceInfo ? JSON.parse(deviceInfo) : null;
  } catch {
    parsedInfo = null;
  }

  const exportData = {
    exportedAt: new Date().toISOString(),
    deviceId,
    deviceInfo: parsedInfo,
    // Include any other persisted data
    settings: localStorage.getItem('jasper_settings'),
    onboarding: localStorage.getItem('jasper_onboarding_state'),
  };
  
  return JSON.stringify(exportData, null, 2);
}

/**
 * Import device data from backup
 * Useful for migration or device recovery
 */
export function importDeviceData(jsonData: string): boolean {
  try {
    const data = JSON.parse(jsonData);
    
    if (data.deviceId) {
      localStorage.setItem(DEVICE_KEY, data.deviceId);
    }
    
    if (data.deviceInfo) {
      localStorage.setItem(DEVICE_INFO_KEY, JSON.stringify(data.deviceInfo));
    }
    
    if (data.settings) {
      localStorage.setItem('jasper_settings', data.settings);
    }
    
    if (data.onboarding) {
      localStorage.setItem('jasper_onboarding_state', data.onboarding);
    }
    
    console.log('Device data imported successfully');
    return true;
  } catch (e) {
    console.error('Failed to import device data:', e);
    return false;
  }
}

/**
 * Clear device data (for testing or reset)
 */
export function clearDeviceData(): void {
  localStorage.removeItem(DEVICE_KEY);
  localStorage.removeItem(DEVICE_INFO_KEY);
  console.log('Device data cleared');
}