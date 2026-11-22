"""
MetaTrader 5 Bridge Broker Service (with MT4 fallback).

Replaces cTrader as the real/demo execution venue for forex, CFDs, metals
and indices. Connection priority:

1. Native ``MetaTrader5`` Python package (Windows, terminal running) —
   used automatically when importable and the terminal is reachable.
2. HTTP bridge gateway (``MT5_BRIDGE_URL`` / ``MT4_BRIDGE_URL`` env) —
   a cloud VPS or EA bridge running the terminal. MT4 accounts fall back
   to the MT4 gateway when the MT5 one rejects the login.
3. Sandbox demo book — when the account is a DEMO account and no live
   transport is reachable, orders fill against an internal simulated book
   ("sandbox demo mode in MT brokers is used when they are connected").

A demo account is flagged ``is_paper_trading = True`` so the trade gate
never treats it as live money. A live account without a reachable
transport refuses to connect (fail-closed).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.brokers.base import (
    BaseBrokerService,
    OrderResult,
    PositionData,
    AccountData,
)

logger = structlog.get_logger(__name__)

try:  # Optional native transport (Windows only).
    import MetaTrader5 as mt5  # type: ignore

    NATIVE_MT5_AVAILABLE = True
except Exception:  # noqa: BLE001
    mt5 = None  # type: ignore
    NATIVE_MT5_AVAILABLE = False


class MT5BridgeService(BaseBrokerService):
    """MT5 bridge with MT4 fallback; demo accounts get a sandbox book."""

    def __init__(
        self,
        platform: str = "mt5",
        login: Optional[str] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        broker_name: Optional[str] = None,
        demo: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ):
        platform = (platform or "mt5").lower()
        if platform not in ("mt5", "mt4"):
            platform = "mt5"
        super().__init__(name=platform, config=config or {})
        self.platform = platform
        self.login = str(login) if login else None
        self.password = password
        self.server = server
        self.broker_name = broker_name or server or platform.upper()
        self.demo = bool(demo)
        # Demo accounts are sandbox/paper; live accounts are real money.
        self.is_paper_trading = self.demo

        self.bridge_url = os.environ.get(
            "MT5_BRIDGE_URL" if platform == "mt5" else "MT4_BRIDGE_URL"
        )
        self._transport: Optional[str] = None  # "native" | "bridge" | "sandbox"
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._positions: Dict[str, PositionData] = {}
        self._demo_balance = float((config or {}).get("demo_balance", 100_000.0))

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    async def connect(self) -> bool:
        if not self.login or not self.password or not self.server:
            logger.error("MT5 bridge: login/password/server required")
            return False

        # 1. Native terminal transport.
        if NATIVE_MT5_AVAILABLE and self.platform == "mt5":
            try:
                if mt5.initialize():
                    if mt5.login(int(self.login), password=self.password, server=self.server):
                        self._transport = "native"
                        self.is_connected = True
                        logger.info("MT5 bridge connected via native terminal", login=self.login, server=self.server)
                        return True
                    mt5.shutdown()
            except Exception as e:  # noqa: BLE001
                logger.debug("MT5 native transport unavailable", error=str(e))

        # 2. HTTP bridge gateway.
        if self.bridge_url:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{self.bridge_url.rstrip('/')}/connect",
                        json={
                            "platform": self.platform,
                            "login": self.login,
                            "password": self.password,
                            "server": self.server,
                        },
                    )
                if resp.status_code == 200 and resp.json().get("success"):
                    self._transport = "bridge"
                    self.is_connected = True
                    logger.info("MT5 bridge connected via HTTP bridge", platform=self.platform, server=self.server)
                    return True
            except Exception as e:  # noqa: BLE001
                logger.debug("MT5 bridge transport failed", platform=self.platform, error=str(e))

        # 3. Sandbox demo book — only for demo accounts (fail-closed for live).
        if self.demo:
            self._transport = "sandbox"
            self.is_connected = True
            logger.info(
                "MT5 bridge using sandbox demo book (no live transport)",
                platform=self.platform,
                server=self.server,
            )
            return True

        logger.error("MT5 bridge: live account but no transport reachable (native terminal or MT5_BRIDGE_URL)")
        return False

    async def disconnect(self):
        if self._transport == "native" and NATIVE_MT5_AVAILABLE:
            try:
                mt5.shutdown()
            except Exception:  # noqa: BLE001
                pass
        self._transport = None

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "gtc",
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        valid, err = self.validate_order(symbol, side, quantity, order_type)
        if not valid:
            return OrderResult(success=False, message=err)
        if not self.is_connected:
            return OrderResult(success=False, message="not connected")

        order_id = client_order_id or f"mt5-{uuid.uuid4().hex[:12]}"

        if self._transport in ("native", "bridge"):
            try:
                return await self._submit_remote(symbol, side, quantity, order_type, limit_price, order_id)
            except Exception as e:  # noqa: BLE001
                logger.error("MT5 remote order failed", symbol=symbol, error=str(e))
                return OrderResult(success=False, message=str(e))

        # Sandbox demo book: fill at market (limit/stop approximated at trigger).
        price = limit_price or stop_price or await self._last_price(symbol) or 0.0
        if price <= 0:
            return OrderResult(success=False, message="no price available for sandbox fill")
        signed_qty = quantity if side == "buy" else -quantity
        pos = self._positions.get(symbol)
        if pos is None:
            self._positions[symbol] = PositionData(
                symbol=symbol, quantity=abs(signed_qty), avg_price=price,
                current_price=price, side="long" if signed_qty > 0 else "short",
            )
        else:
            pos.avg_price = (pos.avg_price * pos.quantity + price * abs(signed_qty)) / (pos.quantity + abs(signed_qty))
            pos.quantity += abs(signed_qty)
            pos.side = "long" if signed_qty > 0 else "short"
        self._orders[order_id] = {
            "symbol": symbol, "side": side, "quantity": quantity,
            "price": price, "status": "filled", "time": datetime.utcnow().isoformat(),
        }
        if side == "buy":
            self._demo_balance -= price * quantity
        else:
            self._demo_balance += price * quantity
        return OrderResult(success=True, order_id=order_id, filled_quantity=quantity, filled_price=price)

    async def _submit_remote(self, symbol, side, quantity, order_type, limit_price, order_id) -> OrderResult:
        if self._transport == "native":
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return OrderResult(success=False, message=f"symbol {symbol} not found")
            price = tick.ask if side == "buy" else tick.bid
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(quantity),
                "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "jasper-auto",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(success=False, message=f"mt5 error {getattr(result, 'retcode', None)}")
            return OrderResult(
                success=True, order_id=str(result.order),
                filled_quantity=result.volume, filled_price=result.price,
            )
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.bridge_url.rstrip('/')}/order",
                json={
                    "platform": self.platform, "login": self.login, "server": self.server,
                    "symbol": symbol, "side": side, "volume": quantity,
                    "order_type": order_type, "limit_price": limit_price, "client_order_id": order_id,
                },
            )
        data = resp.json()
        return OrderResult(
            success=bool(data.get("success")), order_id=str(data.get("order_id") or order_id),
            message=data.get("message"), filled_quantity=float(data.get("filled_quantity") or 0),
            filled_price=data.get("filled_price"),
        )

        self.is_connected = False


    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            return True
        if self._transport == "native" and NATIVE_MT5_AVAILABLE:
            try:
                res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_id)})
                return bool(res.retcode == mt5.TRADE_RETCODE_DONE)
            except Exception:  # noqa: BLE001
                return False
        return False

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return self._orders.get(order_id, {"order_id": order_id, "status": "unknown"})

    # ------------------------------------------------------------------
    # Positions / account
    # ------------------------------------------------------------------
    async def get_position(self, symbol: str) -> Optional[PositionData]:
        if self._transport == "native" and NATIVE_MT5_AVAILABLE:
            try:
                positions = mt5.positions_get(symbol=symbol) or []
                if positions:
                    p = positions[0]
                    return PositionData(
                        symbol=symbol, quantity=p.volume, avg_price=p.price_open,
                        current_price=p.price_current, unrealized_pnl=p.profit,
                        side="long" if p.type == mt5.POSITION_TYPE_BUY else "short",
                    )
            except Exception:  # noqa: BLE001
                pass
        return self._positions.get(symbol)

    async def get_positions(self) -> List[PositionData]:
        return list(self._positions.values())

    async def get_account(self) -> AccountData:
        if self._transport == "native" and NATIVE_MT5_AVAILABLE:
            try:
                info = mt5.account_info()
                if info is not None:
                    return AccountData(
                        account_id=str(self.login), cash=info.balance - info.profit,
                        portfolio_value=info.equity, buying_power=info.margin_free,
                        equity=info.equity,
                    )
            except Exception:  # noqa: BLE001
                pass
        return AccountData(
            account_id=str(self.login or "demo"),
            cash=self._demo_balance,
            portfolio_value=self._demo_balance,
            buying_power=self._demo_balance,
            equity=self._demo_balance,
        )

    async def get_clock(self) -> Dict[str, Any]:
        now = datetime.utcnow()
        return {"is_open": True, "timestamp": now.isoformat(), "note": "forex/CFD markets ~24/5"}

    async def _last_price(self, symbol: str) -> Optional[float]:
        """Best-effort price for sandbox fills (keyless market data)."""
        try:
            from app.services.unified_market_data import get_unified_market_data

            mv = await get_unified_market_data().get_market_movement(symbol, "crypto")
            return mv.get("price")
        except Exception:  # noqa: BLE001
            return None

    def __repr__(self) -> str:
        return f"MT5BridgeService(platform={self.platform}, server={self.server}, demo={self.demo}, transport={self._transport})"


def get_mt5_bridge(
    platform: str = "mt5",
    login: Optional[str] = None,
    password: Optional[str] = None,
    server: Optional[str] = None,
    broker_name: Optional[str] = None,
    demo: bool = True,
) -> MT5BridgeService:
    """Factory used by the broker registry and the connect API."""
    return MT5BridgeService(
        platform=platform, login=login, password=password,
        server=server, broker_name=broker_name, demo=demo,
    )
