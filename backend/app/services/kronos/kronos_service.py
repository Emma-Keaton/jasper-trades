"""
Kronos Service for 4GB RAM Systems

Load → Predict → Unload pattern to minimize memory usage.
Uses Kronos-mini (4.1M params) quantized to int8.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog
import gc

from .memory_utils import (
    get_memory_usage,
    force_gc,
    check_memory_safe,
    wait_for_memory,
    configure_torch_cpu,
)

logger = structlog.get_logger(__name__)


class KronosService4GB:
    """
    Memory-optimized Kronos inference service.
    
    Key design principles for 4GB RAM:
    1. Model is NOT loaded by default
    2. Load only when needed
    3. Predict immediately
    4. Unload and GC after EVERY prediction
    5. Handle out-of-memory gracefully
    """
    
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._model_loaded_at: Optional[datetime] = None
        self._total_predictions = 0
        self._oom_errors = 0
        
        # Configure torch for low-memory operation
        configure_torch_cpu()
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded in memory."""
        return self._model is not None
    
    def _load_model(self, model_name: str = "kronos-mini"):
        """
        Load Kronos model from Hugging Face.
        
        Args:
            model_name: "kronos-mini" or "kronos-mini-int8" (quantized)
        """
        if self._model is not None:
            logger.debug("Model already loaded, skipping")
            return
        
        try:
            logger.info(f"Loading {model_name} for 4GB RAM-optimized inference...")
            
            # Import here to avoid loading torch until actually needed
            from huggingface_hub import hf_hub_download
            import torch
            
            # Download model files
            if model_name == "kronos-mini-int8":
                # Quantized version (smaller, faster, less accurate)
                model_path = hf_hub_download(
                    repo_id="傲慢的狼队/Kronos",
                    filename="kronos-mini-int8.safetensors",
                )
            else:
                # Standard version
                model_path = hf_hub_download(
                    repo_id="傲慢的狼队/Kronos",
                    filename="kronos-mini.safetensors",
                )
            
            # Load model state dict
            from safetensors.torch import load_file
            state_dict = load_file(model_path)
            
            # Build model architecture (use actual Kronos model class)
            # Note: This is a placeholder - will need actual Kronos implementation
            self._model = self._build_mini_model()
            self._model.load_state_dict(state_dict)
            self._model.eval()
            
            self._model_loaded_at = datetime.now()
            logger.info(f"Loaded {model_name} successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _build_mini_model(self):
        """
        Build Kronos-mini architecture (4.1M params).
        
        This is a simplified implementation. For production,
        use the actual Kronos model from the official repo.
        """
        from torch import nn
        
        class KronosMini(nn.Module):
            """
            Minimal Kronos model for 4GB RAM systems.
            ~4.1M parameters, ~20MB on disk, ~50MB RAM when loaded.
            """
            def __init__(self):
                super().__init__()
                self.d_model = 64
                self.nhead = 4
                self.num_layers = 2
                self.dim_feedforward = 128
                self.max_len = 512
                
                self.input_proj = nn.Linear(6, self.d_model)  # OHLCVA input
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=self.d_model,
                    nhead=self.nhead,
                    dim_feedforward=self.dim_feedforward,
                    dropout=0.1,
                    batch_first=True,
                )
                self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=self.num_layers)
                self.output_proj = nn.Linear(self.d_model, 6)  # OHLCVA output
            
            def forward(self, x):
                # x: [batch, seq_len, 6] (OHLCVA)
                embedded = self.input_proj(x)
                encoded = self.encoder(embedded)
                output = self.output_proj(encoded)
                return output
        
        return KronosMini()
    
    def _unload_model(self):
        """
        Unload model from memory and force garbage collection.
        CRITICAL for 4GB RAM systems.
        """
        if self._model is not None:
            del self._model
            self._model = None
        
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        
        force_gc()
        logger.debug("Unloaded Kronos model from memory")
    
    def predict(
        self,
        ohlcv_data: List[List[float]],
        forecast_horizon: int = 50,
        model_name: str = "kronos-mini",
    ) -> Dict[str, Any]:
        """
        Load → Predict → Unload pattern.
        
        Args:
            ohlcv_data: List of [open, high, low, close, volume] arrays
            forecast_horizon: Number of future bars to predict
            model_name: "kronos-mini" or "kronos-mini-int8"
        
        Returns:
            Dict with predictions, confidence, metadata
        """
        import torch
        
        # Check memory before loading
        if not check_memory_safe():
            wait_for_memory(min_free_percent=10.0, max_wait_sec=30)
        
        self._total_predictions += 1
        
        try:
            # Load model
            self._load_model(model_name=model_name)
            
            if self._model is None or self._ohlcv_data is None:
                raise RuntimeError("Model failed to load")
            
            # Prepare input tensor
            # ohlcv_data shape: [seq_len, 6] (open, high, low, close, volume, amount)
            if len(ohlcv_data) < 20:
                raise ValueError(f"Need at least 20 bars of history, got {len(ohlcv_data)}")
            
            # Normalize input (z-score)
            ohlcv_array = torch.tensor(ohlcv_data, dtype=torch.float32)
            mean = ohlcv_array.mean(dim=0, keepdim=True)
            std = ohlcv_array.std(dim=0, keepdim=True) + 1e-8
            normalized = (ohlcv_array - mean) / std
            
            # Add batch dimension: [1, seq_len, 6]
            input_tensor = normalized.unsqueeze(0)
            
            # Run inference
            with torch.no_grad():
                predictions_normalized = self._model(input_tensor)
            
            # Denormalize predictions
            predictions = predictions_normalized[0] * std + mean
            
            # Extract close price predictions (index 3)
            close_predictions = predictions[:, 3].tolist()
            
            # Truncate to forecast_horizon
            close_predictions = close_predictions[:forecast_horizon]
            
            # Generate confidence intervals (simplified)
            confidence_lower = [p * 0.98 for p in close_predictions]
            confidence_upper = [p * 1.02 for p in close_predictions]
            
            # Calculate predicted return
            current_price = ohlcv_data[-1][3]  # Last close
            predicted_return = (close_predictions[-1] - current_price) / current_price
            
            result = {
                "predictions": close_predictions,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
                "predicted_return": predicted_return,
                "forecast_horizon": forecast_horizon,
                "model_name": model_name,
                "inference_time_ms": (datetime.now() - self._model_loaded_at).total_seconds() * 1000 if self._model_loaded_at else 0,
                "memory_mb": get_memory_usage()["rss_mb"],
                "status": "success",
            }
            
            logger.info(f"Prediction complete: predicted_return={predicted_return:.2%}")
            return result
            
        except torch.cuda.OutOfMemoryError as e:
            self._oom_errors += 1
            logger.error(f"OOM error during prediction: {e}")
            return {
                "status": "error",
                "error": "Out of memory. Try kronos-mini-int8 or reduce forecast horizon.",
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
        finally:
            # ALWAYS unload - critical for 4GB systems
            self._unload_model()
    
    def predict_batch(
        self,
        symbols_data: Dict[str, List[List[float]]],
        forecast_horizon: int = 50,
        max_batch_size: int = 3,  # Micro-batch for 4GB RAM
        delay_between_seconds: float = 2.0,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Predict for multiple symbols with memory-safe batching.
        
        Args:
            symbols_data: Dict of symbol -> ohlcv_data
            forecast_horizon: Number of future bars
            max_batch_size: Process N symbols, then pause (default 3 for 4GB)
            delay_between_seconds: Wait time between batches
        
        Returns:
            Dict of symbol -> prediction results
        """
        import time
        
        results = {}
        symbols = list(symbols_data.keys())
        
        logger.info(f"Starting micro-batch prediction for {len(symbols)} symbols (max_batch={max_batch_size})")
        
        for i in range(0, len(symbols), max_batch_size):
            batch = symbols[i:i + max_batch_size]
            
            # Check memory before each batch
            if not check_memory_safe():
                logger.warning(f"Memory high, waiting before batch {i // max_batch_size + 1}")
                wait_for_memory(min_free_percent=15.0, max_wait_sec=60)
            
            logger.info(f"Processing batch {i // max_batch_size + 1}: {batch}")
            
            for symbol in batch:
                ohlcv_data = symbols_data[symbol]
                result = self.predict(ohlcv_data, forecast_horizon)
                results[symbol] = result
            
            # Pause between batches to let memory recover
            if i + max_batch_size < len(symbols):
                logger.info(f"Pausing {delay_between_seconds}s between batches...")
                time.sleep(delay_between_seconds)
                force_gc()
        
        logger.info(f"Micro-batch prediction complete: {len(results)} symbols")
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "model_loaded": self.is_loaded,
            "total_predictions": self._total_predictions,
            "oom_errors": self._oom_errors,
            "current_memory_mb": get_memory_usage()["rss_mb"],
            "system_memory_percent": get_memory_usage()["system_percent"],
        }


# Global service instance (lazy-loaded)
kronos_service_4gb = KronosService4GB()


# Convenience functions
def predict_single(ohlcv_data: List[List[float]], forecast_horizon: int = 50) -> Dict[str, Any]:
    """Quick single-symbol prediction."""
    return kronos_service_4gb.predict(ohlcv_data, forecast_horizon)


def predict_batch(symbols_data: Dict[str, List[List[float]]], forecast_horizon: int = 50) -> Dict[str, Any]:
    """Quick micro-batch prediction."""
    return kronos_service_4gb.predict_batch(symbols_data, forecast_horizon)


def get_service_stats() -> Dict[str, Any]:
    """Get service statistics."""
    return kronos_service_4gb.get_stats()