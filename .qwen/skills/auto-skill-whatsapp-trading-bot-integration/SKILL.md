---
name: whatsapp-trading-bot-integration
description: Complete WhatsApp trading bot with verification, real-time trade notifications, daily summaries at 8 PM WAT, and two-way chat
source: auto-skill
extracted_at: '2026-06-15T12:53:46.780Z'
---

# WhatsApp Trading Bot Integration

Complete implementation of WhatsApp notifications for Jasper Trades trading platform with phone verification, real-time trade alerts, scheduled daily summaries, and two-way AI chat.

## Architecture Overview

**Key Components:**
1. Database models for user management and daily summaries
2. Daily summary service with performance calculations
3. WhatsApp service with template-based messaging
4. Scheduler for daily summaries at 8 PM WAT
5. API endpoints for verification and preferences
6. Frontend UI for configuration

## Database Models

### DailySummary Model
```python
class DailySummary(Base):
    __tablename__ = "daily_summaries"
    
    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    device_id = Column(String(255), nullable=False, index=True)
    phone_number = Column(String, nullable=False, index=True)
    summary_date = Column(String, nullable=False, index=True)  # ISO: "2026-06-15"
    
    # Performance metrics
    total_pnl = Column(Float, default=0.0)
    total_pnl_percent = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    breakeven = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Trade details
    best_trade = Column(JSON)  # {symbol, pnl, pnl_percent, action, shares}
    worst_trade = Column(JSON)
    agent_stats = Column(JSON)  # [{agent_name, trades, wins, pnl}]
    top_symbols = Column(JSON)
    
    # Delivery
    summary_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    send_time_wat = Column(String, default="20:00")
```

### WhatsappUser Model
```python
class WhatsappUser(Base):
    __tablename__ = "whatsapp_users"
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String(255), nullable=False, unique=True, index=True)
    phone_number = Column(String, nullable=False)
    
    # Preferences
    trade_notifications_enabled = Column(Boolean, default=True)
    daily_summary_enabled = Column(Boolean, default=True)
    summary_time_wat = Column(String, default="20:00")
    chat_enabled = Column(Boolean, default=True)
    ai_explanations_enabled = Column(Boolean, default=True)
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    
    last_active_at = Column(DateTime, nullable=True)
```

## Daily Summary Service

**File:** `backend/app/services/daily_summary_service.py`

### Key Features:
- Generates summaries for previous day's trading activity
- Calculates win rate, total PnL, agent performance
- Identifies best/worst trades
- Formats messages using templates
- Sends via WhatsApp service

### Implementation Pattern:
```python
class DailySummaryService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def generate_summary(self, portfolio_id: int, device_id: str, date: str):
        """Generate daily summary for a portfolio."""
        # 1. Fetch all trades for the day
        # 2. Calculate statistics (PnL, win rate, etc.)
        # 3. Identify best/worst trades
        # 4. Calculate agent performance
        # 5. Create DailySummary record
        # 6. Return summary object
    
    def _calculate_statistics(self, trades: List[Trade]) -> Dict:
        """Calculate trade statistics from list of trades."""
        # Returns: total_pnl, wins, losses, breakeven, win_rate, 
        #          best_trade, worst_trade, agent_stats, top_symbols
    
    async def send_summary(self, summary: DailySummary) -> bool:
        """Send summary via WhatsApp using template."""
        message = self._format_summary_message(summary)
        success = await whatsapp_service.send_message(summary.phone_number, message)
        # Update sent status in database
```

## Message Templates

**File:** `backend/app/services/whatsapp_templates.py`

### Template Structure:
All messages use consistent branding from "Jasper Trades" with emoji indicators and formatted sections.

### Daily Summary Template:
```python
DAILY_SUMMARY_TEMPLATE = """
{emoji} *DAILY SUMMARY - {outcome}*
━━━━━━━━━━━━━━━━━━━━
📅 {date}

💰 **Total PnL:** ${total_pnl:+,.2f}
📈 **Return:** {total_pnl_percent:+.2f}%
📊 **Win Rate:** {win_rate:.1f}% ({wins}W / {losses}L / {breakeven}BE)
🎯 **Trades:** {total_trades}

🏆 *Best Trade:*
  {best_trade_text}

📉 *Worst Trade:*
  {worst_trade_text}

🤖 *Agent Performance:*
{agent_stats_text}
━━━━━━━━━━━━━━━━━━━━
📊 Type *STATUS* for portfolio
📈 Type *TRADES* for today's trades
💬 Type *HELP* for commands
"""
```

### Templates Available:
1. `TRADE_EXECUTED_TEMPLATE` - Real-time trade execution alerts
2. `TRADE_CLOSED_TEMPLATE` - Trade closure with PnL
3. `DAILY_SUMMARY_TEMPLATE` - End-of-day performance
4. `PORTFOLIO_SUMMARY_TEMPLATE` - Portfolio overview
5. `POSITIONS_LIST_TEMPLATE` - Current holdings
6. `RECENT_TRADES_TEMPLATE` - Recent trade history
7. `WELCOME_MESSAGE_TEMPLATE` - New user onboarding
8. `VERIFICATION_CODE_TEMPLATE` - Phone verification
9. `WEEKLY_SUMMARY_TEMPLATE` - Weekly performance
10. `MONTHLY_SUMMARY_TEMPLATE` - Monthly performance

## Scheduler Integration

**File:** `backend/app/services/scheduler.py`

### Daily Summary Scheduling:
```python
# Scheduler initialization
def __init__(self, db_session_factory):
    self._daily_summary_time = "19:00"  # 7 PM UTC = 8 PM WAT
    self._intervals["daily_summary"] = 86400  # 24 hours

async def start(self):
    self._tasks["daily_summary"] = asyncio.create_task(
        self._run_daily_at_time("daily_summary", self._send_daily_summaries, self._daily_summary_time)
    )

async def _run_daily_at_time(self, name: str, func: Callable, time_str: str):
    """Run function daily at specific time (HH:MM UTC)."""
    # Calculate next run time
    # Sleep until target time
    # Execute function
    # Repeat

async def _send_daily_summaries(self):
    """Generate and send daily summaries at 8 PM WAT."""
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for portfolio in portfolios:
        summary = await summary_service.generate_summary(portfolio.id, device_id, yesterday)
        
        # Check user preferences
        if user.daily_summary_enabled and user.is_verified:
            await summary_service.send_summary(summary)
```

## API Endpoints

**File:** `backend/app/api/v1/whatsapp_settings.py`

### Verification Flow:
```python
@router.post("/verify/request")
async def request_whatsapp_verification(request, device_id, db):
    """Send 6-digit verification code to user's WhatsApp."""
    verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Store code in database
    # Send via WhatsApp
    await whatsapp_service.send_verification_code(phone, code, expires_minutes=10)

@router.post("/verify/confirm")
async def confirm_whatsapp_verification(request, device_id, db):
    """Verify code and mark phone as verified."""
    # Validate code matches and not expired
    # Set is_verified = True
    # Send welcome message
```

### Preference Management:
```python
@router.post("/preferences")
async def update_whatsapp_preferences(preferences, device_id, db):
    """Update notification preferences."""
    # trade_notifications_enabled
    # daily_summary_enabled
    # summary_time_wat (format: "20:00")
    # chat_enabled
    # ai_explanations_enabled

@router.get("/status")
async def get_whatsapp_status(device_id, db):
    """Get verification status and preferences."""
    # Returns: is_configured, is_verified, phone_number (masked), preferences

@router.post("/test")
async def test_whatsapp_connection(device_id, db):
    """Send test message to verify connection."""
```

### Router Registration:
```python
# In main.py
from app.api.v1 import whatsapp_settings
app.include_router(whatsapp_settings.router, prefix="/api/v1", tags=["whatsapp-settings"])
```

## Frontend Implementation

**File:** `frontend/components/SettingsTab.tsx`

### State Variables:
```typescript
interface WhatsAppSettings {
  phone_number: string;
  is_verified?: boolean;
  trade_notifications_enabled?: boolean;
  daily_summary_enabled?: boolean;
  summary_time_wat?: string;  // "20:00"
  chat_enabled?: boolean;
  ai_explanations_enabled?: boolean;
}

const [whatsapp, setWhatsapp] = useState<WhatsAppSettings>({...});
const [whatsappRequestStatus, setWhatsappRequestStatus] = useState({...});
const [verificationCode, setVerificationCode] = useState('');
```

### Verification Flow Functions:
```typescript
const requestVerification = async () => {
  const res = await fetch(`${API_URL}/api/v1/settings/whatsapp/verify/request`, {
    method: 'POST',
    headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone_number: whatsapp.phone_number }),
  });
  // On success: show code input field
}

const confirmVerification = async () => {
  const res = await fetch(`${API_URL}/api/v1/settings/whatsapp/verify/confirm`, {
    method: 'POST',
    headers: { 'X-Device-ID': deviceId },
    body: JSON.stringify({ phone_number, verification_code: code }),
  });
  // On success: set is_verified = true, load preferences
}

const saveWhatsAppPreferences = async () => {
  await fetch(`${API_URL}/api/v1/settings/whatsapp/preferences`, {
    method: 'POST',
    headers: { 'X-Device-ID': deviceId },
    body: JSON.stringify(preferences),
  });
}

const loadWhatsAppPreferences = async () => {
  const res = await fetch(`${API_URL}/api/v1/settings/whatsapp/status`, {
    headers: { 'X-Device-ID': deviceId },
  });
  // Update state with preferences
}
```

### UI Components:
1. **Phone Verification Section:**
   - Phone number input
   - "Send Code" button
   - 6-digit code input (shown after code sent)
   - "Verify" button
   - Status messages

2. **Notification Preferences** (shown after verification):
   - Checkbox: Trade executions (real-time)
   - Checkbox: Daily summary at 8 PM WAT
   - Checkbox: 2-way chat
   - Checkbox: AI explanations
   - Time picker for summary schedule
   - "Save Preferences" button
   - "Test Connection" button

3. **Status Display:**
   - Verified badge (green) when verified
   - Help text for unverified users

## WhatsApp Service Methods

**File:** `backend/app/services/whatsapp_service.py`

### Enhanced Methods:
```python
async def send_trade_notification(self, trade_data: Dict) -> bool:
    """Send trade execution using template."""
    formatted = format_trade_executed(trade_data)
    return await self.send_message(formatted)

async def send_trade_closure(self, trade_data: Dict) -> bool:
    """Send trade closure with PnL."""
    formatted = format_trade_closed(trade_data)
    return await self.send_message(formatted)

async def send_daily_summary(self, summary_data: Dict) -> bool:
    """Send daily summary."""
    formatted = format_daily_summary(summary_data)
    return await self.send_message(formatted)

async def send_welcome_message(self, phone_number: str, summary_time: str) -> bool:
    """Send welcome message to new users."""
    formatted = format_welcome_message(summary_time)
    return await self.send_message(phone_number, formatted)

async def send_verification_code(self, phone_number: str, code: str, expires_minutes: int) -> bool:
    """Send verification code."""
    formatted = format_verification_code(code, expires_minutes)
    return await self.send_message(phone_number, formatted)
```

## Testing Checklist

### Backend:
```bash
# Start backend
cd backend && python -m uvicorn app.main:app --reload

# Test health
curl http://localhost:8000/api/v1/health

# Test WhatsApp status
curl http://localhost:8000/api/v1/settings/whatsapp/status \
  -H "X-Device-ID: test-device-123"

# Test verification request
curl -X POST http://localhost:8000/api/v1/settings/whatsapp/verify/request \
  -H "X-Device-ID: test-device-123" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+2341234567890"}'

# Test preferences
curl -X POST http://localhost:8000/api/v1/settings/whatsapp/preferences \
  -H "X-Device-ID: test-device-123" \
  -H "Content-Type: application/json" \
  -d '{
    "trade_notifications_enabled": true,
    "daily_summary_enabled": true,
    "summary_time_wat": "20:00",
    "chat_enabled": true
  }'
```

### Frontend:
1. Navigate to Settings → Notifications
2. Enter phone number
3. Click "Send Code"
4. Enter 6-digit code from WhatsApp
5. Click "Verify"
6. Configure preferences
7. Set summary time
8. Click "Save Preferences"
9. Click "Test Connection" - receive test message

## Deployment Considerations

### Timezone Handling:
- User sets time in WAT (West Africa Time, UTC+1)
- Scheduler stores as UTC internally (19:00 UTC = 20:00 WAT)
- Convert on display: `new Date(utcTime).toLocaleString('en-NG', {timeZone: 'Africa/Lagos'})`

### Database Migration:
Tables are auto-created on startup via SQLAlchemy's `Base.metadata.create_all()`. No manual migration needed.

### OpenWA Requirements:
- Node.js 16+ installed
- `@open-wa/wa-automate` package
- OpenWA server script auto-generated on first run
- Runs on port 3001 (embedded) or 2785 (separate service)

## Message Flow Examples

### New User Onboarding:
1. User enters phone in Settings
2. Receives verification code via WhatsApp
3. Enters code, verified
4. Receives welcome message with features overview
5. Configures preferences

### Daily Summary:
1. 8 PM WAT trigger
2. Generate summary for yesterday's trades
3. Check user preferences (daily_summary_enabled)
4. Format message with template
5. Send via WhatsApp
6. Mark as sent in database

### Trade Execution:
1. Trade executed by AI agent
2. Check user preferences (trade_notifications_enabled)
3. Format trade execution message
4. Send real-time via WhatsApp
5. User can reply with commands (if chat_enabled)

## Key Success Factors

1. **Verified Phone Numbers:** Only send to verified numbers
2. **User Preferences:** Respect enable/disable toggles
3. **Timezone Awareness:** Store UTC, display local time
4. **Template Consistency:** All messages use branded templates
5. **Error Handling:** Graceful failures without crashing
6. **Testing:** Always provide test connection option