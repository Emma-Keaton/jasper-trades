"""
Base Broker Service - Abstract interface for all broker implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class OrderResult:
    """Result of an order submission."""

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
    """Position data from broker."""

    def __init__(
        self,
        symbol: str,
        quantity: float,
        avg_price: float,
        current_price: Optional[float] = None,
        market_value: Optional[float] = None,
        unrealized_pnl: Optional[float] = None,
        unrealized_pnl_percent: Optional[float] = None,
        side: str = "long",
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.current_price = current_price
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.unrealized_pnl_percent = unrealized_pnl_percent
        self.side = side

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "side": self.side,
        }


class AccountData:
    """Account data from broker."""

    def __init__(
        self,
        account_id: str,
        cash: float,
        portfolio_value: float,
        buying_power: Optional[float] = None,
        equity: Optional[float] = None,
        last_equity: Optional[float] = None,
        day_trading_buying_power: Optional[float] = None,
    ):
        self.account_id = account_id
        self.cash = cash
        self.portfolio_value = portfolio_value
        self.buying_power = buying_power
        self.equity = equity
        self.last_equity = last_equity
        self.day_trading_buying_power = day_trading_buying_power

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "buying_power": self.buying_power,
            "equity": self.equity,
            "last_equity": self.last_equity,
            "day_trading_buying_power": self.day_trading_buying_power,
        }


class BaseBrokerService(ABC):
    """
    Abstract base class for all broker services.

    Defines the interface that all broker implementations must follow.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_connected = False
        self.is_paper_trading = True
        logger.info(f"Initialized {name} broker service")

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker.

        Returns:
            True if connection successful, False otherwise
        """
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
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Submit an order to the broker.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "BTC/USD")
            side: "buy" or "sell"
            quantity: Number of shares/contracts
            order_type: "market", "limit", "stop", "stop_limit"
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: "day", "gtc", "ioc", "opg"
            client_order_id: Optional client order ID

        Returns:
            OrderResult with order details
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Broker order ID to cancel

        Returns:
            True if cancellation successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[PositionData]:
        """
        Get current position for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            PositionData if position exists, None otherwise
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[PositionData]:
        """
        Get all current positions.

        Returns:
            List of PositionData objects
        """
        pass

    @abstractmethod
    async def get_account(self) -> AccountData:
        """
        Get account information.

        Returns:
            AccountData with account details
        """
        pass

    @abstractmethod
    async def get_clock(self) -> Dict[str, Any]:
        """
        Get market clock/market hours status.

        Returns:
            Dict with is_open, next_open, next_close, timestamp
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order.

        Args:
            order_id: Broker order ID

        Returns:
            Dict with order status details
        """
        pass

    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate order parameters before submission.

        Returns:
            (is_valid, error_message)
        """
        if not symbol or not isinstance(symbol, str):
            return False, "Invalid symbol"

        if side not in ["buy", "sell"]:
            return False, "Side must be 'buy' or 'sell'"

        if quantity <= 0:
            return False, "Quantity must be positive"

        if order_type not in ["market", "limit", "stop", "stop_limit"]:
            return False, "Invalid order type"

        return True, None

    def map_side(self, side: str) -> str:
        """Map 'buy'/'sell' to broker-specific format."""
        return side.upper()

    def map_order_type(self, order_type: str) -> str:
        """Map order type to broker-specific format."""
        type_mapping = {
            "market": "market",
            "limit": "limit",
            "stop": "stop",
            "stop_limit": "stop_limit",
        }
        return type_mapping.get(order_type, order_type)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, paper={self.is_paper_trading})"