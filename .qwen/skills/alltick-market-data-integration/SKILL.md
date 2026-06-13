---
name: alltick-market-data-integration
description: Integrate AllTick open-source WebSocket API for real-time multi-asset market data (stocks, forex, crypto)
source: auto-skill
extracted_at: '2026-06-11T01:57:47.100Z'
---

## AllTick Market Data Integration

AllTick is an open-source real-time financial market data API that provides tick-by-tick data for multiple asset classes with low latency (~170ms average).

### Supported Asset Classes

- **US Stocks** (NYSE, NASDAQ) - Code format: `SYMBOL.US` (e.g., `AAPL.US`, `TSLA.US`)
- **Hong Kong Stocks** (HKEX) - Code format: `CODE.HK` (e.g., `700.HK`, `1288.HK`)
- **Forex** (Major pairs) - Code format: `EURUSD` (no suffix)
- **Cryptocurrencies** - Code format: `BTCUSDT` (no suffix)
- **Commodities/Precious Metals** - Code format: `XAUUSD` (no suffix)

### WebSocket Endpoints

**Stocks (US & HK):**
```
wss://quote.alltick.co/quote-stock-b-ws-api?token=YOUR_TOKEN
```

**Forex/Crypto/Commodities:**
```
wss://quote.alltick.co/quote-b-ws-api?token=YOUR_TOKEN
```

### Protocol Command IDs

| cmd_id | Name | Direction | Description |
|--------|------|-----------|-------------|
| 22000 | Heartbeat | Client → Server | Keep connection alive (must send every 10s) |
| 22002 | Subscribe Depth | Client → Server | Subscribe to order book data |
| 22004 | Subscribe Trade | Client → Server | Subscribe to tick-by-tick trades |
| 22003 | Depth Response | Server → Client | Confirmation of depth subscription |
| 22005 | Trade Response | Server → Client | Confirmation of trade subscription |
| 22998 | Push Data | Server → Client | Real-time tick data push |
| 40000 | Error | Server → Client | Error response |

### Heartbeat Requirement

**Critical:** Must send heartbeat every 10 seconds. Server disconnects after 30 seconds of no heartbeat.

```python
heartbeat = {
    "cmd_id": 22000,
    "seq_id": 123,
    "trace": "heartbeat-1234567890",
    "data": {}
}
await ws.send(json.dumps(heartbeat))
```

### Subscription Flow (Trade Quotes)

1. **Connect to WebSocket** with token in URL query parameter
2. **Send subscription request:**

```json
{
    "cmd_id": 22004,
    "seq_id": 1623456789000,
    "trace": "sub-trade-timestamp",
    "data": {
        "symbol_list": [
            {"code": "AAPL.US"},
            {"code": "700.HK"},
            {"code": "EURUSD"}
        ]
    }
}
```

3. **Receive confirmation:**

```json
{
    "ret": 200,
    "msg": "ok",
    "cmd_id": 22005,
    "seq_id": 1623456789000,
    "trace": "sub-trade-timestamp",
    "data": {}
}
```

4. **Receive tick data pushes:**

```json
{
    "cmd_id": 22998,
    "data": {
        "code": "AAPL.US",
        "seq": "1605509068000001",
        "tick_time": "1605509068",
        "price": "175.25",
        "volume": "100",
        "turnover": "17525.00",
        "trade_direction": 1
    }
}
```

### Tick Data Fields

| Field | Type | Description |
|-------|------|-------------|
| code | string | Symbol code (e.g., "AAPL.US") |
| seq | string | Quote sequence number |
| tick_time | string | Timestamp in milliseconds |
| price | string | Transaction price (last price) |
| volume | string | Transaction volume |
| turnover | string | Turnover amount (price × volume) |
| trade_direction | uint32 | 0=default, 1=BUY, 2=SELL |

**Note on Turnover:**
- For forex, precious metals, and energy: turnover is not provided (calculate as `price * volume`)
- For stocks and cryptocurrencies: turnover is returned normally

### Token Acquisition

Get a free API token from: https://alltick.co

Token application process:
1. Visit https://alltick.co
2. Sign up for account
3. Request API token (free tier available)
4. Use token in WebSocket URL: `wss://...?token=YOUR_TOKEN`

### Implementation Considerations

1. **Single Active Subscription:** Each WebSocket connection allows only one active subscription. Sending a new subscription request overwrites the previous one.

2. **No Partial Unsubscribe:** To remove symbols, resend subscription without them (cannot unsubscribe individual symbols).

3. **Auto-Reconnect:** Implement automatic reconnection on disconnection. Server may disconnect due to network issues or timeout.

4. **Subscription Persistence:** After reconnection, must resend subscription request.

5. **Symbol Case Sensitivity:** Code values must match exactly as listed in product code list (case-sensitive).

### References

- GitHub: https://github.com/alltick/alltick-realtime-forex-crypto-stock-tick-finance-websocket-api
- Official Site: https://alltick.co
- Product Code Lists: See `product_code_list_*.md` files in repo for valid symbols
- Error Codes: See `error_code_description.md` for error code meanings