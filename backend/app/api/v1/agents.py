"""
Agent management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
import structlog

from app.agents import agent_registry
from app.agents.base import BaseAgent

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("")
async def list_agents():
    """List all registered agents."""
    agents = []
    for agent in agent_registry.get_all():
        agents.append(agent.get_stats())
    
    return {"agents": agents}


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Get agent details."""
    agent = agent_registry.get(agent_name.lower())
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent.get_stats()


@router.post("/{agent_name}/start")
async def start_agent(agent_name: str):
    """Start an agent."""
    agent = agent_registry.get(agent_name.lower())
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await agent.start()
    
    return {"status": "success", "message": f"Agent {agent_name} started"}


@router.post("/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop an agent."""
    agent = agent_registry.get(agent_name.lower())
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await agent.stop()
    
    return {"status": "success", "message": f"Agent {agent_name} stopped"}


@router.get("/{agent_name}/stats")
async def get_agent_stats(agent_name: str):
    """Get agent performance statistics."""
    agent = agent_registry.get(agent_name.lower())
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent.get_stats()
