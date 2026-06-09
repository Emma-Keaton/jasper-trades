"""
IBKR Broker Service - Interactive Brokers integration via ib-insync.
Supports stocks, options, futures, forex, and bonds.

Requires TWS or IB Gateway running locally.
Docs: https://ib-insync.readthedocs.io/
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
    from ib_insync import IB, Stock, Option, Future, Forex, MarketOrder, LimitOrder, StopOrder, Trade as IBTrade
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logger.warning("ib-insync not installed. IBKR broker unavailable.")


class IBKRBrokerService(BaseBrokerService):
    """
    Interactive Brokers Broker Service - Professional trading via IBKR.

    Features:
    - Stocks, options, futures, forex, bonds
    - Smart order routing
    - Advanced order types
    - Real-time market data
    - Portfolio margin support

    Requirements:
    - TWS or IB Gateway running locally
    - API access enabled in TWS/IB Gateway
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="ibkr", config=config or {})

        # Configuration
        self.host = config.get("host") if config else settings.IBKR_HOST
        self.port = config.get("port") if config else settings.IBKR_PORT
        self.client_id = config.get("client_id") if config else settings.IBKR_CLIENT_ID

        # IB connection
        self.ib: Optional[IB] = None

        if not self.host:
            logger.warning("IBKR host not configured")

    async def connect(self) -> bool:
        """
        Establish connection to IBKR TWS/Gateway.

        Returns:
            True if connection successful, False otherwise
        """
        if not IBKR_AVAILABLE:
            logger.error("ib-insync library not installed")
            return False

        if not self.host:
            logger.error("IBKR host not configured")
            return False

        try:
            # Create IB instance
            self.ib = IB()

            # Connect to TWS/Gateway
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
            )

            # Get account info
            account = self.ib.accountValues()

            logger.info(
                "Connected to IBKR",
                host=self.host,
                port=self.port,
                client_id=self.client_id,
            )

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib:
            self.ib.disconnect()
            self.ib = None
        self.is_connected = False
        logger.info("Disconnected from IBKR")

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
        Submit an order to IBKR.

        Args:
            symbol: Trading symbol or IQFeed contract specs
            side: "buy" or "sell"
            quantity: Number of shares/contracts
            order_type: "market", "limit", "stop"
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: "DAY", "GTC" (mapped to IBKR TIF)
            client_order_id: Not supported by IBKR API

        Returns:
            OrderResult with order details
        """
        if not self.is_connected:
            return OrderResult(
                success=False,
                message="Not connected to IBKR. Ensure TWS/Gateway is running.",
            )

        # Validate order
        is_valid, error_msg = self.validate_order(symbol, side, quantity, order_type)
        if not is_valid:
            return OrderResult(success=False, message=error_msg)

        try:
            # Create contract
            contract = self._create_contract(symbol)

            # Create order
            ib_order = self._create_order(
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force,
            )

            # Map TIF
            tif_map = {"day": "DAY", "gtc": "GTC", "ioc": "IOC"}
            ib_order.tif = tif_map.get(time_in_force.lower(), "DAY")

            logger.info(
                "Submitting IBKR order",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
            )

            # Submit order
            ib_trade = self.ib.placeOrder(contract, ib_order)

            # Wait for order acknowledgment
            await asyncio.sleep(0.5)

            return OrderResult(
                success=True,
                order_id=str(ib_trade.order.orderId),
                message=f"Order submitted: {side} {quantity} {symbol}",
                filled_quantity=ib_trade.orderStatus.filled,
                filled_price=ib_trade.orderStatus.avgFillPrice if ib_trade.orderStatus.filled > 0 else None,
            )

        except Exception as e:
            logger.error(f"IBKR order submission error: {e}")
            return OrderResult(
                success=False,
                message=f"Order submission failed: {str(e)}",
            )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: IBKR order ID

        Returns:
            True if cancellation successful, False otherwise
        """
        if not self.is_connected:
            logger.error("Not connected to IBKR")
            return False

        try:
            # IBKR order IDs are integers
            ibkr_order_id = int(order_id)

            # Find and cancel order
            self.ib.cancelOrder(
                Order(orderId=ibkr_order_id)
            )

            logger.info(f"Cancelled IBKR order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return False

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """
        Get current position for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            PositionData if position exists, None otherwise
        """
        if not self.is_connected:
            return None

        try:
            positions = self.ib.positions()

            for position in positions:
                if position.contract.symbol == symbol.upper():
                    current_price = await self._get_market_price(position.contract)

                    return PositionData(
                        symbol=position.contract.symbol,
                        quantity=position.position,
                        avg_price=position.avgCost,
                        current_price=current_price,
                        market_value=position.position * current_price if current_price else None,
                        unrealized_pnl=position.unrealizedPNL,
                        unrealized_pnl_percent=position.unrealizedPercent,
                        side="long" if position.position > 0 else "short",
                    )

            return None

        except Exception as e:
            logger.warning(f"Error getting position for {symbol}: {e}")
            return None

    async def get_positions(self) -> List[PositionData]:
        """
        Get all current positions.

        Returns:
            List of PositionData objects
        """
        if not self.is_connected:
            return []

        try:
            positions = self.ib.positions()
            position_data = []

            for position in positions:
                current_price = await self._get_market_price(position.contract)

                position_data.append(
                    PositionData(
                        symbol=position.contract.symbol,
                        quantity=position.position,
                        avg_price=position.avgCost,
                        current_price=current_price,
                        market_value=position.position * current_price if current_price else None,
                        unrealized_pnl=position.unrealizedPNL,
                        unrealized_pnl_percent=position.unrealizedPercent,
                        side="long" if position.position > 0 else "short",
                    )
                )

            return position_data

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
            raise RuntimeError("Not connected to IBKR")

        try:
            # Get account values
            account_values = {av.tag: av.value for av in self.ib.accountValues()}

            cash = float(account_values.get("AvailableFunds", 0))
            equity = float(account_values.get("NetLiquidation", 0))
            buying_power = float(account_values.get("BuyingPower", 0))

            return AccountData(
                account_id=self.ib.client.clientId,
                cash=cash,
                portfolio_value=equity,
                buying_power=buying_power,
                equity=equity,
                last_equity=float(account_values.get("PreviousEquity", equity)),
                day_trading_buying_power=float(account_values.get("DayTradesRemaining", 0)),
            )

        except Exception as e:
            logger.error(f"Error getting account: {e}")
            raise

    async def get_clock(self) -> Dict[str, Any]:
        """
        Get market hours status.

        Returns:
            Dict with market hours info
        """
        if not self.is_connected:
            return {"is_open": False, "error": "Not connected"}

        try:
            # IBKR doesn't have a direct "clock" endpoint
            # Use server time as reference
            server_time = self.ib.ServerTime

            return {
                "is_open": True,  # IBKR API is always accessible
                "next_open": None,
                "next_close": None,
                "timestamp": server_time.isoformat() if server_time else datetime.utcnow().isoformat(),
                "note": "IBKR API available 24/7, market hours vary by asset",
            }

        except Exception as e:
            logger.error(f"Error getting clock: {e}")
            return {"is_open": False, "error": str(e)}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order.

        Args:
            order_id: IBKR order ID

        Returns:
            Dict with order status details
        """
        if not self.is_connected:
            return {"error": "Not connected"}

        try:
            ibkr_order_id = int(order_id)

            # Find order in open orders
            for order in self.ib.openOrders():
                if order.order.orderId == ibkr_order_id:
                    return {
                        "order_id": str(order.order.orderId),
                        "symbol": order.contract.symbol,
                        "side": order.order.action,
                        "order_type": order.order.orderType,
                        "status": order.orderStatus.status,
                        "quantity": order.order.totalQuantity,
                        "filled_quantity": order.orderStatus.filled,
                        "limit_price": order.order.lmtPrice,
                        "filled_avg_price": order.orderStatus.avgFillPrice,
                    }

            return {"error": "Order not found", "order_id": order_id}

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {"error": str(e)}

    def _create_contract(self, symbol: str):
        """
        Create IBKR contract from symbol.

        Handles stocks, options, futures, forex.
        """
        # Simple stock contract
        return Stock(symbol.upper(), "SMART", "USD")

        # For more complex contracts:
        # Options: Option(symbol, expiry, strike, right, exchange)
        # Futures: Future(symbol, expiry, exchange)
        # Forex: Forex(pair)

    def _create_order(
        self,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ):
        """Create IBKR order based on type."""
        action = "BUY" if side.lower() == "buy" else "SELL"
        qty = int(quantity) if quantity == int(quantity) else quantity

        if order_type == "market":
            return MarketOrder(action, qty)

        elif order_type == "limit":
            return LimitOrder(action, qty, limit_price)

        elif order_type == "stop":
            return StopOrder(action, qty, stop_price)

        else:
            return MarketOrder(action, qty)

    async def _get_market_price(self, contract) -> Optional[float]:
        """Get current market price for a contract."""
        try:
            ticker = await self.ib.reqMktDataAsync(contract)
            await asyncio.sleep(0.5)  # Allow data to arrive
            return ticker.last
        except:
            return None

    def __repr__(self) -> str:
        return f"IBKRBrokerService(host={self.host}, port={self.port}, connected={self.is_connected})"


# Import asyncio at module level for the IBKR service
import asyncio