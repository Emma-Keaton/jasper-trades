"""
Exness REST API Service

Official Exness broker integration via REST API.
Works on both Windows (local) and Linux (cloud hosting).

API Documentation: https://api.exness.com/docs/

Features:
- Account management (balance, equity, margin)
- Trading operations (market orders, pending orders)
- Historical data sync
- Withdrawal requests (via separate withdrawal endpoint)

Authentication:
- Uses API keys from settings (encrypted in database)
- OAuth 2.0 for account linking
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog
import httpx
import hashlib
import hmac
import time

logger = structlog.get_logger(__name__)


# Exness API Endpoints
EXNESS_API_BASE = "https://api.exness.com"
EXNESS_SANDBOX_BASE = "https://api-sandbox.exness.com"


class ExnessService:
    """Exness REST API integration service."""

    def __init__(self, api_key: str = None, secret_key: str = None, sandbox: bool = False):
        """
        Initialize Exness service.

        Args:
            api_key: Exness API key (from settings)
            secret_key: Exness API secret (from settings)
            sandbox: Use sandbox/testnet environment
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = EXNESS_SANDBOX_BASE if sandbox else EXNESS_API_BASE
        self.connected = False
        self.account_info: Optional[Dict] = None

    def _generate_signature(self, timestamp: int) -> str:
        """Generate HMAC signature for API request."""
        if not self.secret_key:
            return ""

        message = f"{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest().upper()
        return signature

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers with authentication."""
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-Exness-API-KEY": self.api_key or "",
            "X-Exness-API-TIMESTAMP": str(timestamp),
            "X-Exness-API-SIGNATURE": signature,
        }
        return headers

    async def authenticate(self) -> bool:
        """
        Test API key authentication.

        Returns:
            bool: True if authentication successful
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/user/profile",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    self.connected = True
                    logger.info("Exness API authentication successful")
                    return True
                else:
                    logger.error(f"Exness API auth failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Exness API connection error: {e}")
            return False

    async def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get account information.

        Returns:
            Account info dict or None
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/account/std",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    accounts = data.get("accounts", [])
                    if accounts:
                        # Return first account (can be extended for multi-account)
                        acc = accounts[0]
                        self.account_info = {
                            "account_id": acc.get("id"),
                            "name": acc.get("name"),
                            "balance": acc.get("balance", 0.0),
                            "equity": acc.get("equity", 0.0),
                            "margin": acc.get("margin", 0.0),
                            "free_margin": acc.get("free_margin", 0.0),
                            "profit": acc.get("profit", 0.0),
                            "currency": acc.get("currency", "USD"),
                            "leverage": acc.get("leverage", 100),
                            "type": acc.get("type"),  # "standard", "raw", etc.
                        }
                        return self.account_info

                logger.error(f"Failed to get account info: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Get account info error: {e}")
            return None

    async def get_balance(self) -> Optional[float]:
        """Get current account balance."""
        info = await self.get_account_info()
        return info.get("balance") if info else None

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/order/std/positions",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    positions = data.get("positions", [])
                    return [
                        {
                            "id": pos.get("id"),
                            "symbol": pos.get("symbol"),
                            "type": pos.get("type"),  # "buy" or "sell"
                            "volume": pos.get("volume"),
                            "price_open": pos.get("price_open"),
                            "price_current": pos.get("price_current"),
                            "sl": pos.get("stop_loss"),
                            "tp": pos.get("take_profit"),
                            "profit": pos.get("profit"),
                            "swap": pos.get("swap"),
                        }
                        for pos in positions
                    ]

                logger.error(f"Get positions failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/order/std/pending",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    orders = data.get("orders", [])
                    return [
                        {
                            "id": order.get("id"),
                            "symbol": order.get("symbol"),
                            "type": order.get("type"),
                            "volume": order.get("volume"),
                            "price_open": order.get("price_open"),
                            "sl": order.get("stop_loss"),
                            "tp": order.get("take_profit"),
                        }
                        for order in orders
                    ]

                return []

        except Exception as e:
            logger.error(f"Get orders error: {e}")
            return []

    async def market_order(
        self,
        symbol: str,
        type: str,
        volume: float,
        sl: float = None,
        tp: float = None,
        comment: str = "Jasper Trades"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute market order.

        Args:
            symbol: Trading symbol (e.g., "eurusd")
            type: "buy" or "sell"
            volume: Lot size
            sl: Stop loss (optional)
            tp: Take profit (optional)
            comment: Order comment

        Returns:
            Order result dict or None
        """
        try:
            payload = {
                "symbol": symbol.lower(),
                "type": type.lower(),
                "volume": volume,
                "comment": comment,
            }

            if sl:
                payload["stop_loss"] = sl
            if tp:
                payload["take_profit"] = tp

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/order/std/market",
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.info(f"Exness order executed: {type} {volume} {symbol}")
                    return {
                        "success": True,
                        "id": data.get("id"),
                        "symbol": data.get("symbol"),
                        "type": data.get("type"),
                        "volume": data.get("volume"),
                        "price": data.get("price"),
                        "profit": data.get("profit", 0.0),
                    }
                else:
                    error_data = response.json() if response.content else {}
                    logger.error(f"Exness order failed: {response.status_code} - {error_data}")
                    return {
                        "success": False,
                        "error": error_data.get("message", "Unknown error"),
                        "status_code": response.status_code,
                    }

        except Exception as e:
            logger.error(f"Market order error: {e}")
            return {"success": False, "error": str(e)}

    async def buy(
        self,
        symbol: str,
        volume: float,
        sl: float = None,
        tp: float = None,
        comment: str = "Jasper Trades"
    ) -> Optional[Dict[str, Any]]:
        """Execute market buy order."""
        return await self.market_order(symbol, "buy", volume, sl, tp, comment)

    async def sell(
        self,
        symbol: str,
        volume: float,
        sl: float = None,
        tp: float = None,
        comment: str = "Jasper Trades"
    ) -> Optional[Dict[str, Any]]:
        """Execute market sell order."""
        return await self.market_order(symbol, "sell", volume, sl, tp, comment)

    async def close_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Close a position by ID."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{self.base_url}/order/std/positions/{position_id}",
                    headers=self._get_headers()
                )

                if response.status_code in [200, 204]:
                    logger.info(f"Position {position_id} closed")
                    return {"success": True, "position_id": position_id}
                else:
                    error_data = response.json() if response.content else {}
                    logger.error(f"Close position failed: {response.status_code}")
                    return {
                        "success": False,
                        "error": error_data.get("message", "Failed to close"),
                    }

        except Exception as e:
            logger.error(f"Close position error: {e}")
            return {"success": False, "error": str(e)}

    async def get_historical_orders(
        self,
        from_date: datetime,
        to_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get historical orders within date range."""
        if to_date is None:
            to_date = datetime.now()

        try:
            params = {
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/order/std/history",
                    params=params,
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    orders = data.get("orders", [])
                    return [
                        {
                            "id": order.get("id"),
                            "symbol": order.get("symbol"),
                            "type": order.get("type"),
                            "volume": order.get("volume"),
                            "price_open": order.get("price_open"),
                            "price_close": order.get("price_close"),
                            "profit": order.get("profit"),
                            "time": order.get("time"),
                        }
                        for order in orders
                    ]

                return []

        except Exception as e:
            logger.error(f"Get historical orders error: {e}")
            return []

    async def get_symbols(self) -> List[Dict[str, Any]]:
        """Get list of available trading symbols."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/instruments",
                    headers=self._get_headers()
                )

                if response.status_code == 200:
                    data = response.json()
                    instruments = data.get("instruments", [])
                    return [
                        {
                            "symbol": inst.get("symbol"),
                            "name": inst.get("name"),
                            "type": inst.get("type"),  # "forex", "metal", "crypto", etc.
                            "min_volume": inst.get("min_volume"),
                            "max_volume": inst.get("max_volume"),
                            "step": inst.get("volume_step"),
                            "spread": inst.get("spread"),
                        }
                        for inst in instruments
                    ]

                return []

        except Exception as e:
            logger.error(f"Get symbols error: {e}")
            return []

    async def request_withdrawal(
        self,
        amount: float,
        method: str = "usdt_trc20",
        address: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Request withdrawal to external wallet.

        Note: This is for withdrawing FROM Exness to external wallet.
        For Jasper Trades withdrawal TO Exness, use withdrawal_service.

        Args:
            amount: Withdrawal amount
            method: Withdrawal method ("usdt_trc20", "btc", etc.)
            address: Destination wallet address

        Returns:
            Withdrawal result dict
        """
        try:
            payload = {
                "currency": "USDT",
                "amount": amount,
                "method": method,
            }

            if address:
                payload["address"] = address

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/withdrawal",
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.info(f"Exness withdrawal requested: {amount} USDT")
                    return {
                        "success": True,
                        "withdrawal_id": data.get("id"),
                        "amount": amount,
                        "method": method,
                        "status": data.get("status", "pending"),
                    }
                else:
                    error_data = response.json() if response.content else {}
                    logger.error(f"Withdrawal request failed: {response.status_code}")
                    return {
                        "success": False,
                        "error": error_data.get("message", "Withdrawal failed"),
                    }

        except Exception as e:
            logger.error(f"Withdrawal request error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
_exness_service: Optional[ExnessService] = None


def get_exness_service(
    api_key: str = None,
    secret_key: str = None,
    sandbox: bool = False
) -> ExnessService:
    """Get or create Exness service instance."""
    global _exness_service
    if _exness_service is None:
        _exness_service = ExnessService(api_key, secret_key, sandbox)
    return _exness_service