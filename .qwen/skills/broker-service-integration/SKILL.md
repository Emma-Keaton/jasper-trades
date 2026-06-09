---
name: broker-service-integration
description: Pattern for implementing unified broker services with abstract base classes, concrete implementations, and registry-based service location
source: auto-skill
extracted_at: '2026-05-30T21:37:49.178Z'
---

# Broker Service Integration Pattern

A systematic approach to building unified interfaces for multiple external service providers (brokers, APIs, etc.) with automatic service registration and smart routing.

## When to Use This Pattern

- Integrating multiple providers with similar capabilities (e.g., stock brokers, crypto exchanges, payment gateways)
- Need to abstract provider-specific implementation details from business logic
- Want automatic service discovery and failover
- Require consistent error handling and logging across providers

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Business Logic (Agents, Services)                           │
│ - Calls broker services via registry                        │
│ - No knowledge of specific implementations                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Service Registry (Singleton)                                │
│ - register(name, service)                                   │
│ - get(name) → service                                       │
│ - get_for_asset(asset_class) → service                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Concrete Services (Alpaca, CCXT, IBKR, Solana)              │
│ - Implement base class interface                            │
│ - Handle provider-specific API calls                        │
│ - Normalize responses                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Base Service (Abstract Class)                               │
│ - Defines interface all services must implement             │
│ - Provides common validation and utilities                  │
│ - Standardizes request/response models                      │
└─────────────────────────────────────────────────────────────┘
```

## Step 1: Define Abstract Base Class

Create a base class that defines the interface all services must implement:

```python
# app/brokers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

class OrderResult:
    """Standardized result of an order submission."""

    def __init__(
        self,
        success: bool,
        order_id: Optional[str] = None,
        message: Optional[str] = None,
        filled_quantity: float = 0,
        filled_price: Optional[float] = None,
        commission: float = 0,
    ):
        self.success = success
        self.order_id = order_id
        self.message = message
        self.filled_quantity = filled_quantity
        self.filled_price = filled_price
        self.commission = commission
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "message": self.message,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
        }


class PositionData:
    """Standardized position data."""

    def __init__(
        self,
        symbol: str,
        quantity: float,
        avg_price: float,
        current_price: Optional[float] = None,
        market_value: Optional[float] = None,
        unrealized_pnl: Optional[float] = None,
        side: str = "long",
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.current_price = current_price
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.side = side

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "side": self.side,
        }


class BaseBrokerService(ABC):
    """Abstract base class for all broker services."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_connected = False
        self.is_paper_trading = True

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection to broker."""
        pass

    @abstractmethod
    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> OrderResult:
        """Submit an order to the broker."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """Get current position for a symbol."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[PositionData]:
        """Get all current positions."""
        pass

    @abstractmethod
    async def get_account(self) -> Any:
        """Get account information."""
        pass

    # Common utilities provided by base class
    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
    ) -> tuple[bool, Optional[str]]:
        """Validate order parameters before submission."""
        if not symbol or not isinstance(symbol, str):
            return False, "Invalid symbol"

        if side not in ["buy", "sell"]:
            return False, "Side must be 'buy' or 'sell'"

        if quantity <= 0:
            return False, "Quantity must be positive"

        if order_type not in ["market", "limit", "stop", "stop_limit"]:
            return False, "Invalid order type"

        return True, None
```

## Step 2: Implement Concrete Services

Create one implementation per provider, following the base class interface:

```python
# app/brokers/alpaca_service.py
from app.brokers.base import BaseBrokerService, OrderResult, PositionData
from app.config import settings
import structlog

logger = structlog.get_logger(__name__)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


class AlpacaBrokerService(BaseBrokerService):
    """Alpaca Securities broker integration."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="alpaca", config=config or {})
        
        self.api_key = config.get("api_key") if config else settings.ALPACA_API_KEY
        self.api_secret = config.get("api_secret") if config else settings.ALPACA_API_SECRET
        self.is_paper_trading = config.get("paper", True) if config else settings.ALPACA_PAPER
        
        self.trading_client: Optional[TradingClient] = None

    async def connect(self) -> bool:
        if not ALPACA_AVAILABLE:
            logger.error("alpaca-py library not installed")
            return False

        if not self.api_key or not self.api_secret:
            logger.error("Alpaca API credentials not configured")
            return False

        try:
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.is_paper_trading,
            )

            # Test connection
            account = self.trading_client.get_account()
            logger.info("Connected to Alpaca", account_id=account.id)

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            return False

    async def disconnect(self):
        self.trading_client = None
        self.is_connected = False

    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        **kwargs,
    ) -> OrderResult:
        if not self.is_connected:
            return OrderResult(
                success=False,
                message="Not connected to Alpaca",
            )

        # Validate order
        is_valid, error_msg = self.validate_order(symbol, side, quantity, order_type)
        if not is_valid:
            return OrderResult(success=False, message=error_msg)

        try:
            # Create order request
            if order_type == "market":
                order_request = MarketOrderRequest(
                    symbol=symbol.upper(),
                    qty=quantity,
                    side=side.upper(),
                    time_in_force="day",
                )
            elif order_type == "limit":
                order_request = LimitOrderRequest(
                    symbol=symbol.upper(),
                    qty=quantity,
                    side=side.upper(),
                    time_in_force="day",
                    limit_price=limit_price,
                )
            else:
                return OrderResult(success=False, message=f"Unsupported order type: {order_type}")

            # Submit order
            order = self.trading_client.submit_order(order_request)

            return OrderResult(
                success=True,
                order_id=str(order.id),
                message=f"Order submitted: {side} {quantity} {symbol}",
                filled_quantity=float(order.filled_qty or 0),
                filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            )

        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return OrderResult(success=False, message=str(e))

    async def cancel_order(self, order_id: str) -> bool:
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"Cancel error: {e}")
            return False

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        try:
            position = self.trading_client.get_open_position(symbol.upper())
            if not position:
                return None

            return PositionData(
                symbol=position.symbol,
                quantity=float(position.qty),
                avg_price=float(position.avg_entry_price),
                current_price=self._get_current_price(position.symbol),
                market_value=float(position.market_value),
                unrealized_pnl=float(position.unrealized_pl),
            )
        except:
            return None

    async def get_positions(self) -> List[PositionData]:
        positions = self.trading_client.get_all_positions()
        return [
            PositionData(
                symbol=p.symbol,
                quantity=float(p.qty),
                avg_price=float(p.avg_entry_price),
                current_price=self._get_current_price(p.symbol),
                market_value=float(p.market_value),
                unrealized_pnl=float(p.unrealized_pl),
            )
            for p in positions
        ]

    async def get_account(self) -> Any:
        return self.trading_client.get_account()

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Helper method to get current market price."""
        # Implementation depends on available data client
        pass
```

## Step 3: Create Service Registry

Implement a singleton registry for service discovery and routing:

```python
# app/brokers/registry.py
from typing import Dict, Any, Optional, List
from app.brokers.base import BaseBrokerService
import structlog

logger = structlog.get_logger(__name__)


class BrokerRegistry:
    """Registry and factory for broker services."""

    _instance: Optional["BrokerRegistry"] = None
    _brokers: Dict[str, BaseBrokerService]

    def __new__(cls) -> "BrokerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._brokers = {}
        return cls._instance

    def register(self, name: str, broker: BaseBrokerService) -> None:
        """Register a broker instance."""
        self._brokers[name.lower()] = broker
        logger.info(f"Registered broker: {name}")

    def get(self, name: str) -> Optional[BaseBrokerService]:
        """Get a broker instance by name."""
        return self._brokers.get(name.lower())

    def get_all(self) -> Dict[str, BaseBrokerService]:
        """Get all registered brokers."""
        return self._brokers.copy()

    def list_brokers(self) -> List[str]:
        """List registered broker names."""
        return list(self._brokers.keys())

    async def connect_all(self) -> Dict[str, bool]:
        """Connect all registered brokers."""
        results = {}
        for name, broker in self._brokers.items():
            try:
                success = await broker.connect()
                results[name] = success
            except Exception as e:
                logger.error(f"Failed to connect {name}: {e}")
                results[name] = False
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all registered brokers."""
        for broker in self._brokers.values():
            try:
                await broker.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting broker: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get status of all brokers."""
        return {
            name: {
                "connected": broker.is_connected,
                "paper_trading": broker.is_paper_trading,
            }
            for name, broker in self._brokers.items()
        }

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._brokers


# Global registry instance
broker_registry = BrokerRegistry()


def initialize_brokers(config: Optional[Dict[str, Any]] = None) -> BrokerRegistry:
    """Initialize and register all configured brokers."""
    registry = BrokerRegistry()
    config = config or {}

    # Initialize Alpaca
    if config.get("alpaca", {}).get("enabled", True):
        try:
            from app.brokers.alpaca_service import AlpacaBrokerService
            alpaca = AlpacaBrokerService(config.get("alpaca", {}))
            registry.register("alpaca", alpaca)
        except Exception as e:
            logger.warning(f"Failed to initialize Alpaca: {e}")

    # Initialize CCXT (crypto)
    if config.get("ccxt", {}).get("enabled", True):
        try:
            from app.brokers.ccxt_service import CCXTBrokerService
            ccxt = CCXTBrokerService(
                exchange_id=config.get("ccxt", {}).get("exchange", "binance"),
                config=config.get("ccxt", {}),
            )
            registry.register("binance", ccxt)
        except Exception as e:
            logger.warning(f"Failed to initialize CCXT: {e}")

    # Add more brokers as needed...

    return registry


def get_broker(name: str) -> Optional[BaseBrokerService]:
    """Get a broker instance by name."""
    return broker_registry.get(name)


def get_broker_for_asset(asset_class: str) -> Optional[BaseBrokerService]:
    """Get the appropriate broker for an asset class."""
    asset_to_broker = {
        "stocks": "alpaca",
        "crypto": "binance",
        "defi": "solana",
    }
    broker_name = asset_to_broker.get(asset_class.lower())
    if broker_name:
        return broker_registry.get(broker_name)
    return None
```

## Step 4: Integrate with Business Logic

Update existing business logic to use the registry:

```python
# app/agents/execution.py
from app.brokers import get_broker, get_broker_for_asset, broker_registry
from app.brokers.base import OrderResult


class ExecutionAgent(BaseAgent):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="Execution", config=config or {})
        self.broker_registry = broker_registry
        self._brokers_initialized = False

    async def initialize_brokers(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize all configured brokers."""
        if self._brokers_initialized:
            return True

        try:
            from app.brokers.registry import initialize_brokers
            initialize_brokers(config)
            
            results = await self.broker_registry.connect_all()
            successful = [name for name, success in results.items() if success]
            logger.info("Brokers initialized", brokers=successful)
            
            self._brokers_initialized = True
            return len(successful) > 0
        except Exception as e:
            logger.error(f"Failed to initialize brokers: {e}")
            return False

    async def submit_to_broker(
        self,
        trade: Trade,
        broker: str = "auto",
    ) -> Trade:
        """Submit trade to broker using registry."""
        try:
            logger.info(f"Submitting {trade.symbol} to {broker}")

            # Auto-select broker based on asset class
            if broker == "auto":
                broker = self._select_broker_for_symbol(trade.symbol)

            # Get broker from registry
            broker_service = self.broker_registry.get(broker)

            if not broker_service:
                logger.warning(f"Broker {broker} not available, using alpaca")
                broker_service = self.broker_registry.get("alpaca")

            if not broker_service:
                trade.status = "rejected"
                return trade

            # Ensure connected
            if not broker_service.is_connected:
                connected = await broker_service.connect()
                if not connected:
                    trade.status = "rejected"
                    return trade

            # Submit order using broker service
            result = await broker_service.submit_order(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                order_type=trade.order_type,
                limit_price=trade.price,
            )

            # Update trade with result
            if result.success:
                trade.broker = broker
                trade.broker_order_id = result.order_id
                trade.status = "submitted"
            else:
                trade.status = "rejected"

            return trade

        except Exception as e:
            logger.error(f"Broker submission error: {e}")
            trade.status = "error"
            return trade

    def _select_broker_for_symbol(self, symbol: str) -> str:
        """Select appropriate broker based on symbol."""
        symbol_upper = symbol.upper()

        # Crypto symbols
        if symbol_upper in ["BTC", "ETH", "SOL", "BNB"]:
            return "binance"

        # Default to stocks
        return "alpaca"
```

## Step 5: Application Initialization

Wire everything together in the main application:

```python
# app/main.py
from app.brokers import broker_registry, initialize_brokers
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up Jasper Trades...")
    await init_db()

    # Initialize agents
    # ... agent initialization ...

    # Initialize brokers
    try:
        initialize_brokers()
        broker_results = await broker_registry.connect_all()
        logger.info("Brokers initialized", results=broker_results)
    except Exception as e:
        logger.warning(f"Broker initialization failed: {e}")

    yield

    # Shutdown
    await broker_registry.disconnect_all()
    logger.info("Brokers disconnected")


app = FastAPI(lifespan=lifespan)
```

## Key Implementation Details

### Error Handling Strategy

```python
# Always return structured results, never raise
async def submit_order(...) -> OrderResult:
    try:
        # ... implementation ...
        return OrderResult(success=True, ...)
    except Exception as e:
        logger.error(f"Error: {e}")
        return OrderResult(success=False, message=str(e))
```

### Lazy Connection Pattern

```python
# Connect on first use if not already connected
async def submit_to_broker(self, trade, broker):
    broker_service = self.broker_registry.get(broker)
    
    if not broker_service.is_connected:
        connected = await broker_service.connect()
        if not connected:
            return OrderResult(success=False, message="Connection failed")
    
    return await broker_service.submit_order(...)
```

### Smart Routing

```python
def _select_broker_for_symbol(self, symbol: str) -> str:
    """Route to appropriate broker based on asset class."""
    if symbol.upper() in ["BTC", "ETH", "SOL"]:
        return "binance"  # Crypto
    elif symbol.upper() in ["AAPL", "NVDA", "MSFT"]:
        return "alpaca"   # Stocks
    else:
        return "alpaca"   # Default
```

## Testing Strategy

```python
# tests/brokers/test_alpaca_service.py
import pytest
from app.brokers.alpaca_service import AlpacaBrokerService

@pytest.mark.asyncio
async def test_connect_success():
    service = AlpacaBrokerService({
        "api_key": "test_key",
        "api_secret": "test_secret",
        "paper": True,
    })
    
    result = await service.connect()
    assert result == True
    assert service.is_connected == True

@pytest.mark.asyncio
async def test_submit_order():
    service = AlpacaBrokerService()
    await service.connect()
    
    result = await service.submit_order(
        symbol="AAPL",
        side="buy",
        quantity=10,
        order_type="market",
    )
    
    assert result.success == True
    assert result.order_id is not None
```

## Common Pitfalls to Avoid

1. **Don't mix provider-specific code with business logic** - always go through the registry
2. **Don't raise exceptions from broker methods** - return failed results instead
3. **Don't assume all brokers support all features** - check capabilities or use try/except
4. **Don't forget to disconnect** - cleanup in application shutdown
5. **Don't hardcode broker names in business logic** - use asset-based routing

## When to Extend This Pattern

- Adding new service providers (just create new concrete class)
- Adding new asset classes (extend the routing logic)
- Implementing circuit breakers (add to base class)
- Adding request/response logging (add middleware to base class)
- Implementing rate limiting (add to base class or each service)

This pattern was successfully used to integrate 4 broker services (Alpaca, CCXT/Binance, IBKR, Solana/Jupiter) in the Jasper Trades AI trading platform, providing unified trading capabilities across stocks, crypto, and DeFi with automatic failover and smart routing.