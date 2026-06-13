---
name: multi-broker-asset-routing
description: Routing trades to appropriate broker based on asset class without IBKR
source: auto-skill
extracted_at: '2026-06-12T19:35:56.931Z'
---

# Multi-Broker Asset Routing Strategy

## Context

After removing IBKR (not suitable for Nigerian users), redistribute trading across available brokers: Trove (stocks), cTrader (forex/CFD), Binance (crypto), Solana (DeFi).

## Broker Capabilities Matrix

| Broker | Stocks | Options | Forex | Futures | Crypto | DeFi | Fractional |
|--------|--------|---------|-------|---------|--------|------|------------|
| Trove | ✅ US+NGX | ✅ US | ❌ | ❌ | ❌ | ❌ | ✅ |
| cTrader | ❌ | ❌ | ✅ | ✅ CFD | ❌ | ❌ | ❌ |
| Binance | ❌ | ❌ | ❌ | ✅ Futures | ✅ | ❌ | ❌ |
| Solana | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

## Implementation

### Asset Class Mapping

In `backend/app/brokers/registry.py`:

```python
def get_broker_for_asset(asset_class: str):
    """
    Route asset class to appropriate broker.
    
    Routing Strategy:
    - Trove: Primary for stocks/equities (US + Nigerian NGX)
    - cTrader: Forex, CFD futures (via FxPro, Exness OAuth)
    - Binance: Crypto spot/futures
    - Solana: DeFi tokens, SPL tokens
    """
    asset_to_broker = {
        # Trove - US and Nigerian markets
        "stocks": "trove",
        "equities": "trove",
        "us-stocks": "trove",
        "ngx": "trove",  # Nigerian Stock Exchange
        "options": "trove",  # US options via Trove
        
        # cTrader - Forex, CFDs, Futures
        "forex": "ctrader",
        "fx": "ctrader",
        "futures": "ctrader",  # CFD futures
        "cfds": "ctrader",
        
        # Binance - Crypto
        "crypto": "binance",
        "cryptocurrency": "binance",
        
        # Solana - DeFi, SPL tokens
        "defi": "solana",
        "solana": "solana",
        "spl": "solana",
    }
    
    broker_name = asset_to_broker.get(asset_class.lower())
    if broker_name:
        return broker_registry.get(broker_name)
    
    return None
```

### Symbol-Based Auto-Detection

For automatic broker selection based on symbol format:

```python
def get_broker_for_symbol(symbol: str):
    """
    Auto-detect broker from symbol pattern.
    
    Patterns:
    - AAPL, TSLA, DANGCEM.LAGOS → Trove (stocks)
    - GBPUSD, EURUSD → cTrader (forex)
    - BTC/USDT, ETHUSDT → Binance (crypto)
    - SOL, USDC → Solana (DeFi)
    """
    symbol_upper = symbol.upper()
    
    # Forex pairs (6 characters, e.g., GBPUSD)
    if len(symbol_upper) == 6 and symbol_upper.endswith(("USD", "NGN", "EUR", "GBP", "JPY")):
        return broker_registry.get("ctrader")
    
    # Crypto symbols
    if any(x in symbol_upper for x in ["BTC", "ETH", "USDT", "USDC", "BNB"]):
        if "/" in symbol_upper or symbol_upper.endswith(("USDT", "USDC")):
            return broker_registry.get("binance")
        if symbol_upper in ["SOL", "USDC", "RAY", "SRM"]:
            return broker_registry.get("solana")
    
    # Stock symbols (default to Trove)
    if "." in symbol_upper or symbol_upper.replace(".", "").isalpha():
        return broker_registry.get("trove")
    
    # Default: Trove for stock tickers
    return broker_registry.get("trove")
```

### Usage in Trading Flow

```python
# In trading endpoint
from app.brokers.registry import get_broker_for_asset, get_broker_for_symbol

async def execute_trade(symbol: str, side: str, quantity: float):
    # Option 1: Route by asset class (if known)
    broker = get_broker_for_asset("stocks")
    
    # Option 2: Auto-detect from symbol
    broker = get_broker_for_symbol(symbol)
    
    if not broker:
        raise HTTPException(400, f"No broker available for {symbol}")
    
    # Submit order
    result = await broker.submit_order(symbol, side, quantity)
    return result
```

## Nigerian Stock Exchange (NGX) Support

NGX symbols have special formatting:

```python
# NGX symbol patterns
NGX_SYMBOLS = {
    "DANGCEM": "DANGCEM.LAGOS",  # Dangote Cement
    "MTNN": "MTNN.LAGOS",        # MTN Nigeria
    "BUACEMENT": "BUACEMENT.LAGOS",
    "AIRWAfrica": "AIRWAfrica.LAGOS",
}

# When routing NGX stocks
if symbol in NGX_SYMBOLS:
    full_symbol = NGX_SYMBOLS[symbol]
    broker = get_broker_for_symbol(full_symbol)  # Returns Trove
```

## Broker Initialization Flow

```python
def initialize_brokers(config: dict):
    """Initialize all enabled brokers from config."""
    registry = BrokerRegistry()
    
    # Trove (disabled by default, enable via Settings)
    if config.get("trove", {}).get("enabled", False):
        trove = TroveBrokerService(
            api_key=config["trove"]["api_key"],
            base_url=config["trove"]["base_url"],
            sandbox=config["trove"]["sandbox"],
        )
        registry.register("trove", trove)
    
    # cTrader (OAuth copy-trading)
    if config.get("ctrader", {}).get("enabled", True):
        ctrader = CTraderBrokerService(sandbox=config["ctrader"]["sandbox"])
        registry.register("ctrader", ctrader)
    
    # Binance (crypto)
    if config.get("binance", {}).get("enabled", False):
        binance = CCXTBrokerService(exchange_id="binance", config=config["binance"])
        registry.register("binance", binance)
    
    # Solana (DeFi)
    if config.get("solana", {}).get("enabled", False):
        solana = SolanaBrokerService(config["solana"])
        registry.register("solana", solana)
    
    return registry
```

## Testing Broker Routing

```python
def test_broker_routing():
    # Stocks → Trove
    assert get_broker_for_asset("stocks") == trove_broker
    assert get_broker_for_symbol("AAPL") == trove_broker
    assert get_broker_for_symbol("DANGCEM.LAGOS") == trove_broker
    
    # Forex → cTrader
    assert get_broker_for_asset("forex") == ctrader_broker
    assert get_broker_for_symbol("GBPUSD") == ctrader_broker
    
    # Crypto → Binance
    assert get_broker_for_asset("crypto") == binance_broker
    assert get_broker_for_symbol("BTC/USDT") == binance_broker
    
    # DeFi → Solana
    assert get_broker_for_asset("defi") == solana_broker
    assert get_broker_for_symbol("SOL") == solana_broker
```

## Error Handling

When no broker is available for an asset class:

```python
broker = get_broker_for_asset("commodities")
if broker is None:
    raise HTTPException(
        status_code=400,
        detail="No broker configured for commodities. Available: stocks, forex, crypto, defi"
    )
```

## Performance Considerations

1. **Lazy Loading**: Initialize brokers only when first requested
2. **Connection Pooling**: Reuse broker connections across multiple trades
3. **Rate Limiting**: Respect per-broker API rate limits
4. **Fallback Logic**: If primary broker fails, try alternative (if available)

## Monitoring

Log broker selection for debugging:

```python
logger.info(
    "Routing trade to broker",
    symbol=symbol,
    asset_class=asset_class,
    broker_name=broker.name,
)
```

## Related Files

- `backend/app/brokers/registry.py`
- `backend/app/brokers/trove_service.py`
- `backend/app/brokers/ctrader_service.py`
- `backend/app/brokers/ccxt_service.py`
- `backend/app/brokers/solana_service.py`