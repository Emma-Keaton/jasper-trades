---
name: auto-payout-withdrawal-system
description: Complete auto-payout (50% daily profit) and manual withdrawal system with multi-chain USDT payouts
source: auto-skill
extracted_at: '2026-06-07T08:31:21.503Z'
---

# Auto-Payout & Withdrawal System Implementation

## Overview
Build a complete payout system that automatically sends 50% of daily trading profits to a user's crypto wallet (USDT/USDC only), plus manual withdrawal functionality.

## Architecture

### Backend Components

**1. Database Models** (`backend/app/models.py`)
```python
class Withdrawal(Base):
    """Withdrawal request and execution log."""
    id, portfolio_id, amount, currency
    withdrawal_type: "manual" | "auto_payout"
    destination_type: "crypto_wallet" | "broker"
    destination_address: str
    status: "pending" | "processing" | "completed" | "failed"
    transaction_hash: str  # Blockchain tx hash
    fee: float  # Platform fee (default 0.1%)
    net_amount: float  # amount - fee
    daily_pnl: float  # Daily PnL when auto-payout triggered
    payout_percentage: float  # % of profit (default 50%)
    requested_at, processed_at, error_message

# Add to DeviceSettings:
payout_config: JSON  # {crypto_wallet, payout_enabled, payout_percentage, payout_schedule_hour, broker_account}
```

**2. Withdrawal Service** (`backend/app/services/withdrawal_service.py`)
```python
class WithdrawalService:
    async def create_withdrawal(portfolio_id, amount, withdrawal_type, destination_type, destination_address)
    async def process_withdrawal(withdrawal_id)  # Execute blockchain transfer
    async def calculate_daily_profit(portfolio_id, date) -> float  # Sum realized PnL
    async def execute_auto_payout(portfolio_id) -> Optional[Withdrawal]  # Main auto-payout logic
```

**Key Logic - Auto-Payout:**
```python
async def execute_auto_payout(self, portfolio_id):
    # 1. Get payout settings
    settings = get_payout_settings(portfolio_id)
    if not settings.payout_enabled: return None
    
    # 2. Check if already paid today (prevent duplicates)
    existing = get_today_payout(portfolio_id)
    if existing: return None
    
    # 3. Calculate daily profit (sum of all closed trades today)
    daily_pnl = calculate_daily_profit(portfolio_id, today)
    if daily_pnl <= 0: return None  # No profit = no payout
    
    # 4. Calculate payout amount
    payout_percentage = settings.payout_percentage  # Default 50%
    payout_amount = daily_pnl * (payout_percentage / 100)
    
    # 5. Create withdrawal record
    withdrawal = create_withdrawal(
        portfolio_id=portfolio_id,
        amount=payout_amount,
        withdrawal_type="auto_payout",
        destination_type="crypto_wallet",
        destination_address=settings.crypto_wallet,
        daily_pnl=daily_pnl,
        payout_percentage=payout_percentage,
    )
    
    # 6. Process withdrawal (convert to USDT + send)
    await process_withdrawal(withdrawal.id)
    
    # 7. Send notifications
    await notify_service.notify_withdrawal_completed(withdrawal)
    
    return withdrawal
```

**3. Payout Scheduler** (`backend/app/services/payout_scheduler.py`)
```python
class PayoutScheduler:
    """Background task - runs every hour, checks portfolios"""
    
    async def start(self):
        while is_running:
            await check_and_execute_payouts()
            await asyncio.sleep(3600)  # Check every hour
    
    async def check_and_execute_payouts(self):
        # Get current hour in ET (Eastern Time)
        current_hour_et = datetime.now(pytz.timezone('America/New_York')).hour
        
        for portfolio in all_portfolios:
            settings = get_payout_settings(portfolio.id)
            
            # Check conditions:
            if not settings.payout_enabled: continue
            if current_hour_et != settings.payout_schedule_hour: continue
            
            # Execute auto-payout
            result = await execute_auto_payout(portfolio.id)
            if result:
                logger.info(f"Auto-payout executed: ${result.amount}")
```

**4. Withdrawal API** (`backend/app/api/v1/withdrawal.py`)
```python
# Manual withdrawal
POST /api/v1/withdrawal/request
  Body: { portfolio_id, amount, destination_type, destination_address }

# Withdrawal history
GET /api/v1/withdrawal/history?portfolio_id=1&limit=50

# Withdrawal stats
GET /api/v1/withdrawal/stats?portfolio_id=1
  Returns: { total_withdrawn, pending_count, auto_payout_total }

# Payout settings
GET  /api/v1/withdrawal/payout/settings
POST /api/v1/withdrawal/payout/settings
  Body: { crypto_wallet, payout_enabled, payout_percentage, payout_schedule_hour }

# Validate crypto wallet
POST /api/v1/withdrawal/payout/validate-wallet
  Body: { address, network: "ethereum" | "solana" }

# Test immediate payout (dev only)
POST /api/v1/withdrawal/scheduler/execute/{portfolio_id}
```

**5. Notification Integration** (`backend/app/services/notify_service.py`)
```python
async def notify_withdrawal_requested(withdrawal)
  # "Withdrawal Requested - $500 pending"

async def notify_withdrawal_completed(withdrawal)
  # "Auto-Payout Executed - $500 sent to 0x742..."
  # Include: daily_pnl, payout_percentage, tx_hash

async def notify_withdrawal_failed(withdrawal, error)
  # "Withdrawal Failed - Insufficient balance"
```

**6. Main Integration** (`backend/app/main.py`)
```python
@app.on_event("startup")
async def startup():
    # Start payout scheduler
    from app.services.payout_scheduler import payout_scheduler
    await payout_scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    # Stop scheduler
    await payout_scheduler.stop()
```

### Frontend Components

**1. Withdraw Modal** (`frontend/components/WithdrawModal.tsx`)
```tsx
interface WithdrawModalProps {
  portfolioId: number;
  availableBalance: number;
  onClose: () => void;
}

Features:
- Amount input with MAX button
- Real-time fee calculator (0.1%)
- Net amount display
- Destination selector (crypto wallet / broker)
- Wallet address input with validation
- Withdrawal history button
```

**2. Portfolio Integration** (`frontend/components/PortfolioTab.tsx`)
```tsx
// Add Withdraw button next to Cash balance
<button onClick={() => setShowWithdrawModal(true)}>
  <ArrowUpRight /> Withdraw
</button>

{showWithdrawModal && (
  <WithdrawModal
    portfolioId={1}
    availableBalance={cash}
    onClose={() => setShowWithdrawModal(false)}
  />
)}
```

**3. Payout Settings Section** (`frontend/components/SettingsTab.tsx`)
```tsx
<section>
  <h2>Auto-Payout (50% Daily Profit)</h2>
  
  {/* Crypto Wallet */}
  <input placeholder="0x... (USDT/USDC only)" />
  <button onClick={validateWallet}>Validate</button>
  <p>⚠️ USDT or USDC only - All profits converted to USDT</p>
  
  {/* Enable Toggle */}
  <checkbox>Enable Auto-Payout</checkbox>
  
  {/* Percentage Slider */}
  <input type="range" min="0" max="100" value={payout_percentage} />
  <span>{payout_percentage}%</span>
  
  {/* Schedule Time (ET) */}
  <select value={payout_schedule_hour}>
    {[...Array(24)].map((_, i) => (
      <option>{hour}:00 {ampm} ET</option>
    ))}
  </select>
  <p>⏰ Time is in Eastern Time (ET)</p>
  
  <button onClick={savePayoutSettings}>Save Auto-Payout Settings</button>
</section>
```

## Currency Conversion Flow

**All profits → USDT before payout:**

1. **Forex profits** (IBKR): Realized in USD → Convert to USDT
3. **Crypto profits** (Binance): Realized in USDT → No conversion needed

**Conversion Options (Production):**
```python
# Ethereum (ERC20 USDT)
async def convert_usd_to_usdt_eth(amount_usd):
    # Use Uniswap V3 API or 1inch API
    # Swap USDC → USDT (both stablecoins, ~1:1)
    return usdt_amount

# Solana (SPL USDT)
async def convert_usd_to_usdt_sol(amount_usd):
    # Use Jupiter API
    # Swap USDC → USDT
    return usdt_amount

# Binance (Internal)
async def convert_usd_to_usdt_binance(amount_usd):
    # Use Binance internal conversion (no gas fees)
    return usdt_amount
```

**Current Implementation (Simulated):**
```python
async def _process_crypto_withdrawal(self, withdrawal):
    # SIMULATED - In production, integrate with blockchain API
    tx_hash = "0x" + hashlib.sha256(f"{withdrawal.id}{datetime.utcnow()}").hexdigest()
    withdrawal.transaction_hash = tx_hash
    withdrawal.status = "completed"
    await self.db.commit()
    
    # TODO: Real implementation
    # 1. Call Uniswap/Jupiter to swap USD → USDT
    # 2. Send USDT to withdrawal.destination_address
    # 3. Deduct gas fee from withdrawal amount
    # 4. Return actual tx hash
```

## Key Features

### Auto-Payout
- ✅ Runs once per day at user-scheduled time (ET timezone)
- ✅ Calculates total realized PnL for the day
- ✅ Takes configured percentage (default 50%)
- ✅ Converts to USDT (production)
- ✅ Sends to user's crypto wallet
- ✅ Sends notification on completion
- ✅ Prevents duplicate payouts (checks if already paid today)
- ✅ Skips if no profit (daily_pnl <= 0)

### Manual Withdrawal
- ✅ User enters any amount (no minimum)
- ✅ Real-time fee display (0.1%)
- ✅ Net amount calculation
- ✅ Crypto wallet or broker destination
- ✅ Wallet address validation (Ethereum/Solana)
- ✅ Withdrawal history view
- ✅ Statistics (total withdrawn, auto-payout total, pending)

### Notifications
- ✅ Withdrawal requested (all channels)
- ✅ Withdrawal completed (with tx hash)
- ✅ Withdrawal failed (with error message)
- ✅ Channels: WhatsApp, Discord, Slack, Email, Telegram

## Security Considerations

1. **Encrypted Storage**: Wallet addresses encrypted in database (like API keys)
2. **Transaction Signing**: In production, use multi-sig for large amounts
3. **Rate Limiting**: Max 5 withdrawal requests per hour
4. **KYC/AML**: For production, integrate identity verification
5. **Audit Log**: Log all withdrawal requests with IP/timestamp
6. **Daily Limits**: Configure max withdrawal amount per day

## Testing

```bash
# 1. Configure payout settings
curl -X POST http://localhost:8000/api/v1/withdrawal/payout/settings \
  -H "X-Device-ID: test123" \
  -H "Content-Type: application/json" \
  -d '{
    "crypto_wallet": "0x742d35Cc6634C0532925a3b844Bc9e7595fBE891",
    "payout_enabled": true,
    "payout_percentage": 50,
    "payout_schedule_hour": 20
  }'

# 2. Request manual withdrawal
curl -X POST http://localhost:8000/api/v1/withdrawal/request \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": 1,
    "amount": 500,
    "destination_type": "crypto_wallet",
    "destination_address": "0x742d35Cc6634C0532925a3b844Bc9e7595fBE891"
  }'

# 3. Get withdrawal history
curl "http://localhost:8000/api/v1/withdrawal/history?portfolio_id=1"

# 4. Test immediate auto-payout
curl -X POST "http://localhost:8000/api/v1/withdrawal/scheduler/execute/1"
```

## Production Deployment Checklist

- [ ] Integrate real blockchain transfer (Alchemy/Jupiter)
- [ ] Add on-chain swap (Uniswap/1inch for USD→USDT)
- [ ] Set up gas fee estimation and management
- [ ] Implement withdrawal daily/monthly limits
- [ ] Add KYC/AML screening
- [ ] Multi-sig approval for large payouts (>$10,000)
- [ ] Transaction monitoring and alerting
- [ ] Backup wallet key management (HSM)
- [ ] Compliance with local regulations

## Common Issues & Solutions

**Issue: Payout not executing at scheduled time**
- Check scheduler is running: `GET /api/v1/withdrawal/scheduler/status`
- Verify timezone: Scheduler uses ET, make sure user selects ET hour
- Check daily profit: Auto-payout only executes if daily_pnl > 0

**Issue: Wallet validation fails**
- Ethereum addresses: Must be 0x + 40 hex chars (0x742d...)
- Solana addresses: 32-44 base58 chars
- Only USDT/USDC wallets supported (not BTC, not ETH native)

**Issue: Withdrawal stuck in "pending"**
- Check portfolio has sufficient cash balance
- Verify blockchain network status (Ethereum gas spikes can delay)
- Manual intervention may be needed for failed transfers

**Issue: Notifications not sending**
- Check notification service is configured (Settings → Notifications)
- Verify WhatsApp number / Discord webhook / etc.
- Check backend logs for notification errors