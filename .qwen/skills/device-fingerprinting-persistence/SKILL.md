---
name: device-fingerprinting-persistence
description: Implement persistent device identification so users retain settings across app updates
source: auto-skill
extracted_at: '2026-06-10T10:45:00.000Z'
---

# Device Fingerprinting for Persistent User Settings

## Problem
When the app is updated and redeployed, users lose their device ID (stored in localStorage) and must reconfigure all settings from scratch. This creates a poor user experience and frustration.

## Solution
Implement a device fingerprinting system that generates a stable, persistent device ID that survives app updates through localStorage backup and recovery mechanisms.

## Implementation Steps

### 1. Create Device Fingerprint Library

**File:** `frontend/lib/deviceFingerprint.ts`

```typescript
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

function generateDeviceId(): string {
  const timestamp = Date.now().toString(36);
  const randomPart = Math.random().toString(36).substring(2, 15);
  const platform = navigator.platform || 'unknown';
  
  const fingerprint = `${platform}-${timestamp}-${randomPart}`;
  return btoa(fingerprint).replace(/[^a-zA-Z0-9]/g, '').substring(0, 32);
}

export function getOrCreateDeviceId(): string {
  let deviceId = localStorage.getItem(DEVICE_KEY);
  
  if (!deviceId) {
    // Try to recover from backup device info
    const savedInfo = localStorage.getItem(DEVICE_INFO_KEY);
    if (savedInfo) {
      try {
        const info: DeviceInfo = JSON.parse(savedInfo);
        deviceId = info.deviceId;
        console.log('Recovered device ID from backup');
      } catch (e) {
        console.error('Failed to recover device info:', e);
      }
    }
    
    // Generate new if still no ID
    if (!deviceId) {
      deviceId = generateDeviceId();
      console.log('Generated new device ID:', deviceId);
    }
    
    // Save to both primary and backup locations
    localStorage.setItem(DEVICE_KEY, deviceId);
    
    const deviceInfo: DeviceInfo = {
      deviceId,
      createdAt: new Date().toISOString(),
      lastSeenAt: new Date().toISOString(),
      userAgent: navigator.userAgent,
      screenResolution: `${screen.width}x${screen.height}`,
      platform: navigator.platform,
      version: '1.0.0'
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

export function exportDeviceData(): string {
  const deviceId = localStorage.getItem(DEVICE_KEY);
  const deviceInfo = localStorage.getItem(DEVICE_INFO_KEY);
  const settings = localStorage.getItem('jasper_settings');
  const onboarding = localStorage.getItem('jasper_onboarding');
  
  const exportData = {
    exportedAt: new Date().toISOString(),
    deviceId,
    deviceInfo: deviceInfo ? JSON.parse(deviceInfo) : null,
    settings,
    onboarding,
  };
  
  return JSON.stringify(exportData, null, 2);
}

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
      localStorage.setItem('jasper_onboarding', data.onboarding);
    }
    
    console.log('Device data imported successfully');
    return true;
  } catch (e) {
    console.error('Failed to import device data:', e);
    return false;
  }
}
```

### 2. Update Settings Component

**File:** `frontend/components/SettingsTab.tsx`

```typescript
import { getOrCreateDeviceId } from '@/lib/deviceFingerprint';

const fetchSettings = async () => {
  setLoading(true);
  try {
    // Get persistent device ID (survives app updates)
    let deviceId = getOrCreateDeviceId();
    console.log('Using persistent device ID:', deviceId);

    const res = await fetch(`${API_URL}/api/v1/settings`, {
      headers: {
        'X-Device-ID': deviceId,
      },
    });

    // ... rest of settings fetch logic
  }
};
```

### 3. How It Survives App Updates

**Storage Strategy:**
1. **Primary Storage:** `localStorage.jasper_device_id`
2. **Backup Storage:** `localStorage.jasper_device_info` (contains deviceId field)
3. **Recovery Logic:** If primary is missing, extract from backup

**Why It Works:**
- localStorage persists across browser sessions and app updates
- Only cleared if user explicitly clears browser data
- Multiple storage locations provide redundancy
- Device metadata helps with debugging/support

### 4. Testing the Implementation

**Test 1: Initial Visit**
```javascript
const deviceId1 = getOrCreateDeviceId();
// Should generate new ID and save to localStorage
```

**Test 2: Page Refresh**
```javascript
const deviceId2 = getOrCreateDeviceId();
// Should return same ID as deviceId1
assert(deviceId1 === deviceId2);
```

**Test 3: Simulate App Update**
```javascript
// Clear primary only (simulate partial clear)
localStorage.removeItem('jasper_device_id');

const deviceId3 = getOrCreateDeviceId();
// Should recover from backup info
assert(deviceId1 === deviceId3);
```

**Test 4: Export/Import**
```javascript
const exported = exportDeviceData();
localStorage.clear();
importDeviceData(exported);

const deviceId4 = getOrCreateDeviceId();
// Should match original after import
assert(deviceId1 === deviceId4);
```

## Key Benefits

1. **No Reconfiguration:** Users keep settings after app updates
2. **Transparent:** Works automatically, no user action needed
3. **Redundant:** Multiple storage locations prevent data loss
4. **Debuggable:** Device info includes platform, screen, timestamps
5. **Portable:** Export/import for device migration

## Files Modified

- `frontend/lib/deviceFingerprint.ts` (new)
- `frontend/components/SettingsTab.tsx` (updated import and usage)

## Backend Requirements

Backend must:
1. Accept `X-Device-ID` header in requests
2. Create DeviceSettings record if not exists
3. Store all settings keyed by device_id
4. Return existing settings on subsequent requests

**Example Backend Endpoint:**
```python
@router.get("/")
async def get_settings(x_device_id: str = Header(None)):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID required")
    
    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == x_device_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create new device settings
        settings = DeviceSettings(device_id=x_device_id)
        db.add(settings)
        await db.commit()
    
    return settings.to_dict()
```

## Edge Cases Handled

1. **First Visit:** Generates new device ID
2. **App Update:** Recovers from localStorage
3. **Partial Clear:** Recovers from backup key
4. **Browser Clear:** Generates new ID (unavoidable)
5. **Multiple Tabs:** Same ID across all tabs
6. **Incognito Mode:** New ID each session (expected behavior)