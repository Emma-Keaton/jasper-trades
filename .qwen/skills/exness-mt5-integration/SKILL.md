---
name: exness-mt5-integration
description: MetaTrader 5 and Exness broker integration with trading caps and withdrawal support
source: auto-skill
extracted_at: '2026-06-08T08:37:15.932Z'
---

# Exness & MetaTrader 5 Integration

## Overview

This skill covers integrating Exness broker into Jasper Trades using both MetaTrader 5 (MT5) protocol for trading execution and Exness REST API for account management and withdrawals.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Jasper Trades Backend                                       │
│ ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│ │  MT5 Service    │  │ Exness Service  │  │ Withdrawal   │ │
│ │  (trading)      │  │ (REST API)      │  │  Service     │ │
│ └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
└──────────┼────────────────────┼──────────────────┼─────────┘
           │                    │                  │
           ▼                    ▼                  ▼
    ┌─────────────┐      ┌─────────────┐    ┌──────────────┐
    │ MT5 Server  │      │ Exness API  │    │ Exness Wallet│
    │ (Exness)    │      │ (OAuth/REST)│    │  Withdrawals │
    └─────────────┘      └─────────────┘    └──────────────┘
```

## Key Components

### 1. Trading Caps (Risk Control)

**Purpose:** Prevent users from over-exposing their portfolio by limiting trade sizes.

**Implementation:**
- Store caps in `DeviceSettings` or dedicated `TradingCaps` model
- Two limits (both enforced):
  - `max_amount`: Fixed dollar cap (e.g., $5,000 max per trade)
  - `max_portfolio_percentage`: Percentage cap (e.g., 20% of portfolio value)
- Effective cap = MIN(fixed_amount, portfolio_value × percentage)

**Where to enforce:**
- In trade execution service before order submission
- In agent decision pipeline (Risk Agent checks caps)
- In API endpoints that create trades

**Schema:**
```python
class TradingCaps(BaseModel):
    max_amount: float = 5000.0  # Fixed $ cap
    max_portfolio_percentage: float = 20.0  # % cap
    enabled: bool = True

# Effective cap calculation
effective_cap = min(
    caps.max_amount,
    portfolio_value * (caps.max_portfolio_percentage / 100)
)
```

### 2. MetaTrader 5 Service (`mt5_service.py`)

**Purpose:** Direct trading execution via MT5 protocol (low latency, standard for forex/CFD).

**Key Methods:**
```python
class MT5Service:
    async def connect(self, login: str, password: str, server: str) -> bool
    async def disconnect(self) -> None
    async def get_account_info(self) -> dict  # balance, equity, margin, free_margin
    async def get_positions(self) -> list  # open positions
    async def get_symbols(self) -> list  # available trading symbols
    async def place_order(self, symbol: str, action: str, volume: float, 
                          price: float = None, stop_loss: float = None, 
                          take_profit: float = None) -> dict
    async def close_position(self, position_id: int) -> dict
    async def get_history(self, from_date: datetime, to_date: datetime) -> list
```

**MT5 Order Types:**
- `ORDER_TYPE_BUY` / `ORDER_TYPE_SELL` (market)
- `ORDER_TYPE_BUY_LIMIT` / `ORDER_TYPE_SELL_LIMIT` (pending)
- `ORDER_TYPE_BUY_STOP` / `ORDER_TYPE_SELL_STOP` (stop orders)

**Symbol Mapping:**
- MT5 symbols differ from standard tickers (e.g., `EURUSD` vs `EUR/USD`)
- Maintain mapping table: `symbol_map = {"EURUSD": "EUR/USD", ...}`

**Connection:**
```python
import MetaTrader5 as mt5

async def connect(self, login, password, server):
    if not mt5.initialize():
        return False
    
    authorized = mt5.login(login=login, password=password, server=server)
    return authorized
```

### 3. Exness REST API Service (`exness_service.py`)

**Purpose:** Account management, OAuth linking, and withdrawal processing via official Exness API.

**Base URLs:**
- Production: `https://api.exness.com`
- Demo/Test: `https://api.exness-test.com`

**Key Endpoints:**
```python
class ExnessService:
    # OAuth/Authentication
    async def oauth_authorize_url(self) -> str  # Get OAuth URL for user consent
    async def oauth_callback(self, code: str) -> dict  # Exchange code for tokens
    
    # Account Info
    async def get_accounts(self) -> list  # List linked accounts
    async def get_balance(self, account_id: str) -> float
    async def get_equity(self, account_id: str) -> float
    
    # Trading
    async def place_market_order(self, account_id: str, symbol: str, 
                                 side: str, volume: float) -> dict
    async def get_orders(self, account_id: str) -> list
    
    # Withdrawals
    async def request_withdrawal(self, amount: float, currency: str, 
                                 method: str) -> dict
    async def get_withdrawal_history(self) -> list
```

**OAuth Flow:**
1. User clicks "Connect Exness" → redirect to Exness OAuth
2. User authorizes Jasper Trades
3. Exness redirects back with auth code
4. Backend exchanges code for access/refresh tokens
5. Store tokens encrypted in `DeviceSettings` or `BrokerAccount`

### 4. Broker Account Model (`BrokerAccount`)

**Purpose:** Track linked Exness/MT5 accounts per user.

```python
class BrokerAccount(Base):
    __tablename__ = "broker_accounts"
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String, ForeignKey("device_settings.device_id"))
    broker = Column(String, nullable=False)  # "exness", "mt5"
    account_id = Column(String)  # Exness account ID or MT5 login
    server = Column(String)  # MT5 server name
    is_active = Column(Boolean, default=True)
    
    # Auth tokens (encrypted)
    access_token = Column(String)
    refresh_token = Column(String)
    token_expires_at = Column(DateTime)
    
    # Sync state
    last_synced_at = Column(DateTime)
    sync_status = Column(String)  # "ok", "disconnected", "error"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 5. Exness Withdrawal Integration

**Extend Withdrawal Model:**
```python
# In models.py, add to Withdrawal.destination_type
# Existing: "crypto_wallet", "broker"
# Add: "exness_wallet"
```

**Withdrawal Flow:**

**Manual Request:**
1. User selects "Exness" as withdrawal destination
2. Enters amount and Exness account ID
3. Withdrawal created with status="pending"
4. Admin processes via Exness portal manually
5. Admin marks withdrawal as completed

**Automatic API Withdrawal:**
1. User has OAuth-connected Exness account
2. User requests withdrawal in UI
3. Backend calls Exness withdrawal API
4. Withdrawal processed automatically
5. Transaction ID stored in `withdrawal.transaction_hash`

**Implementation in `withdrawal_service.py`:**
```python
async def _exness_withdrawal(self, w: Withdrawal) -> str:
    """Execute Exness withdrawal via API."""
    # Get Exness service with auth tokens
    exness = await self._get_exness_service(w.portfolio_id)
    
    if not exness:
        raise ValueError("Exness account not linked")
    
    # Request withdrawal
    result = await exness.request_withdrawal(
        amount=w.amount,
        currency="USD",
        method="internal_transfer"  # or "bank_wire", "crypto"
    )
    
    return f"EXNESS_{result['id']}"
```

### 6. API Endpoints

**Exness Endpoints (`/api/v1/exness`):**
```python
@router.get("/oauth-url")
async def get_oauth_url()

@router.get("/oauth/callback")
async def oauth_callback(code: str, device_id: str)

@router.get("/accounts")
async def get_linked_accounts(device_id: str)

@router.post("/accounts/link")
async def link_account(account_data: dict)

@router.post("/withdraw")
async def request_exness_withdrawal(withdrawal_req: dict)
```

**Trading Cap Endpoints (`/api/v1/settings/trading-caps`):**
```python
@router.get("")
async def get_trading_caps(device_id: str)

@router.post("")
async def save_trading_caps(caps: TradingCaps, device_id: str)
```

### 7. Frontend Integration

**Settings Page Additions:**
- Trading Caps section (max $ and max %)
- Exness account linking button ("Connect Exness")
- Exness withdrawal option in withdrawal form

**New Components:**
- `ExnessConnectButton.tsx` - OAuth flow trigger
- `TradingCapsForm.tsx` - Cap configuration
- `LinkedAccountsList.tsx` - Show connected broker accounts

### 8. Risk Enforcement Pipeline

**Where to check caps:**
```python
# In trade execution service, BEFORE order submission
async def execute_trade(self, trade_request: TradeRequest):
    # 1. Get trading caps
    caps = await self._get_trading_caps(trade_request.device_id)
    
    # 2. Get current portfolio value
    portfolio = await self._get_portfolio(trade_request.portfolio_id)
    
    # 3. Calculate effective cap
    effective_cap = min(
        caps.max_amount,
        portfolio.value * (caps.max_portfolio_percentage / 100)
    )
    
    # 4. Validate trade size
    trade_value = trade_request.quantity * trade_request.price
    if trade_value > effective_cap:
        raise ValueError(
            f"Trade size ${trade_value} exceeds cap ${effective_cap} "
            f"(max ${caps.max_amount} or {caps.max_portfolio_percentage}% of portfolio)"
        )
    
    # 5. Proceed with execution
    ...
```

## Dependencies

```txt
# Python packages
MetaTrader5>=5.0.0  # MT5 protocol (requires MT5 terminal installed)
httpx  # For Exness REST API
```

**Note:** MT5 Python library requires MetaTrader 5 terminal installed on the system. On Windows, this is a standard .exe installer from Exness.

## Testing Strategy

1. **Unit Tests:**
   - Trading cap calculations (edge cases: zero portfolio, very large caps)
   - Symbol mapping between MT5 and standard format
   - Withdrawal flow mocking Exness API

2. **Integration Tests:**
   - MT5 connection with Exness demo account
   - OAuth flow with Exness test environment
   - End-to-end withdrawal (pending → processing → completed)

3. **Manual Testing:**
   - Connect real Exness account
   - Place test trades with various cap configurations
   - Request withdrawal and verify processing

## Security Considerations

1. **Token Storage:** Encrypt all OAuth tokens using existing `EncryptionHelper`
2. **API Keys:** Never expose Exness API keys in frontend
3. **Withdrawal Limits:** Enforce daily/monthly withdrawal limits
4. **Session Validation:** Check OAuth token expiry before API calls

## Troubleshooting

| Issue | Solution |
|-------|----------|
| MT5 connection fails | Check MT5 terminal is installed, server name is correct |
| OAuth callback fails | Verify redirect URL matches Exness app settings |
| Withdrawal rejected | Ensure account has sufficient balance and is verified |
| Symbol not found | Check symbol mapping table, MT5 symbol naming conventions |