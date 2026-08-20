"""Execution routes: gated paper/live behavior across all 6 routes + Tiger."""
from types import SimpleNamespace

import pytest


@pytest.fixture
def fake_price(monkeypatch):
    """Make ValuationService.get_price return a fixed price (no network)."""
    from app.services.valuation_service import ValuationService

    async def _fake(self, symbol):
        return 10.0

    monkeypatch.setattr(ValuationService, "get_price", _fake)


async def _place_akshare_order(client, **kwargs):
    return await client.post(
        "/api/v1/akshare/order",
        params={
            "symbol": kwargs.get("symbol", "600000"),
            "side": kwargs.get("side", "buy"),
            "quantity": kwargs.get("quantity", 100),
            "order_type": kwargs.get("order_type", "market"),
        },
        headers={"X-Device-ID": kwargs.get("device_id", "dev-1")},
    )


# ---------------------------------------------------------------------------
# /trading/execute
# ---------------------------------------------------------------------------

async def test_execute_paper_success(app_client, fake_price):
    resp = await app_client.post(
        "/api/v1/trading/execute",
        params={"symbol": "BTC", "side": "buy", "quantity": 0.5},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["mode"] == "paper"
    assert body["broker"] == "paper"


async def test_execute_live_blocked_without_broker(app_client, live_device, fake_price):
    resp = await app_client.post(
        "/api/v1/trading/execute",
        params={"symbol": "BTC", "side": "buy", "quantity": 0.5},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 403
    assert "blocked" in resp.json()["detail"]


async def test_execute_live_cn_blocked_without_tiger(app_client, live_device, fake_price):
    resp = await app_client.post(
        "/api/v1/trading/execute",
        params={"symbol": "600000", "side": "buy", "quantity": 100},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 403
    assert "Tiger OpenAPI" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /paper/trade
# ---------------------------------------------------------------------------

async def test_paper_trade_success(app_client):
    resp = await app_client.post(
        "/api/v1/paper/trade",
        json={
            "symbol": "BTC",
            "side": "buy",
            "quantity": 0.05,
            "price": 60000,
            "asset_class": "crypto",
        },
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_paper_trade_invalid_side(app_client):
    resp = await app_client.post(
        "/api/v1/paper/trade",
        json={"symbol": "BTC", "side": "close", "quantity": 0.05, "price": 60000},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 400


async def test_paper_trade_blocked_by_circuit_breaker(app_client):
    from app.services.circuit_breaker import get_circuit_breaker

    get_circuit_breaker().trigger_halt("scheduled maintenance")
    resp = await app_client.post(
        "/api/v1/paper/trade",
        json={"symbol": "BTC", "side": "buy", "quantity": 0.05, "price": 60000},
        headers={"X-Device-ID": "dev-1"},
    )
    get_circuit_breaker().resume_trading()
    assert resp.status_code == 403
    assert "Paper trade blocked" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /trove/order
# ---------------------------------------------------------------------------

async def test_trove_order_paper_success(app_client):
    resp = await app_client.post(
        "/api/v1/trove/order",
        json={"symbol": "AAPL", "side": "buy", "quantity": 2, "order_type": "market", "price": 150.0},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "filled"
    assert body["symbol"] == "AAPL"


async def test_trove_order_live_without_creds_400(app_client, live_device):
    resp = await app_client.post(
        "/api/v1/trove/order",
        json={"symbol": "AAPL", "side": "buy", "quantity": 2, "order_type": "market", "price": 150.0},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 400
    assert "Trove API key not configured" in resp.json()["detail"]


async def test_trove_order_limit_requires_price(app_client):
    resp = await app_client.post(
        "/api/v1/trove/order",
        json={"symbol": "AAPL", "side": "buy", "quantity": 2, "order_type": "limit"},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /akshare/order
# ---------------------------------------------------------------------------

async def test_akshare_order_paper_success(app_client, monkeypatch):
    class FakeAKShare:
        async def submit_order(self, **kwargs):
            return SimpleNamespace(success=True, order_id="ak-1", filled_price=10.0, message="ok", error=None)

    monkeypatch.setattr("app.api.v1.akshare.AKShareBrokerService", FakeAKShare)
    resp = await _place_akshare_order(app_client)
    assert resp.status_code == 200
    assert resp.json()["order_id"] == "ak-1"


async def test_akshare_order_live_blocked(app_client, live_device):
    resp = await _place_akshare_order(app_client)
    assert resp.status_code == 403
    assert "does not support live trading" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /memecoin/trade
# ---------------------------------------------------------------------------

async def test_memecoin_trade_paper_success(app_client):
    resp = await app_client.post(
        "/api/v1/memecoin/trade",
        json={"symbol": "PEPE", "side": "buy", "quantity": 1000, "price": 0.0001},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "paper"
    assert body["success"] is True


async def test_memecoin_trade_live_blocked_without_wallet(app_client, live_device):
    resp = await app_client.post(
        "/api/v1/memecoin/trade",
        json={"symbol": "PEPE", "side": "buy", "quantity": 1000, "price": 0.0001},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 403
    assert "solana_wallet_configured" in resp.json()["detail"]


async def test_memecoin_trade_live_success(app_client, db, live_device, monkeypatch):
    from app.models_ext.crypto_credentials import DeviceCryptoCredential

    db.add(DeviceCryptoCredential(
        device_id="dev-1",
        exchange="solana",
        encrypted_api_key="k",
        encrypted_api_secret="s",
        wallet_address="8xY9abcdefghijklmnop",
    ))
    live_device.jupiter_enabled = True
    await db.commit()

    class FakeSolanaBroker:
        def __init__(self, config=None):
            self.is_connected = False
            self.wallet_address = None

        async def connect(self):
            self.is_connected = True
            return True

        async def submit_order(self, symbol, side, quantity):
            return SimpleNamespace(
                success=True, order_id="sw-123", filled_quantity=quantity, message="swapped", error=None
            )

    monkeypatch.setattr("app.brokers.solana_service.SolanaBrokerService", FakeSolanaBroker)
    resp = await app_client.post(
        "/api/v1/memecoin/trade",
        json={"symbol": "PEPE", "side": "buy", "quantity": 1000, "price": 0.0001},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "live"
    assert body["broker"] == "solana"
    assert body["order_id"] == "sw-123"


# ---------------------------------------------------------------------------
# /tiger/order
# ---------------------------------------------------------------------------

async def test_tiger_order_paper_success(app_client):
    resp = await app_client.post(
        "/api/v1/tiger/order",
        json={"symbol": "AAPL", "side": "buy", "quantity": 2, "order_type": "market", "price": 150.0},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "filled"
    assert body["symbol"] == "AAPL"


async def test_tiger_order_paper_cn_symbol_normalized(app_client):
    resp = await app_client.post(
        "/api/v1/tiger/order",
        json={
            "symbol": "600000",
            "side": "buy",
            "quantity": 100,
            "order_type": "market",
            "price": 10.0,
            "asset_class": "cn",
        },
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "600000.SH"


async def test_tiger_order_live_blocked_without_creds(app_client, live_device):
    resp = await app_client.post(
        "/api/v1/tiger/order",
        json={"symbol": "AAPL", "side": "buy", "quantity": 2, "order_type": "market", "price": 150.0},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 403
    assert "Tiger" in resp.json()["detail"]


async def test_tiger_order_limit_requires_price(app_client):
    resp = await app_client.post(
        "/api/v1/tiger/order",
        json={"symbol": "AAPL", "side": "buy", "quantity": 2, "order_type": "limit"},
        headers={"X-Device-ID": "dev-1"},
    )
    assert resp.status_code == 400
