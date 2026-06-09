"""
Fincept Specialist Agents Registry
Central registry for all 10 specialist agents (6 investor personas + 4 analysts).

Usage:
    from app.agents.specialists.registry import get_specialist_agent
    
    # Get investor persona
    buffett = get_specialist_agent("buffett")
    analysis = await buffett.analyze("AAPL", financial_data)
    
    # Get analyst type
    tech_analyst = get_specialist_agent("technical")
    analysis = await tech_analyst.analyze("NVDA", ohlcv_data)
    
    # Or get all specialists
    from app.agents.specialists.registry import ALL_SPECIALISTS
    for name, agent_cls in ALL_SPECIALISTS.items():
        agent = agent_cls()
"""
from typing import Optional, Dict, Type
from app.agents.specialists.investor_personas import INVESTOR_PERSONAS
from app.agents.specialists.analyst_team import ANALYST_TYPES
import structlog

logger = structlog.get_logger(__name__)


# Combined registry
ALL_SPECIALISTS: Dict[str, Type] = {
    # Investor personas (6)
    **{name: cls for name, cls in INVESTOR_PERSONAS.items()},
    # Analyst types (4)
    **{name: cls for name, cls in ANALYST_TYPES.items()},
}


def get_specialist_agent(name: str):
    """
    Get a specialist agent by name.
    
    Args:
        name: Agent name (buffett, graham, lynch, munger, klarman, marks,
              fundamentals, technical, sentiment, macro)
    
    Returns:
        Instantiated agent or None if not found
    """
    name = name.lower().strip()
    
    if name not in ALL_SPECIALISTS:
        logger.warning(f"Specialist agent '{name}' not found. Available: {list(ALL_SPECIALISTS.keys())}")
        return None
    
    try:
        agent_cls = ALL_SPECIALISTS[name]
        agent = agent_cls()
        logger.info(f"Loaded specialist agent: {name}")
        return agent
    except Exception as e:
        logger.error(f"Failed to instantiate specialist agent '{name}': {e}")
        return None


def list_specialists() -> Dict[str, str]:
    """List all available specialist agents with descriptions."""
    return {
        # Investor personas
        "buffett": "Warren Buffett - Value investing, moats, long-term ownership",
        "graham": "Benjamin Graham - Deep value, net-nets, quantitative screening",
        "lynch": "Peter Lynch - GARP, tenbaggers, invest in what you know",
        "munger": "Charlie Munger - Mental models, quality at fair price",
        "klarman": "Seth Klarman - Margin of safety, catalyst-driven, distressed",
        "marks": "Howard Marks - Second-level thinking, market cycles",
        
        # Analyst types
        "fundamentals": "Fundamental analyst - Financial statements, DCF valuation",
        "technical": "Technical analyst - Charts, patterns, indicators",
        "sentiment": "Sentiment analyst - News, social media, positioning",
        "macro": "Macro analyst - Fed, rates, geopolitics, global flows",
    }


# Convenience function for multi-agent analysis
async def run_multi_agent_analysis(
    symbol: str,
    data: dict,
    specialists: Optional[list] = None
) -> dict:
    """
    Run analysis from multiple specialists and aggregate views.
    
    Args:
        symbol: Ticker symbol
        data: Company/market data
        specialists: List of specialist names (default: all)
    
    Returns:
        Aggregated analysis from all specialists
    """
    if specialists is None:
        specialists = list(ALL_SPECIALISTS.keys())
    
    results = {}
    for name in specialists:
        agent = get_specialist_agent(name)
        if agent:
            try:
                if hasattr(agent, 'analyze'):
                    results[name] = await agent.analyze(symbol, data)
                else:
                    logger.warning(f"Agent {name} has no analyze method")
            except Exception as e:
                logger.error(f"Error running {name} analysis: {e}")
    
    return results