"""Paper fills must be visible in the authoritative tables.

This is the single most important correctness property in paper trading, and it
was absent. Paper state lived only in a JSON blob on
`DeviceSettings.universal_paper_trading_config`. Nothing wrote `Portfolio.cash`
or created a `Position` row, so after a successful $1,000 buy:

    Portfolio.cash      10000.0     (unchanged)
    Position rows       0
    JSON ledger balance 8999.0       (the only thing that knew)

Every user-facing and downstream view reads the tables, not the blob:
`/trading/positions`, the portfolio total, the mark-to-market job, the daily
equity snapshot, and the auto-payout source. Paper trading therefore produced
no evidence at all - which is the entire reason to run it before risking money.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import DeviceSettings, Portfolio, Position, Trade
from app.services.paper_trading_service import get_paper_trading_service


async def _paper(db, device_id: str) -> tuple[int, object]:
    """A paper portfolio plus a service cleared of cached state.

    Uses the suite's `db` session, which is bound to the test engine. Reaching
    for `app.database.AsyncSessionLocal` directly would read and write the real
    configured database instead of the test one.
    """
    service = get_paper_trading_service()
    service.clear_cache()
    portfolio = Portfolio(
        device_id=device_id,
        name="Paper",
        cash=10000.0,
        initial_value=10000.0,
        initial_capital=10000.0,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio.id, service


async def _reload(db, portfolio_id: int) -> Portfolio:
    return (
        await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    ).scalar_one()


async def _positions(db, portfolio_id: int) -> list:
    result = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio_id)
    )
    return list(result.scalars().all())


class TestPaperFillUpdatesPortfolio:
    async def test_buy_debits_cash(self, db):
        portfolio_id, service = await _paper(db, "pf-cash")
        await service.place_trade(
            device_id="pf-cash", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        db.expire_all()
        portfolio = await _reload(db, portfolio_id)
        notional = 10 * 100.0
        commission = notional * 0.001  # default commission_rate
        assert portfolio.cash == pytest.approx(10000.0 - notional - commission), (
            "a $1,000 paper buy must debit the portfolio, commission included"
        )

    async def test_buy_creates_a_position(self, db):
        portfolio_id, service = await _paper(db, "pf-pos")
        await service.place_trade(
            device_id="pf-pos", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        db.expire_all()
        positions = await _positions(db, portfolio_id)
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"
        assert positions[0].quantity == pytest.approx(10.0)
        assert positions[0].avg_price == pytest.approx(100.0)

    async def test_partial_sell_reduces_position_and_credits_cash(self, db):
        portfolio_id, service = await _paper(db, "pf-partial")
        await service.place_trade(
            device_id="pf-partial", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        await service.place_trade(
            device_id="pf-partial", symbol="AAPL", side="sell",
            qty=4, price=120.0, asset_class="stocks",
        )
        db.expire_all()
        portfolio = await _reload(db, portfolio_id)
        positions = await _positions(db, portfolio_id)
        buy_notional = 10 * 100.0
        sell_notional = 4 * 120.0
        expected = (
            10000.0
            - buy_notional - buy_notional * 0.001
            + sell_notional - sell_notional * 0.001
        )
        assert portfolio.cash == pytest.approx(expected)
        assert len(positions) == 1
        assert positions[0].quantity == pytest.approx(6.0)
        # Cost basis is unchanged by the sale.
        assert positions[0].avg_price == pytest.approx(100.0)

    async def test_full_close_removes_the_position(self, db):
        """A closed position should not linger as a zero-quantity row."""
        portfolio_id, service = await _paper(db, "pf-close")
        await service.place_trade(
            device_id="pf-close", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        await service.place_trade(
            device_id="pf-close", symbol="AAPL", side="sell",
            qty=10, price=120.0, asset_class="stocks",
        )
        db.expire_all()
        assert await _positions(db, portfolio_id) == []

    async def test_averaging_up_recomputes_cost_basis(self, db):
        portfolio_id, service = await _paper(db, "pf-avg")
        await service.place_trade(
            device_id="pf-avg", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        await service.place_trade(
            device_id="pf-avg", symbol="AAPL", side="buy",
            qty=10, price=200.0, asset_class="stocks",
        )
        db.expire_all()
        position = (await _positions(db, portfolio_id))[0]
        # (100*10 + 200*10) / 20 = 150
        assert position.avg_price == pytest.approx(150.0)
        assert position.quantity == pytest.approx(20.0)


class TestPortfolioMatchesLedger:
    async def test_cash_equals_the_json_ledger(self, db):
        """The two must not diverge; the ledger is what payouts read."""
        portfolio_id, service = await _paper(db, "pf-recon")
        await service.place_trade(
            device_id="pf-recon", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        await service.place_trade(
            device_id="pf-recon", symbol="AAPL", side="sell",
            qty=4, price=120.0, asset_class="stocks",
        )
        portfolio = await _reload(db, portfolio_id)
        account = await service.get_account("pf-recon")
        assert portfolio.cash == pytest.approx(account["current_balance"], abs=0.01), (
            "Portfolio.cash and the paper ledger have diverged"
        )


class TestFailClosed:
    async def test_insufficient_balance_creates_nothing(self, db):
        portfolio_id, service = await _paper(db, "pf-nofunds")
        result = await service.place_trade(
            device_id="pf-nofunds", symbol="AAPL", side="buy",
            qty=1000, price=100.0, asset_class="stocks",
        )
        assert "error" in result
        portfolio = await _reload(db, portfolio_id)
        assert portfolio.cash == pytest.approx(10000.0)
        assert await _positions(db, portfolio_id) == []

    async def test_selling_what_you_do_not_hold_creates_nothing(self, db):
        portfolio_id, service = await _paper(db, "pf-noshort")
        result = await service.place_trade(
            device_id="pf-noshort", symbol="AAPL", side="sell",
            qty=1, price=100.0, asset_class="stocks",
        )
        assert "error" in result
        portfolio = await _reload(db, portfolio_id)
        assert portfolio.cash == pytest.approx(10000.0), (
            "a rejected sell must not credit cash"
        )

    async def test_no_portfolio_does_not_crash_the_fill(self, db):
        """A device with no portfolio still gets a recorded trade."""
        service = get_paper_trading_service()
        service.clear_cache()
        result = await service.place_trade(
            device_id="no-such-device", symbol="AAPL", side="buy",
            qty=1, price=100.0, asset_class="stocks",
        )
        assert result.get("success") is True

    async def test_disabled_paper_trading_is_refused(self, db):
        service = get_paper_trading_service()
        service.clear_cache()
        db.add(
            DeviceSettings(
                device_id="pf-off",
                universal_paper_trading_config='{"enabled": false}',
            )
        )
        await db.commit()
        result = await service.place_trade(
            device_id="pf-off", symbol="AAPL", side="buy",
            qty=1, price=100.0, asset_class="stocks",
        )
        assert "error" in result


class TestTradeRecord:
    async def test_trade_is_recorded_with_realised_pnl(self, db):
        portfolio_id, service = await _paper(db, "pf-trade")
        await service.place_trade(
            device_id="pf-trade", symbol="AAPL", side="buy",
            qty=10, price=100.0, asset_class="stocks",
        )
        await service.place_trade(
            device_id="pf-trade", symbol="AAPL", side="sell",
            qty=10, price=120.0, asset_class="stocks",
        )
        db.expire_all()
        trades = list(
            (
                await db.execute(
                    select(Trade).where(Trade.portfolio_id == portfolio_id)
                )
            ).scalars().all()
        )
        assert len(trades) == 2
        sells = [t for t in trades if t.side == "sell"]
        # (120-100)*10 = 200 gross, less 0.1% commission on the 1200 exit.
        expected_pnl = 200.0 - (10 * 120.0 * 0.001)
        assert sells[0].pnl == pytest.approx(expected_pnl)
        assert all(t.broker == "paper" for t in trades)
        assert all(t.status == "filled" for t in trades)