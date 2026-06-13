"""
Trove API Broker Service

Integration with Trove's Developer API for trading Nigerian (NGX) and US stocks.
Supports fractional share trading, multi-currency (USD/NGN), and real-time market data.

Trove API Documentation:
- Sandbox: https://sandbox.api.trovefinance.com/v1
- Production: https://api.trovefinance.com/v1
- Supports: US stocks, NGX stocks, fractional shares, forex conversion
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog
import httpx
from decimal import Decimal

from app.brokers.base import (
    BaseBrokerService,
    OrderResult,
    PositionData,
    AccountData,
)

logger = structlog.get_logger(__name__)


class TroveBrokerService(BaseBrokerService):
    """
    Trove API Broker Service - Nigerian/US stocks trading.

    Features:
    - Fractional share trading (buy/sell by dollar amount)
    - Multi-currency support (USD, NGN)
    - Real-time market data (US & NGX markets)
    - Forex conversion (NGN/USD rates)
    - Market/limit order types
    - Sandbox and production environments

    Usage:
        1. Initialize with API key and base URL
        2. Connect to validate credentials
        3. Submit orders with amount (fractional) or quantity
        4. Get positions and account balance in selected currency
    """

    # Trove API endpoints
    SANDBOX_BASE_URL = "https://sandbox.api.trovefinance.com/v1"
    LIVE_BASE_URL = "https://api.trovefinance.com/v1"

    # Rate limiting (adjust based on Trove's actual limits)
    MAX_REQUESTS_PER_SECOND = 100
    REQUEST_BURST_LIMIT = 150

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        sandbox: bool = True,
        account_id: Optional[str] = None,
    ):
        super().__init__(name="trove", config={})

        # API configuration
        self.api_key = api_key
        self.sandbox = sandbox
        self.account_id = account_id

        # Set base URL
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = self.SANDBOX_BASE_URL if sandbox else self.LIVE_BASE_URL

        # Rate limiting state
        self._request_timestamps: List[datetime] = []
        self._last_rate_limit_check = datetime.utcnow()

        # Connection state
        self.is_connected = False

        # Trove supports both paper (sandbox) and live trading
        self.is_paper_trading = sandbox

        # Currency preference
        self.default_currency = "USD"

        if not self.api_key:
            logger.warning("Trove API key not provided")

    async def connect(self) -> bool:
        """
        Establish connection to Trove API.

        Validates API credentials and fetches account info.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.api_key:
            logger.error("Trove API key not provided")
            return False

        try:
            # Test connection by fetching account info
            account_info = await self._make_request("GET", "/account")

            if account_info:
                self.account_id = account_info.get("account_id")
                logger.info(
                    "Connected to Trove API",
                    account_id=self.account_id,
                    sandbox=self.sandbox,
                    currency=account_info.get("currency", "USD"),
                )
                self.is_connected = True
                return True
            else:
                logger.error("Failed to fetch Trove account info")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Trove API: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Close connection to Trove API."""
        self.is_connected = False
        logger.info("Disconnected from Trove API")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to Trove API with rate limiting.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/account", "/orders")
            payload: Optional JSON payload for POST/PUT requests

        Returns:
            JSON response or None if request failed
        """
        # Rate limiting check
        await self._enforce_rate_limit()

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                )

                response.raise_for_status()

                if response.status_code == 204:
                    return None

                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Trove API HTTP error: {e.response.status_code}",
                endpoint=endpoint,
                response=e.response.text,
            )
            return None

        except httpx.RequestError as e:
            logger.error(f"Trove API request error: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in Trove API request: {e}")
            return None

    async def _enforce_rate_limit(self):
        """Enforce rate limiting to avoid API throttling."""
        now = datetime.utcnow()

        # Remove timestamps older than 1 second
        self._request_timestamps = [
            ts for ts in self._request_timestamps
            if (now - ts).total_seconds() < 1.0
        ]

        # Check if we've exceeded rate limit
        if len(self._request_timestamps) >= self.MAX_REQUESTS_PER_SECOND:
            sleep_time = 1.0 - (now - self._request_timestamps[0]).total_seconds()
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

        self._request_timestamps.append(now)

    async def get_clock(self) -> Dict[str, Any]:
        """
        Get market clock/market hours status.

        Returns both US and NGX market status.

        Returns:
            Dict with is_open, next_open, next_close, timestamp for both markets
        """
        try:
            # Fetch market status
            market_status = await self._make_request("GET", "/market/status")

            if not market_status:
                # Fallback: return both markets as closed
                return {
                    "us_market": {
                        "is_open": False,
                        "next_open": None,
                        "next_close": None,
                    },
                    "ngx_market": {
                        "is_open": False,
                        "next_open": None,
                        "next_close": None,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {
                "us_market": {
                    "is_open": market_status.get("us_market_open", False),
                    "next_open": market_status.get("us_next_open"),
                    "next_close": market_status.get("us_next_close"),
                },
                "ngx_market": {
                    "is_open": market_status.get("ngx_market_open", False),
                    "next_open": market_status.get("ngx_next_open"),
                    "next_close": market_status.get("ngx_next_close"),
                },
                "timestamp": market_status.get("timestamp", datetime.utcnow().isoformat()),
            }

        except Exception as e:
            logger.error(f"Failed to get market status: {e}")
            return {
                "us_market": {"is_open": False, "next_open": None, "next_close": None},
                "ngx_market": {"is_open": False, "next_open": None, "next_close": None},
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def get_market_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time market quote for a symbol.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "DANGCEM.LAGOS")

        Returns:
            Quote data with bid, ask, last_price, volume
        """
        try:
            quote = await self._make_request("GET", f"/market/quote/{symbol}")

            if not quote:
                return None

            return {
                "symbol": symbol,
                "bid": float(quote.get("bid_price", 0)),
                "ask": float(quote.get("ask_price", 0)),
                "last_price": float(quote.get("last_price", 0)),
                "volume": int(quote.get("volume", 0)),
                "currency": quote.get("currency", "USD"),
                "market": quote.get("market", "US"),  # "US" or "NGX"
                "timestamp": quote.get("timestamp", datetime.utcnow().isoformat()),
            }

        except Exception as e:
            logger.error(f"Failed to get market quote for {symbol}: {e}")
            return None

    async def get_forex_rate(
        self,
        from_currency: str,
        to_currency: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get forex exchange rate.

        Args:
            from_currency: Source currency (e.g., "NGN")
            to_currency: Target currency (e.g., "USD")

        Returns:
            Exchange rate with bid/ask prices
        """
        try:
            rate_data = await self._make_request(
                "GET",
                f"/forex/rate?from={from_currency}&to={to_currency}",
            )

            if not rate_data:
                return None

            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": float(rate_data.get("rate", 0)),
                "bid": float(rate_data.get("bid", 0)),
                "ask": float(rate_data.get("ask", 0)),
                "timestamp": rate_data.get("timestamp", datetime.utcnow().isoformat()),
            }

        except Exception as e:
            logger.error(f"Failed to get forex rate {from_currency}->{to_currency}: {e}")
            return None

    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: Optional[float] = None,
        amount: Optional[float] = None,  # For fractional trading
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit an order to Trove.

        Supports both quantity-based and amount-based (fractional) orders.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "DANGCEM.LAGOS")
            side: "buy" or "sell"
            quantity: Number of shares (optional if amount provided)
            amount: Dollar/Naira amount for fractional trading (optional)
            order_type: "market", "limit", "stop"
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: "day", "gtc", "ioc"
            client_order_id: Optional client order ID

        Returns:
            OrderResult with order details
        """
        # Validate order
        is_valid, error_message = self.validate_order(symbol, side, quantity or 0, order_type)
        if not is_valid and not amount:  # Allow amount-based orders
            return OrderResult(
                success=False,
                message=error_message,
            )

        if not quantity and not amount:
            return OrderResult(
                success=False,
                message="Either quantity or amount must be specified",
            )

        # Build order payload
        order_payload = {
            "account_id": self.account_id,
            "symbol": symbol,
            "action": side.upper(),  # BUY or SELL
            "order_type": order_type,
            "time_in_force": time_in_force,
        }

        # Add quantity or amount
        if quantity:
            order_payload["quantity"] = quantity
        elif amount:
            order_payload["amount"] = amount  # Fractional trading

        # Add optional fields
        if order_type == "limit" and limit_price:
            order_payload["limit_price"] = limit_price
        elif order_type == "stop" and stop_price:
            order_payload["stop_price"] = stop_price

        if client_order_id:
            order_payload["client_order_id"] = client_order_id

        try:
            response = await self._make_request("POST", "/orders", order_payload)

            if not response:
                return OrderResult(
                    success=False,
                    message="Failed to submit order",
                )

            order_id = response.get("order_id")
            status = response.get("status", "pending")

            logger.info(
                "Order submitted to Trove",
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                amount=amount,
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                message=f"Order {status}",
                filled_quantity=0,  # Will be updated when filled
                filled_price=None,
            )

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            return OrderResult(
                success=False,
                message=str(e),
            )

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order.

        Args:
            order_id: Trove order ID

        Returns:
            Dict with order status details
        """
        try:
            order_data = await self._make_request("GET", f"/orders/{order_id}")

            if not order_data:
                return {"error": "Order not found"}

            return {
                "order_id": order_id,
                "symbol": order_data.get("symbol"),
                "side": order_data.get("action", "BUY"),
                "quantity": float(order_data.get("quantity", 0)),
                "amount": float(order_data.get("amount", 0)),
                "status": order_data.get("status", "unknown"),
                "filled_quantity": float(order_data.get("filled_quantity", 0)),
                "filled_price": float(order_data.get("filled_price", 0)) if order_data.get("filled_price") else None,
                "order_type": order_data.get("order_type"),
                "created_at": order_data.get("created_at"),
                "updated_at": order_data.get("updated_at"),
            }

        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return {"error": str(e)}

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Trove order ID

        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            response = await self._make_request("DELETE", f"/orders/{order_id}")
            return response is not None

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """
        Get current position for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            PositionData if position exists, None otherwise
        """
        try:
            position_data = await self._make_request("GET", f"/account/positions/{symbol}")

            if not position_data:
                return None

            quantity = float(position_data.get("quantity", 0))
            if quantity == 0:
                return None

            avg_price = float(position_data.get("avg_cost", 0))
            current_price = float(position_data.get("current_price", 0))
            market_value = float(position_data.get("market_value", 0))
            unrealized_pnl = float(position_data.get("unrealized_pnl", 0))

            unrealized_pnl_percent = (
                (unrealized_pnl / (avg_price * quantity) * 100)
                if avg_price * quantity > 0
                else 0
            )

            return PositionData(
                symbol=symbol,
                quantity=quantity,
                avg_price=avg_price,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=unrealized_pnl_percent,
                side="long" if quantity > 0 else "short",
            )

        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None

    async def get_positions(self) -> List[PositionData]:
        """
        Get all current positions.

        Returns:
            List of PositionData objects
        """
        try:
            positions_data = await self._make_request("GET", "/account/positions")

            if not positions_data:
                return []

            positions = []
            for pos in positions_data:
                symbol = pos.get("symbol", "")
                quantity = float(pos.get("quantity", 0))

                if quantity == 0:
                    continue

                avg_price = float(pos.get("avg_cost", 0))
                current_price = float(pos.get("current_price", 0))
                market_value = float(pos.get("market_value", 0))
                unrealized_pnl = float(pos.get("unrealized_pnl", 0))
                unrealized_pnl_percent = (
                    (unrealized_pnl / (avg_price * quantity) * 100)
                    if avg_price * quantity > 0
                    else 0
                )

                positions.append(
                    PositionData(
                        symbol=symbol,
                        quantity=quantity,
                        avg_price=avg_price,
                        current_price=current_price,
                        market_value=market_value,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_pnl_percent=unrealized_pnl_percent,
                        side="long" if quantity > 0 else "short",
                    )
                )

            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    async def get_account(self) -> AccountData:
        """
        Get account information.

        Returns:
            AccountData with account details
        """
        try:
            account_data = await self._make_request("GET", "/account")

            if not account_data:
                return AccountData(
                    account_id=self.account_id or "unknown",
                    cash=0,
                    portfolio_value=0,
                )

            cash = float(account_data.get("cash_balance", 0))
            portfolio_value = float(account_data.get("total_value", 0))
            buying_power = float(account_data.get("buying_power", cash))

            return AccountData(
                account_id=account_data.get("account_id", self.account_id or "unknown"),
                cash=cash,
                portfolio_value=portfolio_value,
                buying_power=buying_power,
                equity=portfolio_value,
            )

        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return AccountData(
                account_id=self.account_id or "unknown",
                cash=0,
                portfolio_value=0,
            )

    def convert_currency(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate: Optional[float] = None,
    ) -> float:
        """
        Convert amount between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate: Optional exchange rate (if not provided, uses 1:1 for same currency)

        Returns:
            Converted amount
        """
        if from_currency == to_currency:
            return amount

        if rate is None:
            # If rate not provided, return original amount (should fetch rate separately)
            logger.warning(
                f"No exchange rate provided for {from_currency} -> {to_currency}"
            )
            return amount

        return amount * rate

    def format_currency(self, amount: float, currency: str) -> str:
        """
        Format amount with currency symbol.

        Args:
            amount: Amount to format
            currency: Currency code (USD, NGN)

        Returns:
            Formatted string (e.g., "$1,234.56", "₦1,234,567.89")
        """
        currency_symbols = {
            "USD": "$",
            "NGN": "₦",
        }

        symbol = currency_symbols.get(currency, currency)

        if currency == "NGN":
            # Nigerian Naira uses 2 decimal places
            return f"{symbol}{amount:,.2f}"
        else:
            # USD and others
            return f"{symbol}{amount:,.2f}"

    def __repr__(self) -> str:
        return (
            f"TroveBrokerService(sandbox={self.sandbox}, "
            f"account={self.account_id}, currency={self.default_currency})"
        )


# Import asyncio at the module level for rate limiting
import asyncio