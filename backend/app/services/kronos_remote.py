"""
Kronos Remote Service Client
Calls external Kronos service via HTTP (Render deployment)
Replaces local Kronos integration
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class KronosRemoteClient:
    """
    Client for remote Kronos prediction service.
    Calls external API instead of running models locally.
    """
    
    def __init__(self):
        self.base_url = settings.KRONOS_SERVICE_URL
        self.timeout = 60.0  # 60 second timeout for model loading
    
    async def predict(
        self,
        symbol: str,
        strategy: str = "cascade",
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get prediction for a single symbol from remote service.
        
        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")
            strategy: Prediction strategy (cascade, ensemble, mini, small, base)
            lookback_days: Number of historical days to analyze
            
        Returns:
            Prediction result with direction, confidence, etc.
        """
        if not self.base_url:
            logger.warning("KRONOS_SERVICE_URL not set - returning neutral prediction")
            return {
                "symbol": symbol,
                "direction": "NEUTRAL",
                "confidence": 0.0,
                "error": "Kronos service not configured",
                "strategy": "disabled"
            }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/predict/{symbol}",
                    params={
                        "strategy": strategy,
                        "lookback_days": lookback_days
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"Kronos prediction for {symbol}: {result.get('direction')} ({result.get('confidence'):.2%})")
                return result
                
        except httpx.TimeoutException:
            logger.error(f"Kronos service timeout for {symbol}")
            return {
                "symbol": symbol,
                "direction": "ERROR",
                "confidence": 0.0,
                "error": "Service timeout",
                "strategy": strategy
            }
        except Exception as e:
            logger.error(f"Kronos prediction failed for {symbol}: {e}")
            return {
                "symbol": symbol,
                "direction": "ERROR",
                "confidence": 0.0,
                "error": str(e),
                "strategy": strategy
            }
    
    async def predict_batch(
        self,
        symbols: List[str],
        strategy: str = "cascade",
        lookback_days: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get predictions for multiple symbols.
        
        Args:
            symbols: List of stock ticker symbols
            strategy: Prediction strategy
            lookback_days: Number of historical days
            
        Returns:
            Dictionary mapping symbols to predictions
        """
        if not self.base_url:
            logger.warning("KRONOS_SERVICE_URL not set - returning empty results")
            return {symbol: {"symbol": symbol, "direction": "NEUTRAL", "confidence": 0.0, "error": "Service not configured"} for symbol in symbols}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/predict/batch",
                    json={
                        "symbols": symbols,
                        "strategy": strategy,
                        "lookback_days": lookback_days
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"Kronos batch prediction for {len(symbols)} symbols")
                return result
                
        except Exception as e:
            logger.error(f"Kronos batch prediction failed: {e}")
            return {
                symbol: {"symbol": symbol, "direction": "ERROR", "confidence": 0.0, "error": str(e)}
                for symbol in symbols
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if Kronos service is healthy."""
        if not self.base_url:
            return {"status": "disabled", "url": None}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                result = response.json()
                
                return {
                    "status": "healthy",
                    "url": self.base_url,
                    "models_loaded": result.get("models_loaded", []),
                    "device": result.get("device", "unknown")
                }
                
        except Exception as e:
            logger.error(f"Kronos health check failed: {e}")
            return {
                "status": "unhealthy",
                "url": self.base_url,
                "error": str(e)
            }
    
    async def get_strategies(self) -> List[Dict[str, str]]:
        """Get list of available strategies."""
        if not self.base_url:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/strategies")
                response.raise_for_status()
                result = response.json()
                return result.get("strategies", [])
        except Exception as e:
            logger.error(f"Failed to get Kronos strategies: {e}")
            return []


# Global client instance
kronos_client = KronosRemoteClient()


async def predict_direction(
    symbol: str,
    strategy: str = "cascade",
    forecast_horizon: int = 50
) -> Dict[str, Any]:
    """
    Convenience function for Kronos predictions.
    
    Args:
        symbol: Stock ticker symbol
        strategy: Prediction strategy
        forecast_horizon: Not used (kept for API compatibility)
        
    Returns:
        Prediction result
    """
    return await kronos_client.predict(symbol, strategy, 30)


async def predict_batch_direction(
    symbols: List[str],
    strategy: str = "cascade",
    forecast_horizon: int = 50
) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function for batch Kronos predictions.
    
    Args:
        symbols: List of stock ticker symbols
        strategy: Prediction strategy
        forecast_horizon: Not used (kept for API compatibility)
        
    Returns:
        Dictionary mapping symbols to predictions
    """
    return await kronos_client.predict_batch(symbols, strategy, 30)