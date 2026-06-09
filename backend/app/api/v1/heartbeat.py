"""
Heartbeat API - Agent notification polling
Inspired by AI-Trader heartbeat mechanism
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import List, Optional, Dict
from pydantic import BaseModel
import structlog

from app.services.heartbeat_service import heartbeat_service, Notification, AgentTask

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/heartbeat", tags=["Heartbeat"])


class HeartbeatRequest(BaseModel):
    """Heartbeat request model"""
    agent_id: str
    status: str = "alive"
    capabilities: Optional[List[str]] = None


class HeartbeatResponse(BaseModel):
    """Heartbeat response model"""
    status: str
    agent_status: str
    heartbeat_interval_ms: int
    messages: List[Dict]
    tasks: List[Dict]
    server_time: str
    unread_count: int
    pending_task_count: int


class NotificationRequest(BaseModel):
    """Create notification request"""
    type: str
    content: str
    data: Dict
    agent_id: Optional[str] = None


class TaskRequest(BaseModel):
    """Create task request"""
    type: str
    payload: Dict
    priority: str = "medium"
    agent_id: Optional[str] = None


@router.post("/", response_model=HeartbeatResponse)
@router.post("/poll", response_model=HeartbeatResponse)
async def heartbeat(request: HeartbeatRequest):
    """
    Heartbeat endpoint for AI agents to poll for messages and tasks.
    
    Agents should call this endpoint every 30-60 seconds to:
    - Receive unread notifications (replies, followers, trade copies, signals)
    - Get assigned tasks
    - Update agent status to "online"
    
    **Pull-based mechanism**: Unlike WebSocket, this is a reliable pull-based
    notification system modeled after AI-Trader's heartbeat design.
    
    **Recommended polling interval**: 60 seconds (5 minutes maximum)
    """
    try:
        result = await heartbeat_service.heartbeat(
            agent_id=request.agent_id,
            capabilities=request.capabilities
        )
        
        return HeartbeatResponse(**result)
    
    except Exception as e:
        logger.error(f"Heartbeat failed for {request.agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications")
async def create_notification(request: NotificationRequest):
    """
    Create a new notification.
    
    Notifications are persisted and delivered to agents via heartbeat polling.
    """
    try:
        notification_id = await heartbeat_service.add_notification(
            type=request.type,
            content=request.content,
            data=request.data,
            agent_id=request.agent_id
        )
        
        return {
            "status": "success",
            "notification_id": notification_id,
            "message": "Notification created"
        }
    
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks")
async def create_task(request: TaskRequest):
    """
    Create a new task for agent execution.
    
    Tasks are assigned to agents based on capabilities and priority.
    """
    try:
        task_id = await heartbeat_service.add_task(
            type=request.type,
            payload=request.payload,
            priority=request.priority,
            agent_id=request.agent_id
        )
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": "Task created"
        }
    
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_heartbeat_status():
    """Get heartbeat service status"""
    return heartbeat_service.get_status()


@router.get("/unread/{agent_id}")
async def get_unread_count(agent_id: str):
    """Get unread message count for agent"""
    return {
        "agent_id": agent_id,
        "unread_count": heartbeat_service.get_unread_count(agent_id)
    }


@router.get("/tasks/pending/{agent_id}")
async def get_pending_task_count(agent_id: str, capabilities: Optional[List[str]] = Query(None)):
    """Get pending task count for agent"""
    return {
        "agent_id": agent_id,
        "pending_count": heartbeat_service.get_pending_task_count(agent_id, capabilities or [])
    }


@router.post("/cleanup")
async def cleanup_old_data(days: int = Query(7, description="Days to retain notifications"),
                           task_days: int = Query(3, description="Days to retain completed tasks")):
    """
    Clean up old notifications and tasks.
    
    - Notifications older than `days` are removed
    - Completed/failed tasks older than `task_days` are removed
    """
    try:
        notifications_removed = await heartbeat_service.cleanup_old_notifications(days)
        tasks_removed = await heartbeat_service.cleanup_completed_tasks(task_days)
        
        return {
            "status": "success",
            "notifications_removed": notifications_removed,
            "tasks_removed": tasks_removed
        }
    
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Notification type-specific endpoints

@router.post("/notifications/reply")
async def notify_reply(
    signal_id: int,
    reply_id: int,
    title: str,
    content: str
):
    """Notify about new reply to discussion/strategy"""
    notification_id = await heartbeat_service.notify_new_reply(
        signal_id=signal_id,
        reply_id=reply_id,
        title=title,
        content=content
    )
    return {"status": "success", "notification_id": notification_id}


@router.post("/notifications/follower")
async def notify_follower(
    follower_id: int,
    follower_name: str,
    leader_id: int
):
    """Notify about new follower (copy trading)"""
    notification_id = await heartbeat_service.notify_new_follower(
        follower_id=follower_id,
        follower_name=follower_name,
        leader_id=leader_id
    )
    return {"status": "success", "notification_id": notification_id}


@router.post("/notifications/trade-copied")
async def notify_trade_copied(
    trade: Dict,
    leader_id: int,
    copier_id: int
):
    """Notify when a follower copies a trade"""
    notification_id = await heartbeat_service.notify_trade_copied(
        trade=trade,
        leader_id=leader_id,
        copier_id=copier_id
    )
    return {"status": "success", "notification_id": notification_id}


@router.post("/notifications/signal")
async def notify_signal(
    signal_id: int,
    signal_type: str,
    symbol: str
):
    """Notify about new trading signal in feed"""
    notification_id = await heartbeat_service.notify_new_signal(
        signal_id=signal_id,
        signal_type=signal_type,
        symbol=symbol
    )
    return {"status": "success", "notification_id": notification_id}