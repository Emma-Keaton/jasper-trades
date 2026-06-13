"""
Pydantic schemas for Trove API responses.

Used for request/response validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Market Data Schemas ============

class MarketQuote(BaseModel):
    """Real-time market quote for a symbol."""
    symbol: str
    bid: float
    ask: float
    last_price: float
    volume: int
    currency: str = "USD"
    market: str = "US"  # "US" or "NGX"
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "bid": 175.20,
                "ask": 175.25,
                "last_price": 175.23,
                "volume": 1250000,
                "currency": "USD",
                "market": "US",
                "timestamp": "2026-06-11T14:35:00Z",
            }
        }


class MarketStatus(BaseModel):
    """Market hours status for US and NGX markets."""
    us_market_open: bool = False
    us_next_open: Optional[str] = None
    us_next_close: Optional[str] = None
    ngx_market_open: bool = False
    ngx_next_open: Optional[str] = None
    ngx_next_close: Optional[str] = None
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "us_market_open": True,
                "us_next_open": None,
                "us_next_close": "2026-06-11T20:00:00Z",
                "ngx_market_open": False,
                "ngx_next_open": "2026-06-12T09:00:00Z",
                "ngx_next_close": None,
                "timestamp": "2026-06-11T14:35:00Z",
            }
        }


class ForexRate(BaseModel):
    """Currency exchange rate."""
    from_currency: str
    to_currency: str
    rate: float
    bid: float
    ask: float
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "from_currency": "NGN",
                "to_currency": "USD",
                "rate": 0.00065,
                "bid": 0.00064,
                "ask": 0.00066,
                "timestamp": "2026-06-11T14:35:00Z",
            }
        }


# ============ Account Schemas ============

class AccountInfo(BaseModel):
    """Account information."""
    account_id: str
    cash_balance: float
    total_value: float
    buying_power: float
    currency: str = "USD"
    account_type: str = "individual"
    status: str = "active"

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": "TRV-123456",
                "cash_balance": 50000.00,
                "total_value": 125000.00,
                "buying_power": 48000.00,
                "currency": "USD",
                "account_type": "individual",
                "status": "active",
            }
        }


class Position(BaseModel):
    """Position in a symbol."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    currency: str = "USD"
    side: str = "long"  # "long" or "short"

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "quantity": 100.0,
                "avg_cost": 165.50,
                "current_price": 175.23,
                "market_value": 17523.00,
                "unrealized_pnl": 973.00,
                "unrealized_pnl_percent": 5.88,
                "currency": "USD",
                "side": "long",
            }
        }


# ============ Order Schemas ============

class OrderRequest(BaseModel):
    """Order submission request."""
    account_id: str
    symbol: str
    action: str  # "BUY" or "SELL"
    order_type: str = "market"  # "market", "limit", "stop"
    quantity: Optional[float] = None
    amount: Optional[float] = None  # For fractional trading
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"  # "day", "gtc", "ioc"
    client_order_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "account_id": "TRV-123456",
                "symbol": "AAPL",
                "action": "BUY",
                "order_type": "market",
                "quantity": 10.0,
                "time_in_force": "day",
            }
        }


class OrderResponse(BaseModel):
    """Order submission response."""
    order_id: str
    symbol: str
    action: str
    order_type: str
    quantity: Optional[float] = None
    amount: Optional[float] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str
    status: str  # "pending", "submitted", "filled", "cancelled", "rejected"
    filled_quantity: float = 0
    filled_price: Optional[float] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "ORD-789012",
                "symbol": "AAPL",
                "action": "BUY",
                "order_type": "market",
                "quantity": 10.0,
                "time_in_force": "day",
                "status": "submitted",
                "filled_quantity": 0,
                "filled_price": None,
                "created_at": "2026-06-11T14:35:00Z",
                "updated_at": None,
            }
        }


class OrderStatus(BaseModel):
    """Order status response."""
    order_id: str
    symbol: str
    side: str
    quantity: float
    amount: Optional[float] = None
    status: str
    filled_quantity: float
    filled_price: Optional[float] = None
    order_type: str
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "ORD-789012",
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 10.0,
                "status": "filled",
                "filled_quantity": 10.0,
                "filled_price": 175.25,
                "order_type": "market",
                "created_at": "2026-06-11T14:35:00Z",
                "updated_at": "2026-06-11T14:35:02Z",
            }
        }


# ============ Webhook Schemas ============

class TroveWebhookPayload(BaseModel):
    """Trove webhook event payload."""
    event: str  # "ORDER_FILLED", "ORDER_REJECTED", "WALLET_FUNDED", etc.
    data: Dict[str, Any]
    timestamp: str
    signature: Optional[str] = None  # Webhook signature for verification

    class Config:
        json_schema_extra = {
            "example": {
                "event": "ORDER_FILLED",
                "data": {
                    "order_id": "ORD-789012",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "filled_quantity": 10.0,
                    "filled_price": 175.25,
                    "commission": 0.005,
                },
                "timestamp": "2026-06-11T14:35:02Z",
                "signature": "sha256=abc123...",
            }
        }


class WebhookEventTypes:
    """Constants for Trove webhook event types."""
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    WALLET_FUNDED = "WALLET_FUNDED"
    WITHDRAWAL_COMPLETED = "WITHDRAWAL_COMPLETED"
    POSITION_UPDATED = "POSITION_UPDATED"
    ACCOUNT_UPDATED = "ACCOUNT_UPDATED"


# ============ Settings Schemas ============

class TroveSettingsRequest(BaseModel):
    """Trove settings configuration request."""
    trove_api_key: str
    trove_base_url: Optional[str] = None
    trove_enabled: bool = False
    trove_sandbox: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "trove_api_key": "trv_sk_abc123...",
                "trove_base_url": "https://sandbox.api.trovefinance.com/v1",
                "trove_enabled": True,
                "trove_sandbox": True,
            }
        }


class TroveSettingsResponse(BaseModel):
    """Trove settings response (excludes sensitive API key)."""
    trove_enabled: bool
    trove_base_url: Optional[str]
    trove_sandbox: bool
    trove_account_id: Optional[str]
    is_connected: bool

    class Config:
        json_schema_extra = {
            "example": {
                "trove_enabled": True,
                "trove_base_url": "https://sandbox.api.trovefinance.com/v1",
                "trove_sandbox": True,
                "trove_account_id": "TRV-123456",
                "is_connected": True,
            }
        }


class CurrencyPreferenceRequest(BaseModel):
    """Currency preference update request."""
    default_currency: str = "USD"  # "USD" or "NGN"
    currency_conversion_enabled: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "default_currency": "NGN",
                "currency_conversion_enabled": True,
            }
        }


# ============ Conversion Schemas ============

class CurrencyConversionRequest(BaseModel):
    """Currency conversion request."""
    amount: float
    from_currency: str
    to_currency: str

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 1000000,
                "from_currency": "NGN",
                "to_currency": "USD",
            }
        }


class CurrencyConversionResponse(BaseModel):
    """Currency conversion response."""
    amount: float
    from_currency: str
    to_currency: str
    converted_amount: float
    exchange_rate: float
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 1000000,
                "from_currency": "NGN",
                "to_currency": "USD",
                "converted_amount": 650.0,
                "exchange_rate": 0.00065,
                "timestamp": "2026-06-11T14:35:00Z",
            }
        }