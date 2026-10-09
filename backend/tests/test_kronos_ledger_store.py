"""Tests for the durable Kronos ledger: recording, scoring, learning, ranking.

Runs against the suite's in-memory database through the real ORM and the real
`LedgerStore`. A mock would not exercise the parts most likely to break: the JSON
round trip on trajectories, the horizon-eligibility filter, and the
versioning/history arithmetic on learned parameters.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sqlalchemy import select

from app.models import KronosForecast, LearnedParameter, LearnedParameterHistory, ModelAssignment
from app.services import strategy_learner as learner
from app.services.kronos_ledger_store import LedgerStore


def trajectories(n: int = 8, steps: int = 6, base: float = 100.0):
    return [
        [base + step * (1 + i * 0.01) for step in range(steps)] for i in range(n)
    ]


async def record(store, **overrides):
    """Record one forecast, defaulting a valid non-degenerate prediction."""
    kwargs = {
        "symbol": "BTC/USDT",
        "source": "kronos",
        "model": "kronos-mini",
        "horizon": 1,
        "interval_seconds": 3600,
        "sample_count": 8,
        "last_close": 100.0,
        "mean_path": [100.5, 101.0, 101.5, 102.0, 102.5, 103.0],
        "trajectories": trajectories(),
        "probability_up": 0.7,
        "confidence": 75,
        "terminal_low": 96.0,
        "terminal_high": 108.0,
    }
    kwargs.update(overrides)
    return await store.record_forecast(**kwargs)


class TestRecordingRefusals:
    async def test_non_kronos_source_is_refused(self, db):
        store = LedgerStore(db)
        row = await record(store, source="replacement")
        assert row is None

    async def test_single_path_is_refused(self, db):
        """One trajectory is not a distribution; scoring it would poison calibration."""
        store = LedgerStore(db)
        row = await record(store, sample_count=1, trajectories=[[101.0, 102.0]])
        assert row is None

    async def test_no_trajectories_is_refused(self, db):
        store = LedgerStore(db)
        row = await record(store, trajectories=[])
        assert row is None

    async def test_valid_forecast_is_stored_with_trajectories(self, db):
        store = LedgerStore(db)
        row = await record(store)
        assert row is not None
        assert row.id is not None
        assert len(row.trajectories) == 8
        assert row.scored is False


class TestScoring:
    async def test_up_move_marks_was_up_and_band_membership(self, db):
        store = LedgerStore(db)
        row = await record(store)
        await store.score(row, realised=105.0)
        assert row.scored is True
        assert row.was_up is True
        assert row.within_band is True
        assert row.realised == 105.0

    async def test_down_move_marks_was_up_false(self, db):
        store = LedgerStore(db)
        row = await record(store)
        await store.score(row, realised=90.0)
        assert row.was_up is False
        assert row.within_band is False

    async def test_realised_exactly_at_close_is_not_up(self, db):
        store = LedgerStore(db)
        row = await record(store)
        await store.score(row, realised=100.0)
        assert row.was_up is False

    async def test_unscoreable_is_closed_but_keeps_realised_null(self, db):
        store = LedgerStore(db)
        row = await record(store)
        await store.mark_unscoreable(row, "price unavailable")
        assert row.scored is True
        assert row.realised is None

    async def test_absolute_error_uses_final_mean(self, db):
        store = LedgerStore(db)
        row = await record(store)
        await store.score(row, realised=110.0)
        assert row.absolute_error == pytest.approx(7.0)

    async def test_score_survives_a_new_session(self, db, session_factory):
        """A score written by one session must be visible to the next.

        This is what makes the ledger survive a free-tier restart, where the
        container and all in-memory state are destroyed.
        """
        store = LedgerStore(db)
        row = await record(store)
        await store.score(row, realised=105.0)

        async with session_factory() as fresh:
            reloaded = await fresh.get(KronosForecast, row.id)
            assert reloaded is not None
            assert reloaded.scored is True
            assert reloaded.realised == pytest.approx(105.0)


class TestDueForecasts:
    async def test_unelapsed_horizon_is_not_due(self, db):
        store = LedgerStore(db)
        await record(store, horizon=24, interval_seconds=3600)
        assert await store.due_forecasts() == []

    async def test_elapsed_horizon_is_due(self, db):
        store = LedgerStore(db)
        row = await record(store, horizon=1, interval_seconds=1)
        row.created_at = datetime.utcnow() - timedelta(hours=2)
        await db.commit()
        due = await store.due_forecasts()
        assert [r.id for r in due] == [row.id]

    async def test_scored_forecast_is_not_returned_again(self, db):
        store = LedgerStore(db)
        row = await record(store, horizon=1, interval_seconds=1)
        row.created_at = datetime.utcnow() - timedelta(hours=2)
        await db.commit()
        await store.score(row, realised=105.0)
        assert await store.due_forecasts() == []


class TestLearnedParametersAreGlobal:
    def _state(self, value=77.0, *, validated=True, n=100, reason="test"):
        return learner.LearnedState(
            values=dict.fromkeys(learner.PARAMETER_NAMES, value),
            sample_size=n,
            hit_rate=0.7,
            validated=validated,
            reason=reason,
        )

    async def test_persist_uses_global_scope(self, db):
        store = LedgerStore(db)
        await store.persist_learned(self._state())
        rows = (
            (
                await db.execute(
                    select(LearnedParameter).where(
                        LearnedParameter.name == "confidence_threshold"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].device_id == LedgerStore.GLOBAL

    async def test_reload_returns_persisted_values(self, db, session_factory):
        await LedgerStore(db).persist_learned(self._state())
        async with session_factory() as fresh:
            loaded = await LedgerStore(fresh).load_learned()
            assert loaded is not None
            assert loaded.validated is True
            assert loaded.values["confidence_threshold"] == pytest.approx(77.0)

    async def test_changed_value_bumps_version_and_writes_history(self, db):
        store = LedgerStore(db)
        await store.persist_learned(self._state(70.0, reason="first"))
        await store.persist_learned(self._state(80.0, reason="second"))

        row = (
            (
                await db.execute(
                    select(LearnedParameter).where(
                        LearnedParameter.name == "confidence_threshold"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.value == pytest.approx(80.0)
        assert row.version == 2

        history = (
            (
                await db.execute(
                    select(LearnedParameterHistory)
                    .where(LearnedParameterHistory.name == "confidence_threshold")
                    .order_by(LearnedParameterHistory.version.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(history) == 2
        assert history[0].previous_value is None
        assert history[0].new_value == pytest.approx(70.0)
        assert history[1].previous_value == pytest.approx(70.0)
        assert history[1].new_value == pytest.approx(80.0)

    async def test_effective_params_ignores_unvalidated(self, db):
        store = LedgerStore(db)
        await store.persist_learned(self._state(90.0, validated=False, n=20))
        effective, loaded = await store.effective_params(
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] == 70
        assert loaded.validated is False

    async def test_effective_params_uses_validated(self, db):
        store = LedgerStore(db)
        await store.persist_learned(self._state(90.0, validated=True))
        effective, loaded = await store.effective_params(
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] == pytest.approx(90.0)
        assert loaded.validated is True

    async def test_effective_params_falls_back_when_never_fitted(self, db):
        store = LedgerStore(db)
        effective, loaded = await store.effective_params(
            configured_threshold=70,
            configured_band_tolerance=0.06,
            configured_sample_penalty=0.0,
        )
        assert effective["confidence_threshold"] == 70
        assert loaded.validated is False


async def _seed(store, model, hits, misses, symbol):
    """Record and score `hits` winners then `misses` losers for one model."""
    rows = []
    for _ in range(hits):
        row = await record(
            store,
            model=model,
            symbol=symbol,
            horizon=1,
            interval_seconds=1,
            probability_up=0.8,
            confidence=80,
        )
        await store.score(row, realised=105.0)
        rows.append(row)
    for _ in range(misses):
        row = await record(
            store,
            model=model,
            symbol=symbol,
            horizon=1,
            interval_seconds=1,
            probability_up=0.8,
            confidence=80,
        )
        await store.score(row, realised=80.0)
        rows.append(row)
    return rows


class TestFitAndRanking:
    async def test_fit_with_no_evidence_is_unvalidated(self, db):
        state = await LedgerStore(db).fit()
        assert state.validated is False
        assert state.sample_size == 0

    async def test_ranking_prefers_the_better_model(self, db):
        store = LedgerStore(db)
        await _seed(store, "kronos-mini", 40, 5, "BTC/USDT")
        await _seed(store, "kronos-base", 5, 40, "ETH/USDT")

        ranked = await store.rank_models()
        names = [entry["model"] for entry in ranked]
        assert names.index("kronos-mini") < names.index("kronos-base")
        strong = next(e for e in ranked if e["model"] == "kronos-mini")
        assert strong["hit_rate"] == pytest.approx(40 / 45, abs=1e-3)

    async def test_model_with_too_few_samples_is_not_ranked(self, db):
        store = LedgerStore(db)
        await _seed(store, "kronos-mini", 3, 0, "BTC/USDT")
        assert await store.rank_models() == []

    async def test_unscored_forecasts_do_not_affect_ranking(self, db):
        store = LedgerStore(db)
        for _ in range(30):
            await record(store, horizon=1, interval_seconds=1)
        assert await store.rank_models() == []

    async def test_coin_flip_model_is_not_significant(self, db):
        store = LedgerStore(db)
        await _seed(store, "kronos-flaky", 25, 25, "BTC/USDT")
        ranked = await store.rank_models()
        assert len(ranked) == 1
        assert ranked[0]["significant"] is False


class TestModelAssignment:
    def _ranking(self, *models):
        return [
            {
                "model": m,
                "scored": 400,
                "hit_rate": 0.72,
                "mean_confidence": 80.0,
                "within_band": 0.9,
                "significant": True,
            }
            for m in (models or ("kronos-mini",))
        ]

    async def test_promoted_when_evidence_is_significant(self, db):
        row = await LedgerStore(db).assign_model("kronos-mini", ranking=self._ranking())
        assert row.promoted is True
        assert await LedgerStore(db).active_model() == "kronos-mini"

    async def test_not_promoted_without_evidence(self, db):
        row = await LedgerStore(db).assign_model("kronos-mini", ranking=[])
        assert row.promoted is False
        assert await LedgerStore(db).active_model() is None

    async def test_not_promoted_when_not_significant(self, db):
        ranking = [dict(self._ranking()[0], significant=False)]
        row = await LedgerStore(db).assign_model("kronos-mini", ranking=ranking)
        assert row.promoted is False
        assert await LedgerStore(db).active_model() is None

    async def test_symbol_specific_assignment_wins_over_global(self, db):
        store = LedgerStore(db)
        await store.assign_model("kronos-mini", ranking=self._ranking())
        await store.assign_model(
            "kronos-base",
            symbol="ETH/USDT",
            ranking=self._ranking("kronos-mini", "kronos-base"),
        )
        assert await store.active_model(symbol="ETH/USDT") == "kronos-base"
        assert await store.active_model(symbol="BTC/USDT") == "kronos-mini"
        assert await store.active_model() == "kronos-mini"

    async def test_no_assignment_returns_none(self, db):
        assert await LedgerStore(db).active_model() is None


class TestInMemoryFootprint:
    """The in-memory pending window must not duplicate the ledger.

    `RecordedForecast` carries `trajectories` so it can be written to the ledger,
    but keeping them afterwards costs ~30 MB at the 2000-record cap on a 512 MB
    container - and nothing in the scoring path reads them.
    """

    async def test_recorded_forecast_can_carry_trajectories(self):
        """The field must exist: persistence needs it before it is released."""
        from app.services.kronos_remote import RecordedForecast

        outcome = RecordedForecast(
            symbol="BTC/USDT",
            at=datetime.utcnow(),
            horizon=6,
            interval_seconds=3600,
            last_close=100.0,
            mean_path=[101.0],
            confidence=75.0,
            probability_up=0.7,
            terminal_low=99.0,
            terminal_high=102.0,
            model="kronos-mini",
            trajectories=[[101.0, 102.0, 103.0]],
        )
        assert len(outcome.trajectories) == 1

    async def test_trajectories_default_to_empty(self):
        """A caller that does not supply trajectories must not fail."""
        from app.services.kronos_remote import RecordedForecast

        outcome = RecordedForecast(
            symbol="BTC/USDT",
            at=datetime.utcnow(),
            horizon=6,
            interval_seconds=3600,
            last_close=100.0,
            mean_path=[101.0],
            confidence=75.0,
            probability_up=0.7,
            terminal_low=99.0,
            terminal_high=102.0,
            model="kronos-mini",
        )
        assert outcome.trajectories == []

    async def test_the_ledger_still_stores_trajectories(self, db):
        """Releasing them from memory must not affect what is persisted."""
        store = LedgerStore(db)
        row = await record(store)
        assert len(row.trajectories) == 8

    async def test_scoring_works_without_in_memory_trajectories(self, db):
        """Scoring reads price fields, never trajectories."""
        store = LedgerStore(db)
        row = await record(store)
        row.trajectories = []
        await store.score(row, realised=105.0)
        assert row.was_up is True
        assert row.within_band is True


class TestScoredForecastLoading:
    async def test_filters_by_symbol_and_model(self, db):
        store = LedgerStore(db)
        a = await record(store, model="kronos-mini", symbol="BTC/USDT", horizon=1, interval_seconds=1)
        b = await record(store, model="kronos-base", symbol="ETH/USDT", horizon=1, interval_seconds=1)
        await store.score(a, realised=105.0)
        await store.score(b, realised=95.0)

        only_btc = await store.scored_forecasts(symbol="BTC/USDT")
        assert [r.symbol for r in only_btc] == ["BTC/USDT"]

        only_mini = await store.scored_forecasts(model="kronos-mini")
        assert [r.symbol for r in only_mini] == ["BTC/USDT"]

    async def test_unscored_rows_are_excluded(self, db):
        store = LedgerStore(db)
        await record(store, horizon=1, interval_seconds=1)
        assert await store.scored_forecasts() == []