"""
Broker Registry - Factory and registry for all broker services.

Supports:
- Trove: US and Nigerian (NGX) stocks
- cTrader: Forex, CFDs (OAuth copy-trading)
- CCXT (Binance): Crypto
- Solana: DeFi, Solana tokens
"""
from typing import Dict, Any, Optional, List, Type
import structlog

from app.brokers.base import BaseBrokerService
from app.brokers.ccxt_service import CCXTBrokerService
from app.brokers.solana_service import SolanaBrokerService
from app.brokers.ctrader_service import CTraderBrokerService
from app.brokers.trove_service import TroveBrokerService

logger = structlog.get_logger(__name__)


class BrokerRegistry:
    """
    Registry and factory for broker services.

    Manages broker instances and provides unified access.
    """

    _instance: Optional["BrokerRegistry"] = None
    _brokers: Dict[str, BaseBrokerService]

    def __new__(cls) -> "BrokerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._brokers = {}
        return cls._instance

    def register(
        self,
        name: str,
        broker: BaseBrokerService,
    ) -> None:
        """
        Register a broker instance.

        Args:
            name: Broker identifier
            broker: Broker service instance
        """
        self._brokers[name.lower()] = broker
        logger.info(f"Registered broker: {name}")

    def get(self, name: str) -> Optional[BaseBrokerService]:
        """
        Get a broker instance by name.

        Args:
            name: Broker identifier

        Returns:
            Broker instance or None if not found
        """
        return self._brokers.get(name.lower())

    def get_all(self) -> Dict[str, BaseBrokerService]:
        """
        Get all registered brokers.

        Returns:
            Dict of broker name -> instance
        """
        return self._brokers.copy()

    def list_brokers(self) -> List[str]:
        """
        List registered broker names.

        Returns:
            List of broker names
        """
        return list(self._brokers.keys())

    def remove(self, name: str) -> bool:
        """
        Remove a broker from registry.

        Args:
            name: Broker identifier

        Returns:
            True if removed, False if not found
        """
        if name.lower() in self._brokers:
            del self._brokers[name.lower()]
            logger.info(f"Removed broker: {name}")
            return True
        return False

    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect all registered brokers.

        Returns:
            Dict of broker name -> connection success
        """
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
        """
        Get status of all brokers.

        Returns:
            Dict with broker connection status
        """
        return {
            name: {
                "connected": broker.is_connected,
                "paper_trading": broker.is_paper_trading if hasattr(broker, 'is_paper_trading') else None,
            }
            for name, broker in self._brokers.items()
        }

    def __contains__(self, name: str) -> bool:
        """Check if broker is registered."""
        return name.lower() in self._brokers

    def __len__(self) -> int:
        """Get number of registered brokers."""
        return len(self._brokers)

    def __repr__(self) -> str:
        return f"BrokerRegistry(brokers={list(self._brokers.keys())})"


# Global registry instance
broker_registry = BrokerRegistry()


def initialize_brokers(config: Optional[Dict[str, Any]] = None) -> BrokerRegistry:
    """
    Initialize and register all configured brokers.

    Args:
        config: Optional configuration dict

    Returns:
        BrokerRegistry with initialized brokers
    """
    registry = BrokerRegistry()

    # Configuration
    config = config or {}

    # Initialize CCXT (crypto)
    if config.get("ccxt", {}).get("enabled", True):
        try:
            ccxt_config = config.get("ccxt", {})
            exchange_id = ccxt_config.get("exchange", "binance")
            ccxt = CCXTBrokerService(exchange_id=exchange_id, config=ccxt_config)
            registry.register(exchange_id, ccxt)
        except Exception as e:
            logger.warning(f"Failed to initialize CCXT: {e}")

    # Initialize Solana
    if config.get("solana", {}).get("enabled", False):
        try:
            solana = SolanaBrokerService(config.get("solana", {}))
            registry.register("solana", solana)
        except Exception as e:
            logger.warning(f"Failed to initialize Solana: {e}")

    # Initialize cTrader (OAuth copy-trading)
    if config.get("ctrader", {}).get("enabled", True):  # Enable by default
        try:
            # Create a placeholder cTrader broker instance (will be updated with user tokens on connect)
            ctrader = CTraderBrokerService(sandbox=config.get("ctrader", {}).get("sandbox", True))
            registry.register("ctrader", ctrader)
            logger.info("Initialized cTrader broker service placeholder")
        except Exception as e:
            logger.warning(f"Failed to initialize cTrader: {e}")

    # Initialize Trove (Nigerian/US stocks)
    if config.get("trove", {}).get("enabled", False):  # Disabled by default, enable via Settings
        try:
            trove_config = config.get("trove", {})
            trove = TroveBrokerService(
                api_key=trove_config.get("api_key"),
                base_url=trove_config.get("base_url"),
                sandbox=trove_config.get("sandbox", True),
                account_id=trove_config.get("account_id"),
            )
            registry.register("trove", trove)
            logger.info("Initialized Trove broker service")
        except Exception as e:
            logger.warning(f"Failed to initialize Trove: {e}")

    return registry


def get_broker(name: str) -> Optional[BaseBrokerService]:
    """
    Get a broker instance by name.

    Convenience function that uses the global registry.

    Args:
        name: Broker identifier

    Returns:
        Broker instance or None if not found
    """
    return broker_registry.get(name)


def get_broker_for_asset(asset_class: str) -> Optional[BaseBrokerService]:
    """
    Get the appropriate broker for an asset class.

    Broker Routing Strategy (IBKR removed - not suitable for Nigerian users):
    
    | Asset Class          | Broker     | Reason                                      |
    |---------------------|------------|---------------------------------------------|
    | Stocks/Equities     | Trove      | US + Nigerian (NGX) stocks, fractional      |
    | Options             | Trove      | US options via Trove                        |
    | Forex/CFD           | cTrader    | Multi-broker OAuth (FxPro, etc.)        |
    | Futures             | cTrader    | CFD futures via cTrader brokers             |
    | Crypto              | Binance    | Spot and futures via CCXT                   |
    | DeFi/Solana         | Solana     | SPL tokens, DeFi protocols                  |

    Args:
        asset_class: One of "stocks", "equities", "options", "forex", "futures", 
                     "crypto", "defi", "solana"

    Returns:
        Broker instance or None if not found
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


def get_broker_for_symbol(symbol: str) -> Optional[BaseBrokerService]:
    """
    Auto-detect broker based on symbol format.

    Symbol Patterns:
    - AAPL, TSLA, DANGCEM.LAGOS → Trove (stocks)
    - GBPUSD, EURUSD → cTrader (forex)
    - BTC/USDT, ETHUSDT → Binance (crypto)
    - SOL, USDC → Solana (DeFi)

    Args:
        symbol: Trading symbol

    Returns:
        Appropriate broker instance
    """
    symbol_upper = symbol.upper()

    # Forex pairs (6 characters, e.g., GBPUSD)
    if len(symbol_upper) == 6 and symbol_upper.endswith(("USD", "NGN", "EUR", "GBP", "JPY")):
        return broker_registry.get("ctrader")

    # Crypto symbols
    if any(x in symbol_upper for x in ["BTC", "ETH", "USDT", "USDC", "BNB"]):
        if "/" in symbol_upper or symbol_upper.endswith(("USDT", "USDC")):
            return broker_registry.get("binance")
        # Pure SOL tokens → Solana
        if symbol_upper in ["SOL", "USDC", "RAY", "SRM", "MNGO"]:
            return broker_registry.get("solana")

    # Stock symbols (default to Trove)
    # NGX symbols often have .LAGOS suffix
    if "." in symbol_upper or symbol_upper.replace(".", "").isalpha():
        return broker_registry.get("trove")

    # Default: Trove for anything that looks like a stock ticker
    return broker_registry.get("trove")