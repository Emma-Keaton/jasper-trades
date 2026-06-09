"""
Ensemble API - Multi-LLM ensemble predictions
"""
from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import structlog

from app.services.ensemble_service import ensemble_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/ensemble", tags=["Multi-LLM Ensemble"])


class EnsembleRequest(BaseModel):
    """Ensemble prediction request"""
    prompt: str = Field(..., description="Input prompt for all models")
    asset_class: Optional[str] = Field(None, description="Asset class (stocks, crypto, forex)")
    temperature: float = Field(0.3, ge=0.0, le=1.0, description="Sampling temperature")
    max_tokens: int = Field(500, ge=100, le=2000, description="Max tokens per model")
    use_free_tier_only: bool = Field(False, description="Only use free models")
    min_models: int = Field(3, ge=1, le=6, description="Minimum models required")


class EnsemblePrediction(BaseModel):
    """Ensemble prediction response"""
    prediction: str
    individual_predictions: List[Dict[str, Any]]
    confidence: float
    disagreement: float
    disagreement_interpretation: str
    models_used: List[str]
    models_count: int
    cost_estimate: float
    is_free_tier: bool
    timestamp: str


@router.post("/predict", response_model=Dict[str, Any])
async def get_ensemble_prediction(request: EnsembleRequest):
    """
    Get ensemble prediction from multiple LLM models.

    **How it works:**
    1. Selects 3-6 models based on task and free-tier preference
    2. Runs all models in parallel
    3. Aggregates predictions with weighted voting
    4. Returns calibrated confidence and disagreement metric

    **Why Ensemble:**
    - 5-15% higher accuracy than single models
    - Reduces individual model bias
    - Better confidence calibration
    - Disagreement metric flags uncertain predictions

    **Cost Optimization:**
    - Free tier models: Phi-3-Medium, Llama-3.1-70B-FREE, Mistral-Large
    - Premium models: Llama-3.3-70B, Nemotron-120B (only when needed)
    - Estimated cost shown in response

    **Example Use Cases:**
    - Trading signal generation (high confidence required)
    - Market analysis synthesis
    - Risk assessment
    - Complex reasoning tasks
    """
    try:
        result = await ensemble_service.get_ensemble_prediction(
            prompt=request.prompt,
            asset_class=request.asset_class,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            use_free_tier_only=request.use_free_tier_only,
            min_models=request.min_models,
        )

        # Log if using premium models
        if not result["is_free_tier"]:
            logger.info(
                f"Ensemble prediction: {result['models_count']} models, cost ${result['cost_estimate']:.4f}"
            )

        return result

    except Exception as e:
        logger.error(f"Ensemble prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_available_models():
    """
    Get list of available ensemble models.

    Returns model metadata including:
    - Name and ID
    - Free vs premium
    - Specialty (general, analysis, classification)
    - Expected latency
    - Cost per 1M tokens
    - Historical accuracy by asset class
    """
    return {
        "models": ensemble_service.get_model_performance(),
        "total_count": len(ensemble_service.models),
        "free_count": sum(1 for m in ensemble_service.models.values() if m.is_free),
        "premium_count": sum(1 for m in ensemble_service.models.values() if not m.is_free),
    }


@router.post("/accuracy/update")
async def update_model_accuracy(
    model_name: str = Body(..., description="Model name"),
    asset_class: str = Body(..., description="Asset class (stocks, crypto, forex)"),
    was_correct: bool = Body(..., description="Whether prediction was correct"),
):
    """
    Update historical accuracy for a model.

    Call this after a prediction's outcome is known to improve future weighting.

    **Example:**
    ```json
    {
      "model_name": "llama-31-70b-free",
      "asset_class": "stocks",
      "was_correct": true
    }
    ```
    """
    try:
        await ensemble_service.update_model_accuracy(
            model_name=model_name,
            asset_class=asset_class,
            was_correct=was_correct,
        )
        return {
            "status": "success",
            "model": model_name,
            "asset_class": asset_class,
            "updated": True,
        }
    except Exception as e:
        logger.error(f"Failed to update accuracy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_model_performance():
    """
    Get performance statistics for all ensemble models.

    Shows:
    - Historical accuracy by asset class
    - Free vs premium breakdown
    - Expected latency and costs
    """
    return {
        "performance": ensemble_service.get_model_performance(),
        "recommendation": "Use free tier models for cost efficiency. Premium models only for complex analysis.",
    }


@router.get("/status")
async def get_ensemble_status():
    """Get ensemble service status"""
    return ensemble_service.get_status()


@router.get("/compare")
async def compare_models(
    prompt: str = Query(..., description="Test prompt"),
    asset_class: Optional[str] = Query(None, description="Asset class"),
):
    """
    Compare outputs from all models for a given prompt.

    Useful for:
    - Understanding model differences
    - Selecting best model for your use case
    - Debugging ensemble behavior

    Returns all model outputs side-by-side.
    """
    try:
        from app.nvidia_nim import nvidia_client
        import asyncio

        async def get_model_output(model_name: str, model: Any) -> Dict[str, Any]:
            try:
                output = await nvidia_client.complete(
                    model=model.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=300,
                )
                return {
                    "model": model.name,
                    "output": output[:300],
                    "is_free": model.is_free,
                    "cost_per_1m": model.cost_per_1m_tokens,
                }
            except Exception as e:
                return {
                    "model": model.name,
                    "output": f"Error: {e}",
                    "is_free": model.is_free,
                }

        tasks = [
            get_model_output(name, model)
            for name, model in ensemble_service.models.items()
        ]
        results = await asyncio.gather(*tasks)

        return {
            "prompt": prompt[:100],
            "asset_class": asset_class,
            "models_compared": len(results),
            "outputs": results,
        }

    except Exception as e:
        logger.error(f"Model comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))