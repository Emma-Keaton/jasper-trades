"""
Kronos Integration for 4GB RAM Systems
"""

import structlog
from typing import Callable, Any

logger = structlog.get_logger(__name__)

# Graceful fallback for when torch is not available
class _KronosUnavailable:
    """Placeholder class when Kronos is unavailable"""
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, *args, **kwargs):
        return None

# Try to import all components gracefully
try:
    from .memory_utils import (
        get_memory_usage,
        force_gc,
        check_memory_safe,
        wait_for_memory,
        set_memory_limits,
        configure_torch_cpu,
    )

    from .kronos_service import (
        KronosService4GB,
        kronos_service_4gb,
        predict_single,
        predict_batch,
        get_service_stats,
    )

    from .prediction_store import (
        KronosPredictionStore,
        prediction_store,
        get_prediction_store,
    )

    from .hybrid_service import (
        HybridKronosService,
        hybrid_kronos_service,
        predict_with_fallback,
        predict_batch_with_fallback,
        configure_colab_fallback,
    )

    from .symbol_priority import (
        SymbolPriorityQueue,
        symbol_priority_queue,
        get_symbol_priority_queue,
    )

    __all__ = [
        # Memory utilities
        "get_memory_usage",
        "force_gc",
        "check_memory_safe",
        "wait_for_memory",
        "set_memory_limits",
        "configure_torch_cpu",
        # Kronos service (local)
        "KronosService4GB",
        "kronos_service_4gb",
        "predict_single",
        "predict_batch",
        "get_service_stats",
        # Prediction storage
        "KronosPredictionStore",
        "prediction_store",
        "get_prediction_store",
        # Hybrid service (local + cloud)
        "HybridKronosService",
        "hybrid_kronos_service",
        "predict_with_fallback",
        "predict_batch_with_fallback",
        "configure_colab_fallback",
        # Symbol priority
        "SymbolPriorityQueue",
        "symbol_priority_queue",
        "get_symbol_priority_queue",
    ]
    
    logger.info("Kronos AI integration loaded successfully")

except (ImportError, OSError, RuntimeError) as e:
    # Handle torch/DLL errors gracefully (common on Windows)
    logger.warning(f"Kronos AI not available (will use remote service instead): {e}")
    
    # Provide safe fallbacks
    set_memory_limits: Callable[..., None] = lambda **kwargs: None
    configure_torch_cpu: Callable[[], None] = lambda: None
    KronosService4GB = _KronosUnavailable
    HybridKronosService = _KronosUnavailable
    KronosPredictionStore = _KronosUnavailable
    SymbolPriorityQueue = _KronosUnavailable
    
    # Define stub functions
    def predict_single(*args, **kwargs):
        logger.debug("predict_single called but Kronos unavailable")
        return None
    
    def predict_batch(*args, **kwargs):
        logger.debug("predict_batch called but Kronos unavailable")
        return []
    
    def kronos_service_4gb(*args, **kwargs):
        logger.debug("kronos_service_4gb called but Kronos unavailable")
        return None
    
    def hybrid_kronos_service(*args, **kwargs):
        logger.debug("hybrid_kronos_service called but Kronos unavailable")
        return None
    
    def get_service_stats(*args, **kwargs):
        return {"kronos_available": False}
    
    def get_prediction_store(*args, **kwargs):
        return None
    
    def symbol_priority_queue(*args, **kwargs):
        return None
    
    def predict_with_fallback(*args, **kwargs):
        return predict_single(*args, **kwargs)
    
    def predict_batch_with_fallback(*args, **kwargs):
        return predict_batch(*args, **kwargs)
    
    def configure_colab_fallback(*args, **kwargs):
        logger.info("Colab fallback configured (local Kronos unavailable)")
        pass
    
    def wait_for_memory(*args, **kwargs):
        pass
    
    def check_memory_safe(*args, **kwargs):
        return True
    
    def force_gc(*args, **kwargs):
        import gc
        gc.collect()
    
    def get_memory_usage(*args, **kwargs):
        return {"ram_percent": 0}
    
    __all__ = [
        "set_memory_limits",
        "configure_torch_cpu",
        "KronosService4GB",
        "kronos_service_4gb",
        "predict_single",
        "predict_batch",
        "get_service_stats",
        "KronosPredictionStore",
        "get_prediction_store",
        "HybridKronosService",
        "hybrid_kronos_service",
        "predict_with_fallback",
        "predict_batch_with_fallback",
        "configure_colab_fallback",
        "SymbolPriorityQueue",
        "symbol_priority_queue",
        "get_memory_usage",
        "force_gc",
        "check_memory_safe",
        "wait_for_memory",
    ]