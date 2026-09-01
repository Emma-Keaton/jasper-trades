"""
Agent management endpoints.

Agents are the four specialized AI modules that each handle one stage of the
trading pipeline: Director (strategy), Quant (analysis), Risk (sizing),
Execution (order routing).  Starting an agent sets a per-device flag in
preferences and immediately triggers a factor sweep so the user sees a fast
response rather than waiting for the next scheduler tick.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import structlog

from app.agents import agent_registry
from app.database import get_db
from app.services.factor_trading import run_factor_sweep

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _set_agents_started(db, device_id: str, started: bool):
    """Persist the agents_started flag to the device's preferences JSON."""
    import json
    from app.models import DeviceSettings
    from sqlalchemy import select

    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    row = result.scalar_one_or_none()
    prefs: dict = {}
    if row and row.preferences:
        try:
            prefs = json.loads(row.preferences)
        except (TypeError, ValueError):
            prefs = {}
    prefs["agents_started"] = started
    if row:
        row.preferences = json.dumps(prefs)
    else:
        row = DeviceSettings(device_id=device_id, preferences=json.dumps(prefs))
        db.add(row)
    await db.commit()


async def _get_agents_started(db, device_id: str) -> bool:
    """Read the agents_started flag from preferences."""
    import json
    from app.models import DeviceSettings
    from sqlalchemy import select

    result = await db.execute(
        select(DeviceSettings).where(DeviceSettings.device_id == device_id)
    )
    row = result.scalar_one_or_none()
    if not row or not row.preferences:
        return False
    try:
        prefs = json.loads(row.preferences)
        return bool(prefs.get("agents_started", False))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_agents():
    """List all registered agents."""
    return {"agents": [agent.get_stats() for agent in agent_registry.get_all()]}


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Get agent details."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.get_stats()


@router.post("/{agent_name}/start")
async def start_agent(
    agent_name: str,
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db=Depends(get_db),
):
    """Start an agent: persist the flag, trigger an immediate factor sweep."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    device_id = (x_device_id or "").strip() or "default-device"

    # Persist the "started" flag so the scheduler respects it too
    await _set_agents_started(db, device_id, True)

    # Flip the in-memory flag
    await agent.start()

    # Trigger an immediate factor sweep for this device
    try:
        stats = await run_factor_sweep(db)
        logger.info(
            "Immediate factor sweep after agent start",
            agent=agent_name,
            device=device_id,
            traded=stats.get("traded", 0),
        )
    except Exception as exc:
        logger.warning("Immediate sweep failed", error=str(exc))
        stats = {}

    return {
        "status": "success",
        "message": f"Agent {agent_name} started",
        "sweep": stats,
    }


@router.post("/{agent_name}/stop")
async def stop_agent(
    agent_name: str,
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    db=Depends(get_db),
):
    """Stop an agent: persist the flag so the scheduler skips this device."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    device_id = (x_device_id or "").strip() or "default-device"

    await _set_agents_started(db, device_id, False)
    await agent.stop()

    return {"status": "success", "message": f"Agent {agent_name} stopped"}


@router.get("/{agent_name}/stats")
async def get_agent_stats(agent_name: str):
    """Get agent performance statistics."""
    agent = agent_registry.get(agent_name.lower())
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.get_stats()
