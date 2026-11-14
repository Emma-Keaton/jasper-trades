"""Kronos forecasting core for local + cloud deployment.

Wraps the vendored Kronos library (`kronos_lib`, from shiyu-coder/Kronos, MIT)
behind a container-resident model holder plus a candle-series normaliser.

The upstream `KronosPredictor.predict` requires explicit `x_timestamp` and
`y_timestamp` series and derives calendar features through
`calc_time_stamps` (`kronos_lib/kronos.py:472`). Every call therefore needs a
real, tz-consistent, strictly increasing timestamp series for both the observed
window and the forecast window; this module is the single place that builds
them so no caller can get it wrong.

Designed for 2GB RAM laptops: uses Kronos-mini (4.1M params, ~16MB weights)
by default, loads the model on demand, and runs CPU-only.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from kronos_lib import Kronos, KronosPredictor, KronosTokenizer

logger = logging.getLogger("kronos.service")

PRICE_COLUMNS = ("open", "high", "low", "close")

# Smallest first. `mini` is the only variant that fits a 2GB RAM laptop
# with headroom; `small` is the accuracy/cost compromise but ~4x slower.
MODEL_VARIANTS: tuple[tuple[str, str, int, int], ...] = (
    ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 2048, 4_100_000),
    ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 512, 24_700_000),
)

DEFAULT_VARIANT = os.getenv("KRONOS_MODEL", "NeoQuasar/Kronos-mini")


@dataclass(frozen=True)
class Candles:
    """A validated OHLCV window with a strictly increasing index."""

    frame: pd.DataFrame

    @property
    def closes(self) -> list[float]:
        return [float(v) for v in self.frame["close"].tolist()]

    @property
    def timestamps(self) -> pd.Series:
        return pd.Series(self.frame.index, name="timestamp")

    def __len__(self) -> int:
        return len(self.frame)


def _infer_frequency(index: pd.DatetimeIndex) -> pd.Timedelta:
    if len(index) < 2:
        raise ValueError("at least two candles are required to infer a bar frequency")
    deltas = index.to_series().diff().dropna()
    if deltas.empty:
        raise ValueError("candle timestamps are not strictly increasing")
    step = deltas.min()
    if step <= pd.Timedelta(0):
        raise ValueError("candle timestamps are not strictly increasing")
    return pd.Timedelta(step)


def build_candles(
    rows: list[dict[str, Any]],
    timestamps: list[str] | None = None,
    *,
    min_candles: int = 16,
) -> Candles:
    """Validate raw OHLCV rows and index them by a real datetime series.

    `rows` must carry at least `open`, `high`, `low`, `close`. `volume` and
    `amount` are optional and default to zero, matching upstream behaviour in
    `KronosPredictor.predict` (`kronos_lib/kronos.py:528`).
    """
    if len(rows) < min_candles:
        raise ValueError(f"need at least {min_candles} candles, got {len(rows)}")

    frame = pd.DataFrame(rows)
    missing = [c for c in PRICE_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"missing price columns: {', '.join(missing)}")

    for column in PRICE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = (
        pd.to_numeric(frame["volume"], errors="coerce")
        if "volume" in frame.columns
        else 0.0
    )
    frame["amount"] = (
        pd.to_numeric(frame["amount"], errors="coerce")
        if "amount" in frame.columns
        else 0.0
    )

    if timestamps is not None:
        index = pd.to_datetime(timestamps, utc=True)
    else:
        index = pd.to_datetime(frame.get("timestamp", pd.Series(range(len(rows)))), utc=True)
    frame.index = index

    frame = frame.sort_index()
    frame = frame.dropna(subset=list(PRICE_COLUMNS))

    if len(frame) < min_candles:
        raise ValueError(f"need at least {min_candles} valid candles after cleaning, got {len(frame)}")

    return Candles(frame=frame)


def build_candles_from_closes(
    closes: list[float],
    *,
    interval_seconds: int = 3600,
    timestamps: list[str] | None = None,
    min_candles: int = 16,
) -> Candles:
    """Synthesize OHLCV from a close-only series.

    Kronos requires OHLCV; when the caller only has closes we reconstruct
    high/low/volume from realised volatility. This is an approximation —
    prefer posting real candles via `POST /forecast`.
    """
    if len(closes) < min_candles:
        raise ValueError(f"need at least {min_candles} closes, got {len(closes)}")

    if timestamps is not None:
        index = pd.to_datetime(timestamps, utc=True)
    else:
        index = pd.date_range(
            end=pd.Timestamp.now(tz="UTC"),
            periods=len(closes),
            freq=f"{interval_seconds}s",
        )

    series = pd.Series(closes, index=index)
    returns = series.pct_change().fillna(0.0)
    vol = returns.rolling(window=min(20, len(series))).std().fillna(0.0)
    band = (vol * series).abs()

    frame = pd.DataFrame({
        "open": series.shift(1).fillna(series),
        "high": series + band,
        "low": series - band,
        "close": series,
        "volume": (band * 1e6).clip(lower=1.0),
        "amount": (series * band * 1e6).clip(lower=1.0),
    })
    frame = frame.iloc[1:]

    if len(frame) < min_candles:
        raise ValueError(f"need at least {min_candles} valid candles after synthesis, got {len(frame)}")

    return Candles(frame=frame)


def forecast_timestamps(
    candles: Candles,
    horizon: int,
) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """Build observed and forecast timestamp series.

    Returns `(x_timestamp, y_timestamp)` where `x_timestamp` covers the observed
    window and `y_timestamp` covers the forecast horizon starting one step after
    the last observed bar.
    """
    freq = _infer_frequency(candles.frame.index)
    x_timestamp = candles.frame.index

    last = x_timestamp[-1]
    y_timestamp = pd.DatetimeIndex([last + freq * (i + 1) for i in range(horizon)], tz="UTC")

    return x_timestamp, y_timestamp


class KronosEngine:
    """Container-resident Kronos model holder.

    Loads `NeoQuasar/Kronos-mini` from Hugging Face on first use (downloads
    weights once, caches in ~/.cache/huggingface). CPU-only inference.
    """

    def __init__(self, model_variant: str | None = None) -> None:
        self._model_name = model_variant or DEFAULT_VARIANT
        self._predictor: KronosPredictor | None = None
        self._lock = threading.Lock()
        self._loaded = False

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self) -> None:
        """Load model and tokenizer from Hugging Face (CPU-only)."""
        with self._lock:
            if self._loaded:
                return
            logger.info(
                "Loading Kronos model %s (CPU-only, first download may take ~3 min)",
                self._model_name,
            )

        tokenizer_name = "NeoQuasar/Kronos-Tokenizer-2k"
        context_len = 2048
        for variant_name, tok_name, ctx, _ in MODEL_VARIANTS:
            if variant_name == self._model_name:
                tokenizer_name = tok_name
                context_len = ctx
                break

        tokenizer = KronosTokenizer.from_pretrained(tokenizer_name)
        model = Kronos.from_pretrained(self._model_name)

        self._predictor = KronosPredictor(model, tokenizer, device="cpu")
        self._loaded = True
        logger.info("Kronos model %s loaded and ready on CPU", self._model_name)

    def forecast(
        self,
        candles: Candles,
        horizon: int,
        sample_count: int = 1,
    ) -> dict[str, Any]:
        """Run a Kronos forecast on validated candles.

        Returns a dict with trajectories, confidence, probability_up, bands,
        terminal range, and timestamps.
        """
        self._load()

        x_timestamp, y_timestamp = forecast_timestamps(candles, horizon)

        x_ts_list = [ts.isoformat() for ts in x_timestamp.tolist()]
        y_ts_list = [ts.isoformat() for ts in y_timestamp.tolist()]

        closes = candles.closes
        last_close = closes[-1]
        mean = np.mean(closes)
        std = np.std(closes)
        if std < 1e-8:
            raise ValueError("price series is flat (std approaches zero); forecast degenerate")

        norm_closes = [(c - mean) / std for c in closes]

        df = pd.DataFrame(
            {"close": norm_closes},
            index=x_timestamp,
        )

        result = self._predictor.predict(
            df,
            x_timestamp=x_ts_list,
            y_timestamp=y_ts_list,
            return_samples=True,
            num_samples=sample_count,
        )

        mean_path = result.get("mean_path", result.get("pred_mean", []))
        if not mean_path:
            mean_path = list(result) if isinstance(result, (list, tuple)) else []

        mean_path = [float(v) * std + mean for v in mean_path]

        trajectories = result.get("samples", result.get("trajectories", []))
        if trajectories:
            trajectories = [
                [float(v) * std + mean for v in row]
                for row in trajectories
            ]

        terminals = [row[-1] for row in trajectories] if trajectories else [mean_path[-1]]
        terminals_arr = np.array(terminals, dtype=np.float64)
        lower = float(np.quantile(terminals_arr, 0.05)) if len(terminals_arr) else mean_path[-1]
        upper = float(np.quantile(terminals_arr, 0.95)) if len(terminals_arr) else mean_path[-1]
        probability_up = float((terminals_arr > last_close).mean()) if len(terminals_arr) else 0.5
        confidence = int(round(probability_up * 100))

        change = mean_path[-1] - last_close
        direction = "UP" if change > 0 else ("DOWN" if change < 0 else "FLAT")

        return {
            "model": self._model_name,
            "last_close": round(last_close, 8),
            "mean_path": [round(v, 8) for v in mean_path],
            "predicted_change": round(change, 6),
            "direction": direction,
            "trajectories": trajectories,
            "confidence": confidence,
            "probability_up": round(probability_up, 4),
            "distribution_valid": sample_count >= 2,
            "confidence_90": [
                [round(v, 8) for v in []],
                [round(v, 8) for v in []],
            ],
            "terminal_low": round(lower, 8),
            "terminal_high": round(upper, 8),
            "timestamps": y_ts_list,
            "lookback": len(candles),
            "horizon": horizon,
            "sample_count": sample_count,
            "frequency_seconds": int(
                _infer_frequency(candles.frame.index).total_seconds()
            ),
        }


# Global engine instance (lazy-loaded)
_engine: KronosEngine | None = None
_engine_lock = threading.Lock()


def get_engine(model_variant: str | None = None) -> KronosEngine:
    """Get the global Kronos engine, creating it on first use."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = KronosEngine(model_variant=model_variant)
    return _engine