"""
Hybrid Kronos Service: Local + Cloud Fallback

Routes predictions to:
1. Local Kronos-mini (default, 4GB optimized)
2. Hugging Face Inference API (free tier fallback)
3. Google Colab GPU server with 3-model ensemble (unlimited free fallback)

Perfect for 4GB RAM systems that need cloud burst capability.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog
import httpx

from app.config import settings
from .kronos_service import kronos_service_4gb, get_memory_usage, check_memory_safe
from .prediction_store import prediction_store

logger = structlog.get_logger(__name__)


class HybridKronosService:
    """
    Intelligent routing between local and cloud inference.

    Routing logic:
    1. If RAM < 85% → Local (kronos-mini)
    2. If RAM > 85% and HF token set → Hugging Face API
    3. If Colab URL configured → Colab GPU (3-model ensemble)
    4. If all else fails → Skip prediction, log warning
    """

    def __init__(self):
        self.colab_url: Optional[str] = None
        self.hf_model_id: str = "NeoQuasar/Kronos-mini"  # Placeholder
        self._local_predictions = 0
        self._cloud_predictions = 0
        self._errors = 0

    def configure_colab(self, url: str):
        """
        Configure Google Colab fallback URL.

        Args:
            url: ngrok URL from Colab notebook (e.g., "https://abc123.ngrok.io")
        """
        self.colab_url = url
        logger.info(f"Configured Colab fallback: {url}")

    async def predict(
        self,
        symbol: str,
        ohlcv_data: List[List[float]],
        forecast_horizon: int = None,
        use_cloud_if_busy: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict with intelligent routing.

        Args:
            symbol: Trading symbol
            ohlcv_data: OHLCV history
            forecast_horizon: Bars to predict
            use_cloud_if_busy: Use cloud if local RAM is high

        Returns:
            Prediction results
        """
        if forecast_horizon is None:
            forecast_horizon = settings.KRONOS_FORECAST_HORIZON

        # Check memory
        memory_safe = check_memory_safe()

        if memory_safe or not use_cloud_if_busy:
            # Try local inference
            logger.info(f"Using local inference for {symbol}")
            try:
                result = kronos_service_4gb.predict(
                    ohlcv_data,
                    forecast_horizon,
                    model_name=settings.KRONOS_MODEL,
                )

                if result.get("status") == "success":
                    self._local_predictions += 1

                    # Save to DuckDB
                    prediction_store.save_prediction(
                        symbol=symbol,
                        predictions=result["predictions"],
                        model_name=settings.KRONOS_MODEL,
                        forecast_horizon=forecast_horizon,
                        current_price=ohlcv_data[-1][3] if ohlcv_data else 0,
                        confidence_lower=result.get("confidence_lower"),
                        confidence_upper=result.get("confidence_upper"),
                        predicted_return=result.get("predicted_return"),
                    )

                    result["source"] = "local"
                    result["symbol"] = symbol
                    return result

                # Local failed, try cloud
                logger.warning(f"Local inference failed for {symbol}: {result.get('error')}")

            except Exception as e:
                logger.error(f"Local inference error for {symbol}: {e}")
                self._errors += 1

        # Try Hugging Face API
        if settings.HUGGINGFACE_API_TOKEN:
            logger.info(f"Trying Hugging Face API for {symbol}")
            try:
                result = await self._hf_predict(symbol, ohlcv_data, forecast_horizon)
                if result.get("status") == "success":
                    self._cloud_predictions += 1

                    prediction_store.save_prediction(
                        symbol=symbol,
                        predictions=result["predictions"],
                        model_name=self.hf_model_id,
                        forecast_horizon=forecast_horizon,
                        current_price=ohlcv_data[-1][3] if ohlcv_data else 0,
                        predicted_return=result.get("predicted_return"),
                    )

                    result["source"] = "huggingface"
                    result["symbol"] = symbol
                    return result
                
            except Exception as e:
                logger.warning(f"Hugging Face API failed for {symbol}: {e}")

        # Try Colab GPU
        if self.colab_url and use_cloud_if_busy:
            logger.info(f"Trying Colab GPU for {symbol}")
            try:
                result = await self._colab_predict(symbol, ohlcv_data, forecast_horizon)
                if result.get("status") == "success":
                    self._cloud_predictions += 1

                    prediction_store.save_prediction(
                        symbol=symbol,
                        predictions=result["predictions"],
                        model_name=f"kronos-colab-{settings.KRONOS_COLAB_STRATEGY}",
                        forecast_horizon=forecast_horizon,
                        current_price=ohlcv_data[-1][3] if ohlcv_data else 0,
                        predicted_return=result.get("predicted_return"),
                    )

                    result["source"] = "colab"
                    result["symbol"] = symbol
                    return result

            except Exception as e:
                logger.warning(f"Colab GPU failed for {symbol}: {e}")

        # All methods failed
        self._errors += 1
        logger.warning(f"All prediction methods failed for {symbol}")

        return {
            "status": "error",
            "error": "Local + cloud inference unavailable",
            "symbol": symbol,
            "source": "none",
        }

    async def _hf_predict(
        self,
        symbol: str,
        ohlcv_data: List[List[float]],
        forecast_horizon: int,
    ) -> Dict[str, Any]:
        """Call Hugging Face Inference API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api-inference.huggingface.co/models/{self.hf_model_id}",
                headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}"},
                json={
                    "inputs": ohlcv_data,
                    "parameters": {"forecast_horizon": forecast_horizon},
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                return {"status": "error", "error": f"HF API: {response.status_code}"}

            return response.json()

    async def _colab_predict(
        self,
        symbol: str,
        ohlcv_data: List[List[float]],
        forecast_horizon: int,
    ) -> Dict[str, Any]:
        """
        Call Google Colab GPU server with 3-model support.
        
        The Colab notebook supports 3 strategies:
        - cascade: Fast filtering (mini → small → base)
        - ensemble: Weighted average of all 3 models
        - context: Auto-select by data length
        
        Converts OHLCV to returns format and parses the multi-model response.
        """
        if not self.colab_url:
            return {"status": "error", "error": "Colab URL not configured"}

        # Convert OHLCV to returns (Kronos format)
        # ohlcv_data: [seq_len, 6] where index 3 = close price
        if len(ohlcv_data) < 2:
            return {"status": "error", "error": "Insufficient data for returns calculation"}
        
        close_prices = [bar[3] for bar in ohlcv_data]
        returns = [(close_prices[i] - close_prices[i-1]) / close_prices[i-1] 
                   for i in range(1, len(close_prices))]

        async with httpx.AsyncClient() as client:
            # Call new 3-model API format
            response = await client.post(
                f"{self.colab_url}/predict/batch",
                json={
                    "symbols": [symbol],
                    "strategy": settings.KRONOS_COLAB_STRATEGY,
                    "returns": returns,
                    "forecast_horizon": forecast_horizon,
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                return {"status": "error", "error": f"Colab: {response.status_code}"}
            
            result = response.json()
            
            # Extract prediction for the symbol from batch response
            if symbol in result:
                symbol_result = result[symbol]
                # Convert Colab response to backend format
                if symbol_result.get("direction") == "UP":
                    predicted_return = abs(symbol_result.get("predicted_change", 0))
                elif symbol_result.get("direction") == "DOWN":
                    predicted_return = -abs(symbol_result.get("predicted_change", 0))
                else:
                    predicted_return = 0
                
                # Generate price predictions from returns
                last_close = ohlcv_data[-1][3]
                predictions = [last_close * (1 + predicted_return * (i + 1) / forecast_horizon) 
                              for i in range(forecast_horizon)]
                
                return {
                    "status": "success",
                    "predictions": predictions,
                    "predicted_return": predicted_return,
                    "forecast_horizon": forecast_horizon,
                    "confidence_lower": [p * 0.98 for p in predictions],
                    "confidence_upper": [p * 1.02 for p in predictions],
                    "strategy": symbol_result.get("strategy", settings.KRONOS_COLAB_STRATEGY),
                    "source": "colab",
                    "symbol": symbol,
                    "inference_time_ms": symbol_result.get("inference_time_ms", 0),
                }
            
            return {"status": "error", "error": "Symbol not in response"}

    async def predict_batch(
        self,
        symbols_data: Dict[str, List[List[float]]],
        forecast_horizon: int = None,
        priority_symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Predict for multiple symbols with priority queuing.

        Args:
            symbols_data: Dict of symbol -> OHLCV data
            forecast_horizon: Bars to predict
            priority_symbols: Process these first (Tier 1 holdings)

        Returns:
            Dict of symbol -> prediction results
        """
        if forecast_horizon is None:
            forecast_horizon = settings.KRONOS_FORECAST_HORIZON

        # Prioritize symbols
        symbols = list(symbols_data.keys())
        if priority_symbols:
            priority = [s for s in symbols if s in priority_symbols]
            non_priority = [s for s in symbols if s not in priority_symbols]
            symbols = priority + non_priority

        logger.info(f"Starting hybrid batch prediction for {len(symbols)} symbols")

        results = {}
        for symbol in symbols:
            ohlcv_data = symbols_data[symbol]
            result = await self.predict(symbol, ohlcv_data, forecast_horizon)
            results[symbol] = result

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        memory = get_memory_usage()

        return {
            "local_predictions": self._local_predictions,
            "cloud_predictions": self._cloud_predictions,
            "errors": self._errors,
            "total_predictions": self._local_predictions + self._cloud_predictions,
            "colab_configured": self.colab_url is not None,
            "colab_strategy": settings.KRONOS_COLAB_STRATEGY,
            "hf_token_configured": settings.HUGGINGFACE_API_TOKEN is not None,
            "current_memory_mb": memory["rss_mb"],
            "system_memory_percent": memory["system_percent"],
            "is_safe_for_inference": check_memory_safe(),
        }

    def get_top_k_predictions(
        self,
        k: int = 10,
        timeframe: str = '1h',
        min_confidence: float = 0.02,
    ) -> List[Dict[str, Any]]:
        """
        Get top-K predictions by predicted return.

        This is the "Top-K Strategy" from Kronos - rank assets by forecast.
        
        Args:
            k: Number of predictions
            timeframe: Bar timeframe
            min_confidence: Minimum absolute predicted return
        
        Returns:
            Top-K symbols ranked by predicted return
        """
        return prediction_store.get_top_k_predictions(k, timeframe, min_confidence)


# Global instance
hybrid_kronos_service = HybridKronosService()


# Convenience functions
async def predict_with_fallback(
    symbol: str,
    ohlcv_data: List[List[float]],
    forecast_horizon: int = 50,
) -> Dict[str, Any]:
    """Quick single prediction with cloud fallback."""
    return await hybrid_kronos_service.predict(symbol, ohlcv_data, forecast_horizon)


async def predict_batch_with_fallback(
    symbols_data: Dict[str, List[List[float]]],
    forecast_horizon: int = 50,
) -> Dict[str, Any]:
    """Quick batch prediction with cloud fallback."""
    return await hybrid_kronos_service.predict_batch(symbols_data, forecast_horizon)


def configure_colab_fallback(url: str):
    """Configure Colab GPU fallback URL."""
    hybrid_kronos_service.configure_colab(url)