---
name: whatsapp-trade-notifications
description: Implement WhatsApp notifications for trade executions and closures using OpenWA with encrypted phone storage
source: auto-skill
extracted_at: '2026-06-02T11:06:29.947Z'
---

# WhatsApp Trade Notifications Integration

## Overview
Integrate real-time WhatsApp notifications for trading applications using OpenWA (local WhatsApp Web API). All notifications are sent when trades execute or close, with phone numbers encrypted per-device.

## Architecture

```
Trade Execution → WhatsApp Service → OpenWA (localhost:3001) → User's WhatsApp
       ↓                ↓                    ↓
   Backend API    Encrypted Storage    WhatsApp Web
```

## Key Files

### Backend Service
```
backend/app/services/whatsapp_service.py
```

**Core features:**
- Fernet (AES-256) encryption for phone numbers
- Per-device configuration storage
- Message templates for different events
- Lazy connection to OpenWA

### API Router
```
backend/app/api/v1/whatsapp.py
```

**Endpoints:**
- `GET /api/v1/whatsapp/status` - Get configuration
- `POST /api/v1/whatsapp/configure` - Save phone + enable
- `POST /api/v1/whatsapp/test` - Send test message
- `POST /api/v1/whatsapp/enable` / `disable` - Toggle notifications

### Frontend Settings
```
frontend/app/settings/page.tsx
```

**UI components:**
- Phone number input (international format)
- OpenWA URL configuration
- Enable/disable toggle checkbox
- Test connection button
- Status indicator

## Implementation Steps

### Step 1: Create WhatsApp Service
```python
from cryptography.fernet import Fernet
import httpx
from pathlib import Path

class WhatsAppService:
    def __init__(self):
        self.cipher = self._init_encryption()
        self.config_file = Path("data/whatsapp_config.json")
        self.load_config()
    
    def _init_encryption(self):
        key_path = Path("data/whatsapp.key")
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
        return Fernet(key)
    
    async def send_message(self, phone: str, message: str) -> bool:
        formatted = self._format_phone(phone)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.openwa_url}/api/send",
                json={"phone": formatted, "message": message}
            )
            return resp.status_code == 200
```

### Step 2: Add Notification Triggers
**Trade execution** (`backend/app/api/v1/trading.py`):
```python
@router.post("/execute")
async def execute_trade(...):
    # ... execute trade ...
    
    # Send WhatsApp after successful execution
    asyncio.create_task(_send_trade_whatsapp(trade, side, quantity, symbol))
```

**Trade closure** (`backend/app/services/trade_monitor.py`):
```python
async def on_trade_closed(self, trade: Trade):
    # ... calculate PnL ...
    
    # Send WhatsApp with PnL details
    asyncio.create_task(
        whatsapp_service.notify_trade_closed({
            "action": trade.type,
            "symbol": trade.symbol,
            "pnl": trade.pnl,
            "pnl_percent": pnl_percent,
 inevitability         "hold_duration": duration_minutes
        })
    )
```

### Step 3: Build Settings UI
```tsx
interface WhatsAppSettings {
  phone_number: string;
  enabled: boolean;
  openwa_url: string;
}

export default function SettingsPage() {
  const [whatsapp, setWhatsapp] = useState<WhatsAppSettings>(...);
  
  const saveConfig = async () => {
    await fetch('/api/v1/whatsapp/configure', {
      method: 'POST',
      body: JSON.stringify(whatsapp),
    });
  };
  
  const testConnection = async () => {
    const res = await fetch('/api/v1/whatsapp/test', { method: 'POST' });
    // Show success/failure toast
  };
  
  return (
    <section>
      <input 
        type="tel" 
        value={whatsapp.phone_number}
        placeholder="+1 234 567 8900"
      />
      <input
        type="url"
        value={whatsapp.openwa_url}
        placeholder="http://localhost:3001"
      />
      <checkbox checked={whatsapp.enabled} />
      <button onClick={saveConfig}>Save</button>
      <button onClick={testConnection}>Test</button>
    </section>
  );
}
```

### Step 4: Handle Python 3.14 Compatibility
**Problem:** `ib_insync` uses `eventkit` which calls `get_event_loop()` at import time, breaking on Python 3.14.

**Solution:** Lazy-load IBKR service:
```python
# backend/app/brokers/registry.py
def _get_ibkr_class():
    try:
        from app.brokers.ibkr_service import IBKRBrokerService
        return IBKRBrokerService
    except RuntimeError as e:
        if "event loop" in str(e):
            return None  # Gracefully skip IBKR
        raise

# Use in initialize_brokers()
IBKRClass = _get_ibkr_class()
if IBKRClass:
    ibkr = IBKRClass(config)
```

## Message Templates

### Trade Executed
```
🔔 TRADE EXECUTED

{ACTION} {SHARES} {SYMBOL}
━━━━━━━━━━━━━━━━━━━━
💰 Price: ${PRICE}
💵 Total: ${TOTAL}
🤖 Agent: {AGENT}
📈 Type: {ORDER_TYPE}
━━━━━━━━━━━━━━━━━━━━
⏰ {TIMESTAMP}
```

### Trade Closed
```
✅ TRADE CLOSED - {WIN/LOSS}

{ACTION} {SHARES} {SYMBOL}
━━━━━━━━━━━━━━━━━━━━
💰 Entry: ${ENTRY}
💰 Exit: ${EXIT}
📊 PnL: ${PNL} ({PNL_PERCENT}%)
⏱ Hold: {DURATION}
━━━━━━━━━━━━━━━━━━━━
⏰ {TIMESTAMP}
```

## Configuration Flow

1. **User enters phone** → Frontend stores in state
2. **Click Save** → POST to `/api/v1/whatsapp/configure`
3. **Backend encrypts** → Saves to SQLite with device ID
4. **Click Test** → POST to `/api/v1/whatsapp/test`
5. **Service sends** → OpenWA sends WhatsApp message
6. **User receives** → Confirms working on phone

## Security Considerations

- **Encryption key** stored at `backend/data/whatsapp.key` (never commit)
- **Phone numbers** encrypted before DB storage
- **Per-device isolation** → Each device has separate config
- **Local-only** → OpenWA runs on user's machine, no external data

## Testing Checklist

- [ ] OpenWA server running on localhost:3001
- [ ] QR code scanned and connected
- [ ] Phone number saved (check DB: encrypted)
- [ ] Test message received on WhatsApp
- [ ] Trade execution triggers notification
- [ ] Trade closure triggers notification with PnL
- [ ] Disable toggle stops notifications
- [ ] Re-enable works without re-configuring

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "OpenWA not reachable" | Start OpenWA: `npm start` |
| Message not received | Check phone format (+1...), verify WhatsApp connected |
| Import error on startup | Lazy-load IBKR (Python 3.14 fix) |
| Notifications not sending | Check `enabled` flag in DB, verify OpenWA URL |

## External Resources

- OpenWA: https://github.com/rmyndharis/OpenWA
- Twilio WhatsApp (production alternative): https://www.twilio.com/whatsapp
- Fernet encryption docs: https://cryptography.io/en/latest/fernet/