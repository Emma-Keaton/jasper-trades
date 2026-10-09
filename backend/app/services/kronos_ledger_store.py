"""Durable store for the Kronos prediction ledger, learned parameters, and model
assignments — jasper-trades.

Same contract as aegis-quant's `kronos_ledger_store`, ported to this app's
schema conventions (`device_id` rather than `profile_id`).

Why it exists: Kronos predicts and never learns. To improve behaviour from real
outcomes, this backend must persist every prediction, score it against realised
prices, and store what it learned. That state must survive a restart, because
Render's free tier suspends idle instances and discards process memory.

Learning is **workspace-global**, not per-device. Kronos is the same frozen
forecaster for every device, so evidence from one device's trades legitimately
improves the estimate for all of them. Keying per-device would fragment the
evidence until each device had hundreds of scored forecasts of its own, which on
a paper-trading tier may never happen — leaving everyone permanently on the
configured defaults. `GLOBAL_KEY` is the sentinel used for those rows.

`strategy_learner` holds the decision logic and stays pure; this module is the
only place that touches the database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import Index, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    GLOBAL_KEY,
    KronosForecast,
    LearnedParameter,
    LearnedParameterHistory,
    ModelAssignment,
)
from app.services import strategy_learner as learner

logger = logging.getLogger(__name__)

MAX_FIT_SAMPLE = 5000


class LedgerStore:
    """Async CRUD over the Kronos ledger tables. Workspace-global scope."""

    GLOBAL = GLOBAL_KEY

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    # -- forecasts -----------------------------------------------------------

    async def record_forecast(
        self,
        *,
        symbol: str,
        source: str,
        model: Optional[str],
        horizon: int,
        interval_seconds: int,
        sample_count: int,
        last_close: float,
        mean_path: Sequence[float],
        trajectories: Optional[Sequence[Sequence[float]]],
        probability_up: Optional[float],
        confidence: Optional[int],
        terminal_low: Optional[float] = None,
        terminal_high: Optional[float] = None,
    ) -> Optional[KronosForecast]:
        """Persist one prediction.

        Only real, non-degenerate forecasts are recorded. Logging a placeholder
        or a single-path result would poison calibration: those rows carry no
        distributional information but would still count as evidence.

        Predictions are recorded under the global scope. Kronos is the same
        frozen forecaster for every device, so a prediction made on one device is
        evidence for all of them; keying rows per device would fragment the
        calibration record until no device ever had enough evidence to trust.
        """
        if source != "kronos":
            return None
        if not trajectories or len(trajectories) < 2:
            return None

        row = KronosForecast(
            device_id=str(self.GLOBAL),
            symbol=symbol,
            source=source,
            model=model,
            horizon=horizon,
            interval_seconds=interval_seconds,
            sample_count=sample_count,
            last_close=float(last_close),
            mean_path=list(mean_path),
            trajectories=[list(path) for path in trajectories],
            probability_up=probability_up,
            confidence=confidence,
            terminal_low=terminal_low,
            terminal_high=terminal_high,
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def due_forecasts(self, limit: int = 200) -> List[KronosForecast]:
        """Unscored forecasts whose horizon has already elapsed.

        All arithmetic stays in naive UTC because the `DateTime` columns here are
        naive. Mixing an aware `now()` in raises `TypeError` on every unscored
        row, which would make horizon eligibility uncomputable rather than merely
        wrong.
        """
        now = datetime.utcnow()
        result = await self._db.execute(
            select(KronosForecast)
            .where(KronosForecast.scored.is_(False))
            .order_by(KronosForecast.created_at.asc())
            .limit(limit)
        )
        rows: List[KronosForecast] = []
        for row in result.scalars().all():
            created = row.created_at
            # A driver may hand back an aware value; drop the offset rather than
            # comparing mixed kinds.
            if created.tzinfo is not None:
                created = created.astimezone(timezone.utc).replace(tzinfo=None)
            due = created + timedelta(seconds=row.horizon * row.interval_seconds)
            if due <= now:
                rows.append(row)
        return rows

    async def score(self, row: KronosForecast, realised: float) -> None:
        """Record what actually happened for one prediction."""
        row.scored = True
        row.scored_at = datetime.utcnow()
        row.realised = float(realised)
        row.was_up = row.realised > row.last_close
        if row.terminal_low is not None and row.terminal_high is not None:
            row.within_band = row.terminal_low <= row.realised <= row.terminal_high
        mean_path = row.mean_path or []
        if mean_path:
            row.absolute_error = row.realised - float(mean_path[-1])
        await self._db.commit()

    async def mark_unscoreable(self, row: KronosForecast, reason: str) -> None:
        """Close out a forecast whose realised price is unavailable.

        Marked scored so it is not retried forever; `realised` stays NULL so it
        never contributes to calibration.
        """
        row.scored = True
        row.scored_at = datetime.utcnow()
        await self._db.commit()
        logger.debug("Unscoreable forecast %s for %s: %s", row.id, row.symbol, reason)

    async def scored_forecasts(
        self,
        symbol: Optional[str] = None,
        model: Optional[str] = None,
        limit: int = MAX_FIT_SAMPLE,
    ) -> List[learner.ScoredForecast]:
        """Load scored forecasts for fitting.

        Deliberately not filtered by device: the estimate is global.
        """
        stmt = select(KronosForecast).where(KronosForecast.scored.is_(True))
        if symbol:
            stmt = stmt.where(KronosForecast.symbol == symbol)
        if model:
            stmt = stmt.where(KronosForecast.model == model)
        stmt = stmt.order_by(KronosForecast.created_at.desc()).limit(limit)
        result = await self._db.execute(stmt)
        return [self._to_scored(row) for row in result.scalars().all()]

    @staticmethod
    def _to_scored(row: KronosForecast) -> learner.ScoredForecast:
        return learner.ScoredForecast(
            symbol=row.symbol,
            horizon=row.horizon,
            interval_seconds=row.interval_seconds,
            confidence=row.confidence or 50,
            probability_up=row.probability_up if row.probability_up is not None else 0.5,
            last_close=row.last_close,
            realised=row.realised or 0.0,
            within_band=row.within_band,
            absolute_error=row.absolute_error,
            created_at=row.created_at,
        )

    async def fit(self, **fit_kwargs: Any) -> learner.LearnedState:
        rows = await self.scored_forecasts()
        return learner.fit(rows, **fit_kwargs)

    # -- learned parameters --------------------------------------------------

    async def persist_learned(
        self, state: learner.LearnedState
    ) -> Dict[str, LearnedParameter]:
        """Write fitted parameters, auditing each change.

        Unvalidated state is stored with `validated = False`. Persisting it is
        deliberate: the values stay inspectable while `apply()` still refuses to
        use them, so evidence can be reviewed before it moves a live threshold.
        """
        result: Dict[str, LearnedParameter] = {}
        for name in learner.PARAMETER_NAMES:
            value = state.values.get(name)
            if value is None:
                continue
            existing = await self._get_parameter(name)
            if existing is None:
                row = LearnedParameter(
                    device_id=self.GLOBAL,
                    name=name,
                    value=float(value),
                    version=1,
                    sample_size=state.sample_size,
                    hit_rate=state.hit_rate,
                    validated=state.validated,
                )
                self._db.add(row)
                result[name] = row
                self._db.add(
                    LearnedParameterHistory(
                        device_id=self.GLOBAL,
                        name=name,
                        previous_value=None,
                        new_value=float(value),
                        version=1,
                        sample_size=state.sample_size,
                        hit_rate=state.hit_rate,
                        reason=state.reason,
                    )
                )
                continue

            # Evidence is refreshed even when the value is unchanged: a
            # parameter fitted on 12 forecasts is unvalidated, and the same value
            # refitted on 600 may now be validated. Without this a parameter could
            # never graduate without its value moving.
            if abs(existing.value - float(value)) >= 1e-9:
                self._db.add(
                    LearnedParameterHistory(
                        device_id=self.GLOBAL,
                        name=name,
                        previous_value=existing.value,
                        new_value=float(value),
                        version=existing.version + 1,
                        sample_size=state.sample_size,
                        hit_rate=state.hit_rate,
                        reason=state.reason,
                    )
                )
                existing.version += 1
                existing.value = float(value)
            existing.sample_size = state.sample_size
            existing.hit_rate = state.hit_rate
            existing.validated = state.validated
            existing.updated_at = datetime.utcnow()
            result[name] = existing
        await self._db.commit()
        return result

    async def _get_parameter(self, name: str) -> Optional[LearnedParameter]:
        result = await self._db.execute(
            select(LearnedParameter)
            .where(
                LearnedParameter.device_id == self.GLOBAL,
                LearnedParameter.name == name,
            )
            # The session uses expire_on_commit=False, so an already-loaded row
            # is returned from the identity map without refreshing its columns.
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def load_learned(self) -> Optional[learner.LearnedState]:
        result = await self._db.execute(
            select(LearnedParameter)
            .where(LearnedParameter.device_id == self.GLOBAL)
            .execution_options(populate_existing=True)
        )
        rows = result.scalars().all()
        if not rows:
            return None
        first = rows[0]
        return learner.LearnedState(
            values={row.name: row.value for row in rows},
            sample_size=first.sample_size,
            hit_rate=first.hit_rate,
            validated=all(row.validated for row in rows),
            reason="loaded from store",
            updated_at=first.updated_at,
        )

    async def effective_params(
        self,
        *,
        configured_threshold: int,
        configured_band_tolerance: float,
        configured_sample_penalty: float,
        configured_horizon_weight: float = 1.0,
    ) -> Tuple[Dict[str, float], learner.LearnedState]:
        """Resolve the parameters a live trade should use.

        Falls back to the configured values whenever stored state is missing or
        unvalidated. That fallback is the guardrail: early, noisy learning cannot
        move a real threshold.
        """
        fallback = {
            "confidence_threshold": float(configured_threshold),
            "band_width_tolerance": configured_band_tolerance,
            "sample_penalty": configured_sample_penalty,
            "horizon_weight": configured_horizon_weight,
        }
        state = await self.load_learned()
        if state is None:
            return fallback, learner.LearnedState(reason="never fitted")
        return (
            learner.apply(
                state,
                configured_threshold=configured_threshold,
                configured_band_tolerance=configured_band_tolerance,
                configured_sample_penalty=configured_sample_penalty,
                configured_horizon_weight=configured_horizon_weight,
            ),
            state,
        )

    # -- model ranking and assignment ---------------------------------------

    async def rank_models(self) -> List[Dict[str, Any]]:
        """Rank every model variant by observed evidence.

        Variants below `MIN_BUCKET_SAMPLES` are excluded: a ranking that listed a
        model on three samples would invite a promotion based on noise.
        """
        result = await self._db.execute(
            select(
                KronosForecast.model,
                func.count(KronosForecast.id),
                func.avg(KronosForecast.confidence),
            )
            .where(KronosForecast.scored.is_(True))
            .group_by(KronosForecast.model)
        )
        ranking: List[Dict[str, Any]] = []
        for model, total, mean_conf in result.all():
            if not model or total < learner.MIN_BUCKET_SAMPLES:
                continue
            rows = await self.scored_forecasts(model=model)
            hits = sum(1 for row in rows if row.hit)
            banded = [r for r in rows if r.within_band is not None]
            ranking.append(
                {
                    "model": model,
                    "scored": len(rows),
                    "hit_rate": round(hits / len(rows), 4) if rows else 0.0,
                    "mean_confidence": round(float(mean_conf or 0), 2),
                    "within_band": (
                        round(sum(1 for r in banded if r.within_band) / len(banded), 4)
                        if banded
                        else None
                    ),
                    "significant": learner.beats_coin_flip(hits, len(rows)),
                }
            )
        ranking.sort(key=lambda r: (-r["hit_rate"], -r["scored"]))
        return ranking

    async def assign_model(
        self,
        model: str,
        *,
        scope: str = "global",
        symbol: Optional[str] = None,
        ranking: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelAssignment:
        """Record a model assignment, promoting only on evidence.

        Promotion requires the candidate to be ranked, beat a coin flip with
        statistical confidence, and have enough scored forecasts. Anything else
        is recorded unpromoted so the intent is auditable without having been
        acted on.
        """
        ranking = ranking if ranking is not None else await self.rank_models()
        entry = next((r for r in ranking if r["model"] == model), None)
        promoted = bool(entry and entry.get("significant"))

        result = await self._db.execute(
            select(ModelAssignment)
            .where(
                ModelAssignment.device_id == self.GLOBAL,
                ModelAssignment.scope == scope,
                ModelAssignment.symbol == symbol,
            )
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ModelAssignment(device_id=self.GLOBAL, scope=scope, symbol=symbol, model=model)
            self._db.add(row)
        row.model = model
        row.hit_rate = entry["hit_rate"] if entry else None
        row.sample_size = int(entry["scored"]) if entry else 0
        row.promoted = promoted
        row.assigned_at = datetime.utcnow()
        row.promoted_at = datetime.utcnow() if promoted else None

        await self._db.commit()
        await self._db.refresh(row)
        if not promoted:
            logger.info(
                "Model %s assigned but NOT promoted: %s samples",
                model,
                row.sample_size,
            )
        return row

    async def active_model(self, symbol: Optional[str] = None) -> Optional[str]:
        """Return the promoted model for a symbol, else the global one."""
        result = await self._db.execute(
            select(ModelAssignment)
            .where(
                ModelAssignment.device_id == self.GLOBAL,
                ModelAssignment.symbol == symbol,
                ModelAssignment.promoted.is_(True),
            )
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row:
            return row.model
        result = await self._db.execute(
            select(ModelAssignment)
            .where(
                ModelAssignment.device_id == self.GLOBAL,
                ModelAssignment.symbol.is_(None),
                ModelAssignment.promoted.is_(True),
            )
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        return row.model if row else None