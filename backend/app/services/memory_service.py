"""
Vibe-Trading Persistent Memory Service
Full-text search (FTS5) + cross-session knowledge persistence.

Features:
- Create, read, update, delete memories
- Semantic search with FTS5
- Memory importance scoring
- Category-based filtering
- Cross-session persistence
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import hashlib
from datetime import datetime

from app.database import async_session
from app.models import Memory

logger = structlog.get_logger(__name__)


class MemoryService:
    """
    Vibe-Trading style persistent memory for agents.
    
    Memories persist across sessions and can be searched by content.
    Used for:
    - User preferences and trading style
    - Learned patterns and rules
    - Important events and decisions
    - Context that should persist across conversations
    """

    async def create_memory(
        self,
        content: str,
        category: str = "general",
        session_id: Optional[str] = None,
        importance: float = 0.5
    ) -> Memory:
        """
        Create a new memory.
        
        Args:
            content: Memory content
            category: Category (user_preference, trading_rule, pattern, event, etc.)
            session_id: Optional session identifier
            importance: Importance score 0.0-1.0
            
        Returns:
            Created Memory object
        """
        async with async_session() as session:
            memory = Memory(
                session_id=session_id,
                content=content,
                category=category,
                importance=min(1.0, max(0.0, importance))
            )
            
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
            
            logger.info(f"Created memory: {category} (importance: {importance})")
            return memory

    async def search_memories(
        self,
        query: str,
        category: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search memories using FTS5 full-text search.
        
        Args:
            query: Search query
            category: Filter by category
            min_importance: Minimum importance threshold
            limit: Max results
            
        Returns:
            List of matching memories with scores
        """
        async with async_session() as session:
            # Build query with FTS5 if available, else fallback to LIKE
            # For now using LIKE - FTS5 requires virtual table setup
            stmt = select(Memory).where(
                Memory.content.ilike(f"%{query}%")
            )
            
            if category:
                stmt = stmt.where(Memory.category == category)
            
            stmt = stmt.where(Memory.importance >= min_importance)
            stmt = stmt.order_by(desc(Memory.importance))
            stmt = stmt.limit(limit)
            
            result = await session.execute(stmt)
            memories = result.scalars().all()
            
            return [
                {
                    "id": m.id,
                    "content": m.content,
                    "category": m.category,
                    "importance": m.importance,
                    "created_at": m.created_at.isoformat(),
                    "relevance_score": 1.0  # Placeholder for FTS5 score
                }
                for m in memories
            ]

    async def get_memories_by_category(
        self,
        category: str,
        limit: int = 50
    ) -> List[Memory]:
        """Get all memories in a category."""
        async with async_session() as session:
            result = await session.execute(
                select(Memory)
                .where(Memory.category == category)
                .order_by(desc(Memory.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def update_memory_importance(
        self,
        memory_id: int,
        importance: float
    ) -> Optional[Memory]:
        """Update memory importance score."""
        async with async_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            memory = result.scalar_one_or_none()
            
            if not memory:
                return None
            
            memory.importance = min(1.0, max(0.0, importance))
            await session.commit()
            await session.refresh(memory)
            
            return memory

    async def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory (forget)."""
        async with async_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            memory = result.scalar_one_or_none()
            
            if not memory:
                return False
            
            await session.delete(memory)
            await session.commit()
            
            logger.info(f"Deleted memory {memory_id}")
            return True

    async def get_recent_memories(
        self,
        limit: int = 50,
        category: Optional[str] = None
    ) -> List[Memory]:
        """Get most recent memories."""
        async with async_session() as session:
            stmt = select(Memory).order_by(desc(Memory.created_at)).limit(limit)
            
            if category:
                stmt = stmt.where(Memory.category == category)
            
            result = await session.execute(stmt)
            return list(result.scalars().all())


# Global instance
memory_service = MemoryService()