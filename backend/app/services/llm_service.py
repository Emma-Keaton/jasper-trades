"""
LLM Service - Groq free tier with multi-key rotation.

Uses Groq's OpenAI-compatible endpoint via the already-installed `openai`
SDK (AsyncOpenAI) -> zero new dependencies. A User-Agent header is required
or Groq's edge returns 403. Reasoning models (gpt-oss-*) emit a separate
`reasoning` field; we fall back to it when `content` is empty.

Design:
- Public interface mirrors the old NVIDIANIMClient (chat_completion,
  risk_assess, ensemble_analysis, structured outputs, plus raw chat/complete)
  so every agent swaps transparently.
- Model routing maps task types onto qwen/qwen3.8-27b (fast) and
  openai/gpt-oss-120b (analysis/deep).
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog
from openai import AsyncOpenAI

from app.config import settings

logger = structlog.get_logger(__name__)

GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_HEADERS = {"User-Agent": "curl/8.0"}

_DEFAULT_FAST = "qwen/qwen3.8-27b"
_DEFAULT_BALANCED = "openai/gpt-oss-120b"
_DEFAULT_SMART = "openai/gpt-oss-120b"
_DEFAULT_DEEP = "openai/gpt-oss-120b"
_DEFAULT_ALT = "openai/gpt-oss-20b"


def _message_text(message: Any) -> str:
    text = getattr(message, "content", "") or ""
    if not text:
        reasoning = getattr(message, "reasoning", None)
        if not reasoning:
            extra = getattr(message, "model_extra", None)
            if isinstance(extra, dict):
                reasoning = extra.get("reasoning")
        if reasoning:
            text = reasoning
    return text


@dataclass
class _KeyState:
    index: int
    api_key: str
    client: AsyncOpenAI
    cooldown_until: float = 0.0
    consecutive_429s: int = 0
    requests_made: int = 0


def _parse_keys(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    keys: List[str] = []
    for part in raw.replace("\n", ",").split(","):
        k = part.strip()
        if k:
            keys.append(k)
    return keys


class GroqKeyRotator:
    """Round-robin multi-key rotator with cooldown-on-429 failover."""

    def __init__(self, keys: List[str], base_url: str = GROQ_OPENAI_BASE_URL):
        if not keys:
            raise ValueError(
                "No Groq API keys configured. Set GROQ_API_KEY "
                "(comma-separated)."
            )
        self.base_url = base_url
        self._states: List[_KeyState] = [
            _KeyState(
                index=i,
                api_key=k,
                client=AsyncOpenAI(
                    base_url=base_url, api_key=k, default_headers=_GROQ_HEADERS
                ),
            )
            for i, k in enumerate(keys)
        ]
        self._cursor = 0
        self._lock = asyncio.Lock()
        self._history: deque = deque(maxlen=100)

    @property
    def num_keys(self) -> int:
        return len(self._states)

    async def acquire(self) -> _KeyState:
        while True:
            async with self._lock:
                now = time.time()
                for _ in range(len(self._states)):
                    self._cursor = (self._cursor + 1) % len(self._states)
                    if self._states[self._cursor].cooldown_until <= now:
                        state = self._states[self._cursor]
                        state.requests_made += 1
                        self._history.append(
                            {"ts": now, "key_index": state.index, "cooldowns": state.consecutive_429s}
                        )
                        return state
            next_wake = min(s.cooldown_until for s in self._states)
            wait_for = max(0.05, next_wake - time.time())
            logger.warning("All Groq keys cooling down; waiting", wait_seconds=round(wait_for, 2))
            await asyncio.sleep(wait_for)

    def mark_rate_limited(self, state: _KeyState, retry_after: Optional[float] = None) -> None:
        cooldown = float(retry_after) if retry_after and retry_after > 0 else 60.0
        state.consecutive_429s += 1
        cooldown = min(cooldown * state.consecutive_429s, 600.0)
        state.cooldown_until = time.time() + cooldown
        logger.warning("Groq key cooling down", key_index=state.index, cooldown_seconds=round(cooldown, 1))

    def mark_success(self, state: _KeyState) -> None:
        if state.consecutive_429s:
            state.consecutive_429s = 0
        state.cooldown_until = 0.0

    def status(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [
            {
                "key_index": s.index,
                "requests_made": s.requests_made,
                "cooling_down": s.cooldown_until > now,
                "cooldown_remaining_s": max(0, round(s.cooldown_until - now, 1)),
                "consecutive_429s": s.consecutive_429s,
            }
            for s in self._states
        ]


class GroqLLMClient:
    def __init__(self, keys: Optional[List[str]] = None):
        resolved = settings.groq_keys if keys is None else keys
        if not resolved:
            self.rotator: Optional[GroqKeyRotator] = None
            self._configured = False
            logger.warning("Groq LLM not configured (GROQ_API_KEY empty). LLM features disabled.")
            return
        self.rotator = GroqKeyRotator(resolved)
        self._configured = True
        logger.info("Groq LLM client initialized", keys=self.rotator.num_keys)

    @property
    def is_configured(self) -> bool:
        return self._configured

    def _get_model_for_task(self, task_type: str) -> str:
        model_map = {
            "simple_task": settings.MODEL_FREE_FAST or _DEFAULT_FAST,
            "execution": settings.MODEL_FAST or _DEFAULT_FAST,
            "risk_check": settings.MODEL_FREE_FAST or _DEFAULT_FAST,
            "copy_trade": settings.MODEL_BALANCED or _DEFAULT_BALANCED,
            "analysis": settings.MODEL_SMART_FREE or _DEFAULT_SMART,
            "news_analysis": settings.MODEL_SMART_FREE or _DEFAULT_SMART,
            "sentiment": settings.MODEL_SMART_FREE or _DEFAULT_SMART,
            "portfolio": settings.MODEL_DEEP or _DEFAULT_DEEP,
            "ensemble": settings.MODEL_ALTERNATIVE or _DEFAULT_ALT,
        }
        return model_map.get(task_type, settings.MODEL_BALANCED or _DEFAULT_BALANCED)

    async def _chat_with_rotation(
        self,
        model: str,
        messages: list,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self._configured or self.rotator is None:
            raise RuntimeError("Groq LLM client is not configured")

        last_error: Optional[Exception] = None
        max_attempts = max(self.rotator.num_keys * 2, 4)
        for attempt in range(max_attempts):
            state = await self.rotator.acquire()
            try:
                kwargs: Dict[str, Any] = dict(model=model, messages=messages, temperature=temperature)
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens
                if response_format is not None:
                    kwargs["response_format"] = response_format
                if stream:
                    kwargs["stream"] = True

                response = await state.client.chat.completions.create(**kwargs)

                if stream:
                    chunks: List[str] = []
                    async for chunk in response:
                        delta = (
                            chunk.choices[0].delta.content
                            if chunk.choices and chunk.choices[0].delta
                            else None
                        )
                        if delta:
                            chunks.append(delta)
                    text = "".join(chunks)
                else:
                    text = _message_text(response.choices[0].message)

                self.rotator.mark_success(state)
                return text

            except Exception as e:
                last_error = e
                msg = str(e).lower()
                is_rate_limit = (
                    "429" in msg
                    or "rate" in msg
                    or ("quota" in msg and "exhausted" in msg)
                    or "resource" in msg
                )
                if is_rate_limit:
                    retry_after = getattr(e, "retry_after", None)
                    self.rotator.mark_rate_limited(state, retry_after)
                    logger.warning("Groq rate limited; rotating to next key", attempt=attempt + 1)
                else:
                    logger.warning("Groq call failed; retrying with next key", attempt=attempt + 1, error=str(e)[:200])
        if last_error is not None:
            raise last_error
        raise RuntimeError("Groq call failed after exhausting all retries")

    async def chat_completion(
        self,
        messages: list,
        task_type: str = "analysis",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        model = self._get_model_for_task(task_type)
        return await self._chat_with_rotation(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, stream=stream,
        )

    async def chat(
        self,
        model: Optional[str] = None,
        messages: Optional[list] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        return await self._chat_with_rotation(
            model=model or self._get_model_for_task("analysis"),
            messages=messages or [], temperature=temperature, max_tokens=max_tokens,
        )

    async def complete(
        self,
        model: Optional[str] = None,
        messages: Optional[list] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        return await self.chat(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)

    async def structured_output(
        self,
        messages: list,
        schema: Dict[str, Any],
        task_type: str = "analysis",
    ) -> Dict[str, Any]:
        model = self._get_model_for_task(task_type)
        system_hint = (
            "You are a trading analysis engine. Respond with STRICT JSON only, "
            f"matching this schema: {json.dumps(schema)}. No prose, no markdown."
        )
        full_messages = [{"role": "system", "content": system_hint}] + list(messages)
        try:
            text = await self._chat_with_rotation(
                model=model, messages=full_messages, temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception:
            text = await self._chat_with_rotation(
                model=model, messages=full_messages, temperature=0.2
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            logger.error("Groq structured_output JSON parse failed", raw=text[:500])
            return {}

    async def risk_assess(self, messages: list) -> Dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "risk_level": {"type": "string"},
                "approval": {"type": "boolean"},
                "concerns": {"type": "string"},
                "confidence": {"type": "number"},
            },
        }
        result = await self.structured_output(messages, schema, task_type="risk_check")
        if not result:
            return {
                "risk_level": "high",
                "approval": False,
                "concerns": "Unable to assess (LLM unavailable)",
                "confidence": 0.0,
            }
        return result

    async def ensemble_analysis(self, messages: list, num_models: int = 5) -> Dict[str, Any]:
        if not self._configured or self.rotator is None:
            return {"action": "hold", "confidence": 0.0, "disagreement": 1.0}
        model = self._get_model_for_task("ensemble")

        async def run_one() -> Optional[str]:
            return await self._chat_with_rotation(model=model, messages=messages, temperature=0.7)

        tasks = [run_one() for _ in range(min(num_models, 5))]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        predictions: List[Dict[str, Any]] = []
        for r in responses:
            if isinstance(r, Exception):
                logger.error("Ensemble member failed", error=str(r))
                continue
            try:
                pred = json.loads(r) if isinstance(r, str) else r
                if isinstance(pred, dict):
                    predictions.append(pred)
            except json.JSONDecodeError:
                continue

        if not predictions:
            return {"action": "hold", "confidence": 0.0, "disagreement": 1.0}

        actions = [p.get("action") for p in predictions if p.get("action")]
        confidences = [float(p.get("confidence", 0.5)) for p in predictions if p.get("confidence") is not None]
        if not actions:
            return {"action": "hold", "confidence": 0.0, "disagreement": 1.0}

        action_counts: Dict[str, int] = {}
        for action in actions:
            action_counts[action] = action_counts.get(action, 0) + 1
        majority_action = max(action_counts, key=action_counts.get)
        agreement_pct = action_counts[majority_action] / len(actions)
        disagreement = 1.0 - agreement_pct
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        final_confidence = avg_confidence * agreement_pct

        return {
            "action": majority_action,
            "confidence": final_confidence,
            "disagreement": disagreement,
            "model_predictions": predictions,
            "total_models": len(predictions),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self._configured,
            "provider": "groq",
            "base_url": GROQ_OPENAI_BASE_URL,
            "keys": self.rotator.status() if self._configured and self.rotator else [],
        }


_groq_client: Optional[GroqLLMClient] = None


def get_groq_client() -> GroqLLMClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqLLMClient()
    return _groq_client


class _LazyGroqProxy:
    def __getattr__(self, item):
        return getattr(get_groq_client(), item)


groq_client = _LazyGroqProxy()  # type: ignore[assignment]
