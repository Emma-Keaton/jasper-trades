"""
cTrader Signal Ingestion Service

Receives and processes trading signals from cTrader leaders for copy-trading.

Two ingestion modes:
1. Webhook (real-time) - cTrader pushes signals to our endpoint
2. Polling (fallback) - We poll cTrader API every 5-10 seconds

Architecture:
- Receives signals from cTrader OpenAPI
- Validates leader has active followers
- Converts cTrader format → internal Signal model
- Broadcasts to followers via WebSocket
- Triggers automatic copy-trading execution
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models import Signal, Follow, Portfolio
from app.services.copytrade_service import CopyTradeService

logger = structlog.get_logger(__name__)


class CTraderSignalIngestionService:
    """
    cTrader signal ingestion for copy-trading.
    
    Converts external cTrader signals into internal Signal records
    and triggers automatic copy-trading for followers.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.copytrade_service = CopyTradeService(db)
    
    # === Webhook Handler ===
    
    async def process_webhook_signal(
        self,
        webhook_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process signal from cTrader webhook.
        
        Webhook payload format (cTrader standard):
        {
            "signalId": "12345",
            "leaderAccountId": "67890",
            "symbol": "GBPUSD",
            "action": "BUY",
            "quantity": 1.0,
            "price": 1.2750,
            "stopLoss": 1.2700,
            "takeProfit": 1.2800,
            "timestamp": "2026-06-11T10:30:00Z",
            "metadata": {
                "strategy": "Trend Following",
                "confidence": 0.85
            }
        }
        
        Args:
            webhook_payload: Signal data from cTrader
            
        Returns:
            Processing result with copied count
        """
        try:
            # Extract signal data
            symbol = webhook_payload.get("symbol")
            action = webhook_payload.get("action", "BUY").lower()
            quantity = float(webhook_payload.get("quantity", 0))
            price = float(webhook_payload.get("price", 0))
            leader_account_id = webhook_payload.get("leaderAccountId")
            
            if not all([symbol, action, leader_account_id]):
                logger.error("Invalid webhook payload", payload=webhook_payload)
                return {"error": "Invalid signal payload"}
            
            # Normalize action
            if action in ["buy", "long"]:
                action = "buy"
            elif action in ["sell", "short"]:
                action = "sell"
            else:
                action = "hold"
            
            # Create internal signal
            signal = Signal(
                symbol=symbol,
                action=action,
                strength=webhook_payload.get("metadata", {}).get("confidence", 0.5),
                agent_name=f"ctrader_leader_{leader_account_id}",
                reasoning=f"cTrader signal from leader {leader_account_id}",
                signal_data=webhook_payload,
                is_public=True,
            )
            
            self.db.add(signal)
            await self.db.commit()
            await self.db.refresh(signal)
            
            logger.info(
                f"Processed cTrader webhook signal",
                signal_id=signal.id,
                symbol=symbol,
                action=action,
            )
            
            # Auto-copy to followers
            copy_result = await self._auto_copy_to_followers(signal, leader_account_id)
            
            return {
                "signal_id": signal.id,
                "symbol": symbol,
                "action": action,
                "copied_to_followers": copy_result["copied_count"],
            }
            
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            await self.db.rollback()
            return {"error": str(e)}
    
    # === Polling Service ===
    
    async def poll_leader_signals(
        self,
        leader_account_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Poll cTrader API for new signals from leaders.
        
        Call this every 5-10 seconds via APScheduler.
        
        Args:
            leader_account_ids: List of cTrader account IDs to poll
            
        Returns:
            List of processed signals
        """
        results = []
        
        for leader_id in leader_account_ids:
            try:
                # Fetch recent signals from cTrader API
                # Note: This requires cTrader API endpoint for signal history
                signals = await self._fetch_signals_from_ctrader(leader_id)
                
                for signal_data in signals:
                    result = await self.process_webhook_signal(signal_data)
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"Polling error for leader {leader_id}: {e}")
        
        return results
    
    async def _fetch_signals_from_ctrader(
        self,
        leader_account_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent signals from cTrader API.
        
        This is a placeholder - implement based on cTrader's actual API.
        
        Args:
            leader_account_id: cTrader account ID
            
        Returns:
            List of signal payloads
        """
        # TODO: Implement cTrader API call
        # Example: GET /user/accounts/{id}/signals
        logger.debug(f"Polling signals for leader {leader_account_id}")
        return []
    
    # === Auto-Copy Execution ===
    
    async def _auto_copy_to_followers(
        self,
        signal: Signal,
        leader_account_id: str,
    ) -> Dict[str, Any]:
        """
        Automatically copy signal to all active followers.
        
        Args:
            signal: Internal signal record
            leader_account_id: cTrader leader account ID
            
        Returns:
            Copy execution results
        """
        # Find all active followers of this leader
        leader_identifier = f"ctrader_leader_{leader_account_id}"
        
        result = await self.db.execute(
            select(Follow).where(
                Follow.leader_id == leader_identifier,
                Follow.active == True,
            )
        )
        follows = result.scalars().all()
        
        copied_count = 0
        failed_count = 0
        
        for follow in follows:
            try:
                # Copy signal to follower's portfolio
                copy_result = await self.copytrade_service.copy_signal(
                    signal_id=signal.id,
                    portfolio_id=follow.follower_id,
                    copy_percentage=follow.copy_percentage,
                )
                
                if "error" not in copy_result:
                    copied_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(
                    f"Copy execution error for follower {follow.follower_id}",
                    error=str(e),
                )
                failed_count += 1
        
        logger.info(
            f"Auto-copy complete",
            signal_id=signal.id,
            copied=copied_count,
            failed=failed_count,
        )
        
        return {
            "copied_count": copied_count,
            "failed_count": failed_count,
        }


# Global singleton instance
ctrader_signal_ingestion = CTraderSignalIngestionService


async def get_signal_ingestion_service(
    db: AsyncSession,
) -> CTraderSignalIngestionService:
    """Get signal ingestion service instance"""
    return CTraderSignalIngestionService(db)