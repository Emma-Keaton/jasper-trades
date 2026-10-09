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

TIP_EXTRACTION_PROMPT = """You are a trading-signal extraction engine. Read the message below and decide
whether it contains ONE concrete, actionable trade signal.

Return strict JSON only:
{
  "tip": true | false,
  "symbol": "BTC" | "ETH" | "SOL" | ... (ticker only, uppercase, strip USDT/USD suffix),
  "side": "long" | "short",
  "entry": number | null,
  "stop_loss": number | null,
  "take_profit": number | null,
  "timeframe": "1m"|"5m"|"15m"|"1h"|"4h"|"1d" | null,
  "confidence": 0..1,
  "rationale": "one short sentence"
}

Rules:
- "tip": false when the message is news, commentary, a recap, or has no clear action.
- side: "long" if they say buy/long/enter long; "short" if sell/short.
- Normalise symbols like $BTC, BTC/USDT, BTCUSDT -> BTC.
- If no stop/target is given, use null; do NOT invent numbers.
- confidence reflects how explicit the signal is; a watchlist note is low confidence.

Message:
"""


class TipExtractionService:
    def __init__(self, model=None, api_key=None, keys=None):
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        if keys is None:
            from app.config import settings as app_settings
            keys = app_settings.groq_keys
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
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self._next_key(),
                default_headers={"User-Agent": "curl/8.0"},
            )
            return self._client
        except Exception as e:
            logger.warning("Groq init failed: %s", e)
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
                tip = await _groq_call(client, combined, self.model)
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
                logger.warning("Groq tip extraction failed: %s", e)
                self._client = None  # rotate to the next project key on failure
        return tips
async def _groq_call(client, prompt, model="openai/gpt-oss-120b"):
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TIP_EXTRACTION_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        msg = resp.choices[0].message
        txt = (getattr(msg, "content", "") or "").strip()
        if not txt:
            extra = getattr(msg, "model_extra", None)
            if isinstance(extra, dict):
                txt = (extra.get("reasoning") or "").strip()
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
            "entry": obj.get("entry"),
            "stop_loss": obj.get("stop_loss"),
            "take_profit": obj.get("take_profit"),
        }
    except Exception as e:
        logger.warning("Groq call failed: %s", e)
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
    return (
        f"[{d.get('source_type','?')}/{d.get('source_id','?')}] @{author}\n{text}\n\n"
        "Use the JSON schema above. Reply with JSON only."
    )


def _make_slug(symbol, side):
    return f"{symbol}-{side}"
