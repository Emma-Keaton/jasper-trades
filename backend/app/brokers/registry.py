"""
Broker Registry - Factory and registry for all broker services.
Lazy-loads IBKR to avoid Python 3.14 eventkit compatibility issues
"""
from typing import Dict, Any, Optional, List, Type
import structlog

from app.brokers.base import BaseBrokerService
from app.brokers.alpaca_service import AlpacaBrokerService
from app.brokers.ccxt_service import CCXTBrokerService
from app.brokers.solana_service import SolanaBrokerService

logger = structlog.get_logger(__name__)


def _get_ibkr_class():
    """Lazy load IBKR service to avoid event loop issues at import time"""
    try:
        from app.brokers.ibkr_service import IBKRBrokerService
        return IBKRBrokerService
    except RuntimeError as e:
        if "event loop" in str(e):
            logger.warning("IBKR service unavailable (eventkit Python 3.14 issue)")
            return None
        raise


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

    # Initialize Alpaca
    if config.get("alpaca", {}).get("enabled", True):
        try:
            alpaca = AlpacaBrokerService(config.get("alpaca", {}))
            registry.register("alpaca", alpaca)
        except Exception as e:
            logger.warning(f"Failed to initialize Alpaca: {e}")

    # Initialize CCXT (crypto)
    if config.get("ccxt", {}).get("enabled", True):
        try:
            ccxt_config = config.get("ccxt", {})
            exchange_id = ccxt_config.get("exchange", "binance")
            ccxt = CCXTBrokerService(exchange_id=exchange_id, config=ccxt_config)
            registry.register(exchange_id, ccxt)
        except Exception as e:
            logger.warning(f"Failed to initialize CCXT: {e}")

    # Initialize IBKR (lazy-loaded to avoid eventkit issues)
    if config.get("ibkr", {}).get("enabled", False):
        try:
            IBKRClass = _get_ibkr_class()
            if IBKRClass:
                ibkr = IBKRClass(config.get("ibkr", {}))
                registry.register("ibkr", ibkr)
            else:
                logger.warning("IBKR service not available (Python 3.14 eventkit issue)")
        except Exception as e:
            logger.warning(f"Failed to initialize IBKR: {e}")

    # Initialize Solana
    if config.get("solana", {}).get("enabled", False):
        try:
            solana = SolanaBrokerService(config.get("solana", {}))
            registry.register("solana", solana)
        except Exception as e:
            logger.warning(f"Failed to initialize Solana: {e}")

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

    Args:
        asset_class: One of "stocks", "crypto", "options", "futures", "defi"

    Returns:
        Broker instance or None if not found
    """
    asset_to_broker = {
        "stocks": "alpaca",
        "equities": "alpaca",
        "crypto": "binance",  # or ccxt
        "options": "alpaca",  # or ibkr
        "futures": "ibkr",
        "defi": "solana",
        "solana": "solana",
    }

    broker_name = asset_to_broker.get(asset_class.lower())
    if broker_name:
        return broker_registry.get(broker_name)

    return None