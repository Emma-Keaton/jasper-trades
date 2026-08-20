"""Tip extraction and scoring for signal sources.

For each raw SignalDraft we ask the LLM whether the draft contains a concrete,
tradeable tip.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TIP_EXTRACTION_PROMPT = """You are a trading-signal extraction engine. ..."""


class TipExtractionService:
    def __init__(self, model=None, api_key=None, keys=None):
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if keys is None:
            from app.config import settings as app_settings
            keys = app_settings.gemini_keys
        self.keys = list(keys) if keys else []
        self.api_key = api_key or self.keys[0] if self.keys else None
        self._client = None
        self._cursor = 0

    def _next_key(self):
        """Round-robin across the configured project keys."""
        if not self.keys:
            return None
        key = self.keys[self._cursor % len(self.keys)]
        self._cursor += 1
        return key

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.keys:
            return None
        try:
            from google import genai
            self._client = genai.Client(api_key=self._next_key())
            return self._client
        except Exception as e:
            logger.warning("Gemini init failed: %s", e)
            return None

    async def extract_tips(self, drafts, batch=5):
        if not drafts:
            return []
        client = self._get_client()
        if client is None:
            return _fallback_extract(drafts)
        tips = []
        for i in range(0, len(drafts), batch):
            chunk = drafts[i:i+batch]
            combined = "\n\n---\n\n".join(_prep_prompt(d) for d in chunk)
            try:
                tip = await _gemini_call(client, combined)
                if tip:
                    src = chunk[0]
                    tip.update({
                        "source_type": src.get("source_type"),
                        "source_id": src.get("source_id"),
                        "text": src.get("content") or src.get("title"),
                        "url": src.get("url"),
                        "created_at": src.get("created_at"),
                    })
                    tips.append(tip)
            except Exception as e:
                logger.warning("Gemini tip extraction failed: %s", e)
                self._client = None  # rotate to the next project key on failure
        return tips
async def _gemini_call(client, prompt):
    try:
        resp = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        txt = (resp.text or "").strip()
        if not txt:
            return None
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if not m:
            return None
        obj = json.loads(m.group(0))
        if obj.get("tip") is False:
            return None
        if "symbol" not in obj:
            return None
        side = (obj.get("side") or "long").lower()
        sym = (obj.get("symbol") or "").upper().strip()
        conf = float(obj.get("confidence") or 0.0)
        return {
            "slug": _make_slug(sym, side),
            "symbol": sym,
            "side": side if side in ("long", "short") else ("long" if side == "buy" else "short"),
            "timeframe": obj.get("timeframe"),
            "confidence": max(0.0, min(1.0, conf)),
            "rationale": obj.get("rationale"),
        }
    except Exception as e:
        logger.warning("Gemini call failed: %s", e)
        return None


def _fallback_extract(drafts):
    out = []
    for d in drafts:
        txt = ((d.get("content") or "") + " " + (d.get("title") or "")).upper()
        keywords = [
            ("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL"),
            ("DOGEUSDT", "DOGE"), ("BNBUSDT", "BNB"), ("XRPUSDT", "XRP"),
        ]
        for fut, base in keywords:
            if base in txt:
                side = "long" if any(k in txt for k in ("LONG", "BUY", "BULLISH", "MOON", "PUMP")) else "short"
                out.append({
                    "source_type": d.get("source_type"),
                    "source_id": d.get("source_id"),
                    "slug": _make_slug(fut, side),
                    "symbol": fut,
                    "side": side,
                    "timeframe": "4h",
                    "confidence": 0.55,
                    "rationale": "keyword-match fallback",
                    "text": d.get("content") or d.get("title"),
                    "url": d.get("url"),
                    "created_at": d.get("created_at"),
                })
                break
    return out


def _prep_prompt(d):
    text = d.get("content") or d.get("title") or ""
    author = d.get("author") or "unknown"
    return f"[{d.get('source_type','?')}/{d.get('source_id','?')}] @{author}\n{text}"


def _make_slug(symbol, side):
    return f"{symbol}-{side}"
