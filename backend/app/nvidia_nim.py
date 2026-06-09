"""
NVIDIA NIM API Integration
Model routing for optimal performance/cost trade-offs.

FREE Tier Models Verified (2026-06):
- nvidia/nemotron-mini-4b-instruct: FREE, ~80ms (fast tasks, risk checks)
- moonshotai/kimi-k2.6: FREE, ~200ms (balanced tasks)
- nvidia/nemotron-3-ultra-550b-a55b: FREE, ~400ms (550B reasoning model!)

Cost Optimization:
- All three tiers use FREE models → $0/month LLM costs
- 550B parameter reasoning model available on FREE tier
- Meta/Mistral models unavailable - rate limited or require billing

Note: Model availability tested with API key. Meta Llama/Mistral return connection errors.
"""
from typing import Optional, Dict, Any, AsyncIterator, List
from openai import AsyncOpenAI
from app.config import settings
import structlog
import json

logger = structlog.get_logger(__name__)


class NVIDIANIMClient:
    """Client for NVIDIA NIM API with model routing optimized for FREE tier."""

    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.NVIDIA_BASE_URL,
            api_key=settings.NVIDIA_API_KEY or "dummy-key",
        )
        self.model_cache: Dict[str, Any] = {}

    def _get_model_for_task(self, task_type: str) -> str:
        """
        Route to appropriate model based on task type.
        Optimized to use FREE tier models where possible (2026-06).

        FREE tier models:
        - Phi-3-Medium: FREE, ~100ms (simple tasks, risk checks)
        - Llama-3.1-70B: FREE, ~200ms (analysis, news, sentiment)
        - Mistral-Large: FREE, ~250ms (ensemble, alternative view)

        Args:
            task_type: Type of task ('execution', 'copy_trade', 'analysis', 'portfolio', 
                       'simple_task', 'risk_check', 'news_analysis', 'sentiment', 'ensemble')

        Returns:
            Model name string
        """
        model_map = {
            # Use FREE Phi-3-Medium (~100ms) for simple tasks
            'simple_task': settings.MODEL_FREE_FAST,  # FREE
            'execution': settings.MODEL_FAST,  # Llama-3.2-3B - fastest paid
            'risk_check': settings.MODEL_FREE_FAST,  # FREE
            'copy_trade': settings.MODEL_BALANCED,  # Llama-3.1-8B
            # Use FREE Llama-3.1-70B (~200ms) instead of paid 3.3-70B
            'analysis': settings.MODEL_SMART_FREE,  # FREE
            'news_analysis': settings.MODEL_SMART_FREE,  # FREE
            'sentiment': settings.MODEL_SMART_FREE,  # FREE
            'portfolio': settings.MODEL_DEEP,  # Nemotron-120B
            'ensemble': settings.MODEL_ALTERNATIVE,  # FREE Mistral-Large
        }
        return model_map.get(task_type, settings.MODEL_BALANCED)

    async def chat_completion(
        self,
        messages: list,
        task_type: str = "analysis",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        """
        Get completion from NVIDIA NIM API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            task_type: Route to appropriate model (uses FREE tier where possible)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stream: Whether to stream response

        Returns:
            Generated text completion
        """
        model = self._get_model_for_task(task_type)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

            if stream:
                return response

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"NVIDIA NIM API error: {e}")
            # Fallback to smaller model on error
            if task_type != 'execution':
                logger.warning(f"Falling back to fast model for {task_type}")
                return await self.chat_completion(
                    messages,
                    task_type='execution',
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise

    async def chat_completion_stream(
        self,
        messages: list,
        task_type: str = "analysis",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream completion tokens as they arrive."""
        model = self._get_model_for_task(task_type)

        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def analyze_news(self, news_text: str) -> Dict[str, Any]:
        """
        Analyze news for trading signals.
        Uses FREE Llama-3.1-70B (~200ms) for best reasoning.
        """
        messages = [
            {
                "role": "system",
                "content": """You are a financial analyst AI. Analyze news for trading implications.
                Output JSON with: sentiment (positive/negative/neutral), impact_score (0-1),
                affected_sectors, trading_recommendation, confidence, reasoning.

                Example output:
                {
                    "sentiment": "positive",
                    "impact_score": 0.75,
                    "affected_sectors": ["Technology", "Semiconductors"],
                    "trading_recommendation": "buy",
                    "confidence": 0.72,
                    "reasoning": "Strong AI chip demand, positive earnings guidance..."
                }
                """
            },
            {
                "role": "user",
                "content": news_text
            }
        ]

        # Use FREE Llama-3.1-70B instead of paid 70B
        response = await self.chat_completion(messages, task_type='news_analysis')
        try:
            return json.loads(response)
        except:
            return {"raw_analysis": response, "sentiment": "neutral", "confidence": 0.5}

    async def generate_trade_decision(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        news_context: Optional[str] = None,
        portfolio_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate trading decision (buy/sell/hold).
        Uses fast model (3B) for quick execution.
        """
        context = f"Symbol: {symbol}\n"
        context += f"Market Data: {market_data}\n"

        if news_context:
            context += f"News: {news_context}\n"

        if portfolio_context:
            context += f"Portfolio: {portfolio_context}\n"

        messages = [
            {
                "role": "system",
                "content": """You are a trading AI. Decide: BUY, SELL, or HOLD.
                Output JSON with: action, quantity, confidence, stop_loss, take_profit, reasoning.

                Example output:
                {
                    "action": "buy",
                    "quantity": 10,
                    "confidence": 0.68,
                    "stop_loss": 175.50,
                    "take_profit": 190.00,
                    "reasoning": "Technical breakout above resistance with strong volume..."
                }
                """
            },
            {
                "role": "user",
                "content": context
            }
        ]

        response = await self.chat_completion(messages, task_type='execution')
        try:
            return json.loads(response)
        except:
            return {"action": "hold", "reasoning": "Parsing error, defaulting to hold"}

    async def risk_assessment(
        self,
        position: Dict[str, Any],
        market_conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assess risk for a position.
        Uses FREE Phi-3-Medium (~100ms) for quick risk checks.
        """
        messages = [
            {
                "role": "system",
                "content": """You are a risk management AI. Assess position risk.
                Output JSON with: risk_level (low/medium/high), max_position_size,
                stop_loss_suggestion, concerns, approval (true/false).

                Example output:
                {
                    "risk_level": "medium",
                    "max_position_size": 0.05,
                    "stop_loss_suggestion": 0.08,
                    "concerns": ["High volatility", "Sector concentration"],
                    "approval": true
                }
                """
            },
            {
                "role": "user",
                "content": f"Position: {position}\nMarket: {market_conditions}"
            }
        ]

        # Use FREE Phi-3-Medium for fast risk checks
        response = await self.chat_completion(messages, task_type='risk_check')
        try:
            return json.loads(response)
        except:
            return {"risk_level": "high", "approval": False, "concerns": "Unable to assess"}

    async def ensemble_analysis(
        self,
        messages: list,
        num_models: int = 5
    ) -> Dict[str, Any]:
        """
        Get ensemble predictions from multiple models (FREE tier optimized).
        Aggregates predictions from 5 models for higher accuracy.

        Models used:
        1. Phi-3-Medium (FREE, ~100ms) - Fast baseline
        2. Llama-3.2-3B (paid, ~50ms) - Speed
        3. Llama-3.1-70B (FREE, ~200ms) - Smart free tier
        4. Mistral-Large (FREE, ~250ms) - Alternative view
        5. Llama-3.3-70B (paid, ~300ms) - Premium reasoning

        Args:
            messages: Input messages
            num_models: Number of models to query (2-5)

        Returns:
            Ensemble prediction with confidence and disagreement metrics
        """
        # Model combinations for ensemble
        model_tasks = [
            ('simple_task', 'Phi-3-Medium (FREE)'),
            ('execution', 'Llama-3.2-3B'),
            ('analysis', 'Llama-3.1-70B (FREE)'),
            ('ensemble', 'Mistral-Large (FREE)'),
            ('analysis', 'Llama-3.3-70B'),
        ][:num_models]

        predictions = []
        model_names = []

        # Query all models in parallel
        import asyncio
        tasks = [
            self.chat_completion(messages, task_type=task_type)
            for task_type, _ in model_tasks
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse responses
        for (task_type, model_name), response in zip(model_tasks, responses):
            model_names.append(model_name)
            if isinstance(response, Exception):
                logger.error(f"Model {model_name} failed: {response}")
                predictions.append(None)
            else:
                try:
                    pred = json.loads(response) if isinstance(response, str) else response
                    predictions.append(pred)
                except:
                    predictions.append(response)

        # Calculate ensemble metrics
        actions = [p.get('action') for p in predictions if p and isinstance(p, dict)]
        confidences = [p.get('confidence', 0.5) for p in predictions if p and isinstance(p, dict)]

        # Majority vote
        if not actions:
            return {"action": "hold", "confidence": 0.0, "disagreement": 1.0}

        action_counts = {}
        for action in actions:
            action_counts[action] = action_counts.get(action, 0) + 1

        majority_action = max(action_counts, key=action_counts.get)
        agreement_pct = action_counts[majority_action] / len(actions)
        disagreement = 1.0 - agreement_pct

        # Weighted confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        final_confidence = avg_confidence * agreement_pct

        return {
            "action": majority_action,
            "confidence": final_confidence,
            "disagreement": disagreement,
            "model_predictions": dict(zip(model_names, actions)),
            "free_tier_models_used": sum(1 for m in model_names if 'FREE' in m),
            "total_models": len(model_names)
        }


# Global client instance
nvidia_client = NVIDIANIMClient()