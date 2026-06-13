"""
Broker Router - Asset-Class Based Trade Routing
Routes trades to appropriate broker based on symbol/asset class.

Routing Modes:
1. "asset_class" (default) - Route to best broker per asset (crypto→Binance)
2. "all" - Execute on ALL connected brokers simultaneously
3. "ai_decided" - Let AI agent decide which broker(s) to use
"""
from typing import Dict, Any, Optional, List, Tuple
import structlog
import re

from app.brokers.base import BaseBrokerService
from app.brokers.registry import broker_registry

logger = structlog.get_logger(__name__)


class BrokerRouter:
    """
    Broker Router - Intelligent trade routing by asset class.

    Features:
    - Auto-detect asset class from symbol
    - Route to appropriate broker
    - Support multi-broker execution
    - Fallback handling
    """

    # Asset class detection patterns
    CRYPTO_PATTERNS = [
        r".*USDT$", r".*USDC$", r".*BUSD$",  # Stablecoin pairs
        r"^BTC.*", r"^ETH.*", r"^BNB.*", r"^SOL.*",  # Major crypto
        r".*\/USDT$", r".*\/USD$",  # Slash notation
    ]

    SOLANA_PATTERNS = [
        r"^SOL.*", r".*\.SOL$",  # Solana native
        r"^So11111111111111111111111111111111111111112$",  # Wrapped SOL
    ]

    # Asset class to broker mapping
    ASSET_BROKER_MAP = {
        "crypto": "binance",
        "cryptospot": "binance",
        "futures": "ctrader",
        "forex": "ctrader",
        "solana": "solana",
        "defi": "solana",
    }

    # Broker capabilities
    BROKER_CAPABILITIES = {
        "binance": ["crypto", "cryptospot", "futures"],  # Binance handles futures too
        "solana": ["solana", "defi"],
        "ctrader": ["forex", "futures"],  # cTrader handles forex and futures
    }

    def __init__(self):
        self.routing_mode = "asset_class"  # Default mode

    def set_routing_mode(self, mode: str):
        """
        Set routing mode.

        Args:
            mode: "asset_class", "all", or "ai_decided"
        """
        if mode not in ["asset_class", "all", "ai_decided"]:
            logger.warning(f"Invalid routing mode: {mode}, using asset_class")
            mode = "asset_class"

        self.routing_mode = mode
        logger.info(f"Broker routing mode set to: {mode}")

    def detect_asset_class(self, symbol: str) -> str:
        """
        Detect asset class from symbol.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "BTCUSDT", "SOL")

        Returns:
            Asset class string
        """
        symbol_upper = symbol.upper().strip()

        # Check Solana patterns first (most specific)
        for pattern in self.SOLANA_PATTERNS:
            if re.match(pattern, symbol_upper):
                return "solana"

        # Check crypto patterns
        for pattern in self.CRYPTO_PATTERNS:
            if re.match(pattern, symbol_upper):
                return "crypto"

        # Check for stock delimiters
        if "." in symbol_upper and not symbol_upper.endswith(".USD"):
            # Likely a stock with exchange suffix (e.g., AAPL.NASDAQ)
            return "stocks"

        # Default to stocks for uppercase alphanumeric (standard US stocks)
        if re.match(r"^[A-Z]{1,5}$", symbol_upper):
            return "stocks"

        # Fallback: crypto for anything with USDT, BTC, ETH, etc.
        if any(x in symbol_upper for x in ["USDT", "USDC", "BTC", "ETH", "BNB"]):
            return "crypto"

        # Ultimate fallback
        logger.warning(f"Could not detect asset class for {symbol}, defaulting to stocks")
        return "stocks"

    def get_primary_broker_for_asset(self, asset_class: str) -> Optional[BaseBrokerService]:
        """
        Get primary broker for asset class.

        Args:
            asset_class: Asset class string

        Returns:
            Broker instance or None if not available
        """
        broker_name = self.ASSET_BROKER_MAP.get(asset_class)
        if not broker_name:
            logger.warning(f"No broker mapping for asset class: {asset_class}")
            return None

        broker = broker_registry.get(broker_name)
        if not broker:
            logger.warning(f"Broker {broker_name} not registered")
            return None

        if not broker.is_connected:
            logger.warning(f"Broker {broker_name} not connected")
            return None

        return broker

    def get_broker_for_symbol(self, symbol: str) -> Optional[BaseBrokerService]:
        """
        Get appropriate broker for symbol based on routing mode.

        Args:
            symbol: Trading symbol

        Returns:
            Broker instance or None
        """
        if self.routing_mode == "all":
            # In "all" mode, we return the primary broker but execution will fan out
            asset_class = self.detect_asset_class(symbol)
            return self.get_primary_broker_for_asset(asset_class)

        elif self.routing_mode == "ai_decided":
            # In AI mode, the agent decides - for now return primary
            # The execution service will add AI logic
            asset_class = self.detect_asset_class(symbol)
            return self.get_primary_broker_for_asset(asset_class)

        else:  # asset_class mode (default)
            asset_class = self.detect_asset_class(symbol)
            return self.get_primary_broker_for_asset(asset_class)

    def get_all_brokers_for_asset(self, asset_class: str) -> List[Tuple[str, BaseBrokerService]]:
        """
        Get all brokers that can trade this asset class.

        Args:
            asset_class: Asset class string

        Returns:
            List of (broker_name, broker_instance) tuples
        """
        result = []

        for broker_name, capabilities in self.BROKER_CAPABILITIES.items():
            if asset_class in capabilities:
                broker = broker_registry.get(broker_name)
                if broker and broker.is_connected:
                    result.append((broker_name, broker))

        return result

    async def execute_on_all_brokers(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute trade on ALL connected brokers.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            quantity: Order quantity
            order_type: Order type
            **kwargs: Additional order parameters

        Returns:
            List of execution results
        """
        asset_class = self.detect_asset_class(symbol)
        brokers = self.get_all_brokers_for_asset(asset_class)

        if not brokers:
            logger.warning(f"No brokers available for {asset_class}")
            return []

        results = []
        for broker_name, broker in brokers:
            try:
                result = await broker.submit_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    **kwargs
                )

                results.append({
                    "broker": broker_name,
                    "success": result.success,
                    "order_id": result.order_id,
                    "message": result.message,
                })

                logger.info(
                    f"Executed on {broker_name}",
                    success=result.success,
                    order_id=result.order_id,
                )

            except Exception as e:
                logger.error(f"Execution failed on {broker_name}: {e}")
                results.append({
                    "broker": broker_name,
                    "success": False,
                    "error": str(e),
                })

        return results

    async def execute_with_routing(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        routing_mode_override: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute trade with intelligent routing.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            quantity: Order quantity
            order_type: Order type
            routing_mode_override: Override instance routing mode
            **kwargs: Additional order parameters

        Returns:
            List of execution results
        """
        mode = routing_mode_override or self.routing_mode

        if mode == "all":
            return await self.execute_on_all_brokers(
                symbol, side, quantity, order_type, **kwargs
            )

        elif mode == "ai_decided":
            # TODO: Implement AI-based broker selection
            # For now, fall through to asset_class routing
            pass

        # Default: asset_class routing (single broker)
        asset_class = self.detect_asset_class(symbol)
        broker = self.get_primary_broker_for_asset(asset_class)

        if not broker:
            logger.error(f"No broker available for {asset_class} ({symbol})")
            return [{
                "broker": None,
                "success": False,
                "error": f"No broker for {asset_class}",
            }]

        try:
            result = await broker.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                **kwargs
            )

            return [{
                "broker": broker.name,
                "success": result.success,
                "order_id": result.order_id,
                "message": result.message,
            }]

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return [{
                "broker": broker.name,
                "success": False,
                "error": str(e),
            }]

    def get_routing_status(self) -> Dict[str, Any]:
        """
        Get routing status and available brokers.

        Returns:
            Status dict with routing mode and broker availability
        """
        all_brokers = broker_registry.get_all()

        return {
            "routing_mode": self.routing_mode,
            "total_brokers": len(all_brokers),
            "connected_brokers": sum(1 for b in all_brokers.values() if b.is_connected),
            "brokers": {
                name: {
                    "connected": broker.is_connected,
                    "paper_trading": getattr(broker, 'is_paper_trading', None),
                    "capabilities": self.BROKER_CAPABILITIES.get(name, []),
                }
                for name, broker in all_brokers.items()
            },
        }

    def __repr__(self) -> str:
        return f"BrokerRouter(mode={self.routing_mode}, brokers={broker_registry.list_brokers()})"


# Singleton instance
broker_router = BrokerRouter()


def get_broker_router() -> BrokerRouter:
    """Get the broker router instance."""
    return broker_router