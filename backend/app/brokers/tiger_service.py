"""
Tiger OpenAPI Broker Service - LIVE ONLY.

Handles live execution of Chinese A-shares (via Stock Connect) and US stocks
using each device's own funded Tiger account. Paper trading is intentionally
NOT supported here - all paper orders go through the Universal Paper Trading
engine (app.services.paper_trading_service).

Credentials are stored per-device (encrypted) on DeviceSettings and loaded at
execution time, so every tenant trades with their own funded account.

Tiger OpenAPI docs: https://quant.itigerup.com/openapi/
Python SDK: pip install tigeropen
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import (
    AccountData,
    BaseBrokerService,
    OrderResult,
    PositionData,
)

logger = structlog.get_logger(__name__)


def _is_chinese_symbol(symbol: str) -> bool:
    """True for 6-digit A/B-share codes (600xxx, 000xxx, 300xxx, 900xxx, 200xxx)."""
    return symbol.isdigit() and len(symbol) == 6


def normalize_tiger_symbol(symbol: str) -> str:
    """Convert a 6-digit CN code to Tiger's format (600000.SH / 000001.SZ)."""
    if not _is_chinese_symbol(symbol):
        return symbol.upper()
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


class TigerBrokerService(BaseBrokerService):
    """
    Live broker for Chinese A-shares and US stocks via a device's funded Tiger account.

    Not thread-safe with other Tiger devices by design: the tigeropen SDK keeps
    credentials in a process-global config, so all SDK calls are serialized behind
    a module lock to guarantee each request uses the correct tenant's keys.
    """

    # Kept for BaseBrokerService sanity; Tiger never paper-trades.
    def __init__(
        self,
        tiger_id: str,
        account: str,
        api_key: str,
        private_key: str,
        name: str = "tiger",
    ):
        super().__init__(name=name, config={})
        self.tiger_id = tiger_id
        self.account = account or tiger_id
        self.api_key = api_key
        self.private_key = private_key
        self.is_paper_trading = False
        self.is_connected = False
        self._client = None
        self._account_info: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # SDK bootstrapping (global config guarded by a module lock)
    # ------------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self):
        from tigeropen.tiger_open_config import TigerOpenClientConfig
        from tigeropen.trade.trade_client import TradeClient

        # SDK 3.x authenticates with the developer's RSA private key content
        # (the old dict-based config_utils API no longer exists). Keep the PEM
        # body without the BEGIN/END markers, mirroring the SDK's read_private_key.
        private_key = str(self.private_key or "").strip()
        if private_key.startswith("-----BEGIN"):
            private_key = (
                private_key.replace("-----BEGIN RSA PRIVATE KEY-----", "")
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END RSA PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replace("\n", "")
                .strip()
            )
        config = TigerOpenClientConfig(enable_dynamic_domain=True)
        config.private_key = private_key
        config.tiger_id = str(self.tiger_id or "")
        config.account = str(self.account or "")
        return TradeClient(client_config=config)

    def _locked(self, thunk):
        with _TIGER_CONFIG_LOCK:
            return thunk()

    async def _run(self, thunk):
        return await asyncio.to_thread(self._locked, thunk)

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        try:
            account_info = await self._run(lambda: self._fetch_assets())
            self._account_info = account_info
            self.is_connected = account_info is not None
            return self.is_connected
        except Exception as e:  # noqa: BLE001
            logger.error("Tiger connection failed", error=str(e), tiger_id=self.tiger_id)
            self.is_connected = False
            return False

    async def disconnect(self):
        self.is_connected = False
        self._client = None

    def _fetch_assets(self) -> Optional[Dict[str, Any]]:
        client = self.client
        assets = client.get_assets(account=self.account)
        if assets:
            asset = assets[0]
            return {
                "account_id": getattr(asset, "account", self.account),
                "cash_balance": getattr(asset, "cash_balance", 0.0) or 0.0,
                "net_liquidation": getattr(asset, "net_liquidation", 0.0) or 0.0,
                "available_funds": getattr(asset, "available_funds", None),
                "market_value": getattr(asset, "market_value", 0.0) or 0.0,
            }
        return None

    async def get_account(self) -> AccountData:
        info = await self._run(lambda: self._fetch_assets())
        if info is None:
            raise RuntimeError("Could not load Tiger account data")
        net = float(info.get("net_liquidation") or 0.0)
        cash = float(info.get("cash_balance") or 0.0)
        return AccountData(
            account_id=str(info.get("account_id") or self.account),
            cash=cash,
            portfolio_value=net,
            equity=net,
            buying_power=float(info.get("available_funds") or cash),
        )

    async def get_clock(self) -> Dict[str, Any]:
        market = "CN" if self._cn else "US"
        try:
            from tigeropen.common.consts import Market
            from tigeropen.quote.quote_client import QuoteClient

            states = await self._run(
                lambda: QuoteClient().get_market_status(market=getattr(Market, market))
            )
            ms = next((m for m in (states or []) if str(getattr(m, "market", "")) == market), None)
            state = str(getattr(ms, "status", "") or "UNKNOWN")
            return {
                "is_open": bool(state.upper() in ("TRADING", "PRE_OPEN", "PREOPEN", "T1")),
                "market": market,
                "state": state,
                "timezone": "Asia/Shanghai" if self._cn else "America/New_York",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("Tiger market clock unavailable", error=str(e))
            return {"is_open": False, "state": "unknown", "timestamp": datetime.now(timezone.utc).isoformat()}

    def _market_state(self, market) -> str:
        from tigeropen.quote.quote_client import QuoteClient

        try:
            states = QuoteClient().get_market_status(market=market)
        except Exception as e:  # noqa: BLE001
            logger.debug("Tiger market state unavailable", error=str(e))
            return "UNKNOWN"
        ms = next(
            (m for m in (states or []) if str(getattr(m, "market", "")) == str(getattr(market, "value", market))),
            None,
        )
        return str(getattr(ms, "status", "") or "UNKNOWN")

    @property
    def _cn(self) -> bool:
        return bool(self.config.get("asset_class") == "cn")

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        try:
            order_id_int = int(order_id)
        except (TypeError, ValueError):
            return {"order_id": order_id, "status": "unknown", "found": False}
        try:
            order = await self._run(lambda: self.client.get_order(order_id=order_id_int))
        except Exception as e:  # noqa: BLE001
            logger.debug("Tiger order status unavailable", error=str(e))
            return {"order_id": order_id, "status": "unknown", "found": False}
        if order is None:
            return {"order_id": order_id, "status": "unknown", "found": False}
        return {
            "order_id": order_id,
            "status": str(getattr(order, "status", "unknown")),
            "filled_quantity": float(getattr(order, "filled_quantity", 0) or 0),
            "filled_price": float(getattr(order, "avg_filled_price", 0) or 0),
            "found": True,
        }

    # ------------------------------------------------------------------
    # Orders (LIVE ONLY - no paper path)
    # ------------------------------------------------------------------

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
        valid, err = self.validate_order(symbol, side, quantity, order_type)
        if not valid:
            return OrderResult(success=False, message=err)

        from tigeropen.common.consts import OrderAction, OrderType as TigerOrderType
        from tigeropen.common.consts import SecType
        from tigeropen.trade.domain.order import Order

        symbol = normalize_tiger_symbol(symbol)
        action = OrderAction.BUY if side.lower() == "buy" else OrderAction.SELL

        if order_type in ("market", "market_on_close", "market_on_open"):
            tiger_type = TigerOrderType.MKT
        elif order_type in ("limit", "limit_on_close", "limit_on_open"):
            tiger_type = TigerOrderType.LMT
        elif order_type == "stop":
            tiger_type = TigerOrderType.STP
        elif order_type == "stop_limit":
            tiger_type = TigerOrderType.STP_LMT
        else:
            tiger_type = TigerOrderType.MKT

        order = Order(
            symbol=symbol,
            sec_type=SecType.STOCK,
            action=action,
            order_type=tiger_type,
            total_quantity=int(quantity),
            currency="CNY" if self._cn else "USD",
        )
        if limit_price:
            order.limit_price = limit_price
        if stop_price:
            order.aux_price = stop_price

        try:
            order_id = await self._run(lambda: self.client.place_order(order))
            if not order_id:
                return OrderResult(success=False, message="Tiger returned no order id")
            status = await self.get_order_status(order_id)
            return OrderResult(
                success=True,
                order_id=str(order_id),
                status=status.get("status", "submitted"),
                filled_quantity=float(status.get("filled_quantity", 0)),
                filled_price=float(status.get("filled_price") or limit_price or 0),
                message=f"Submitted {side} {quantity} {symbol} to Tiger",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Tiger order failed", error=str(e), symbol=symbol, side=side)
            return OrderResult(success=False, message=f"Tiger order failed: {str(e)}")

    async def cancel_order(self, order_id: str) -> bool:
        try:
            result = await self._run(lambda: self.client.cancel_order(order_id))
            return bool(result)
        except Exception as e:  # noqa: BLE001
            logger.error("Tiger cancel failed", error=str(e), order_id=order_id)
            return False

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def get_position(self, symbol: str) -> Optional[PositionData]:
        for pos in await self.get_positions():
            if pos.symbol == symbol:
                return pos
        return None

    async def get_positions(self) -> List[PositionData]:
        try:
            positions = await self._run(lambda: self.client.get_positions(account=self.account))
        except Exception as e:  # noqa: BLE001
            logger.error("Tiger positions failed", error=str(e))
            return []

        result: List[PositionData] = []
        for p in positions:
            symbol = str(getattr(p, "symbol", ""))
            qty = float(getattr(p, "quantity", 0) or 0)
            avg = float(getattr(p, "average_cost", 0) or 0)
            cur = float(getattr(p, "market_price", 0) or 0)
            if not symbol or qty == 0:
                continue
            side = "long" if qty > 0 else "short"
            result.append(
                PositionData(
                    symbol=symbol,
                    quantity=abs(qty),
                    avg_price=abs(avg),
                    current_price=cur,
                    market_value=abs(qty) * cur,
                    unrealized_pnl=float(getattr(p, "unrealized_pnl", 0) or 0),
                    unrealized_pnl_percent=float(getattr(p, "unrealized_pnl_ratio", 0) or 0),
                    side=side,
                )
            )
        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected,
            "paper_trading": False,
            "account_id": self.account,
            "cn_supported": True,
            "us_supported": True,
        }


# ---------------------------------------------------------------------------
# Per-device factory + high-level helper
# ---------------------------------------------------------------------------

_TIGER_CONFIG_LOCK = threading.Lock()


async def load_tiger_client(db: AsyncSession, device_id: str) -> Optional[TigerBrokerService]:
    """Build a live TigerBrokerService from the device's stored (decrypted) creds."""
    from app.models import DeviceSettings
    from app.services.encryption import EncryptionHelper

    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    ds = res.scalar_one_or_none()
    if ds is None or not ds.tiger_enabled:
        return None
    if not (ds.tiger_id and ds.tiger_api_key and ds.tiger_private_key):
        return None

    encryption = EncryptionHelper()
    return TigerBrokerService(
        tiger_id=ds.tiger_id,
        account=ds.tiger_id,
        api_key=encryption.decrypt(ds.tiger_api_key) or "",
        private_key=encryption.decrypt(ds.tiger_private_key) or "",
    )


async def tiger_configured(db: AsyncSession, device_id: str) -> bool:
    """True when the device has valid Tiger live credentials stored and enabled."""
    return await load_tiger_client(db, device_id) is not None


async def place_tiger_live_order(
    db: AsyncSession,
    device_id: str,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    asset_class: str = "stocks",
) -> Dict[str, Any]:
    """
    Place a LIVE order via the device's funded Tiger account.

    Raises RuntimeError if Tiger is not configured; never falls back to paper.
    """
    client = await load_tiger_client(db, device_id)
    if client is None:
        raise RuntimeError(
            "Tiger live trading is not configured for this device. "
            "Add your Tiger OpenAPI credentials in Settings > Connections."
        )

    client.config["asset_class"] = "cn" if asset_class == "cn" else "stocks"
    if not client.is_connected:
        await client.connect()
        if not client.is_connected:
            raise RuntimeError("Tiger connection failed - check your API credentials")

    result = await client.submit_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
    )
    if not result.success:
        raise RuntimeError(result.message or "Tiger order failed")

    return {
        "status": "success",
        "mode": "live",
        "broker": "tiger",
        "symbol": normalize_tiger_symbol(symbol),
        "side": side,
        "quantity": quantity,
        "order_id": result.order_id,
        "filled_price": result.filled_price,
        "message": result.message,
    }
