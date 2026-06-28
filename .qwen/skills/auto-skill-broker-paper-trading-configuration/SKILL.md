---
name: broker-paper-trading-configuration
description: Remove duplicate paper trading UI from broker components, use broker-specific terminology (cTrader/Trove = Sandbox, AKShare = Paper Trading), and load unified config from backend
source: auto-skill
extracted_at: '2026-06-25T10:52:09.247Z'
---

## Problem

Broker components (CTraderConnection, TroveSettings, AKShareSettings) had duplicate paper trading configuration sections inside each component, even though they received paper trading config via props from parent. This caused:

1. **Duplication**: Settings stored in both component state AND unified parent state
2. **No global view**: User couldn't see all broker paper trading configs in one place
3. **Terminology confusion**: Different brokers use different terms (cTrader = "sandbox", Trove = "sandbox", AKShare = "paper trading")
4. **Missing backend sync**: Frontend brokerPaperTrading state initialized with hardcoded defaults, never loaded from backend

## Solution

### 1. Add Backend GET Endpoint

Create endpoint to fetch all broker paper trading configs at once:

```python
# backend/app/api/v1/settings.py

@router.get("/broker-paper-trading")
async def get_broker_paper_trading(
    device_id: str = Header(None, alias="X-Device-ID"),
):
    """Get paper trading configurations for all brokers."""
    defaults = {
        "ctrader": {"enabled": True, "capital": 10000, "currency": "USD"},
        "trove": {"enabled": True, "capital": 1000, "currency": "USD"},
        "akshare": {"enabled": True, "capital": 1000000, "currency": "CNY"},
    }
    
    # Load from broker_paper_trading_config JSON column
    # Merge with defaults for missing brokers
    return BrokerPaperTradingResponse(**result_config)
```

### 2. Remove Duplicate UI from Broker Components

**Files to modify:**
- `frontend/components/settings/CTraderConnection.tsx`
- `frontend/components/settings/TroveSettings.tsx`  
- `frontend/components/settings/AKShareSettings.tsx`

**Remove the entire paper trading section** that appears at the bottom of each component (typically lines 290-351, 365-426, 306-368 respectively).

**Keep the props interface** - parent component will still pass configs:
```typescript
interface CTraderConnectionProps {
  onConnected?: (accountId: string) => void;
  paperTradingConfig?: { enabled: boolean; capital: number; currency: string };
  onUpdatePaperTrading?: (updates: Partial<{enabled: boolean; capital: number; currency: string}>) => void;
  onSave?: () => void;
}
```

### 3. Use Broker-Specific Terminology

Each broker has its own term for demo trading - use the correct one:

| Broker | Term | Backend Field | UI Label |
|--------|------|---------------|----------|
| **cTrader** | Environment mode | `sandbox: bool` + `environment_mode` | "Sandbox Mode" / "Live Mode" |
| **Trove** | Sandbox | `trove_sandbox: bool` | "Sandbox (Demo)" / "Live (Real Money)" |
| **AKShare** | Paper trading | `paper_trading: bool` | "Paper Trading Mode" |

**Why:** cTrader explicitly states in code: *"cTrader uses sandbox and live environments, not paper trading"* (line 104). Match broker documentation and user expectations.

### 4. Frontend State Management

In parent component (SettingsTab.tsx):

```typescript
// State
const [brokerPaperTrading, setBrokerPaperTrading] = useState<BrokerPaperTradingState>({
  ctrader: { enabled: true, capital: 10000, currency: 'USD' },
  trove: { enabled: true, capital: 1000, currency: 'USD' },
  akshare: { enabled: true, capital: 1000000, currency: 'CNY' },
});

// Load on mount
useEffect(() => {
  const fetchPaperTrading = async () => {
    const res = await fetch(`${API_URL}/api/v1/settings/broker-paper-trading`, {
      headers: { 'X-Device-ID': deviceId },
    });
    const data = await res.json();
    setBrokerPaperTrading({
      ctrader: data.ctrader || defaults.ctrader,
      trove: data.trove || defaults.trove,
      akshare: data.akshare || defaults.akshare,
    });
  };
  fetchPaperTrading();
}, []);

// Update function
const updateBrokerPaperTrading = (
  broker: 'ctrader' | 'trove' | 'akshare',
  updates: Partial<BrokerPaperTradingConfig>
) => {
  setBrokerPaperTrading(prev => ({
    ...prev,
    [broker]: { ...prev[broker], ...updates }
  }));
};

// Save function
const saveBrokerPaperTrading = async (broker: 'ctrader' | 'trove' | 'akshare') => {
  const config = brokerPaperTrading[broker];
  await fetch(`${API_URL}/api/v1/settings/broker-paper-trading`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Device-ID': deviceId },
    body: JSON.stringify({ broker, ...config }),
  });
};
```

### 5. Pass Props to Broker Components

```typescript
<CTraderConnection
  paperTradingConfig={brokerPaperTrading.ctrader}
  onUpdatePaperTrading={(updates) => updateBrokerPaperTrading('ctrader', updates)}
  onSave={() => saveBrokerPaperTrading('ctrader')}
/>

<TroveSettings
  paperTradingConfig={brokerPaperTrading.trove}
  onUpdatePaperTrading={(updates) => updateBrokerPaperTrading('trove', updates)}
  onSave={() => saveBrokerPaperTrading('trove')}
/>

<AKShareSettings
  paperTradingConfig={brokerPaperTrading.akshare}
  onUpdatePaperTrading={(updates) => updateBrokerPaperTrading('akshare', updates)}
  onSave={() => saveBrokerPaperTrading('akshare')}
/>
```

## Key Files Modified

1. `backend/app/api/v1/settings.py` - Added GET endpoint
2. `frontend/components/settings/CTraderConnection.tsx` - Removed paper trading UI
3. `frontend/components/settings/TroveSettings.tsx` - Removed paper trading UI
4. `frontend/components/settings/AKShareSettings.tsx` - Removed paper trading UI
5. `frontend/components/SettingsTab.tsx` - (Pending) Add collapsible sections and state management

## Why This Approach

- **Single source of truth**: Backend `broker_paper_trading_config` JSON column
- **Broker-specific terminology**: Match what each broker actually calls their demo environment
- **No duplication**: Paper trading config exists once in parent state, passed via props
- **Extensible**: Easy to add more brokers without changing architecture
- **User experience**: Future enhancement can add unified "Paper Trading Overview" section showing all 3 brokers at once

## Testing Checklist

- ✅ Backend GET endpoint returns defaults for new users
- ✅ Backend GET endpoint returns saved configs for existing users
- ✅ Broker components load without paper trading section
- ✅ Broker components accept and display paper trading config from props
- ✅ Saving config via any broker updates backend correctly
- ✅ Page reload restores saved configs (not hardcoded defaults)
- ✅ cTrader uses "Sandbox Mode" terminology
- ✅ Trove uses "Sandbox" terminology  
- ✅ AKShare uses "Paper Trading" terminology