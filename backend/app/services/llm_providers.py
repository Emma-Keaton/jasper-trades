"""
LLM Provider registry — Groq, Gemini and NVIDIA NIM (side-by-side providers).

Each provider supports:
- ping/test of an API key (lightweight authenticated request + latency)
- listing the models the key is authorized to use
- per-agent-task model recommendations (sorted first in the picker) with a
  short rationale banner, plus safe defaults that work even when the user
  never picks a model.

Agentic tasks (the START-button agents + chat):
  director   - strategy & reasoning (Director agent)
  quant      - market analysis (Quant agent)
  risk       - risk checks (Risk agent)
  execution  - order execution commentary (Execution agent) — needs speed
  chat       - user-facing chat
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "key_prefix": "gsk_",
        "keys_url": "https://console.groq.com/keys",
        "docs": "Free tier, very fast inference.",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GEMINI_API_KEY",
        "key_prefix": "AIza",
        "keys_url": "https://aistudio.google.com/apikey",
        "docs": "Free tier via Google AI Studio.",
    },
    "nvidia": {
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_API_KEY",
        "key_prefix": "nvapi-",
        "keys_url": "https://build.nvidia.com/settings/api-keys",
        "docs": "Free tier NVIDIA NIM endpoints (build.nvidia.com).",
    },
}

# Agentic tasks and per-provider recommended model + rationale banner.
# `default_model` is used when the user never picks a model.
AGENT_TASKS: Dict[str, Dict[str, Any]] = {
    "director": {
        "label": "Director — strategy & reasoning",
        "needs": "deep reasoning",
        "recommended": {
            "groq": ("openai/gpt-oss-120b", "Best Groq reasoning model for strategy decisions"),
            "gemini": ("gemini-2.5-pro", "Strongest Gemini reasoning (free tier)"),
            "nvidia": ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "Reasoning-optimized NIM model for strategy & promotion (verified authorized)"),
        },
        "default": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    },
    "quant": {
        "label": "Quant — market analysis",
        "needs": "fast analysis",
        "recommended": {
            "groq": ("openai/gpt-oss-120b", "Balanced Groq model for analysis"),
            "gemini": ("gemini-2.5-flash", "Fast, accurate Gemini analysis"),
            "nvidia": ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "Strong NIM analysis at good speed (verified authorized)"),
        },
        "default": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    },
    "risk": {
        "label": "Risk — risk checks",
        "needs": "lightning speed, low latency",
        "recommended": {
            "groq": ("qwen/qwen3.8-27b", "Fastest Groq model — ideal for pre-trade risk gates"),
            "gemini": ("gemini-2.0-flash", "Lowest-latency Gemini model"),
            "nvidia": ("nvidia/nemotron-3.5-lightning-30b-a3b", "Speed-optimized NIM model — lightning fast risk checks (verified authorized)"),
        },
        "default": {"provider": "groq", "model": "qwen/qwen3.8-27b"},
    },
    "execution": {
        "label": "Execution — order execution",
        "needs": "lightning speed (must not slow order placement)",
        "recommended": {
            "groq": ("qwen/qwen3.8-27b", "Fastest Groq model for execution commentary"),
            "gemini": ("gemini-2.0-flash-lite", "Fastest Gemini model for execution"),
            "nvidia": ("nvidia/nemotron-3.5-lightning-30b-a3b", "Speed-optimized NIM model — keeps execution snappy (verified authorized)"),
        },
        "default": {"provider": "groq", "model": "qwen/qwen3.8-27b"},
    },
    "chat": {
        "label": "Chat — user conversations",
        "needs": "fast, conversational",
        "recommended": {
            "groq": ("openai/gpt-oss-20b", "Light Groq model for chat"),
            "gemini": ("gemini-2.0-flash", "Fast conversational Gemini"),
            "nvidia": ("z-ai/glm-5.3-flash", "Fast NIM model for chat (verified authorized)"),
        },
        "default": {"provider": "groq", "model": "openai/gpt-oss-20b"},
    },
}


def provider_info() -> Dict[str, Any]:
    """Static provider + task + recommendation metadata for the settings UI."""
    return {
        "providers": {
            name: {
                "name": p["name"],
                "keys_url": p["keys_url"],
                "docs": p["docs"],
                "key_hint": f"starts with {p['key_prefix']}" if p["key_prefix"] else "",
            }
            for name, p in PROVIDERS.items()
        },
        "tasks": {
            task: {
                "label": t["label"],
                "needs": t["needs"],
                "recommended": t["recommended"],
                "default": t["default"],
            }
            for task, t in AGENT_TASKS.items()
        },
    }


# ---------------------------------------------------------------------------
# Key ping / model listing (OpenAI-compatible /models on all three)
# ---------------------------------------------------------------------------


async def _list_models_raw(provider: str, key: str, timeout: float = 15.0) -> Dict[str, Any]:
    """GET {base_url}/models with the Bearer key. Returns models + latency."""
    p = PROVIDERS[provider]
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{p['base_url'].rstrip('/')}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        latency_ms = round((time.monotonic() - started) * 1000)
        if resp.status_code in (401, 403):
            return {"valid": False, "latency_ms": latency_ms, "models": [], "error": "key rejected (401/403)"}
        if resp.status_code != 200:
            return {"valid": False, "latency_ms": latency_ms, "models": [], "error": f"HTTP {resp.status_code}"}
        data = resp.json()
        models = sorted(
            (m.get("id") for m in data.get("data", []) if m.get("id")),
        )
        return {"valid": True, "latency_ms": latency_ms, "models": models, "error": None}
    except Exception as e:  # noqa: BLE001
        latency_ms = round((time.monotonic() - started) * 1000)
        return {"valid": False, "latency_ms": latency_ms, "models": [], "error": str(e)[:200]}


async def ping_provider(provider: str, key: str) -> Dict[str, Any]:
    """Test an API key and pull the authorized model list.

    Models are sorted with this provider's recommended models first so the
    settings picker shows the best choices at the top.
    """
    if provider not in PROVIDERS:
        return {"valid": False, "models": [], "error": f"unknown provider {provider}"}
    key = (key or "").strip()
    if not key:
        return {"valid": False, "models": [], "error": "empty key"}
    raw = await _list_models_raw(provider, key)
    if not raw["valid"]:
        return raw

    recommended_ids = {
        model for rec in AGENT_TASKS.values() for (model, _why) in [rec["recommended"].get(provider, (None, None))] if model
    }
    models = raw["models"]
    models.sort(key=lambda m: (0 if m in recommended_ids else 1, m))
    raw["recommended"] = sorted(recommended_ids & set(models))  # only authorized ones
    raw["recommended_unavailable"] = sorted(recommended_ids - set(models))  # stale/EOL picks
    raw["provider"] = provider
    return raw


async def list_models(provider: str, key: Optional[str] = None) -> Dict[str, Any]:
    """List models using an explicit key, or the env/device-configured key."""
    if key is None:
        from app.config import settings as app_settings

        key = getattr(app_settings, PROVIDERS[provider]["env_key"], None) or ""
    return await ping_provider(provider, key)


# ---------------------------------------------------------------------------
# Thin OpenAI-compatible clients for Gemini and NVIDIA NIM (same interface
# shape as GroqLLMClient) so agents can call them interchangeably.
# ---------------------------------------------------------------------------


class ProviderLLMClient:
    """Minimal OpenAI-compatible chat client for gemini / nvidia providers."""

    def __init__(self, provider: str, key: str, default_model: str):
        from openai import AsyncOpenAI

        p = PROVIDERS[provider]
        self.provider = provider
        self.default_model = default_model
        self.client = AsyncOpenAI(
            base_url=p["base_url"],
            api_key=key,
            default_headers={"User-Agent": "curl/8.0"},
        )

    async def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        resp = await self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        return msg.content or ""


# ---------------------------------------------------------------------------
# Task routing: which provider+model handles an agentic task.
# Side-by-side: a saved per-task selection wins; otherwise the task default;
# the default provider must have a key (env or device) to be usable.
# ---------------------------------------------------------------------------


def resolve_task_model(
    task: str,
    selections: Optional[Dict[str, Any]] = None,
    available_providers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Resolve provider+model for an agentic task.

    selections: {task: {"provider": ..., "model": ...}} saved per device.
    available_providers: providers with a configured key (env or device).
    Falls back to the task default (and to groq) so there is always a
    working default even when the user never picks models.
    """
    available = set(available_providers or ["groq"])
    t = AGENT_TASKS.get(task, AGENT_TASKS["chat"])
    sel = (selections or {}).get(task)
    if sel and sel.get("provider") in available and sel.get("model"):
        return {"provider": sel["provider"], "model": sel["model"], "source": "selection"}
    d = t["default"]
    if d["provider"] in available:
        return {"provider": d["provider"], "model": d["model"], "source": "default"}
    # default provider not keyed -> first available provider with its recommended model
    for prov in ("groq", "nvidia", "gemini"):
        if prov in available:
            rec = t["recommended"].get(prov)
            model = rec[0] if rec else None
            if model:
                return {"provider": prov, "model": model, "source": "fallback"}
    return {"provider": d["provider"], "model": d["model"], "source": "default"}
