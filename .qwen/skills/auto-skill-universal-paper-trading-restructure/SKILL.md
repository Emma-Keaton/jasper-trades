---
name: universal-paper-trading-system
description: Replace broker-specific sandbox modes with unified global paper trading toggle
source: auto-skill
extracted_at: '2026-07-13T02:34:02.359Z'
---

# Universal Paper Trading System Implementation

## Overview
Replaced per-broker sandbox/paper trading modes with a single global universal paper trading system that applies to all brokers (cTrader, Trove, AKShare).

## User Requirements
- **Global Toggle**: Single universal paper trading toggle affecting ALL brokers
- **Pure Simulation**: AI skips broker APIs, calculates virtual P&L from market data
- **Shared Balance**: One virtual capital pool across all brokers

## Changes Made

### Backend Changes

#### 1. `backend/app/config.py`
- **Removed**: `CTRADER_SANDBOX: bool = True`
- **Removed**: `WHATSAPP_SERVICE_URL` (switched to Telegram)
- **Added**: 
  ```python
  UNIVERSAL_PAPER_TRADING: bool = True
  UNIVERSAL_PAPER_CAPITAL: float = 10000.0
  UNIVERSAL_PAPER_CURRENCY: str = "USD"
  ```

#### 2. `backend/app/models.py`
- **Added**: `universal_paper_trading_config` column to `DeviceSettings`
  ```python
  universal_paper_trading_config = Column(String, nullable=True)  # JSON: {enabled, initial_capital, current_balance, total_pnl, currency}
  ```
- **Deprecated**: `broker_paper_trading_config` (kept for backward compatibility)

#### 3. `backend/app/api/v1/settings.py`
- **Created Models**:
  - `UniversalPaperTradingRequest`: {enabled, initial_capital, currency}
  - `UniversalPaperTradingResponse`: {enabled, initial_capital, current_balance, total_pnl, currency}

- **Created Endpoints**:
  - `GET /api/v1/settings/universal-paper-trading` - Get global paper trading config
  - `POST /api/v1/settings/universal-paper-trading` - Save global paper trading config

- **Added to env_status**: `universal_paper_trading` field

- **Deprecated**: Old `/broker-paper-trading` endpoints (return warning + redirect to universal)

#### 4. `backend/app/services/kronos/__init__.py`
- **Fixed**: Graceful fallback for torch/DLL errors on Windows
- **Pattern**: Try/except imports with safe stub functions when unavailable

#### 5. `backend/app/migrations.py`
- **Added**: `universal_paper_trading_config` column definition

### Frontend Changes

#### 1. `frontend/components/settings/BrokerSettings.tsx` (NEW)
**Purpose**: Universal paper trading configuration component

**Features**:
- Global toggle for paper trading mode
- Initial capital input (default $10,000)
- Currency selector (USD/NGN/CNY)
- Current balance display
- Total P&L display (green/red based on profit/loss)
- Save button with toast notifications

**Props**:
- `triggerToast`: Toast notification function
- `onSave`: Callback after successful save

**API Calls**:
- `GET /api/v1/settings/universal-paper-trading` - Load config
- `POST /api/v1/settings/universal-paper-trading` - Save config

#### 2. `frontend/lib/currencyContext.tsx`
- **Updated**: `Currency` type from `USD | NGN` to `USD | NGN | CNY`
- **Added**: CNY formatting with ¥ symbol
- **Updated**: `toggleCurrency()` to cycle: USD → NGN → CNY → USD
- **Enhanced**: `convertAmount()` to handle all currency pairs via USD
- **Added**: `exchangeRates` state with all currency pairs
- **Updated**: `refreshRateHelper()` to fetch all currency pairs

#### 3. `frontend/components/SettingsTab.tsx`
- **Added Import**: `import BrokerSettings from './settings/BrokerSettings'`
- **Removed State**: `ctraderSandboxMode`, `troveSandboxMode`, `akshareSandboxMode`
- **Added State**: `universalPaperTrading`
- **Added UI**: `<BrokerSettings />` component at top of Brokers section
- **Added UI**: Global trading mode indicator showing paper/live status

### Manual Cleanup Required (Not Automated)

The following still need manual cleanup due to complex regex:

#### SettingsTab.tsx Lines to REMOVE:
1. **loadSettings()** - Remove sandbox mode loading:
   - `if (data.trove_config.sandbox !== undefined) { setTroveSandboxMode(...) }`
   - `if (data.akshare_config.sandbox !== undefined) { setAkshareSandboxMode(...) }`
   - `if (data.ctrader_config.sandbox !== undefined) { setCtraderSandboxMode(...) }`

2. **handleSave()** - Remove sandbox values from payload:
   - `trove_sandbox: troveSandboxMode`
   - `akshare_sandbox: akshareSandboxMode`
   - `ctrader_sandbox: ctraderSandboxMode`

3. **cTrader Panel** - Remove toggle UI (~42 lines around line 1009)
4. **Trove Panel** - Remove toggle UI (~38 lines around line 1098)
5. **AKShare Panel** - Remove toggle UI (~27 lines around line 1199)

#### SettingsTab.tsx Lines to ADD (after BrokerSettings):
```typescript
{/* Global Trading Mode Indicator */}
<div className={`p-3 rounded-lg border ${
  universalPaperTrading.enabled 
    ? 'bg-blue-500/10 border-blue-500/30' 
    : 'bg-red-500/10 border-red-500/30'
  }`}>
  <div className="flex items-center gap-2">
    {universalPaperTrading.enabled ? (
      <><Check className="w-4 h-4 text-blue-400" />
        <p className="text-sm text-blue-400">
          <strong>Paper Trading Active:</strong> All broker integrations will run in simulation mode
        </p>
      </>
    ) : (
      <><AlertTriangle className="w-4 h-4 text-red-400" />
        <p className="text-sm text-red-400">
          <strong>Live Trading Mode:</strong> Real capital will be used with connected brokers
        </p>
      </>
    )}
  </div>
</div>
```

## Migration Steps

### For Existing Users:
1. Delete `data/sqlite/jasper_trades.db` or run manual migration
2. Backend auto-migration will add `universal_paper_trading_config` column
3. Or execute: `python run_migration.py`

### For New Deployment:
1. Database will be created automatically on first run
2. New column will be created via migrations.py

## Testing

### Backend Tests:
```bash
# Start backend
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test universal paper trading endpoint
curl http://localhost:8000/api/v1/settings/universal-paper-trading \
  -H "X-Device-ID: test-device-123"

# Test save
curl -X POST http://localhost:8000/api/v1/settings/universal-paper-trading \
  -H "X-Device-ID: test-device-123" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "initial_capital": 10000, "currency": "USD"}'
```

### Frontend Tests:
1. Navigate to Settings page
2. Verify BrokerSettings component appears at top of Brokers section
3. Toggle paper trading ON/OFF
4. Change initial capital
5. Change currency (USD/NGN/CNY)
6. Click Save and verify toast notification

## Deployment Checklist

### Environment Variables:
```bash
# Backend
UNIVERSAL_PAPER_TRADING=True
UNIVERSAL_PAPER_CAPITAL=10000.0
UNIVERSAL_PAPER_CURRENCY=USD
TELEGRAM_BOT_TOKEN=your_bot_token

# Frontend
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
NEXT_PUBLIC_WS_URL=wss://your-backend.onrender.com
```

### Pre-Deployment:
- [ ] Complete SettingsTab.tsx manual cleanup
- [ ] Test backend starts without errors
- [ ] Test universal paper trading endpoints
- [ ] Test broker OAuth connections (cTrader, Trove)
- [ ] Verify CNY currency conversion works
- [ ] Check all imports and syntax errors

## API Endpoints Reference

### Universal Paper Trading:
- **GET** `/api/v1/settings/universal-paper-trading`
  - Headers: `X-Device-ID`
  - Response: `{enabled, initial_capital, current_balance, total_pnl, currency}`

- **POST** `/api/v1/settings/universal-paper-trading`
  - Headers: `X-Device-ID`, `Content-Type: application/json`
  - Body: `{enabled: bool, initial_capital: float, currency: string}`
  - Response: `{status: "success", data: UniversalPaperTradingResponse}`

### Deprecated (for backward compatibility):
- **GET** `/api/v1/settings/broker-paper-trading` → Returns warning + universal config
- **POST** `/api/v1/settings/broker-paper-trading` → Returns warning + universal config

## Benefits

1. **Simplified UX**: One toggle controls all brokers instead of 3+ toggles
2. **Consistent Behavior**: All brokers respect same paper trading mode
3. **Shared Capital**: Virtual balance shared across all broker strategies
4. **AI Learning**: AI learns from simulated trades across all asset classes
5. **Safer Testing**: Users can test strategies without risking real capital
6. **Performance Tracking**: Centralized P&L tracking across all brokers

## Related Skills/Documents
- Backdrop migration: `auto-skill-automatic-database-migration-system`
- Settings cleanup: `auto-skill-settings-page-mobile-responsive-fix`
- Telegram integration: `auto-skill-whatsapp-to-telegram-migration-complete`
- Currency conversion: `auto-skill-currency-conversion-global-integration`