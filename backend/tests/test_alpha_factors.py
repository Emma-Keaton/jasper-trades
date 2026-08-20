"""Tests for the imported 452-factor alpha zoo + strategy advisor."""
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.alpha_factor_service import AlphaFactorService

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def service():
    return AlphaFactorService()


@pytest.fixture(scope="module")
def panel():
    n = 300
    idx = pd.date_range(end="2026-08-19", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(42)
    close = pd.DataFrame({"BTC": 60000 + np.cumsum(rng.normal(0, 800, n))}, index=idx)
    open_ = close + pd.Series(rng.normal(0, 50, n), index=idx).to_frame("BTC")
    high = (
        pd.concat([open_, close], axis=1).max(axis=1).to_frame("BTC")
        + pd.Series(np.abs(rng.normal(0, 100, n)), index=idx).to_frame("BTC")
    )
    low = (
        pd.concat([open_, close], axis=1).min(axis=1).to_frame("BTC")
        - pd.Series(np.abs(rng.normal(0, 100, n)), index=idx).to_frame("BTC")
    )
    volume = pd.DataFrame({"BTC": rng.integers(1000, 50000, n)}, index=idx)
    return {
        "close": close,
        "open": open_,
        "high": high,
        "low": low,
        "volume": volume,
    }


def test_catalog_has_452_real_factors(service):
    assert len(service.alpha_factors) == 452
    zoos = {f["zoo"] for f in service.alpha_factors}
    assert zoos == {"academic", "alpha101", "gtja191", "qlib158"}


def test_catalog_matches_committed_json(service):
    with open(BACKEND_ROOT / "data" / "alpha_factors.json", encoding="utf-8") as fh:
        raw = json.load(fh)
    assert len(raw) == 452
    assert raw[0]["module"].endswith("carhart_mom")
    assert all(e["has_compute"] for e in raw)


def test_factor_metadata_mapped(service):
    factor = service.alpha_factors[0]
    assert "id" in factor
    assert "category" in factor
    assert "difficulty" in factor
    assert "description" in factor
    assert "columns_required" in factor
    assert "module" in factor


@pytest.mark.asyncio
async def test_compute_factor_on_panel(service, panel):
    res = await service.compute_factor("qlib158_ma20", panel)
    assert "error" not in res
    assert res["factor_id"] == "qlib158_ma20"
    assert "BTC" in res["values"]

    res2 = await service.compute_factor("alpha101_006", panel)
    assert "error" not in res2
    assert "BTC" in res2["values"]


@pytest.mark.asyncio
async def test_advise_for_trade(service, panel):
    adv = await service.advise_for_trade("BTC", panel, side="buy", top=10)
    assert adv["computable"] > 100
    assert adv["total_candidates"] == 452
    assert adv["recommended_direction"] in {"long", "short", "neutral"}
    assert "strategy" in adv
    assert adv["strategy"]["theme"]
    assert len(adv["factors"]) <= 10
    # factors are ranked by |z-score| descending
    scores = [f["abs_score"] for f in adv["factors"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_advise_missing_columns(service, panel):
    partial = {"close": panel["close"]}
    adv = await service.advise_for_trade("BTC", partial, side="buy", top=10)
    # Volume/OHLC factors silently drop out; close-only factors remain.
    assert adv["computable"] >= 1


def test_unknown_factor(service):
    res = asyncio.run(service.compute_factor("does_not_exist", {}))
    assert "error" in res