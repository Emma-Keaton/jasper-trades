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
}

const DEVICE_KEY = 'jasper_device_id';
const DEVICE_INFO_KEY = 'jasper_device_info';

/**
 * Generate a unique but stable device fingerprint
 * Uses combination of browser characteristics + random seed
 */
function generateDeviceId(): string {
  const timestamp = Date.now().toString(36);
  const randomPart = Math.random().toString(36).substring(2, 15);
  const platform = (typeof navigator !== 'undefined' && navigator.platform) || 'unknown';

  // Create hash-like identifier
  const fingerprint = `${platform}-${timestamp}-${randomPart}`;
  return btoa(fingerprint).replace(/[^a-zA-Z0-9]/g, '').substring(0, 32);
}

/**
 * Get existing device ID or create new one
 * Persists across app updates via localStorage.
 * SSR-safe: returns a throwaway id when not in the browser.
 */
export function getOrCreateDeviceId(): string {
  if (typeof window === 'undefined') return 'ssr';

  // Try to get existing device ID
  let deviceId = localStorage.getItem(DEVICE_KEY);
  
  if (!deviceId) {
    // Check if we have device info to recover from
    const savedInfo = localStorage.getItem(DEVICE_INFO_KEY);
    if (savedInfo) {
      try {
        const info: DeviceInfo = JSON.parse(savedInfo);
        deviceId = info.deviceId;
        console.log('Recovered device ID from backup info');
      } catch (e) {
        console.error('Failed to recover device info:', e);
      }
    }
    
    // If still no device ID, generate new one
    if (!deviceId) {
      deviceId = generateDeviceId();
      console.log('Generated new device ID:', deviceId);
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
      version: '1.0.0' // App version
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