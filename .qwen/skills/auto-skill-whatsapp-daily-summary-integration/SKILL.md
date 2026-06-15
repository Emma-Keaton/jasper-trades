---
name: whatsapp-daily-summary-integration
description: Implement WhatsApp daily trade summaries with scheduled notifications at 8 PM WAT
source: auto-skill
extracted_at: '2026-06-15T11:02:14.077Z'
---

# WhatsApp Daily Summary Integration

Complete implementation pattern for WhatsApp daily trade summaries with real-time trade notifications and scheduled end-of-day summaries.

## Overview

This pattern implements:
- Real-time WhatsApp notifications for ALL trade executions
- Daily summary generation at 8:00 PM WAT (West Africa Time, UTC+1)
- User verification system for phone numbers
- Template-based message formatting
- Database tracking of summary delivery

## Database Models

### DailySummary Model
```python
class DailySummary(Base):
    """Daily trade summary for WhatsApp notifications."""
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    device_id = Column(String(255), nullable=False, index=True)
    phone_number = Column(String, nullable=False, index=True)
    summary_date = Column(String, nullable=False, index=True)  # ISO format: "2026-06-15"
    
    # Performance metrics
    total_pnl = Column(Float, default=0.0)
    total_pnl_percent = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    breakeven = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Trade details (JSON)
    best_trade = Column(JSON, nullable=True)
    worst_trade = Column(JSON, nullable=True)
    agent_stats = Column(JSON, nullable=True)
    top_symbols = Column(JSON, nullable=True)
    
    # Delivery status
    summary_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    send_time_wat = Column(String, default="20:00")
```

### WhatsappUser Model
```python
class WhatsappUser(Base):
    """WhatsApp user configuration."""
    __tablename__ = "whatsapp_users"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(255), nullable=False, unique=True, index=True)
    phone_number = Column(String, nullable=False)
    
    # Notification preferences
    trade_notifications_enabled = Column(Boolean, default=True)
    daily_summary_enabled = Column(Boolean, default=True)
    summary_time_wat = Column(String, default="20:00")
    chat_enabled = Column(Boolean, default=True)
    ai_explanations_enabled = Column(Boolean, default=True)
    
    # Verification status
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime, nullable=True)
```

## Message Templates System

Create template file `backend/app/services/whatsapp_templates.py`:

```python
"""
WhatsApp Message Templates - All messages from "Jasper Trades"
"""

# Daily Summary Template
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
"""

# Trade Execution Template
TRADE_EXECUTED_TEMPLATE = """
🔔 *TRADE EXECUTED*
━━━━━━━━━━━━━━━━━━━━
📈 {action} {shares} {symbol}
💰 Price: ${price:.2f}
💵 Total: ${total:.2f}
🤖 Agent: {agent_name}
⏰ {timestamp}
━━━━━━━━━━━━━━━━━━━━
"""

# Trade Closure Template
TRADE_CLOSED_TEMPLATE = """
{emoji} *{outcome}* - {symbol}
━━━━━━━━━━━━━━━━━━━━
💰 Entry: ${entry_price:.2f}
💰 Exit: ${exit_price:.2f}
📊 **PnL:** ${pnl:+,.2f} ({pnl_percent:+.2f}%)
⏱ Hold: {hold_duration}
━━━━━━━━━━━━━━━━━━━━
"""

# Helper functions
def format_daily_summary(summary_data: dict) -> str:
    """Format daily summary with emoji based on performance."""
    total_pnl = summary_data.get('total_pnl', 0)
    emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "➖"
    outcome = "PROFIT" if total_pnl > 0 else "LOSS" if total_pnl < 0 else "BREAKEVEN"
    
    # Build formatted message
    return DAILY_SUMMARY_TEMPLATE.format(...)

def format_trade_executed(trade_data: dict) -> str:
    """Format trade execution notification."""
    return TRADE_EXECUTED_TEMPLATE.format(...)
```

## Daily Summary Service

```python
# backend/app/services/daily_summary_service.py

class DailySummaryService:
    """Generate and send daily WhatsApp summaries."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def generate_summary(
        self,
        portfolio_id: int,
        device_id: str,
        date: str,
    ) -> Optional[DailySummary]:
        """Generate daily summary from trades."""
        # 1. Fetch all trades for the date
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        query = select(Trade).where(
            and_(
                Trade.created_at >= start_datetime,
                Trade.created_at <= end_datetime,
            )
        )
        trades = list((await db.execute(query)).scalars().all())
        
        if not trades:
            return None
        
        # 2. Calculate statistics
        stats = self._calculate_statistics(trades)
        
        # 3. Get user's WhatsApp number
        user = await db.get(WhatsappUser, device_id)
        if not user or not user.phone_number:
            return None
        
        # 4. Create summary record
        summary = DailySummary(
            portfolio_id=portfolio_id,
            device_id=device_id,
            phone_number=user.phone_number,
            summary_date=date,
            total_pnl=stats['total_pnl'],
            win_rate=stats['win_rate'],
            best_trade=stats['best_trade'],
            worst_trade=stats['worst_trade'],
            agent_stats=stats['agent_stats'],
        )
        
        db.add(summary)
        await db.commit()
        
        return summary
    
    def _calculate_statistics(self, trades: List[Trade]) -> Dict:
        """Calculate win rate, PnL, agent stats, etc."""
        total_pnl = 0.0
        wins = losses = breakeven = 0
        agent_stats = {}
        
        for trade in trades:
            pnl = trade.pnl or 0.0
            total_pnl += pnl
            
            if pnl > 0.5:
                wins += 1
            elif pnl < -0.5:
                losses += 1
            else:
                breakeven += 1
        
        total_trades = len(trades)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        return {
            'total_pnl': total_pnl,
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': win_rate,
        }
    
    async def send_summary(self, summary: DailySummary) -> bool:
        """Send summary via WhatsApp."""
        message = self._format_summary_message(summary)
        success = await whatsapp_service.send_message(summary.phone_number, message)
        
        if success:
            summary.summary_sent = True
            summary.sent_at = datetime.utcnow()
            await db.commit()
        
        return success
```

## Scheduler Integration

```python
# backend/app/services/scheduler.py

class SchedulerService:
    def __init__(self, db_session_factory):
        self._daily_summary_time = "19:00"  # 7 PM UTC = 8 PM WAT
    
    async def start(self):
        # Start daily summary task
        self._tasks["daily_summary"] = asyncio.create_task(
            self._run_daily_at_time("daily_summary", self._send_daily_summaries, self._daily_summary_time)
        )
    
    async def _run_daily_at_time(self, name: str, func, time_str: str):
        """Run task daily at specific UTC time."""
        hour, minute = map(int, time_str.split(":"))
        
        while self._running:
            now = datetime.utcnow()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if now >= target:
                target = target + timedelta(days=1)
            
            sleep_seconds = (target - now).total_seconds()
            await asyncio.sleep(sleep_seconds)
            
            if self._running:
                await func()
    
    async def _send_daily_summaries(self):
        """Generate and send summaries for yesterday's trades."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        portfolios = await db.execute(select(Portfolio))
        
        for portfolio in portfolios:
            summary = await summary_service.generate_summary(
                portfolio_id=portfolio.id,
                device_id=portfolio.device_id,
                date=yesterday,
            )
            
            if summary:
                # Check if user wants summary
                user = await db.get(WhatsappUser, portfolio.device_id)
                if user and user.is_verified and user.daily_summary_enabled:
                    await summary_service.send_summary(summary)
```

## API Endpoints

```python
# backend/app/api/v1/whatsapp_settings.py

@router.post("/verify/request")
async def request_whatsapp_verification(
    request: WhatsappVerificationRequest,
    device_id: str = Header(alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Send verification code to WhatsApp number."""
    verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Store code and send via WhatsApp
    await whatsapp_service.send_verification_code(request.phone_number, verification_code)
    
    return {"success": True, "expires_in_minutes": 10}

@router.post("/verify/confirm")
async def confirm_whatsapp_verification(
    request: WhatsappVerificationCodeRequest,
    device_id: str = Header(alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Confirm verification code."""
    # Verify code matches and not expired
    user.is_verified = True
    await db.commit()
    
    # Send welcome message
    await whatsapp_service.send_welcome_message(user.phone_number)
    
    return {"success": True}

@router.post("/summary/schedule")
async def update_daily_summary_schedule(
    schedule: dict,
    device_id: str = Header(alias="X-Device-ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update daily summary schedule (e.g., {"enabled": true, "time_wat": "20:00"})."""
    user.daily_summary_enabled = schedule.get("enabled", True)
    user.summary_time_wat = schedule.get("time_wat", "20:00")
    await db.commit()
    
    return {"schedule": {"enabled": user.daily_summary_enabled, "time_wat": user.summary_time_wat}}
```

## Database Migration

```python
# backend/app/migrations.py

async def _migrate_whatsapp_users():
    """Add missing columns to whatsapp_users table."""
    expected_columns = {
        'device_id': "TEXT NOT NULL",
        'phone_number': 'TEXT NOT NULL',
        'trade_notifications_enabled': 'BOOLEAN DEFAULT 1',
        'daily_summary_enabled': 'BOOLEAN DEFAULT 1',
        'summary_time_wat': "TEXT DEFAULT '20:00'",
        'is_verified': 'BOOLEAN DEFAULT 0',
        'verification_code': 'TEXT',
        'verification_expires_at': 'TIMESTAMP',
    }
    
    existing_columns = await get_existing_columns('whatsapp_users')
    
    for column_name, column_type in expected_columns.items():
        if column_name not in existing_columns:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"ALTER TABLE whatsapp_users ADD COLUMN {column_name} {column_type}")
                )
```

## Frontend Integration Points

### WhatsApp Settings Section
```tsx
// frontend/components/SettingsTab.tsx

// State
const [whatsapp, setWhatsapp] = useState({
  phone_number: '',
  is_verified: false,
  trade_notifications_enabled: true,
  daily_summary_enabled: true,
  summary_time_wat: '20:00',
});

// Verify phone number
const requestVerification = async () => {
  const res = await fetch(`${API_URL}/api/v1/settings/whatsapp/verify/request`, {
    method: 'POST',
    headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone_number: whatsapp.phone_number }),
  });
  // Show code input modal
};

// Update schedule
const updateSummarySchedule = async (time: string) => {
  await fetch(`${API_URL}/api/v1/settings/whatsapp/summary/schedule`, {
    method: 'POST',
    headers: { 'X-Device-ID': deviceId, 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      enabled: true, 
      time_wat: time 
    }),
  });
};
```

## Testing Checklist

1. **Database Migration**
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   # Check logs for: "✓ Added column: daily_summary_enabled to whatsapp_users"
   ```

2. **Verification Flow**
   ```bash
   # Request verification
   curl -X POST http://localhost:8000/api/v1/settings/whatsapp/verify/request \
     -H "X-Device-ID: test-123" \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+234XXXXXXXXXX"}'
   
   # Confirm code
   curl -X POST http://localhost:8000/api/v1/settings/whatsapp/verify/confirm \
     -H "X-Device-ID: test-123" \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+234XXXXXXXXXX", "verification_code": "123456"}'
   ```

3. **Test Summary Generation**
   ```python
   from app.services.daily_summary_service import DailySummaryService
   from app.database import async_session
   
   db = async_session()
   service = DailySummaryService(db)
   summary = await service.generate_summary(
       portfolio_id=1,
       device_id="test-123",
       date=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
   )
   success = await service.send_summary(summary)
   ```

4. **Scheduler Test**
   ```bash
   # Check logs at 7 PM UTC (8 PM WAT)
   # Should see: "Generating daily summaries for 2026-06-XX"
   # Should see: "Daily summaries complete, generated=X, sent=Y"
   ```

## Key Files Created

- `backend/app/models.py` - DailySummary, WhatsappUser models
- `backend/app/services/daily_summary_service.py` - Summary generation service
- `backend/app/services/whatsapp_templates.py` - Message templates
- `backend/app/services/scheduler.py` - Updated with daily summary task
- `backend/app/api/v1/whatsapp_settings.py` - Settings API endpoints
- `backend/app/migrations.py` - Updated migration functions

## Deployment Notes

1. **Timezone**: Scheduler uses UTC internally (7 PM UTC = 8 PM WAT)
2. **Database**: Auto-migration creates tables on startup
3. **WhatsApp**: Requires OpenWA running on `localhost:3001` (embedded) or separate service
4. **User Preferences**: Stored per-device via `X-Device-ID` header
5. **Verification**: Codes expire after 10 minutes

## Common Issues

**Issue**: Summary not sent
- Check: `user.is_verified == True`
- Check: `user.daily_summary_enabled == True`
- Check: OpenWA service is running

**Issue**: Wrong time
- Scheduler uses UTC - adjust `_daily_summary_time` for your timezone
- 8 PM WAT = 7 PM UTC (WAT is UTC+1)

**Issue**: Verification code not received
- Check: OpenWA session is active
- Check: Phone number format (include country code, no + symbol)