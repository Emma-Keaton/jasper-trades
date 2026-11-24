"""
LLM Providers API — key ping/test, authorized model listing, and per-agent
model selection for the side-by-side providers (Groq, Gemini, NVIDIA NIM).

Endpoints:
  GET  /api/v1/llm/providers         provider/task metadata + configured status + selections
  POST /api/v1/llm/test-key          ping a key and list its authorized models (recommended first)
  GET  /api/v1/llm/models?provider=  list models with the saved/env key
  POST /api/v1/llm/key               save a provider API key (encrypted, per device)
  GET  /api/v1/llm/key-status        which providers have a key (env or device)
  POST /api/v1/llm/selection         save {task, provider, model}
  GET  /api/v1/llm/selection         current selections merged with defaults + resolved routing
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.device_auth import require_device_id
from app.models import DeviceSettings
from app.config import settings as app_settings
from app.services.encryption import EncryptionHelper
from app.services.llm_providers import (
    AGENT_TASKS,
    PROVIDERS,
    list_models,
    ping_provider,
    provider_info,
    resolve_task_model,
)

router = APIRouter(prefix="/llm", tags=["llm-providers"])

# DeviceSettings column that stores each provider's encrypted key.
_PROVIDER_KEY_COLUMN = {
    "groq": "groq_key",
    "gemini": "gemini_key",
    "nvidia": "nvidia_key",
}


def _env_key(provider: str) -> Optional[str]:
    return getattr(app_settings, PROVIDERS[provider]["env_key"], None)


def _device_id_dep(x_device_id: Optional[str] = Header(None, alias="X-Device-ID")) -> str:
    return require_device_id(x_device_id)


async def _device_row(db: AsyncSession, device_id: str) -> Optional[DeviceSettings]:
    res = await db.execute(select(DeviceSettings).where(DeviceSettings.device_id == device_id))
    return res.scalar_one_or_none()


async def _device_key(db: AsyncSession, device_id: str, provider: str) -> Optional[str]:
    row = await _device_row(db, device_id)
    if row is None:
        return None
    enc = getattr(row, _PROVIDER_KEY_COLUMN[provider], None)
    if not enc:
        return None
    try:
        return EncryptionHelper().decrypt(enc)
    except Exception:  # noqa: BLE001
        return None


async def _configured_providers(db: AsyncSession, device_id: str) -> Dict[str, bool]:
    status = {}
    for prov in PROVIDERS:
        status[prov] = bool(_env_key(prov) or await _device_key(db, device_id, prov))
    return status


class TestKeyRequest(BaseModel):
    provider: str
    key: str


class SaveKeyRequest(BaseModel):
    provider: str
    key: str


class SelectionRequest(BaseModel):
    task: str
    provider: str
    model: str



@router.get("/providers")
async def get_providers(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    info = provider_info()
    info["configured"] = await _configured_providers(db, device_id)
    row = await _device_row(db, device_id)
    selections: Dict[str, Any] = {}
    if row and row.llm_model_selections:
        try:
            selections = json.loads(row.llm_model_selections)
        except Exception:  # noqa: BLE001
            selections = {}
    info["selections"] = selections
    available = [p for p, ok in info["configured"].items() if ok] or ["groq"]
    info["resolved"] = {
        task: resolve_task_model(task, selections, available) for task in AGENT_TASKS
    }
    return info


@router.post("/test-key")
async def test_key(req: TestKeyRequest):
    """Ping the provider with this key and return authorized models.

    Recommended models for each agentic task are sorted to the top so the
    user avoids stale/deprecated/slow models for speed-critical tasks.
    """
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider {req.provider}")
    return await ping_provider(req.provider, req.key)


@router.get("/models")
async def get_models(
    provider: str,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider {provider}")
    key = await _device_key(db, device_id, provider) or _env_key(provider) or ""
    return await list_models(provider, key or None)


@router.post("/key")
async def save_key(
    req: SaveKeyRequest,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider {req.provider}")
    key = (req.key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    row = await _device_row(db, device_id)
    if row is None:
        row = DeviceSettings(device_id=device_id)
        db.add(row)
    setattr(row, _PROVIDER_KEY_COLUMN[req.provider], EncryptionHelper().encrypt(key))
    await db.commit()
    return {"success": True, "provider": req.provider, "configured": True}


@router.get("/key-status")
async def key_status(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    status = await _configured_providers(db, device_id)
    return {
        "providers": status,
        "env": {p: bool(_env_key(p)) for p in PROVIDERS},
    }



@router.post("/selection")
async def save_selection(
    req: SelectionRequest,
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    if req.task not in AGENT_TASKS:
        raise HTTPException(status_code=400, detail=f"unknown task {req.task}")
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider {req.provider}")
    row = await _device_row(db, device_id)
    if row is None:
        row = DeviceSettings(device_id=device_id)
        db.add(row)
    try:
        selections = json.loads(row.llm_model_selections) if row.llm_model_selections else {}
    except Exception:  # noqa: BLE001
        selections = {}
    selections[req.task] = {"provider": req.provider, "model": req.model}
    row.llm_model_selections = json.dumps(selections)
    await db.commit()
    return {"success": True, "task": req.task, "selection": selections[req.task]}


@router.get("/selection")
async def get_selection(
    device_id: str = Depends(_device_id_dep),
    db: AsyncSession = Depends(get_db),
):
    row = await _device_row(db, device_id)
    selections: Dict[str, Any] = {}
    if row and row.llm_model_selections:
        try:
            selections = json.loads(row.llm_model_selections)
        except Exception:  # noqa: BLE001
            selections = {}
    configured = await _configured_providers(db, device_id)
    available = [p for p, ok in configured.items() if ok] or ["groq"]
    return {
        "selections": selections,
        "defaults": {t: AGENT_TASKS[t]["default"] for t in AGENT_TASKS},
        "resolved": {t: resolve_task_model(t, selections, available) for t in AGENT_TASKS},
    }
