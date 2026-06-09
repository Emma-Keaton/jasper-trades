"""
Database Migration Script
Creates new tables for AI-Trader enhanced signal system.

Usage: cd backend && python -m app.tests.migrate_tables
"""
import asyncio
from sqlalchemy import text
from app.database import engine, async_session
from app.models import Base


async def create_new_tables():
    """Create new tables for AI-Trader signal system."""
    
    print("=" * 80)
    print("DATABASE MIGRATION: AI-Trader Enhanced Signal System")
    print("=" * 80)
    
    async with engine.begin() as conn:
        # Create ALL tables from Base (including new ones)
        print("\n📦 Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        
        # Verify new tables were created
        result = await conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name IN ('signals_enhanced', 'subscriptions', 'challenges', 'challenge_participants', 'challenge_trades')
            ORDER BY name
        """))
        created = [row[0] for row in result.fetchall()]
        
        print("\n✅ Created/verified tables:")
        for table in created:
            print(f"   - {table}")
    
    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Start backend: python -m uvicorn app.main:app --reload")
    print("2. Test API: http://localhost:8000/docs")
    print("3. Try endpoint: GET /api/v1/signals/enhanced/feed")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(create_new_tables())