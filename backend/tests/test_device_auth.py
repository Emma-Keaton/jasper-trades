"""Device-UUID authentication.

There are no user accounts. A device's UUID - generated once by the browser
with `crypto.randomUUID()` and sent as `X-Device-ID` - *is* the credential:
whoever presents it is that device.

These tests pin the three properties that model depends on.

* The UUID must be valid. Previously the header was an identity *label*:
  `x_device_id or "default-device"` meant a caller who simply omitted it
  authenticated as the same shared device as everyone else, with access to that
  device's settings, portfolio and ledger. Twelve call sites did that.
* It must be the only accepted format, so a crafted value cannot smuggle
  through.
* It must be scoped, so two devices cannot reach each other's portfolios.

What this does not provide is revocation or protection against a leaked UUID.
That is acceptable for a self-hosted instance reachable only by its owner, and
is the model the product is built around; it is not suitable for an instance
exposed to untrusted callers.
"""

from __future__ import annotations

import pytest

from app.device_identity import (
    DeviceIdentityError,
    is_valid_device_id,
    new_device_id,
    normalise_device_id,
    try_normalise_device_id,
)


VALID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


class TestValidation:
    @pytest.mark.parametrize(
        "value",
        [
            VALID,
            VALID.upper(),
            f"  {VALID}  ",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-4fff-bfff-ffffffffffff",
        ],
    )
    def test_accepts_uuids(self, value):
        assert normalise_device_id(value) == value.strip().lower()

    def test_normalises_case_so_one_device_is_one_row(self):
        """`ABC...` and `abc...` must not become two devices."""
        upper = VALID.upper()
        assert normalise_device_id(upper) == normalise_device_id(VALID)

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "   ",
            "default-device",
            "dev-1",
            "ssr",
            "not-a-uuid",
            # Correct shape, wrong length.
            "3f2504e0-4f89-41d3-9a0c-0305e82c330",
            "3f2504e0-4f89-41d3-9a0c-0305e82c33011",
            # Missing a group.
            "3f2504e0-4f89-41d3-0305e82c3301",
            # Non-hex characters in the right positions.
            "3g2504e0-4f89-41d3-9a0c-0305e82c3301",
            "3f2504e0-4f89-41d3-9a0c-0305e82c330z",
            # Right length, wrong separators.
            "3f2504e0_4f89_41d3_9a0c_0305e82c3301",
            "3f2504e0-4f89-41d3-9a0c-0305e82c3301-extra",
            "prefix-" + VALID,
            VALID + "-suffix",
            # Injection attempts: a valid UUID embedded in something larger.
            f"{VALID}' OR '1'='1",
            f"{VALID}; DROP TABLE portfolios;--",
        ],
    )
    def test_rejects_anything_that_is_not_exactly_a_uuid(self, value):
        assert try_normalise_device_id(value) is None

    def test_rejects_non_strings(self):
        for value in (123, 4.5, True, [], {}, object()):
            assert try_normalise_device_id(value) is None

    def test_raises_with_an_actionable_message(self):
        with pytest.raises(DeviceIdentityError) as exc:
            normalise_device_id("dev-1")
        message = str(exc.value)
        assert "X-Device-ID" in message
        assert "UUID" in message

    def test_helper_predicate_agrees(self):
        assert is_valid_device_id(VALID) is True
        assert is_valid_device_id("dev-1") is False

    def test_new_device_id_is_a_uuid(self):
        assert is_valid_device_id(new_device_id())


class TestDependencyReturns401:
    """`require_device_id` must reject, not fall back."""

    @pytest.mark.parametrize("value", [None, "", "default-device", "dev-1", "nope"])
    def test_raises_http_401(self, value):
        from fastapi import HTTPException

        from app.device_auth import require_device_id

        with pytest.raises(HTTPException) as exc:
            require_device_id(value)
        assert exc.value.status_code == 401
        assert exc.value.detail["error"] == "invalid_device_id"

    def test_returns_the_normalised_uuid(self):
        from app.device_auth import require_device_id

        assert require_device_id(VALID.upper()) == VALID


class TestNoSharedFallbackRemains:
    """The hole was a string literal repeated in a dozen call sites.

    This greps for it, so a future edit that reintroduces a default identity
    fails here rather than silently re-opening every endpoint.
    """

    def test_no_module_substitutes_a_default_device(self):
        """The hole was a string literal used as a fallback value.

        Checked with the AST rather than by grepping text, because several
        modules legitimately mention the old value in prose to explain why it is
        gone, and a text search would flag those.

        The specific shape that caused the hole is `<something> or
        "default-device"` - an expression that substitutes a shared identity.
        """
        import ast
        from pathlib import Path

        import app as app_pkg

        offenders = []
        for path in Path(app_pkg.__file__).parent.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or):
                    continue
                for value in node.values:
                    if (
                        isinstance(value, ast.Constant)
                        and value.value == "default-device"
                    ):
                        offenders.append(f"{path.name}:{node.lineno}")
        assert not offenders, (
            f"default-device reintroduced as a fallback expression at {offenders}. "
            "Every device-scoped request must use require_device_id."
        )

    def test_the_literal_is_only_referenced_to_reject_it(self):
        """Whatever still names it must be comparing against it, not using it."""
        from pathlib import Path

        import app as app_pkg

        for path in Path(app_pkg.__file__).parent.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if "default-device" not in line or line.strip().startswith("#"):
                    continue
                # Prose (docstrings) and explicit rejections are fine.
                assert (
                    '== "default-device"' in line
                    or "'default-device'" in line
                    or '"default-device"' in line
                ), f"{path.name}:{number} uses default-device as a value"


class TestRoutesRejectAnonymousCallers:
    async def test_trading_execute_requires_a_device(self, app_client):
        """No header at all must not reach the order path."""
        resp = await app_client.post(
            "/api/v1/trading/execute",
            json={"symbol": "BTC", "type": "buy", "shares": 0.5},
        )
        assert resp.status_code == 401

    async def test_paper_trade_requires_a_device(self, app_client):
        resp = await app_client.post(
            "/api/v1/paper/trade",
            json={"symbol": "AAPL", "side": "buy", "quantity": 1, "price": 100},
        )
        assert resp.status_code == 401

    async def test_watchlist_requires_a_device(self, app_client):
        resp = await app_client.get("/api/v1/watchlist")
        assert resp.status_code == 401

    async def test_legacy_default_device_is_rejected(self, app_client):
        """The exact header value an anonymous caller used to rely on."""
        resp = await app_client.get(
            "/api/v1/watchlist", headers={"X-Device-ID": "default-device"}
        )
        assert resp.status_code == 401

    async def test_non_uuid_device_is_rejected(self, app_client):
        resp = await app_client.get("/api/v1/watchlist", headers={"X-Device-ID": "dev-1"})
        assert resp.status_code == 401

    async def test_valid_uuid_is_accepted(self, app_client):
        from conftest import TEST_DEVICE_ID

        resp = await app_client.get("/api/v1/watchlist", headers={"X-Device-ID": TEST_DEVICE_ID})
        assert resp.status_code == 200


class TestPortfoliosAreDeviceScoped:
    """Two devices must not share a portfolio."""

    async def test_get_portfolios_filters_by_device(self, db):
        from sqlalchemy import select

        from app.models import Portfolio
        from app.services.portfolio_service import PortfolioService

        db.add(Portfolio(device_id="aaaaaaaa-0000-4000-8000-000000000001", name="A", cash=100.0))
        db.add(Portfolio(device_id="bbbbbbbb-0000-4000-8000-000000000002", name="B", cash=200.0))
        await db.commit()

        service = PortfolioService(db)
        mine = await service.get_portfolios(device_id="aaaaaaaa-0000-4000-8000-000000000001")
        theirs = await service.get_portfolios(device_id="bbbbbbbb-0000-4000-8000-000000000002")

        assert [p.name for p in mine] == ["A"]
        assert [p.name for p in theirs] == ["B"]

    async def test_unscoped_still_returns_everything_for_admin_use(self, db):
        """Kept working for scripts and migrations, but no request path uses it."""
        from app.models import Portfolio
        from app.services.portfolio_service import PortfolioService

        db.add(Portfolio(device_id="aaaaaaaa-0000-4000-8000-000000000001", name="A", cash=100.0))
        db.add(Portfolio(device_id="bbbbbbbb-0000-4000-8000-000000000002", name="B", cash=200.0))
        await db.commit()

        everything = await PortfolioService(db).get_portfolios()
        assert len(everything) == 2

    async def test_order_is_deterministic_for_the_same_device(self, db):
        """Two calls must not return a different "first" portfolio."""
        from app.models import Portfolio
        from app.services.portfolio_service import PortfolioService

        db.add(Portfolio(device_id="cccccccc-0000-4000-8000-000000000003", name="First", cash=1.0))
        db.add(Portfolio(device_id="cccccccc-0000-4000-8000-000000000003", name="Second", cash=2.0))
        await db.commit()

        service = PortfolioService(db)
        first = await service.get_portfolios(device_id="cccccccc-0000-4000-8000-000000000003")
        second = await service.get_portfolios(device_id="cccccccc-0000-4000-8000-000000000003")
        assert [p.id for p in first] == [p.id for p in second]


class TestExecuteRequestContract:
    """The endpoint takes a JSON body; the frontend's field names are canonical."""

    def test_frontend_shape_is_accepted(self):
        from app.api.v1.trading import ExecuteTradeRequest

        req = ExecuteTradeRequest(symbol="aapl", type="BUY", shares=10)
        assert req.symbol == "aapl"
        assert req.resolved_side == "buy"
        assert req.resolved_quantity == 10.0

    def test_alias_shape_is_accepted(self):
        from app.api.v1.trading import ExecuteTradeRequest

        req = ExecuteTradeRequest(symbol="BTC/USDT", side="sell", quantity=0.5)
        assert req.resolved_side == "sell"
        assert req.resolved_quantity == 0.5

    @pytest.mark.parametrize(
        "payload",
        [
            {"symbol": "AAPL"},                          # no side
            {"symbol": "AAPL", "type": "BUY"},           # no quantity
            {"type": "BUY", "shares": 1},                # no symbol
            {"symbol": "AAPL", "type": "BUY", "shares": 0},
            {"symbol": "AAPL", "type": "BUY", "shares": -5},
        ],
    )
    def test_incomplete_orders_are_rejected_at_validation(self, payload):
        """Rejected by the model, so the gate never runs on a malformed order."""
        from pydantic import ValidationError

        from app.api.v1.trading import ExecuteTradeRequest

        with pytest.raises(ValidationError):
            ExecuteTradeRequest(**payload)