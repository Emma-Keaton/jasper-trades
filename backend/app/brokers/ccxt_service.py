"""
CCXT Broker Service - Crypto trading via CCXT library.
Supports Binance, Coinbase, Kraken, and 100+ exchanges.

Docs: https://docs.ccxt.com/
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

from app.brokers.base import (
    BaseBrokerService,
    OrderResult,
    PositionData,
    AccountData,
)
from app.config import settings

logger = structlog.get_logger(__name__)

try:
    import ccxt.async_support as ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False
    logger.warning("ccxt not installed. Crypto broker unavailable.")


class CCXTBrokerService(BaseBrokerService):
    """
    CCXT Broker Service - Unified crypto trading across multiple exchanges.

    Features:
    - Support for 100+ exchanges (Binance, Coinbase, Kraken, etc.)
    - Sandbox and live trading
    - Spot and margin trading
    - Unified API across all exchanges
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=f"ccxt-{exchange_id}", config=config or {})

        self.exchange_id = exchange_id
        self.api_key = config.get("api_key") if config else settings.BINANCE_API_KEY
        self.api_secret = config.get("api_secret") if config else settings.BINANCE_API_SECRET
        self.sandbox = config.get("sandbox", True) if config else True

        # Exchange instance
        self.exchange: Optional[ccxt.Exchange] = None

        # Exchange-specific configuration
        self.symbol_map = config.get("symbol_map", {})  # Map symbols to exchange format
        self.precision_limits = config.get("precision_limits", {})

        if not self.api_key or not self.api_secret:
            logger.debug("CCXT broker instantiated without API credentials – placeholder; will be activated when user provides keys.")

    async def connect(self) -> bool:
        """
        Establish connection to the exchange.

        Returns:
            True if connection successful, False otherwise
        """
        if not CCXT_AVAILABLE:
            logger.error("ccxt library not installed")
            return False

        try:
            # Create exchange instance
            exchange_class = getattr(ccxt, self.exchange_id.lower())

            self.exchange = exchange_class({
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "sandbox": self.sandbox,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",  # spot, margin, future
                },
            })

            # Load markets
            await self.exchange.load_markets()

            # Test connection
            balance = await self.exchange.fetch_balance()

            logger.info(
                f"Connected to {self.exchange_id}",
                sandbox=self.sandbox,
                markets_loaded=len(self.exchange.markets),
            )

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {self.exchange_id}: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close connection to exchange."""
        if self.exchange:
            await self.exchange.close()
            self.exchange = None
        self.is_connected = False
        logger.info(f"Disconnected from {self.exchange_id}")

    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit an order to the exchange.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            side: "buy" or "sell"
            quantity: Amount of base currency
            order_type: "market", "limit"
            limit_price: Limit price for limit orders
            time_in_force: "GTC", "IOC", "FOK"
            client_order_id: Optional client order ID

        Returns:
            OrderResult with order details
        """
        if not self.is_connected:
            return OrderResult(
                success=False,
                message=f"Not connected to {self.exchange_id}. Call connect() first.",
            )

        # Validate order
        is_valid, error_msg = self.validate_order(symbol, side, quantity, order_type)
        if not is_valid:
            return OrderResult(success=False, message=error_msg)

        try:
            # Normalize symbol
            normalized_symbol = self._normalize_symbol(symbol)

            # Check if symbol exists
            if normalized_symbol not in self.exchange.markets:
                return OrderResult(
                    success=False,
                    message=f"Symbol {normalized_symbol} not found on {self.exchange_id}",
                )

            # Get market info
            market = self.exchange.markets[normalized_symbol]

            # Precision and limits
            amount = self._amount_to_precision(normalized_symbol, quantity)
            price = None

            if order_type == "limit" and limit_price:
                price = self._price_to_precision(normalized_symbol, limit_price)

            # Map order type
            ccxt_type = "market" if order_type == "market" else "limit"

            # Prepare params
            params = {}
            if client_order_id:
                params["clientOrderId"] = client_order_id

            # Submit order
            logger.info(
                "Submitting crypto order",
                symbol=normalized_symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
            )

            if order_type == "market":
                order = await self.exchange.create_order(
                    symbol=normalized_symbol,
                    type=ccxt_type,
                    side=self.map_side(side),
                    amount=amount,
                    params=params,
                )
            else:
                order = await self.exchange.create_order(
                    symbol=normalized_symbol,
                    type=ccxt_type,
                    side=self.map_side(side),
                    amount=amount,
                    price=price,
                    params=params,
                )

            logger.info(
                "Order submitted",
                order_id=order["id"],
                status=order["status"],
            )

            filled_qty = float(order.get("filled", 0))
            filled_price = float(order.get("average", 0)) if order.get("average") else None

            return OrderResult(
                success=True,
                order_id=order["id"],
                message=f"Order submitted: {side} {quantity} {symbol}",
                filled_quantity=filled_qty,
                filled_price=filled_price,
                commission=float(order.get("fee", {}).get("cost", 0)),
            )

        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return OrderResult(
                success=False,
                message=f"Order submission failed: {str(e)}",
            )

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Exchange order ID
            symbol: Trading pair (required for some exchanges)

        Returns:
            True if cancellation successful, False otherwise
        """
        if not self.is_connected:
            logger.error("Not connected to exchange")
            return False

        try:
            await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Cancelled order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return False

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """
        Get current balance/position for a symbol.

        Args:
            symbol: Token symbol (e.g., "BTC", "USDT")

        Returns:
            PositionData if balance exists, None otherwise
        """
        if not self.is_connected:
            return None

        try:
            balance = await self.exchange.fetch_balance()

            # Normalize symbol
            token = symbol.upper()

            if token not in balance:
                return None

            token_balance = balance[token]
            total = float(token_balance.get("total", 0))

            if total == 0:
                return None

            # Get current price (in USDT)
            current_price = None
            if token != "USDT":
                try:
                    ticker_symbol = f"{token}/USDT"
                    ticker = await self.exchange.fetch_ticker(ticker_symbol)
                    current_price = float(ticker.get("last", 0))
                except:
                    pass

            market_value = total * current_price if current_price else None

            return PositionData(
                symbol=token,
                quantity=total,
                avg_price=0,  # CCXT doesn't provide avg entry price
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=None,
                unrealized_pnl_percent=None,
                side="long",
            )

        except Exception as e:
            logger.warning(f"Error getting position for {symbol}: {e}")
            return None

    async def get_positions(self) -> List[PositionData]:
        """
        Get all balances (positions).

        Returns:
            List of PositionData objects
        """
        if not self.is_connected:
            return []

        try:
            balance = await self.exchange.fetch_balance()

            positions = []
            for token, token_balance in balance.items():
                if not isinstance(token_balance, dict):
                    continue

                total = float(token_balance.get("total", 0))
                if total == 0:
                    continue

                # Skip USD stablecoins for cleaner output
                if token in ["USDT", "USDC", "BUSD", "DAI"]:
                    continue

                # Get current price
                current_price = None
                market_value = None

                if token != "USDT":
                    try:
                        ticker_symbol = f"{token}/USDT"
                        if ticker_symbol in self.exchange.markets:
                            ticker = await self.exchange.fetch_ticker(ticker_symbol)
                            current_price = float(ticker.get("last", 0))
                            market_value = total * current_price
                    except:
                        pass

                positions.append(
                    PositionData(
                        symbol=token,
                        quantity=total,
                        avg_price=0,
                        current_price=current_price,
                        market_value=market_value,
                        unrealized_pnl=None,
                        unrealized_pnl_percent=None,
                        side="long",
                    )
                )

            return positions

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_account(self) -> AccountData:
        """
        Get account information.

        Returns:
            AccountData with account details
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to exchange")

        try:
            balance = await self.exchange.fetch_balance()

            # Calculate total value in USDT
            total_value = 0
            usdt_balance = float(balance.get("USDT", {}).get("total", 0))

            # Add value of other tokens
            for token, token_balance in balance.items():
                if not isinstance(token_balance, dict) or token in ["USDT", "info"]:
                    continue

                total = float(token_balance.get("total", 0))
                if total == 0:
                    continue

                try:
                    ticker_symbol = f"{token}/USDT"
                    if ticker_symbol in self.exchange.markets:
                        ticker = await self.exchange.fetch_ticker(ticker_symbol)
                        price = float(ticker.get("last", 0))
                        total_value += total * price
                except:
                    pass

            total_value += usdt_balance

            return AccountData(
                account_id=self.api_key[:8] + "..." if self.api_key else "unknown",
                cash=usdt_balance,
                portfolio_value=total_value,
                buying_power=usdt_balance,  # Simplified
                equity=total_value,
                last_equity=None,
                day_trading_buying_power=None,
            )

        except Exception as e:
            logger.error(f"Error getting account: {e}")
            raise

    async def get_clock(self) -> Dict[str, Any]:
        """
        Get exchange status.

        Crypto markets are 24/7, so always open.

        Returns:
            Dict with is_open=True always
        """
        return {
            "is_open": True,
            "next_open": None,
            "next_close": None,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Crypto markets trade 24/7",
        }

    async def get_order_status(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of an order.

        Args:
            order_id: Exchange order ID
            symbol: Trading pair

        Returns:
            Dict with order status details
        """
        if not self.is_connected:
            return {"error": "Not connected"}

        try:
            order = await self.exchange.fetch_order(order_id, symbol)

            return {
                "order_id": order["id"],
                "client_order_id": order.get("clientOrderId"),
                "symbol": order["symbol"],
                "side": order["side"],
                "order_type": order["type"],
                "status": order["status"],
                "quantity": float(order.get("amount", 0)),
                "filled_quantity": float(order.get("filled", 0)),
                "limit_price": float(order.get("price", 0)) if order.get("price") else None,
                "filled_avg_price": (
                    float(order.get("average", 0)) if order.get("average") else None
                ),
                "timestamp": (
                    datetime.fromtimestamp(order["timestamp"] / 1000).isoformat()
                    if order.get("timestamp")
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {"error": str(e)}

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to exchange format."""
        # Check custom map first
        if symbol in self.symbol_map:
            return self.symbol_map[symbol]

        # Try to find in markets
        upper = symbol.upper()

        # Common formats: BTC/USDT, BTCUSDT, BTC-USD
        variants = [
            f"{upper[:3]}/{upper[3:]}",  # BTC/USDT
            upper,  # BTCUSDT
            f"{upper[:3]}-{upper[3:]}",  # BTC-USDT
        ]

        for variant in variants:
            if variant in self.exchange.markets:
                return variant

        # Default fallback
        if "/" not in upper:
            if upper.endswith("USDT"):
                return f"{upper[:-4]}/USDT"

        return upper

    def _amount_to_precision(self, symbol: str, amount: float) -> float:
        """Round amount to exchange precision."""
        if symbol not in self.exchange.markets:
            return amount

        market = self.exchange.markets[symbol]
        precision = market.get("precision", {}).get("amount")

        if precision:
            return self.exchange.amount_to_precision(symbol, amount)

        return amount

    def _price_to_precision(self, symbol: str, price: float) -> float:
        """Round price to exchange precision."""
        if symbol not in self.exchange.markets:
            return price

        market = self.exchange.markets[symbol]
        precision = market.get("precision", {}).get("price")

        if precision:
            return self.exchange.price_to_precision(symbol, price)

        return price

    def __repr__(self) -> str:
        return (
            f"CCXTBrokerService(exchange={self.exchange_id}, "
            f"sandbox={self.sandbox}, connected={self.is_connected})"
        )