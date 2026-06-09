"""
Heartbeat Notification Service
Poll-based notification system for AI agents to receive community interactions
Inspired by AI-Trader heartbeat mechanism
"""
import asyncio
import structlog
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
from pathlib import Path

logger = structlog.get_logger(__name__)


@dataclass
class Notification:
    """Notification message structure"""
    id: int
    type: str  # new_reply, new_follower, trade_copied, signal, system
    content: str
    data: Dict
    created_at: str
    read: bool = False


@dataclass
class AgentTask:
    """Task assigned to agent"""
    id: int
    type: str
    payload: Dict
    priority: str  # low, medium, high, critical
    created_at: str
    status: str = "pending"  # pending, in_progress, completed, failed


class HeartbeatService:
    """
    Heartbeat notification service for AI agents.
    
    Implements pull-based polling mechanism inspired by AI-Trader.
    Agents periodically call heartbeat endpoint to receive messages and tasks.
    
    Features:
    - Unread message tracking
    - Task queue management
    - Notification persistence
    - Multi-channel aggregation (replies, followers, trade copies, signals)
    """

    def __init__(self):
        self.enabled = True
        self.polling_interval_seconds = 60  # Recommended: 30-60s
        self.memory_file = Path("data/heartbeat_memory.json")
        self.notifications: List[Notification] = []
        self.tasks: List[AgentTask] = []
        self.notification_counter = 0
        self.task_counter = 0
        self.load_memory()
        logger.info(f"Heartbeat Service initialized (polling: {self.polling_interval_seconds}s)")

    def load_memory(self):
        """Load persisted notifications and tasks from disk"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    # Restore notifications
                    for n in data.get("notifications", []):
                        self.notifications.append(Notification(**n))
                        self.notification_counter = max(self.notification_counter, n["id"] + 1)
                    # Restore tasks
                    for t in data.get("tasks", []):
                        self.tasks.append(AgentTask(**t))
                        self.task_counter = max(self.task_counter, t["id"] + 1)
                logger.info(f"Loaded {len(self.notifications)} notifications, {len(self.tasks)} tasks from memory")
            except Exception as e:
                logger.error(f"Failed to load heartbeat memory: {e}")

    def save_memory(self):
        """Persist notifications and tasks to disk"""
        self.memory_file.parent.mkdir(exist_ok=True)
        data = {
            "notifications": [asdict(n) for n in self.notifications],
            "tasks": [asdict(t) for t in self.tasks]
        }
        with open(self.memory_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug("Heartbeat memory saved")

    async def heartbeat(self, agent_id: str, capabilities: List[str] = None) -> Dict:
        """
        Heartbeat endpoint - called by agents to poll for messages and tasks.
        
        Args:
            agent_id: Unique agent identifier
            capabilities: List of agent capabilities (e.g., ["trading-signals", "copy-trading"])
            
        Returns:
            Dict with messages, tasks, and server status
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "messages": [],
                "tasks": []
            }

        # Get unread messages for this agent
        unread_messages = [
            asdict(n) for n in self.notifications
            if not n.read and self._message_for_agent(n, agent_id)
        ]

        # Get pending tasks for this agent
        pending_tasks = [
            asdict(t) for t in self.tasks
            if t.status == "pending" and self._task_for_agent(t, agent_id, capabilities or [])
        ]

        # Mark messages as read
        for n in self.notifications:
            if not n.read and self._message_for_agent(n, agent_id):
                n.read = True

        # Update task status to in_progress
        for t in self.tasks:
            if t.status == "pending" and self._task_for_agent(t, agent_id, capabilities or []):
                t.status = "in_progress"

        # Persist read state
        self.save_memory()

        logger.info(f"Heartbeat from {agent_id}: {len(unread_messages)} messages, {len(pending_tasks)} tasks")

        return {
            "status": "ok",
            "agent_status": "online",
            "heartbeat_interval_ms": self.polling_interval_seconds * 1000,
            "messages": unread_messages,
            "tasks": pending_tasks,
            "server_time": datetime.utcnow().isoformat() + "Z",
            "unread_count": len(unread_messages),
            "pending_task_count": len(pending_tasks)
        }

    def _message_for_agent(self, notification: Notification, agent_id: str) -> bool:
        """Check if notification is relevant to agent"""
        # For now, all notifications go to all agents
        # Can be enhanced with agent-specific filtering
        return True

    def _task_for_agent(self, task: AgentTask, agent_id: str, capabilities: List[str]) -> bool:
        """Check if task is relevant to agent based on capabilities"""
        # Simple capability matching
        if not capabilities:
            return True
        # Task type should match agent capabilities
        return task.type in capabilities

    async def add_notification(self, 
                               type: str, 
                               content: str, 
                               data: Dict,
                               agent_id: Optional[str] = None) -> int:
        """
        Add a new notification to the queue.
        
        Args:
            type: Notification type (new_reply, new_follower, trade_copied, signal, system)
            content: Human-readable message content
            data: Structured data payload
            agent_id: Optional target agent (None = broadcast)
            
        Returns:
            Notification ID
        """
        self.notification_counter += 1
        notification = Notification(
            id=self.notification_counter,
            type=type,
            content=content,
            data=data,
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        self.notifications.append(notification)
        self.save_memory()
        
        logger.info(f"Notification #{notification.id} added: {type}")
        return notification.id

    async def add_task(self,
                       type: str,
                       payload: Dict,
                       priority: str = "medium",
                       agent_id: Optional[str] = None) -> int:
        """
        Add a new task to the queue.
        
        Args:
            type: Task type
            payload: Task data payload
            priority: Task priority (low, medium, high, critical)
            agent_id: Optional target agent (None = any available agent)
            
        Returns:
            Task ID
        """
        self.task_counter += 1
        task = AgentTask(
            id=self.task_counter,
            type=type,
            payload=payload,
            priority=priority,
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        self.tasks.append(task)
        self.save_memory()
        
        logger.info(f"Task #{task.id} added: {type} (priority: {priority})")
        return task.id

    # Notification type helpers
    
    async def notify_new_reply(self, signal_id: int, reply_id: int, title: str, content: str) -> int:
        """Notify about new reply to discussion/strategy"""
        return await self.add_notification(
            type="new_reply",
            content=f"New reply to: {title}",
            data={
                "signal_id": signal_id,
                "reply_id": reply_id,
                "title": title,
                "content": content
            }
        )

    async def notify_new_follower(self, follower_id: int, follower_name: str, leader_id: int) -> int:
        """Notify about new follower (copy trading)"""
        return await self.add_notification(
            type="new_follower",
            content=f"{follower_name} started following you",
            data={
                "follower_id": follower_id,
                "follower_name": follower_name,
                "leader_id": leader_id
            }
        )

    async def notify_trade_copied(self, trade: Dict, leader_id: int, copier_id: int) -> int:
        """Notify when a follower copies a trade"""
        return await self.add_notification(
            type="trade_copied",
            content=f"Trade copied: {trade.get('symbol', 'UNKNOWN')}",
            data={
                "leader_id": leader_id,
                "copier_id": copier_id,
                "trade": trade
            }
        )

    async def notify_new_signal(self, signal_id: int, signal_type: str, symbol: str) -> int:
        """Notify about new trading signal in feed"""
        return await self.add_notification(
            type="signal",
            content=f"New {signal_type} signal for {symbol}",
            data={
                "signal_id": signal_id,
                "signal_type": signal_type,
                "symbol": symbol
            }
        )

    # Query helpers
    
    def get_unread_count(self, agent_id: str) -> int:
        """Get count of unread messages for agent"""
        return sum(1 for n in self.notifications if not n.read and self._message_for_agent(n, agent_id))

    def get_pending_task_count(self, agent_id: str, capabilities: List[str] = None) -> int:
        """Get count of pending tasks for agent"""
        return sum(1 for t in self.tasks 
                  if t.status == "pending" and self._task_for_agent(t, agent_id, capabilities or []))

    def get_status(self) -> Dict:
        """Get service status"""
        return {
            "enabled": self.enabled,
            "polling_interval_seconds": self.polling_interval_seconds,
            "total_notifications": len(self.notifications),
            "unread_notifications": sum(1 for n in self.notifications if not n.read),
            "total_tasks": len(self.tasks),
            "pending_tasks": sum(1 for t in self.tasks if t.status == "pending"),
            "memory_file": str(self.memory_file)
        }

    async def cleanup_old_notifications(self, days: int = 7):
        """Remove notifications older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        original_count = len(self.notifications)
        self.notifications = [
            n for n in self.notifications 
            if datetime.fromisoformat(n.created_at.replace('Z', '+00:00')) > cutoff
        ]
        removed = original_count - len(self.notifications)
        self.save_memory()
        logger.info(f"Cleaned up {removed} old notifications (older than {days} days)")
        return removed

    async def cleanup_completed_tasks(self, days: int = 3):
        """Remove completed/failed tasks older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        original_count = len(self.tasks)
        self.tasks = [
            t for t in self.tasks 
            if t.status in ("pending", "in_progress") or 
               datetime.fromisoformat(t.created_at.replace('Z', '+00:00')) > cutoff
        ]
        removed = original_count - len(self.tasks)
        self.save_memory()
        logger.info(f"Cleaned up {removed} old tasks (older than {days} days)")
        return removed


# Singleton instance
heartbeat_service = HeartbeatService()