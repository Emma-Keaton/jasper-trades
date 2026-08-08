"""
LLM Client (backward-compat shim) -> routes to Google Gemini 2.5 Flash.

Historically this module wrapped NVIDIA NIM. NVIDIA NIM has been suffering
from repeated overload/traffic outages, so the PRIMARY LLM is now Google
Gemini 2.5 Flash (free tier, with multi-key rotation) implemented in
`app/services/llm_service.py`.

To avoid touching every agent that does `from app.nvidia_nim import
nvidia_client`, this module re-exports `nvidia_client` as a transparent
proxy that delegates to the Gemini client when GEMINI_API_KEYS is set, and
falls back to a real NVIDIA NIM client (single key) otherwise. Agents keep
calling nvidia_client.chat_completion(...) etc. unchanged.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# NVIDIA NIM fallback (used when Gemini is unavailable at call time)
# ---------------------------------------------------------------------------


class _NVIDIANIMFallback:
    """
    Minimal NVIDIA NIM client used only when Gemini is not configured, so the
    app keeps working during migration. Implements the same public surface.
    """

    def __init__(self):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            base_url=settings.NVIDIA_BASE_URL,
            api_key=settings.NVIDIA_API_KEY or "dummy-key",
        )

    @property
    def is_configured(self) -> bool:
        return bool(settings.NVIDIA_API_KEY)

    def _get_model_for_task(self, task_type: str) -> str:
        model_map = {
            "simple_task": "nvidia/nemotron-mini-4b-instruct",
            "execution": "nvidia/nemotron-mini-4b-instruct",
            "risk_check": "nvidia/nemotron-mini-4b-instruct",
            "copy_trade": "nvidia/llama-3.1-8b-instruct",
            "analysis": "nvidia/llama-3.1-8b-instruct",
            "news_analysis": "nvidia/llama-3.1-8b-instruct",
            "sentiment": "nvidia/llama-3.1-8b-instruct",
            "portfolio": "nvidia/llama-3.3-nemotron-super-49b-v1",
            "ensemble": "openai/gpt-oss-20b",
        }
        return model_map.get(task_type, "nvidia/llama-3.3-nemotron-super-49b-v1")

    async def chat_completion(
        self,
        messages: list,
        task_type: str = "analysis",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        model = self._get_model_for_task(task_type)
        kwargs: Dict[str, Any] = dict(model=model, messages=messages, temperature=temperature)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if stream:
            kwargs["stream"] = True
        response = await self.client.chat.completions.create(**kwargs)
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
            return "".join(chunks)
        return response.choices[0].message.content or ""


    async def structured_output(
        self, messages: list, schema: Dict[str, Any], task_type: str = "analysis"
    ) -> Dict[str, Any]:
        system_hint = (
            "You are a trading analysis engine. Respond with STRICT JSON only, "
            f"matching this schema: {json.dumps(schema)}. No prose, no markdown."
        )
        full = [{"role": "system", "content": system_hint}] + list(messages)
        text = await self.chat_completion(full, task_type=task_type, temperature=0.2)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1 and e > s:
                try:
                    return json.loads(text[s : e + 1])
                except json.JSONDecodeError:
                    pass
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
        return await self.structured_output(messages, schema, task_type="risk_check")

    async def ensemble_analysis(self, messages: list, num_models: int = 5) -> Dict[str, Any]:
        import asyncio

        tasks = [
            self.chat_completion(messages, task_type="ensemble", temperature=0.7)
            for _ in range(min(num_models, 5))
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        predictions: List[Dict[str, Any]] = []
        for r in responses:
            if isinstance(r, Exception):
                continue
            try:
                p = json.loads(r) if isinstance(r, str) else r
                if isinstance(p, dict):
                    predictions.append(p)
            except json.JSONDecodeError:
                pass
        if not predictions:
            return {"action": "hold", "confidence": 0.0, "disagreement": 1.0}
        actions = [p.get("action") for p in predictions if p.get("action")]
        if not actions:
            return {"action": "hold", "confidence": 0.0, "disagreement": 1.0}
        counts: Dict[str, int] = {}
        for a in actions:
            counts[a] = counts.get(a, 0) + 1
        maj = max(counts, key=counts.get)
        conf = sum(float(p.get("confidence", 0.5)) for p in predictions) / len(predictions)
        return {
            "action": maj,
            "confidence": conf,
            "disagreement": 1.0 - counts[maj] / len(actions),
            "model_predictions": predictions,
            "total_models": len(predictions),
        }


# ---------------------------------------------------------------------------
# Transparent proxy -> Gemini-first with NVIDIA NIM runtime fallback.
#
# The primary client is Gemini 2.5 Flash (multi-key rotation) when
# GEMINI_API_KEYS is set. Every request pings Gemini first; on a call-level
# failure (network error, 429-exhaustion, timeouts) it retries the same call
# against NVIDIA NIM so the app stays responsive during Gemini outages.
# Importing this module never fails even when no keys are configured.
# ---------------------------------------------------------------------------
class _FallbackProxy:
    """Routes each call to Gemini first, falling back to NVIDIA on failure."""

    def __init__(self):
        self._gemini = None
        self._nvidia = None

    def _primary(self):
        if self._gemini is None and settings.GEMINI_API_KEYS:
            from app.services.llm_service import get_gemini_client

            client = get_gemini_client()
            if client.is_configured:
                logger.info("LLM provider = Gemini 2.5 Flash (primary, multi-key rotation)")
                self._gemini = client
        return self._gemini

    def _fallback(self):
        if self._nvidia is None and settings.NVIDIA_API_KEY:
            self._nvidia = _NVIDIANIMFallback()
        return self._nvidia

    def _route(self, name: str, *args, **kwargs):
        async def call():
            primary = self._primary()
            if primary is not None:
                try:
                    method = getattr(primary, name)
                    result = method(*args, **kwargs)
                    if hasattr(result, "__await__"):
                        result = await result
                    return result
                except Exception as e:
                    logger.warning(
                        "Gemini call failed; falling back to NVIDIA NIM",
                        method=name,
                        error=str(e)[:200],
                    )
            fallback = self._fallback()
            if fallback is None:
                if primary is not None:
                    raise RuntimeError(f"LLM call '{name}' failed and NVIDIA fallback is not configured")
                raise RuntimeError(
                    "No LLM configured: set GEMINI_API_KEYS (primary) and/or NVIDIA_API_KEY (fallback)"
                )
            method = getattr(fallback, name)
            result = method(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result
            return result

        return call()

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        if item in ("chat_completion", "structured_output", "risk_assess",
                    "ensemble_analysis", "chat", "complete"):
            return lambda *a, **k: self._route(item, *a, **k)
        # Non-callable attributes / properties
        if item == "is_configured":
            return bool(self._primary() or self._fallback())
        return getattr(self._resolve_or_raise(), item)

    def _resolve_or_raise(self):
        return self._primary() or self._fallback() or (_raise_no_llm())


def _raise_no_llm():
    raise RuntimeError("No LLM configured: set GEMINI_API_KEYS (primary) and/or NVIDIA_API_KEY (fallback)")


# Backward-compatible global singleton. All existing
# `from app.nvidia_nim import nvidia_client` imports keep working unchanged
# and now route to Gemini 2.5 Flash (primary) with NVIDIA NIM fallback.
nvidia_client = _FallbackProxy()


# Preserve the historical class name for any code that references it directly.
NVIDIANIMClient = _NVIDIANIMFallback

