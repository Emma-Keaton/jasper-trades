"""
Multi-LLM Ensemble Service
Aggregates predictions from multiple models for higher accuracy.

Ensemble Models:
- Llama-3.2-3B-Instruct (fast baseline, ~50ms)
- Phi-3-Medium (free, fast, ~100ms)
- Llama-3.1-70B-Instruct-FREE (smart, free, ~200ms)
- Mistral-Large (free alternative)
- Llama-3.3-70B-Instruct (premium, ~300ms)
- Nemotron-3-Super-120B (deep analysis, ~600ms)

Features:
- Weight by historical accuracy per asset class
- Calculate disagreement metric
- Calibrate confidence scores
- Cost optimization via free-tier routing
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import asyncio

logger = structlog.get_logger(__name__)


class EnsembleModel:
    """Configuration for an ensemble model"""
    def __init__(
        self,
        name: str,
        model_id: str,
        base_url: str,
        is_free: bool = False,
        expected_latency_ms: int = 100,
        cost_per_1m_tokens: float = 0.0,
        specialty: str = "general",  # general, analysis, classification
    ):
        self.name = name
        self.model_id = model_id
        self.base_url = base_url
        self.is_free = is_free
        self.expected_latency_ms = expected_latency_ms
        self.cost_per_1m_tokens = cost_per_1m_tokens
        self.specialty = specialty
        self.historical_accuracy: Dict[str, float] = {}  # asset_class -> accuracy


class EnsembleService:
    """
    Multi-LLM Ensemble Service - Production ensemble predictions.
    
    Features:
    - Parallel model inference
    - Weighted voting by historical accuracy
    - Disagreement detection
    - Confidence calibration
    - Cost optimization
    
    Why Ensemble:
    - Reduces single-model bias
    - More robust predictions
    - Better calibrated confidence
    - 5-15% accuracy improvement over single models
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.models: Dict[str, EnsembleModel] = {}
        self._initialize_models()
        logger.info("Ensemble Service initialized")

    def _initialize_models(self):
        """Initialize ensemble model configurations"""
        # Free tier models (prioritized)
        self.models["phi-3-medium"] = EnsembleModel(
            name="Phi-3-Medium",
            model_id="microsoft/phi-3-medium-128k-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            is_free=True,
            expected_latency_ms=100,
            cost_per_1m_tokens=0.0,
            specialty="classification",
        )

        self.models["llama-31-70b-free"] = EnsembleModel(
            name="Llama-3.1-70B-Instruct-FREE",
            model_id="meta/llama-3.1-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            is_free=True,
            expected_latency_ms=200,
            cost_per_1m_tokens=0.0,
            specialty="general",
        )

        self.models["mistral-large-free"] = EnsembleModel(
            name="Mistral-Large",
            model_id="mistralai/mistral-large",
            base_url="https://integrate.api.nvidia.com/v1",
            is_free=True,
            expected_latency_ms=250,
            cost_per_1m_tokens=0.0,
            specialty="analysis",
        )

        # Premium models (for complex tasks)
        self.models["llama-33-70b"] = EnsembleModel(
            name="Llama-3.3-70B-Instruct",
            model_id="meta/llama-3.3-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            is_free=False,
            expected_latency_ms=300,
            cost_per_1m_tokens=0.65,
            specialty="general",
        )

        self.models["nemotron-120b"] = EnsembleModel(
            name="Nemotron-3-Super-120B",
            model_id="nvidia/nemotron-3-120b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            is_free=False,
            expected_latency_ms=600,
            cost_per_1m_tokens=2.0,
            specialty="analysis",
        )

        logger.info(f"Initialized {len(self.models)} ensemble models")

    async def get_ensemble_prediction(
        self,
        prompt: str,
        asset_class: Optional[str] = "stocks",
        temperature: float = 0.3,
        max_tokens: int = 500,
        use_free_tier_only: bool = False,
        min_models: int = 3,
    ) -> Dict[str, Any]:
        """
        Get ensemble prediction from multiple models.

        Args:
            prompt: Input prompt for all models
            asset_class: Asset class for accuracy weighting (stocks, crypto, forex)
            temperature: Sampling temperature
            max_tokens: Max tokens per model
            use_free_tier_only: Only use free models
            min_models: Minimum number of models required

        Returns:
            Ensemble prediction with:
            - prediction: Final aggregated prediction
            - individual_predictions: Each model's output
            - confidence: Calibrated confidence score
            - disagreement: Model disagreement metric
            - cost_estimate: Estimated cost
            - models_used: List of models consulted
        """
        # Select models
        selected_models = self._select_models(
            asset_class=asset_class,
            use_free_tier_only=use_free_tier_only,
            min_models=min_models,
        )

        if len(selected_models) < min_models:
            logger.warning(f"Only {len(selected_models)} models available, need {min_models}")
            return self._fallback_prediction(prompt)

        logger.info(f"Running ensemble with {len(selected_models)} models")

        # Run models in parallel
        predictions = await self._run_models_parallel(
            models=selected_models,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Aggregate predictions
        ensemble_result = self._aggregate_predictions(
            predictions=predictions,
            asset_class=asset_class,
        )

        # Calculate cost
        total_cost = sum(p.get("estimated_cost", 0.0) for p in predictions)

        return {
            "prediction": ensemble_result["final_prediction"],
            "individual_predictions": [
                {
                    "model": p["model_name"],
                    "output": p["output"][:200],  # Truncate for response
                    "confidence": p.get("confidence", 0.5),
                    "latency_ms": p.get("latency_ms", 0),
                }
                for p in predictions
            ],
            "confidence": ensemble_result["confidence"],
            "disagreement": ensemble_result["disagreement"],
            "disagreement_interpretation": self._interpret_disagreement(
                ensemble_result["disagreement"]
            ),
            "models_used": [m.name for m in selected_models],
            "models_count": len(selected_models),
            "cost_estimate": round(total_cost, 4),
            "is_free_tier": all(m.is_free for m in selected_models),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _select_models(
        self,
        asset_class: Optional[str],
        use_free_tier_only: bool,
        min_models: int,
    ) -> List[EnsembleModel]:
        """Select models for ensemble"""
        models = list(self.models.values())

        # Filter by free tier if required
        if use_free_tier_only:
            models = [m for m in models if m.is_free]

        # Sort by specialty match and historical accuracy
        def model_score(model: EnsembleModel) -> float:
            score = 0.5  # Base score
            
            # Specialty bonus
            if model.specialty == "general":
                score += 0.1
            elif asset_class and model.specialty == "analysis":
                score += 0.2

            # Historical accuracy bonus
            if asset_class and asset_class in model.historical_accuracy:
                score += model.historical_accuracy[asset_class] * 0.3

            # Free tier preference
            if model.is_free:
                score += 0.1

            return score

        models.sort(key=model_score, reverse=True)

        # Select top models (at least min_models)
        selected = models[:max(min_models, 3)]

        # Ensure diversity: at least one analysis-specialized model
        if not any(m.specialty == "analysis" for m in selected):
            for m in models:
                if m.specialty == "analysis" and m not in selected:
                    selected.append(m)
                    break

        return selected

    async def _run_models_parallel(
        self,
        models: List[EnsembleModel],
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Run all models in parallel"""
        from app.nvidia_nim import nvidia_client

        async def run_single_model(model: EnsembleModel) -> Dict[str, Any]:
            start_time = datetime.utcnow()
            try:
                # Call NVIDIA NIM API
                output = await nvidia_client.complete(
                    model=model.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                estimated_cost = (len(prompt) + len(output)) / 1_000_000 * model.cost_per_1m_tokens

                return {
                    "model_name": model.name,
                    "model_id": model.model_id,
                    "output": output,
                    "confidence": self._extract_confidence(output),
                    "latency_ms": int(latency_ms),
                    "estimated_cost": estimated_cost,
                    "status": "success",
                    "is_free": model.is_free,
                }

            except Exception as e:
                logger.error(f"Model {model.name} failed: {e}")
                return {
                    "model_name": model.name,
                    "output": f"Error: {str(e)}",
                    "status": "error",
                    "latency_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "estimated_cost": 0.0,
                }

        # Run all models concurrently
        tasks = [run_single_model(model) for model in models]
        results = await asyncio.gather(*tasks)

        return [r for r in results if r["status"] == "success"]

    def _aggregate_predictions(
        self,
        predictions: List[Dict[str, Any]],
        asset_class: Optional[str],
    ) -> Dict[str, Any]:
        """
        Aggregate predictions from multiple models.

        Uses weighted voting based on:
        - Historical accuracy per asset class
        - Model confidence
        - Free tier preference (tie-breaker)
        """
        if not predictions:
            return {"final_prediction": "", "confidence": 0.0, "disagreement": 1.0}

        # Extract predictions
        outputs = [p["output"] for p in predictions]
        confidences = [p.get("confidence", 0.5) for p in predictions]

        # Get weights from historical accuracy
        weights = []
        for p in predictions:
            model = next((m for m in self.models.values() if m.name == p["model_name"]), None)
            if model and asset_class and asset_class in model.historical_accuracy:
                weight = model.historical_accuracy[asset_class]
            else:
                weight = 0.5  # Default weight
            weights.append(weight)

        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]

        # Calculate disagreement (variance of outputs)
        disagreement = self._calculate_disagreement(outputs)

        # Weighted average confidence
        avg_confidence = sum(c * w for c, w in zip(confidences, weights))

        # Generate final prediction (weighted majority vote or synthesis)
        final_prediction = self._synthesize_prediction(outputs, weights)

        # Calibrate confidence based on disagreement
        calibrated_confidence = avg_confidence * (1 - disagreement * 0.5)

        return {
            "final_prediction": final_prediction,
            "confidence": round(calibrated_confidence, 3),
            "disagreement": round(disagreement, 3),
            "weights": dict(zip([p["model_name"] for p in predictions], weights)),
        }

    def _calculate_disagreement(self, outputs: List[str]) -> float:
        """
        Calculate disagreement metric between model outputs.

        0.0 = perfect agreement
        1.0 = complete disagreement

        Uses cosine similarity of embeddings (simplified: text overlap for now)
        """
        if len(outputs) < 2:
            return 0.0

        # Simplified: calculate pairwise text similarity
        similarities = []
        for i, out1 in enumerate(outputs):
            for out2 in outputs[i+1:]:
                # Word overlap similarity
                words1 = set(out1.lower().split())
                words2 = set(out2.lower().split())
                overlap = len(words1 & words2) / max(len(words1), len(words2), 1)
                similarities.append(overlap)

        avg_similarity = sum(similarities) / len(similarities) if similarities else 1.0
        
        # Disagreement is inverse of similarity
        return 1.0 - avg_similarity

    def _interpret_disagreement(self, disagreement: float) -> str:
        """Interpret disagreement score"""
        if disagreement < 0.2:
            return "Strong consensus - models agree"
        elif disagreement < 0.4:
            return "Moderate consensus - minor differences"
        elif disagreement < 0.6:
            return "Mixed signals - significant disagreement"
        elif disagreement < 0.8:
            return "High uncertainty - models strongly disagree"
        else:
            return "Extreme uncertainty - no consensus"

    def _synthesize_prediction(
        self,
        outputs: List[str],
        weights: List[float],
    ) -> str:
        """Synthesize final prediction from weighted outputs"""
        # For now, return the highest-weighted model's output
        # In production, would use LLM to synthesize all outputs
        max_weight_idx = weights.index(max(weights))
        return outputs[max_weight_idx]

    def _extract_confidence(self, output: str) -> float:
        """Extract confidence score from model output"""
        # Look for confidence indicators in output
        import re
        
        # Pattern: "confidence: 85%" or "85% confidence"
        match = re.search(r'(\d{1,3})\s*%?\s*confidence', output, re.IGNORECASE)
        if match:
            return int(match.group(1)) / 100.0

        # Pattern: "high confidence", "moderate confidence", etc.
        if "high confidence" in output.lower():
            return 0.8
        elif "moderate confidence" in output.lower() or "medium confidence" in output.lower():
            return 0.6
        elif "low confidence" in output.lower():
            return 0.4

        # Default
        return 0.5

    def _fallback_prediction(self, prompt: str) -> Dict[str, Any]:
        """Fallback when ensemble can't run"""
        return {
            "prediction": "Ensemble unavailable - insufficient models",
            "individual_predictions": [],
            "confidence": 0.0,
            "disagreement": 0.0,
            "disagreement_interpretation": "No ensemble run",
            "models_used": [],
            "models_count": 0,
            "cost_estimate": 0.0,
            "is_free_tier": False,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": "Insufficient models available for ensemble",
        }

    async def update_model_accuracy(
        self,
        model_name: str,
        asset_class: str,
        was_correct: bool,
    ):
        """
        Update historical accuracy for a model.

        Args:
            model_name: Model that made prediction
            asset_class: Asset class (stocks, crypto, forex)
            was_correct: Whether prediction was correct
        """
        if model_name not in self.models:
            logger.warning(f"Unknown model: {model_name}")
            return

        model = self.models[model_name]
        
        # Initialize if needed
        if asset_class not in model.historical_accuracy:
            model.historical_accuracy[asset_class] = 0.5  # Start at 50%

        # Update with exponential moving average
        alpha = 0.1  # Learning rate
        current = model.historical_accuracy[asset_class]
        new_value = 1.0 if was_correct else 0.0
        model.historical_accuracy[asset_class] = current + alpha * (new_value - current)

        logger.info(
            f"Updated {model_name} accuracy for {asset_class}: {model.historical_accuracy[asset_class]:.1%}"
        )

    def get_model_performance(self) -> Dict[str, Any]:
        """Get performance stats for all models"""
        return {
            model.name: {
                "is_free": model.is_free,
                "specialty": model.specialty,
                "expected_latency_ms": model.expected_latency_ms,
                "cost_per_1m_tokens": model.cost_per_1m_tokens,
                "historical_accuracy": model.historical_accuracy,
            }
            for name, model in self.models.items()
        }

    def get_status(self) -> Dict[str, Any]:
        """Get ensemble service status"""
        return {
            "enabled": True,
            "models_count": len(self.models),
            "free_models": sum(1 for m in self.models.values() if m.is_free),
            "premium_models": sum(1 for m in self.models.values() if not m.is_free),
            "models": list(self.models.keys()),
        }


# Singleton instance
ensemble_service = EnsembleService()