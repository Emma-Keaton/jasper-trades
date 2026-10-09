"""
Kronos Remote Service Client (modal-kronos).

Division of responsibility:

- **This service owns market data.** `fetch_candles` reads OHLCV through
  `app.services.data_connectors` and normalises it into the wire format.
- **Kronos owns prediction only.** It never fetches bars and never trains.

The previous implementation called `GET {base_url}/predict/{symbol}` against a
Render deployment. That service did not run Kronos at all: it built a 64-unit
LSTM and a 32-dim transformer, then attempted to `load_state_dict` Kronos
weights into them. The shapes cannot match, so it always fell back to random
initialisation and returned noise. This client now talks to modal-kronos, which
serves the published weights and returns a real predictive distribution.

Calibration lives here, not in Kronos: every prediction is recorded and later
scored against realised prices, so `confidence` can be checked against observed
hit rate before it gates capital.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

#: Kronos needs at least this many candles.
MIN_CANDLES = 16

#: Bar intervals in seconds, for scoring a forecast against its horizon.
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "1d": 86400,
}


@dataclass
class RecordedForecast:
    """A prediction kept so it can be scored once prices are known."""

    symbol: str
    at: datetime
    horizon: int
    interval_seconds: int
    last_close: float
    mean_path: List[float]
    confidence: float
    probability_up: float
    terminal_low: float
    terminal_high: float
    model: str
    trajectories: List[List[float]] = field(default_factory=list)
    scored: bool = False
    realised: Optional[float] = None
    hit: Optional[bool] = None
    within_band: Optional[bool] = None
    #: Primary key of the matching durable ledger row, set when the prediction is
    #: persisted. Scoring writes back through this rather than re-finding the row.
    ledger_id: Optional[int] = None

    @property
    def predicted_up(self) -> bool:
        return self.probability_up >= 0.5


def _parse_iso(value: Any) -> str:
    """Normalise a timestamp to an ISO-8601 string Kronos will accept.

    `data_connectors` already returns ISO strings from a naive local
    `datetime.fromtimestamp` (`data_connectors/__init__.py:263`); those carry no
    timezone, which Kronos treats as UTC. Normalising here keeps the assumption in
    one place.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        # Naive values are treated as UTC, matching `data_connectors`, which
        # builds them from `datetime.fromtimestamp` without a tzinfo.
        stamped = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return stamped.astimezone(timezone.utc).isoformat()
    seconds = float(value) / 1000.0
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def normalise_candles(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert connector OHLCV rows into the Kronos wire format."""
    converted: List[Dict[str, Any]] = []
    for row in rows or []:
        if row.get("timestamp") is None or row.get("close") is None:
            continue
        converted.append(
            {
                "timestamp": _parse_iso(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or 0.0),
            }
        )
    converted.sort(key=lambda item: item["timestamp"])
    deduped: List[Dict[str, Any]] = []
    for entry in converted:
        if deduped and entry["timestamp"] == deduped[-1]["timestamp"]:
            deduped[-1] = entry
        else:
            deduped.append(entry)
    return deduped


class KronosRemoteClient:
    """Client for the modal-kronos prediction service."""

    def __init__(self) -> None:
        self.base_url = (settings.KRONOS_SERVICE_URL or "").rstrip("/")
        # A cold container pays container start + weight load before inference;
        # 60s was already the timeout here, which is the right order of magnitude.
        self.timeout = 90.0
        self._client: Optional[httpx.AsyncClient] = None
        #: Pending predictions awaiting scoring. Calibration itself lives in the
        #: durable ledger, not here; this is only the in-flight window.
        self._outcomes: List[RecordedForecast] = []

    # -- plumbing ------------------------------------------------------------

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            api_key = getattr(settings, "KRONOS_API_KEY", None)
            if api_key:
                headers["x-api-key"] = api_key
            self._client = httpx.AsyncClient(
                timeout=self.timeout, headers=headers
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        headers = {}
        api_key = getattr(settings, "KRONOS_API_KEY", None)
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    # -- market data ---------------------------------------------------------

    async def fetch_candles(
        self,
        symbol: str,
        interval: str = "1d",
        range_: str = "6mo",
    ) -> List[Dict[str, Any]]:
        """Fetch and normalise OHLCV. Market data is this service's job."""
        from app.services.data_connectors import data_connector_service

        rows = await data_connector_service.get_yfinance_data(
            symbol, interval=interval, range_=range_
        )
        candles = normalise_candles(rows or [])
        if len(candles) < MIN_CANDLES:
            raise ValueError(
                f"{symbol} {interval}: only {len(candles)} usable candles, "
                f"need {MIN_CANDLES}"
            )
        return candles

    # -- prediction ----------------------------------------------------------

    async def predict(
        self,
        symbol: str,
        strategy: str = "cascade",
        lookback_days: int = 30,
        *,
        interval: str = "1d",
        horizon: Optional[int] = None,
        samples: int = 10,
        record: bool = True,
    ) -> Dict[str, Any]:
        """Predict direction for one symbol.

        `strategy` is accepted for call-site compatibility and ignored: Kronos
        serves one model per deployment, selected by the `KRONOS_MODEL`
        environment variable on the Modal side. Cascading between model sizes
        would multiply inference cost with no accuracy guarantee.
        """
        if not self.base_url:
            logger.warning("KRONOS_SERVICE_URL not set - using replacement forecast")
            fallback = await self._replacement(symbol, lookback_days)
            if fallback is not None:
                return fallback
            return {
                "symbol": symbol,
                "direction": "NEUTRAL",
                "confidence": 0.0,
                "error": "Kronos service not configured",
                "strategy": "disabled",
            }

        target_horizon = horizon or max(10, lookback_days or 30)
        try:
            candles = await self.fetch_candles(symbol, interval=interval)
        except Exception as exc:
            logger.warning("Market data unavailable for %s: %s", symbol, exc)
            fallback = await self._replacement(symbol, lookback_days)
            if fallback is not None:
                return fallback
            return {
                "symbol": symbol,
                "direction": "NEUTRAL",
                "confidence": 0.0,
                "error": f"market data unavailable: {exc}",
                "strategy": "disabled",
            }

        try:
            return await self._remote_predict(
                symbol,
                candles,
                target_horizon,
                samples,
                strategy,
                interval,
                record,
            )
        except httpx.TimeoutException:
            logger.error("Kronos timeout for %s - using replacement forecast", symbol)
            fallback = await self._replacement(symbol, lookback_days)
            if fallback is not None:
                return fallback
            return {
                "symbol": symbol,
                "direction": "ERROR",
                "confidence": 0.0,
                "error": "Service timeout",
                "strategy": strategy,
            }
        except Exception as exc:
            logger.error("Kronos prediction failed for %s: %s", symbol, exc)
            fallback = await self._replacement(symbol, lookback_days)
            if fallback is not None:
                return fallback
            return {
                "symbol": symbol,
                "direction": "ERROR",
                "confidence": 0.0,
                "error": str(exc),
                "strategy": strategy,
            }

    async def _remote_predict(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
        horizon: int,
        samples: int,
        strategy: str,
        interval: str,
        record: bool,
    ) -> Dict[str, Any]:
        response = await self._http().post(
            f"{self.base_url}/forecast",
            json={
                "candles": candles,
                "horizon": horizon,
                "sample_count": samples,
            },
            headers=self._headers(),
        )
        # 422 means the window was rejected (too flat, malformed). That is a data
        # problem, not a model problem, and must not be papered over with a
        # replacement forecast.
        if response.status_code == 422:
            detail = response.json().get("detail", "rejected")
            logger.warning("Kronos rejected the window for %s: %s", symbol, detail)
            return {
                "symbol": symbol,
                "direction": "NEUTRAL",
                "confidence": 0.0,
                "error": f"invalid window: {detail}",
                "strategy": strategy,
                "model_source": "kronos_rejected",
            }
        response.raise_for_status()
        data = response.json()

        last_close = float(data.get("last_close") or candles[-1]["close"])
        probability_up = float(data.get("probability_up") or 0.5)
        distribution_valid = bool(data.get("distribution_valid")) and len(
            data.get("trajectories") or []
        ) >= 2

        # Direction follows the sampled probability rather than the mean path's
        # last point, so a near-zero mean move with unanimous samples is not
        # reported as FLAT.
        direction = "UP" if probability_up >= 0.5 else "DOWN"
        metadata = {
            "model_source": "kronos",
            "model": data.get("model"),
            "distribution_valid": distribution_valid,
            "probability_up": probability_up,
            "terminal_low": data.get("terminal_low"),
            "terminal_high": data.get("terminal_high"),
            "sample_count": data.get("sample_count", samples),
            "lookback": data.get("lookback", len(candles)),
            "interval": interval,
        }

        result = {
            "symbol": symbol,
            "direction": direction,
            # Callers compare against 0..1, Kronos reports 0..100.
            "confidence": round(float(data.get("confidence", 50)) / 100.0, 4),
            "strategy": f"kronos_{data.get('model', 'unknown')}",
            "model_source": "kronos",
            "predicted_change": data.get("predicted_change"),
            "last_close": last_close,
            "mean_path": data.get("mean_path") or [],
            "trajectories": data.get("trajectories") or [],
            "confidence_90": data.get("confidence_90") or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
        }

        if record and distribution_valid:
            await self._record(symbol, result, candles, interval)

        logger.info(
            "Kronos %s: %s conf=%.2f valid=%s",
            symbol,
            direction,
            result["confidence"],
            distribution_valid,
        )
        return result

    async def predict_batch(
        self,
        symbols: List[str],
        strategy: str = "cascade",
        lookback_days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """Predict several symbols.

        Fetched concurrently because each call is independent and dominated by
        inference latency.
        """
        if not symbols:
            return {}

        async def one(symbol: str) -> tuple:
            return symbol, await self.predict(
                symbol, strategy=strategy, lookback_days=lookback_days
            )

        results = await asyncio.gather(
            *(one(symbol) for symbol in symbols), return_exceptions=True
        )
        output: Dict[str, Dict[str, Any]] = {}
        for symbol, value in zip(symbols, results):
            if isinstance(value, BaseException):
                logger.error("Batch prediction failed for %s: %s", symbol, value)
                output[symbol] = {
                    "symbol": symbol,
                    "direction": "ERROR",
                    "confidence": 0.0,
                    "error": str(value),
                }
            else:
                output[symbol] = value
        return output

    # -- calibration ---------------------------------------------------------

    async def _record(
        self,
        symbol: str,
        result: Dict[str, Any],
        candles: List[Dict[str, Any]],
        interval: str,
    ) -> None:
        """Keep a prediction so it can be scored once prices are known.

        Also written to the durable ledger. Calibration is the evidence that makes
        `confidence` trustworthy, so it must outlive the process: on a free
        instance the container is destroyed between requests, and an in-memory
        list would restart from zero evidence every time.
        """
        mean_path = result.get("mean_path") or []
        if not mean_path:
            return
        metadata = result.get("metadata") or {}
        outcome = RecordedForecast(
            symbol=symbol,
            at=datetime.now(timezone.utc),
            horizon=len(mean_path),
            interval_seconds=INTERVAL_SECONDS.get(interval, 86400),
            last_close=float(result.get("last_close") or candles[-1]["close"]),
            mean_path=list(mean_path),
            confidence=float(result.get("confidence") or 0.0),
            probability_up=float(metadata.get("probability_up") or 0.5),
            terminal_low=float(metadata.get("terminal_low") or 0.0),
            terminal_high=float(metadata.get("terminal_high") or 0.0),
            model=str(metadata.get("model") or "unknown"),
            trajectories=[list(p) for p in (result.get("trajectories") or [])],
        )
        self._outcomes.append(outcome)
        if len(self._outcomes) > 2000:
            del self._outcomes[: len(self._outcomes) - 2000]
        try:
            await self._persist(outcome)
        finally:
            # The trajectories now live in the durable ledger. Keeping them on
            # the in-memory record as well is ~30 MB at the 2000-record cap
            # (8 paths x 50 steps x 2000 records), which is a real cost on a
            # 512 MB container, and nothing in the scoring path reads them.
            outcome.trajectories = []

    # -- durable ledger ------------------------------------------------------

    async def _persist(self, outcome: RecordedForecast) -> None:
        """Write one prediction to the durable ledger.

        Sets `outcome.ledger_id` so scoring writes back to this exact row rather
        than searching for a matching one again.
        """
        from app.database import async_session
        from app.services.kronos_ledger_store import LedgerStore

        try:
            async with async_session() as db:
                row = await LedgerStore(db).record_forecast(
                    symbol=outcome.symbol,
                    source="kronos",
                    model=outcome.model,
                    horizon=outcome.horizon,
                    interval_seconds=outcome.interval_seconds,
                    sample_count=len(outcome.trajectories),
                    last_close=outcome.last_close,
                    mean_path=outcome.mean_path,
                    trajectories=outcome.trajectories,
                    probability_up=outcome.probability_up,
                    confidence=int(outcome.confidence),
                    terminal_low=outcome.terminal_low,
                    terminal_high=outcome.terminal_high,
                )
                if row is not None:
                    outcome.ledger_id = row.id
        except Exception as exc:
            # Losing one prediction is survivable; failing the request is not.
            logger.warning(
                "Could not persist Kronos forecast for %s: %s", outcome.symbol, exc
            )

    async def _write_back(
        self, outcome: RecordedForecast, realised: Optional[float], reason: str = ""
    ) -> None:
        """Score or close out the durable row behind one prediction."""
        if outcome.ledger_id is None:
            return
        from app.database import async_session
        from app.models import KronosForecast
        from app.services.kronos_ledger_store import LedgerStore

        try:
            async with async_session() as db:
                store = LedgerStore(db)
                row = await db.get(KronosForecast, outcome.ledger_id)
                if row is None:
                    return
                if realised is None:
                    await store.mark_unscoreable(row, reason)
                else:
                    await store.score(row, realised=realised)
        except Exception as exc:
            logger.warning(
                "Could not write back Kronos forecast for %s: %s", outcome.symbol, exc
            )

    async def refit(self) -> Dict[str, Any]:
        """Refit global thresholds and promote a model on accumulated evidence.

        Learned parameters and the active model are workspace-global, so one refit
        folds in evidence from every profile and device. Promotion still requires
        a statistically significant record, so an early run cannot install a model
        on noise.
        """
        from app.database import async_session
        from app.services.kronos_ledger_store import LedgerStore

        async with async_session() as db:
            store = LedgerStore(db)
            state = await store.fit()
            await store.persist_learned(state)
            ranking = await store.rank_models()

        promoted = None
        best = ranking[0] if ranking and ranking[0].get("significant") else None
        if best is not None:
            async with async_session() as db:
                promoted = await LedgerStore(db).assign_model(best["model"])

        return {
            "sample_size": state.sample_size,
            "validated": state.validated,
            "reason": state.reason,
            "hit_rate": state.hit_rate,
            "promoted_model": getattr(promoted, "model", None),
            "promoted": bool(getattr(promoted, "promoted", False)),
        }

    async def score_pending(self, price_lookup=None) -> List[RecordedForecast]:
        """Score recorded predictions against realised prices.

        Kronos predicts and never learns. This is the feedback loop that turns
        `confidence` from a raw model frequency into something that can be
        trusted to gate trades.
        """
        now = time.time()
        scored: List[RecordedForecast] = []

        for outcome in list(self._outcomes):
            if outcome.scored:
                continue
            due = outcome.at.timestamp() + outcome.horizon * outcome.interval_seconds
            if now < due:
                continue

            outcome.scored = True
            realised = (
                await price_lookup(outcome.symbol, int(due))
                if price_lookup
                else await self._default_price(outcome.symbol)
            )
            if realised is None or not outcome.last_close:
                await self._write_back(outcome, None, reason="no realised price")
                continue

            outcome.realised = float(realised)
            outcome.hit = (outcome.realised > outcome.last_close) == outcome.predicted_up
            outcome.within_band = (
                outcome.terminal_low <= outcome.realised <= outcome.terminal_high
                if outcome.terminal_high
                else None
            )
            await self._write_back(outcome, realised=outcome.realised)
            scored.append(outcome)

        return scored

    async def _default_price(self, symbol: str) -> Optional[float]:
        from app.services.data_connectors import data_connector_service

        try:
            rows = await data_connector_service.get_yfinance_data(
                symbol, interval="1d", range_="5d"
            )
            return float(rows[-1]["close"]) if rows else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("Price lookup failed for %s: %s", symbol, exc)
            return None

    async def calibration_summary(self) -> Dict[str, Any]:
        """Observed hit rate, bucketed by the confidence that predicted it.

        A `confidence` of 0.8 that lands 55% of the time means the number needs
        recalibrating before it should gate capital.

        Read from the durable ledger rather than an in-process list: this is the
        evidence that decides whether a learned threshold may be trusted, so it
        must cover every scored prediction the workspace has ever made, including
        those from other instances and earlier deployments.
        """
        from app.database import async_session
        from app.services.kronos_ledger_store import LedgerStore

        try:
            async with async_session() as db:
                rows = await LedgerStore(db).scored_forecasts()
        except Exception as exc:
            logger.warning("Could not read calibration ledger: %s", exc)
            return {"scored": 0, "error": str(exc)}

        scored = [row for row in rows if row.was_up is not None]
        if not scored:
            return {"scored": 0, "note": "no scored predictions yet"}

        total = len(scored)
        hits = sum(1 for row in scored if row.hit)
        banded = [r for r in scored if r.within_band is not None]
        buckets: Dict[str, Dict[str, Any]] = {}
        for row in scored:
            key = str(round(row.confidence / 100, 1))
            entry = buckets.setdefault(key, {"n": 0, "hits": 0})
            entry["n"] += 1
            if row.hit:
                entry["hits"] += 1
        for entry in buckets.values():
            entry["hit_rate"] = (
                round(entry["hits"] / entry["n"], 4) if entry["n"] else 0.0
            )

        return {
            "scored": total,
            "hit_rate": round(hits / total, 4) if total else 0.0,
            "within_90_band": (
                round(sum(1 for r in banded if r.within_band) / len(banded), 4)
                if banded
                else None
            ),
            "by_confidence": buckets,
        }

    async def _replacement(
        self, symbol: str, lookback_days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Replacement forecast from the tiered local forecaster."""
        try:
            from app.services.kronos_fallback import replacement_prediction

            return await replacement_prediction(symbol, lookback_days=lookback_days)
        except Exception as exc:  # noqa: BLE001
            logger.error("Replacement forecast unavailable for %s: %s", symbol, exc)
            return None

    async def health_check(self) -> Dict[str, Any]:
        """Check whether the Kronos service is reachable and which model is live."""
        if not self.base_url:
            return {"status": "disabled", "url": None}
        try:
            response = await self._http().get(
                f"{self.base_url}/health", headers=self._headers()
            )
            response.raise_for_status()
            data = response.json()
            return {
                "status": "healthy",
                "url": self.base_url,
                "model": data.get("model"),
                "model_loaded": data.get("model_loaded"),
                "auth_configured": data.get("auth_configured"),
                "rate_limit": data.get("rate_limit"),
                "calibration": await self.calibration_summary(),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Kronos health check failed: %s", exc)
            return {"status": "unhealthy", "url": self.base_url, "error": str(exc)}

    async def get_strategies(self) -> List[Dict[str, str]]:
        """Report the single served model.

        The old service advertised cascade/ensemble/mini/small/base. Only one model
        is deployed, so advertising strategies that do not exist would be worse
        than reporting the truth.
        """
        if not self.base_url:
            return []
        try:
            response = await self._http().get(
                f"{self.base_url}/health", headers=self._headers()
            )
            response.raise_for_status()
            model = response.json().get("model")
            if not model:
                return []
            return [
                {
                    "name": "kronos",
                    "model": model,
                    "description": "modal-kronos predictive distribution",
                }
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to read Kronos model info: %s", exc)
            return []


# Global client instance
kronos_client = KronosRemoteClient()


async def predict_direction(
    symbol: str,
    strategy: str = "cascade",
    forecast_horizon: int = 50,
) -> Dict[str, Any]:
    """Single-symbol prediction. `forecast_horizon` now actually applies."""
    return await kronos_client.predict(
        symbol, strategy=strategy, horizon=forecast_horizon
    )


async def predict_batch_direction(
    symbols: List[str],
    strategy: str = "cascade",
    forecast_horizon: int = 50,
) -> Dict[str, Dict[str, Any]]:
    """Batch prediction."""
    return await kronos_client.predict_batch(
        symbols, strategy=strategy, lookback_days=forecast_horizon
    )