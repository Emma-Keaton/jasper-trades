"""Confidence scoring for signal tips.

Pipeline (per the redesign spec):
1. Try **Kronos** time-series forecast for the symbol.
   - If Kronos has enough data (a real UP/DOWN with confidence > 0), use it as
     the base confidence, boosted when Kronos' direction agrees with the tip's
     side, and penalised when it disagrees.
2. **Gemini fallback**: if Kronos lacks data (NEUTRAL / UNKNOWN / error /
   timeout) but the extracted signal is clear, fall back to the Gemini
   extraction confidence.
3. **Source hit-rate ranking**: scale the result by how many correct calls the
   source has made so far, so high-accuracy sources rank above unproven ones.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SignalTip
from app.services.kronos_remote import kronos_client

logger = logging.getLogger(__name__)

# A source needs at least this many resolved tips before its hit-rate weighs in.
MIN_RESOLVED_FOR_RANKING = 3


async def _source_hit_rate(db: AsyncSession, source_id: int) -> Tuple[float, int]:
    """Return (hit_rate in 0..1, number of resolved tips) for a source."""
    res = await db.execute(
        select(
            func.count(SignalTip.id).label("total"),
            func.sum(func.iif(SignalTip.hit == True, 1, 0)).label("wins"),  # noqa: E712
        ).where(SignalTip.source_id == source_id, SignalTip.hit.isnot(None))
    )
    row = res.one()
    total = int(row.total or 0)
    wins = int(row.wins or 0)
    if total == 0:
        return 0.0, 0
    return wins / total, total


def _kronos_has_data(pred: Dict[str, Any]) -> bool:
    """True if Kronos returned a usable directional prediction."""
    direction = (pred.get("direction") or "").upper()
    confidence = float(pred.get("confidence") or 0.0)
    return direction in ("UP", "DOWN") and confidence > 0 and not pred.get("error")


async def compute_confidence(
    symbol: str,
    side: str,
    gemini_confidence: float,
    source_id: int,
    db: AsyncSession,
) -> Tuple[float, str]:
    """
    Returns (final_confidence in 0..1, basis) where basis is one of:
    'kronos', 'gemini_fallback', 'gemini'.
    """
    # 1) Try Kronos
    try:
        pred = await kronos_client.predict(symbol, strategy="cascade", lookback_days=30)
    except Exception as e:  # noqa: BLE001
        logger.warning("Kronos predict failed for %s: %s", symbol, e)
        pred = {"direction": "ERROR", "confidence": 0.0, "error": str(e)}

    side = (side or "long").lower()
    expected_kronos_dir = "UP" if side == "long" else "DOWN"

    if _kronos_has_data(pred):
        base = float(pred.get("confidence") or 0.0)
        if pred.get("direction", "").upper() == expected_kronos_dir:
            base = min(1.0, base * 1.10)            # model agrees -> boost
        else:
            base = base * 0.60                       # model disagrees -> penalise
        basis = "kronos"
    else:
        # 2) Gemini fallback when Kronos has no data but the signal is clear
        base = max(0.0, min(1.0, float(gemini_confidence or 0.0)))
        basis = "gemini_fallback" if base >= 0.5 else "gemini"

    # 3) Rank by source hit-rate (correct calls so far)
    hit_rate, resolved = await _source_hit_rate(db, source_id)
    if resolved >= MIN_RESOLVED_FOR_RANKING:
        # 0.6 .. 1.0 multiplier: unproven-bad sources sink, accurate sources rise.
        multiplier = 0.6 + 0.4 * hit_rate
    else:
        multiplier = 0.9  # neutral until the source has a track record

    final = max(0.0, min(1.0, base * multiplier))
    return final, basis
