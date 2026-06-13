---
name: trove-api-integration
description: Integrating Trove API for Nigerian/US stocks trading with multi-currency support
source: auto-skill
extracted_at: '2026-06-12T19:35:56.931Z'
---

# Trove API Integration for Nigerian/US Stocks

## Overview

Integrating Trove's Developer API enables trading both US stocks (AAPL, TSLA) and Nigerian NGX stocks (DANGCEM, MTNN) with fractional share support and multi-currency display (USD/NGN).

## Key Architecture Decisions

### 1. Broker Routing (IBKR Removed)

Since Interactive Brokers is not suitable for Nigerian users, redistribute asset classes among available brokers:

| Asset Class | Broker | Reason |
|-------------|--------|--------|
| Stocks/Equities | Trove | US + NGX stocks, fractional shares |
| Options | Trove | US options via Trove |
| Forex/CFD | cTrader | Multi-broker OAuth (FxPro, Exness) |
| Futures | cTrader | CFD futures via cTrader |
| Crypto | Binance | Spot/futures via CCXT |
| DeFi/Solana | Solana | SPL tokens, DeFi protocols |

Update `backend/app/brokers/registry.py`:

```python
def get_broker_for_asset(asset_class: str):
    asset_to_broker = {
        "stocks": "trove",
        "equities": "trove",
        "options": "trove",
        "forex": "ctrader",
        "futures": "ctrader",
        "crypto": "binance",
        "solana": "solana",
    }
```

### 2. API Key Storage

Store Trove credentials encrypted in database via Settings page (not `.env`):

```python
# DeviceSettings model
trove_api_key = Column(String, nullable=True)  # Encrypted
trove_base_url = Column(String, nullable=True)
trove_enabled = Column(Boolean, default=False)
trove_sandbox = Column(Boolean, default=True)
default_currency = Column(String(3), default="USD")  # "USD" or "NGN"
```

### 3. Currency Conversion Priority

When converting NGN ↔ USD:
1. Try Trove API first (if configured)
2. Fallback to Alpha Vantage (FREE tier)
3. Cache rates for 60 seconds

```python
async def get_currency_conversion(amount, from_currency, to_currency):
    # Try Trove first
    if trove_enabled:
        result = await _get_forex_rate_trove(...)
        if result['success']:
            return result
    
    # Fallback to Alpha Vantage
    return await get_forex_rate_alphavantage(...)
```

## Backend Implementation

### TroveBrokerService

Create `backend/app/brokers/trove_service.py` following the `BaseBrokerService` pattern:

**Key Methods:**
- `connect()` - Validate API credentials
- `submit_order()` - Support both quantity and amount (fractional)
- `get_market_quote()` - Real-time bid/ask/last price
- `get_forex_rate()` - NGN/USD conversion
- `get_clock()` - Check both US and NGX market hours

**Fractional Trading:**
```python
async def submit_order(self, symbol, side, quantity=None, amount=None, ...):
    # Supports both:
    # - quantity=10 (10 shares)
    # - amount=50 ($50 worth, fractional)
    if amount:
        order_payload["amount"] = amount
    elif quantity:
        order_payload["quantity"] = quantity
```

### Settings Endpoints

Add to `backend/app/api/v1/settings_extensions.py`:

```python
@router.post("/trove")
async def save_trove_settings(settings: TroveSettingsRequest, device_id: Header):
    # Encrypt API key before storing
    encryption.encrypt(settings.trove_api_key)

@router.post("/trove/test")
async def test_trove_connection(device_id: Header):
    # Test API connection, store account_id

@router.post("/currency/preference")
async def save_currency_preference(request: CurrencyPreferenceRequest):
    # Set default_currency (USD/NGN)

@router.post("/payout/naira-bank")
async def save_naira_bank_details(request: NairaBankDetailsRequest):
    # Nigerian bank account for NGN payouts
```

### Forex API Endpoints

Create `backend/app/api/v1/forex.py`:

```python
@router.get("/rate/{from_currency}/{to_currency}")
async def get_forex_rate(from_currency, to_currency):
    # Returns current exchange rate

@router.post("/convert")
async def convert_currency(request: CurrencyConversionRequest):
    # Convert amount with Trove or Alpha Vantage
```

### Database Migration

Create `backend/app/migrations/0003_trove_integration.py`:

```python
def add_trove_columns(migrator, db):
    migrator.add_sql("ALTER TABLE device_settings ADD COLUMN trove_api_key TEXT")
    migrator.add_sql("ALTER TABLE device_settings ADD COLUMN trove_base_url TEXT")
    migrator.add_sql("ALTER TABLE device_settings ADD COLUMN trove_enabled BOOLEAN DEFAULT 0")
    migrator.add_sql("ALTER TABLE device_settings ADD COLUMN default_currency TEXT DEFAULT 'USD'")
```

## Python Dependencies

Add to `backend/requirements.txt`:

```
httpx>=0.25.0  # Async HTTP client for Trove API
pydantic>=2.5.0  # API validation
```

## Testing Strategy

### 1. Unit Test TroveBrokerService

```python
async def test_trove_connect():
    trove = TroveBrokerService(api_key="test_key", sandbox=True)
    assert await trove.connect() == True

async def test_fractional_order():
    result = await trove.submit_order("AAPL", "buy", amount=50)
    assert result.success == True
```

### 2. Test Forex Conversion

```python
async def test_ngn_to_usd_conversion():
    result = await get_currency_conversion(1000000, "NGN", "USD")
    assert result['success'] == True
    assert result['data']['converted_amount'] > 0
```

### 3. Integration Test

```bash
# Save Trove settings
curl -X POST http://localhost:8000/api/v1/settings/trove \
  -H "X-Device-ID: test-device" \
  -d '{"trove_api_key": "trv_sk_test", "trove_enabled": true}'

# Test connection
curl -X POST http://localhost:8000/api/v1/settings/trove/test \
  -H "X-Device-ID: test-device"

# Convert currency
curl -X POST http://localhost:8000/api/v1/forex/convert \
  -H "X-Device-ID: test-device" \
  -d '{"amount": 1000000, "from_currency": "NGN", "to_currency": "USD"}'
```

## Common Pitfalls

### 1. API Key Encryption

Always encrypt API keys before database storage:

```python
encryption = EncryptionHelper()
encrypted_key = encryption.encrypt(api_key)
decrypted_key = encryption.decrypt(encrypted_key)
```

### 2. Fallback Logic

Never rely on single API provider:

```python
# Trove first, then Alpha Vantage
if trove_enabled:
    result = await trove_forex_rate()
    if result['success']:
        return result

return await alphavantage_forex_rate()
```

### 3. Market Hours

Check both US and NGX market status before trading:

```python
clock = await trove.get_clock()
if not clock['us_market']['is_open'] and not clock['ngx_market']['is_open']:
    return {"error": "Both markets are closed"}
```

### 4. Currency Display

Format amounts correctly:

```python
def format_currency(amount, currency):
    if currency == "NGN":
        return f"₦{amount:,.2f}"
    else:
        return f"${amount:,.2f}"
```

## Security Considerations

1. **Never log API keys** - Use `logger.debug()` without credential values
2. **Encrypt at rest** - All API keys encrypted before database storage
3. **HTTPS only** - Trove API requires HTTPS in production
4. **Rate limiting** - Implement client-side rate limiting (100 req/sec)
5. **Webhook signature verification** - Verify Trove webhook signatures if implemented

## Deployment Checklist

- [ ] Add Trove API key to `.env.example` (fallback only)
- [ ] Create database migration `0003_trove_integration.py`
- [ ] Test with Trove sandbox credentials first
- [ ] Verify forex conversion with known rates
- [ ] Test fractional order submission
- [ ] Confirm Nigerian bank payout flow
- [ ] Update frontend Settings page UI
- [ ] Add currency toggle component
- [ ] Test both USD and NGN display modes

## Related Files

- `backend/app/brokers/trove_service.py`
- `backend/app/brokers/trove_models.py`
- `backend/app/api/v1/forex.py`
- `backend/app/api/v1/settings_extensions.py`
- `backend/app/migrations/0003_trove_integration.py`
- `backend/app/models.py` (DeviceSettings additions)