---
name: settings-env-var-indicators
description: Add visual indicators to settings fields showing when API keys are configured via Render environment variables
source: auto-skill
extracted_at: '2026-06-28T18:29:29.366Z'
---

# Settings Page - Environment Variable Indicators

## Problem
Users need to know which API keys/secrets are already configured in Render dashboard environment variables versus which ones need to be filled in the Settings page. When credentials are set via Render environment variables during deployment, the settings fields should visually indicate this.

## Solution

### Backend Implementation

**File**: `backend/app/api/v1/settings.py`

Add a new endpoint to check environment variable status:

```python
@router.get("/env-status")
async def get_env_status():
    """
    Check which environment variables are configured in the deployment environment.
    
    Returns status of API keys and secrets that should be set via Render dashboard
    environment variables during deployment.
    """
    from app import config
    
    cfg = config.settings
    
    env_status = {
        "nvidia_api_key": {
            "configured": bool(cfg.NVIDIA_API_KEY and cfg.NVIDIA_API_KEY != "" and cfg.NVIDIA_API_KEY != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "NVIDIA_API_KEY",
            "description": "NVIDIA NIM API key for AI model inference",
            "required_for": "AI chat, trade analysis, Kronos predictions"
        },
        "binance_api_key": {
            "configured": bool(cfg.BINANCE_API_KEY and cfg.BINANCE_API_KEY != "" and cfg.BINANCE_API_KEY != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "BINANCE_API_KEY",
            "description": "Binance API key for crypto trading",
            "required_for": "Binance spot/futures trading"
        },
        "binance_api_secret": {
            "configured": bool(cfg.BINANCE_API_SECRET and cfg.BINANCE_API_SECRET != "" and cfg.BINANCE_API_SECRET != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "BINANCE_API_SECRET",
            "description": "Binance API secret for crypto trading",
            "required_for": "Binance spot/futures trading"
        },
        "telegram_bot_token": {
            "configured": bool(cfg.TELEGRAM_BOT_TOKEN and cfg.TELEGRAM_BOT_TOKEN != "" and cfg.TELEGRAM_BOT_TOKEN != "CHANGE_THIS_BEFORE_PRODUCTION"),
            "env_var": "TELEGRAM_BOT_TOKEN",
            "description": "Telegram bot token for notifications",
            "required_for": "Trade notifications, daily summaries"
        },
        # Add more variables as needed
    }
    
    # Calculate summary
    total_vars = len(env_status)
    configured_count = sum(1 for v in env_status.values() if v["configured"])
    
    return {
        "environment_variables": env_status,
        "summary": {
            "total": total_vars,
            "configured": configured_count,
            "missing": total_vars - configured_count
        }
    }
```

### Frontend Implementation

**File**: `frontend/components/SettingsTab.tsx`

#### Step 1: Add state for environment status

```typescript
// Environment variable status
const [envStatus, setEnvStatus] = useState<{
  environment_variables: Record<string, {
    configured: boolean;
    env_var: string;
    description: string;
    required_for: string;
  }>;
  summary: {
    total: number;
    configured: number;
    missing: number;
  };
} | null>(null);
```

#### Step 2: Add fetch function

```typescript
const fetchEnvStatus = async () => {
  try {
    const envRes = await fetch(`${API_URL}/api/v1/settings/env-status`);
    const envData = await envRes.json();
    setEnvStatus(envData);
  } catch (error) {
    console.error('Failed to load env status:', error);
  }
};
```

#### Step 3: Call fetch on component mount

```typescript
useEffect(() => {
  fetchSettings();
  fetchEnvStatus();  // Add this
  checkPolymarketConnection();
}, []);
```

#### Step 4: Add visual indicators to each settings field

For each API key field, add:

**Badge indicator** (next to Test button):
```tsx
{envStatus?.environment_variables?.nvidia_api_key?.configured && (
  <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 border border-green-500/30 flex items-center gap-1">
    <Check className="w-3 h-3" /> ENV
  </span>
)}
```

**Help text below input**:
```tsx
{envStatus?.environment_variables?.nvidia_api_key?.configured && (
  <p className="text-xs text-green-400 mt-2 flex items-center gap-1">
    <Server className="w-3 h-3" />
    Set via Render environment variable: NVIDIA_API_KEY
  </p>
)}
```

## Usage Pattern

1. **Deploy to Render**: User sets environment variables in Render dashboard (Settings → Environment Variables)
2. **Auto-detection**: Backend `/api/v1/settings/env-status` endpoint checks which variables are set
3. **Visual feedback**: Settings page shows green "ENV" badge for fields that are already configured
4. **User guidance**: Users know they don't need to fill in those fields - values come from deployment environment

## Benefits

- **Clear status**: Users immediately see which credentials are pre-configured
- **Deployment awareness**: Bridges gap between deployment environment and runtime UI
- **Reduced confusion**: Prevents users from thinking fields are empty when they actually have values from ENV
- **Security**: Encourages using environment variables for sensitive credentials instead of UI inputs

## Example UI States

**Not configured** (local dev without ENV):
- No badge shown
- No help text
- User fills in the field manually

**Configured via Render ENV**:
- Green "ENV" badge with checkmark next to Test button
- Help text: "Set via Render environment variable: NVIDIA_API_KEY"
- User knows value comes from deployment, not stored in database

## Environment Variables to Track

Common variables for this project:
- `NVIDIA_API_KEY` - AI model inference
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` - Crypto trading
- `TELEGRAM_BOT_TOKEN` - Notifications
- `TROVE_API_KEY` - Nigerian/US stocks broker
- `CTRADER_CLIENT_ID` / `CTRADER_CLIENT_SECRET` - Copy trading OAuth
- `KRONOS_COLAB_URL` - AI predictions endpoint

## Render Deployment Instructions for Users

```
To set environment variables on Render:
1. Go to Render dashboard → Select your backend service
2. Click "Environment" tab
3. Add each variable (e.g., NVIDIA_API_KEY) with its value
4. Click "Save Changes" - Render will automatically redeploy
5. Changes take effect within 2-3 minutes
```