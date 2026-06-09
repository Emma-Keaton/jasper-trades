"""
Alpaca Broker Service
Trading integration with Alpaca Securities (stocks, options, crypto).
Supports both paper trading and live trading.

Docs: https://alpaca.markets/docs/
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
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopOrderRequest,
        StopLimitOrderRequest,
        OrderSide,
        OrderType,
        TimeInForce,
    )
    from alpaca.trading.enums import OrderStatus, QueryOrderStatus
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("alpaca-py not installed. Alpaca broker unavailable.")


class AlpacaBrokerService(BaseBrokerService):
    """
    Alpaca Broker Service - Full integration with Alpaca Trading API.

    Features:
    - Paper trading (unlimited, free)
    - Live trading (same API, different endpoint)
    - Stocks, options, crypto support
    - Real-time market data
    - Account and position management
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="alpaca", config=config or {})

        # Configuration from settings or config dict
        self.api_key = config.get("api_key") if config else settings.ALPACA_API_KEY
        self.api_secret = config.get("api_secret") if config else settings.ALPACA_API_SECRET
        self.is_paper_trading = config.get("paper", True) if config else settings.ALPACA_PAPER

        # Clients (initialized on connect)
        self.trading_client: Optional[TradingClient] = None
        self.data_client: Optional[StockHistoricalDataClient] = None

        # Rate limiting
        self._request_count = 0
        self._last_reset = datetime.utcnow()

        if not self.api_key or not self.api_secret:
            logger.warning("Alpaca API credentials not configured")

    async def connect(self) -> bool:
        """
        Establish connection to Alpaca.

        Returns:
            True if connection successful, False otherwise
        """
        if not ALPACA_AVAILABLE:
            logger.error("alpaca-py library not installed")
            return False

        if not self.api_key or not self.api_secret:
            logger.error("Alpaca API credentials not configured")
            return False

        try:
            # Initialize trading client
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.is_paper_trading,
            )

            # Initialize data client
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
            )

            # Test connection by getting account
            account = self.trading_client.get_account()
            logger.info(
                "Connected to Alpaca",
                account_id=account.id,
                account_number=account.account_number,
                paper=self.is_paper_trading,
                cash=account.cash,
                portfolio_value=account.portfolio_value,
            )

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close connection to Alpaca."""
        self.trading_client = None
        self.data_client = None
        self.is_connected = False
        logger.info("Disconnected from Alpaca")

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
        Submit an order to Alpaca.

        Args:
            symbol: Trading symbol (e.g., "AAPL")
            side: "buy" or "sell"
            quantity: Number of shares
            order_type: "market", "limit", "stop", "stop_limit"
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: "day", "gtc", "ioc", "opg"
            client_order_id: Optional client order ID

        Returns:
            OrderResult with order details
        """
        if not self.is_connected:
            return OrderResult(
                success=False,
                message="Not connected to Alpaca. Call connect() first.",
            )

        # Validate order
        is_valid, error_msg = self.validate_order(symbol, side, quantity, order_type)
        if not is_valid:
            return OrderResult(success=False, message=error_msg)

        try:
            # Map time in force
            tif_mapping = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "opg": TimeInForce.OPG,
            }
            tif = tif_mapping.get(time_in_force.lower(), TimeInForce.DAY)

            # Create order request based on type
            order_request = None

            if order_type == "market":
                order_request = MarketOrderRequest(
                    symbol=symbol.upper(),
                    qty=quantity,
                    side=self.map_side(side),
                    time_in_force=tif,
                    client_order_id=client_order_id,
                )

            elif order_type == "limit":
                if limit_price is None:
                    return OrderResult(success=False, message="Limit price required for limit order")

                order_request = LimitOrderRequest(
                    symbol=symbol.upper(),
                    qty=quantity,
                    side=self.map_side(side),
                    time_in_force=tif,
                    limit_price=limit_price,
                    client_order_id=client_order_id,
                )

            elif order_type == "stop":
                if stop_price is None:
                    return OrderResult(success=False, message="Stop price required for stop order")

                order_request = StopOrderRequest(
                    symbol=symbol.upper(),
                    qty=quantity,
                    side=self.map_side(side),
                    time_in_force=tif,
                    stop_price=stop_price,
                    client_order_id=client_order_id,
                )

            elif order_type == "stop_limit":
                if limit_price is None or stop_price is None:
                    return OrderResult(
                        success=False,
                        message="Both limit and stop prices required for stop-limit order",
                    )

                order_request = StopLimitOrderRequest(
                    symbol=symbol.upper(),
                    qty=quantity,
                    side=self.map_side(side),
                    time_in_force=tif,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    client_order_id=client_order_id,
                )

            else:
                return OrderResult(success=False, message=f"Unsupported order type: {order_type}")

            # Submit order
            logger.info(
                "Submitting order to Alpaca",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            order = self.trading_client.submit_order(order_request)

            logger.info(
                "Order submitted successfully",
                order_id=order.id,
                status=order.status,
            )

            return OrderResult(
                success=True,
                order_id=str(order.id),
                message=f"Order submitted: {side} {quantity} {symbol}",
                filled_quantity=float(order.filled_qty or 0),
                filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            )

        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return OrderResult(
                success=False,
                message=f"Order submission failed: {str(e)}",
            )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Alpaca order ID to cancel

        Returns:
            True if cancellation successful, False otherwise
        """
        if not self.is_connected:
            logger.error("Not connected to Alpaca")
            return False

        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return False

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """
        Get current position for a symbol.

        Args:
            symbol: Trading symbol (e.g., "AAPL")

        Returns:
            PositionData if position exists, None otherwise
        """
        if not self.is_connected:
            return None

        try:
            position = self.trading_client.get_open_position(symbol.upper())

            if not position:
                return None

            # Calculate market value and PnL
            current_price = self._get_current_price(symbol.upper())
            market_value = float(position.market_value) if position.market_value else None
            qty = float(position.qty)

            return PositionData(
                symbol=symbol.upper(),
                quantity=qty,
                avg_price=float(position.avg_entry_price) if position.avg_entry_price else 0,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=float(position.unrealized_pl) if position.unrealized_pl else None,
                unrealized_pnl_percent=(
                    float(position.unrealized_plpc) * 100 if position.unrealized_plpc else None
                ),
                side="long" if qty > 0 else "short",
            )

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
            positions = self.trading_client.get_all_positions()

            position_data = []
            for position in positions:
                current_price = self._get_current_price(position.symbol)
                qty = float(position.qty)

                position_data.append(
                    PositionData(
                        symbol=position.symbol,
                        quantity=qty,
                        avg_price=float(position.avg_entry_price) if position.avg_entry_price else 0,
                        current_price=current_price,
                        market_value=float(position.market_value) if position.market_value else None,
                        unrealized_pnl=float(position.unrealized_pl) if position.unrealized_pl else None,
                        unrealized_pnl_percent=(
                            float(position.unrealized_plpc) * 100 if position.unrealized_plpc else None
                        ),
                        side="long" if qty > 0 else "short",
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
            raise RuntimeError("Not connected to Alpaca")

        try:
            account = self.trading_client.get_account()

            return AccountData(
                account_id=account.id,
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power) if hasattr(account, 'buying_power') else None,
                equity=float(account.equity) if hasattr(account, 'equity') else None,
                last_equity=float(account.last_equity) if hasattr(account, 'last_equity') else None,
                day_trading_buying_power=(
                    float(account.daytrading_buying_power)
                    if hasattr(account, 'daytrading_buying_power')
                    else None
                ),
            )

        except Exception as e:
            logger.error(f"Error getting account: {e}")
            raise

    async def get_clock(self) -> Dict[str, Any]:
        """
        Get market clock/market hours status.

        Returns:
            Dict with is_open, next_open, next_close, timestamp
        """
        if not self.is_connected:
            return {"is_open": False, "error": "Not connected"}

        try:
            clock = self.trading_client.get_clock()

            return {
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat() if clock.next_close else None,
                "timestamp": clock.timestamp.isoformat() if clock.timestamp else None,
            }

        except Exception as e:
            logger.error(f"Error getting clock: {e}")
            return {"is_open": False, "error": str(e)}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order.

        Args:
            order_id: Alpaca order ID

        Returns:
            Dict with order status details
        """
        if not self.is_connected:
            return {"error": "Not connected"}

        try:
            order = self.trading_client.get_order_by_id(order_id)

            return {
                "order_id": str(order.id),
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.type,
                "status": order.status,
                "quantity": float(order.qty),
                "filled_quantity": float(order.filled_qty or 0),
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "stop_price": float(order.stop_price) if order.stop_price else None,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            }

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {"error": str(e)}

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current ask price or None if unavailable
        """
        if not self.data_client:
            return None

        try:
            from alpaca.data.requests import StockLatestQuoteRequest

            request = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
            quote = self.data_client.get_stock_latest_quote(request)

            if quote and symbol.upper() in quote:
                return float(quote[symbol.upper()].ask_price)

        except Exception as e:
            logger.warning(f"Error getting price for {symbol}: {e}")

        return None

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest market data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dict with bid, ask, last, volume
        """
        if not self.data_client:
            return {"error": "Data client not initialized"}

        try:
            from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest

            # Get latest quote
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
            quote = self.data_client.get_stock_latest_quote(quote_request)

            # Get latest trade
            trade_request = StockLatestTradeRequest(symbol_or_symbols=symbol.upper())
            trade = self.data_client.get_stock_latest_trade(trade_request)

            result = {
                "symbol": symbol.upper(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            if quote and symbol.upper() in quote:
                q = quote[symbol.upper()]
                result.update({
                    "bid": float(q.bid_price),
                    "ask": float(q.ask_price),
                    "bid_size": int(q.bid_size),
                    "ask_size": int(q.ask_size),
                })

            if trade and symbol.upper() in trade:
                t = trade[symbol.upper()]
                result.update({
                    "last": float(t.price),
                    "volume": int(t.size),
                })

            return result

        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {"error": str(e)}

    def __repr__(self) -> str:
        return (
            f"AlpacaBrokerService(paper={self.is_paper_trading}, "
            f"connected={self.is_connected})"
        )