"""
Checkpoint Resume Service
Crash recovery with state persistence.
Inspired by TradingAgents LangGraph checkpoint system.

Features:
- Checkpoint state after each agent node
- Resume from last successful step
- Per-ticker SQLite databases
- `--checkpoint` flag to enable
- `--clear-checkpoints` to reset
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json
import sqlite3
import structlog

logger = structlog.get_logger(__name__)


class CheckpointService:
    """
    Checkpoint Resume Service - Crash recovery for long-running analyses.
    
    How it works:
    1. Enable checkpointing with --checkpoint flag
    2. State saved after each agent node completes
    3. On crash, resume from last successful step
    4. Per-ticker SQLite databases for isolation
    5. Auto-clear on successful completion
    
    Use cases:
    - Long-running multi-agent debates
    - Swarm factor research (100+ factors)
    - Backtest runs with many assets
    - Any analysis taking >5 minutes
    """

    def __init__(self):
        self.enabled = False
        self.checkpoint_dir = Path.home() / ".jasper-trades" / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Checkpoint Service initialized (dir: {self.checkpoint_dir})")

    def enable(self):
        """Enable checkpointing"""
        self.enabled = True
        logger.info("Checkpointing enabled")

    def disable(self):
        """Disable checkpointing"""
        self.enabled = False
        logger.info("Checkpointing disabled")

    def save_checkpoint(
        self,
        ticker: str,
        step: str,
        state: Dict[str, Any],
        run_id: Optional[str] = None,
    ):
        """
        Save checkpoint state.
        
        Args:
            ticker: Ticker symbol (e.g., "AAPL")
            step: Current step name
            state: State to persist
            run_id: Optional run identifier
        """
        if not self.enabled:
            return
        
        # Get per-ticker database
        db_path = self.checkpoint_dir / f"{ticker.replace('.', '_')}.db"
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                step TEXT NOT NULL,
                state JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Save checkpoint
        state_json = json.dumps(state, default=str)
        
        cursor.execute('''
            INSERT INTO checkpoints (run_id, step, state)
            VALUES (?, ?, ?)
        ''', (run_id, step, state_json))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Checkpoint saved: {ticker}/{step}")

    def load_checkpoint(
        self,
        ticker: str,
        run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Load last checkpoint for ticker.
        
        Returns:
            State dict or None if no checkpoint exists
        """
        db_path = self.checkpoint_dir / f"{ticker.replace('.', '_')}.db"
        
        if not db_path.exists():
            return None
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        query = "SELECT step, state FROM checkpoints"
        params = []
        
        if run_id:
            query += " WHERE run_id = ?"
            params.append(run_id)
        
        query += " ORDER BY created_at DESC LIMIT 1"
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        step, state_json = row
        state = json.loads(state_json)
        
        logger.info(f"Checkpoint loaded: {ticker}/{step}")
        
        return {
            "step": step,
            "state": state,
        }

    def clear_checkpoints(self, ticker: Optional[str] = None) -> int:
        """
        Clear checkpoints.
        
        Args:
            ticker: Specific ticker or None for all
        
        Returns:
            Number of checkpoints cleared
        """
        cleared = 0
        
        if ticker:
            db_path = self.checkpoint_dir / f"{ticker.replace('.', '_')}.db"
            if db_path.exists():
                db_path.unlink()
                cleared = 1
                logger.info(f"Cleared checkpoints for {ticker}")
        else:
            # Clear all
            for db_file in self.checkpoint_dir.glob("*.db"):
                db_file.unlink()
                cleared += 1
            
            logger.info(f"Cleared {cleared} checkpoint databases")
        
        return cleared

    def get_checkpoint_status(self, ticker: str) -> Dict[str, Any]:
        """
        Get checkpoint status for ticker.
        
        Returns:
            Checkpoint info or None
        """
        db_path = self.checkpoint_dir / f"{ticker.replace('.', '_')}.db"
        
        if not db_path.exists():
            return {
                "has_checkpoint": False,
                "message": "No checkpoint found",
            }
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get latest checkpoint
        cursor.execute("SELECT run_id, step, created_at FROM checkpoints ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        
        # Get total checkpoints
        cursor.execute("SELECT COUNT(*) FROM checkpoints")
        count = cursor.fetchone()[0]
        
        conn.close()
        
        if not row:
            return {"has_checkpoint": False}
        
        return {
            "has_checkpoint": True,
            "run_id": row[0],
            "last_step": row[1],
            "created_at": row[2],
            "total_checkpoints": count,
            "db_path": str(db_path),
        }

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoint databases"""
        checkpoints = []
        
        for db_file in self.checkpoint_dir.glob("*.db"):
            ticker = db_file.stem.replace('_', '.')
            status = self.get_checkpoint_status(ticker)
            status["ticker"] = ticker
            status["db_file"] = db_file.name
            checkpoints.append(status)
        
        return checkpoints

    def cleanup_old_checkpoints(self, days: int = 7) -> int:
        """
        Remove checkpoints older than N days.
        
        Args:
            days: Age threshold
        
        Returns:
            Number removed
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0
        
        for db_file in self.checkpoint_dir.glob("*.db"):
            # Check modification time
            mtime = datetime.fromtimestamp(db_file.stat().st_mtime)
            if mtime < cutoff:
                db_file.unlink()
                removed += 1
        
        logger.info(f"Removed {removed} old checkpoints (>{days} days)")
        return removed

    def resume_from_checkpoint(
        self,
        ticker: str,
        run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resume analysis from checkpoint.
        
        Convenience method that loads checkpoint and returns resume info.
        
        Returns:
            Resume info dict or None
        """
        checkpoint = self.load_checkpoint(ticker, run_id)
        
        if not checkpoint:
            return None
        
        return {
            "status": "resuming",
            "ticker": ticker,
            "from_step": checkpoint["step"],
            "state": checkpoint["state"],
            "message": f"Resuming {ticker} from step '{checkpoint['step']}'",
        }


# Singleton instance
checkpoint_service = CheckpointService()