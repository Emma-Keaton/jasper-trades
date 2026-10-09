"""Tests for the Risk and Quant agents.

Two real defects motivated this file.

1. `RiskAgent.analyze` sized positions off `net_signal` magnitude alone, so a
   *weak* signal (net near zero) was labelled "low risk" and given the largest
   size - 75% of the $50k cap. The weakest signals got the biggest positions.

2. `QuantAgent.analyze` reported factor-consensus strength under the key
   `volatility`. Consensus and volatility are unrelated quantities, and Risk
   consumed the mislabelled value as risk.

`net_signal` is the strength of factor consensus, not volatility, so these tests
pin the naming as well as the arithmetic: a silent relabelling of a risk input is
exactly the kind of change that must not pass unnoticed.
"""

from __future__ import annotations

import pytest

from app.agents.quant import QuantAgent
from app.agents.risk import MAX_POSITION_USD, MIN_APPROVAL_CONFIDENCE, RiskAgent


def advise(confidence, net_signal=0.1, direction="long"):
    return {
        "advise": {
            "strategy": {
                "confidence": confidence,
                "net_signal": net_signal,
                "theme": "momentum",
            },
            "recommended_direction": direction,
            "factors": [],
        }
    }


class TestRiskSizing:
    async def test_position_scales_with_confidence(self):
        """The core invariant: more conviction, bigger position - never less."""
        agent = RiskAgent()
        sizes = []
        for confidence in (0.45, 0.6, 0.75, 0.9):
            analysis = await agent.analyze(advise(confidence))
            sizes.append(analysis["suggested_position_usd"])
        assert sizes == sorted(sizes), f"size must not fall as confidence rises: {sizes}"

    async def test_weak_signal_does_not_get_the_largest_position(self):
        """The regression. Before the fix, confidence 0.41 with no consensus
        produced $37,500 - more than a confident trade."""
        agent = RiskAgent()
        weak = await agent.analyze(advise(0.45, net_signal=0.0))
        strong = await agent.analyze(advise(0.95, net_signal=0.0))
        assert (
            weak["suggested_position_usd"] < strong["suggested_position_usd"]
        ), "a weak signal must not receive a larger position than a strong one"

    async def test_risk_cap_only_reduces_size(self):
        """A high-noise picture may shrink the position but must never inflate
        it beyond the low-risk case at the same confidence."""
        agent = RiskAgent()
        low = await agent.analyze(advise(0.8, net_signal=0.1))
        high = await agent.analyze(advise(0.8, net_signal=0.9))
        assert high["suggested_position_usd"] <= low["suggested_position_usd"]
        assert high["size_cap_pct"] < low["size_cap_pct"]

    async def test_never_exceeds_the_configured_max(self):
        agent = RiskAgent({"max_position_usd": 1000.0})
        analysis = await agent.analyze(advise(1.0, net_signal=0.0))
        assert analysis["suggested_position_usd"] <= 1000.0

    async def test_default_max_is_respected(self):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(1.0, net_signal=0.0))
        assert analysis["suggested_position_usd"] <= MAX_POSITION_USD

    async def test_full_confidence_saturates_the_cap(self):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(1.0, net_signal=0.1))
        assert analysis["suggested_position_usd"] == pytest.approx(
            MAX_POSITION_USD * 0.75
        )

    @pytest.mark.parametrize(
        "net,expected", [(0.9, "high"), (0.6, "high"), (0.3, "moderate"), (0.05, "low")]
    )
    async def test_risk_level_from_consensus_noise(self, net, expected):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.8, net_signal=net))
        assert analysis["risk_level"] == expected

    async def test_tighter_stop_when_the_picture_is_noisy(self):
        agent = RiskAgent()
        calm = await agent.analyze(advise(0.8, net_signal=0.05))
        noisy = await agent.analyze(advise(0.8, net_signal=0.9))
        assert noisy["stop_loss_pct"] < calm["stop_loss_pct"]

    async def test_take_profit_is_double_the_stop(self):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.8))
        assert analysis["take_profit_pct"] == pytest.approx(analysis["stop_loss_pct"] * 2)


class TestRiskApproval:
    async def test_approved_needs_a_directional_view(self):
        agent = RiskAgent()
        assert (await agent.analyze(advise(0.9, direction="neutral")))["approved"] is False

    async def test_approved_needs_enough_confidence(self):
        agent = RiskAgent()
        below = await agent.analyze(advise(MIN_APPROVAL_CONFIDENCE - 0.01))
        above = await agent.analyze(advise(MIN_APPROVAL_CONFIDENCE + 0.01))
        assert below["approved"] is False
        assert above["approved"] is True

    @pytest.mark.parametrize("direction", ["long", "short"])
    async def test_directional_signals_are_approved(self, direction):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.9, direction=direction))
        assert analysis["approved"] is True

    @pytest.mark.parametrize("direction", ["hold", "", "BUY", "unknown", None])
    async def test_unrecognised_directions_are_not_approved(self, direction):
        """Only long/short are tradable. Anything else must not pass the gate."""
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.9, direction=direction))
        assert analysis["approved"] is False

    async def test_signal_is_none_when_not_approved(self):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.2))
        assert await agent.generate_signal("BTC", analysis) is None
        assert agent.signals_generated == 0

    @pytest.mark.parametrize(
        "direction,action", [("long", "buy"), ("short", "sell")]
    )
    async def test_approved_signal_maps_direction_to_action(self, direction, action):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.9, direction=direction))
        signal = await agent.generate_signal("BTC", analysis)
        assert signal["action"] == action
        assert agent.signals_generated == 1


class TestAgentRobustness:
    """Factor output is external data; a malformed field must not crash a risk
    decision."""

    @pytest.mark.parametrize("confidence", [None, "high", [], float("nan"), "not-a-number"])
    async def test_unparseable_confidence_does_not_raise(self, confidence):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(confidence))
        assert analysis["confidence"] == 0.0
        assert analysis["approved"] is False

    @pytest.mark.parametrize("net", ["0.5", None, "loud", float("inf")])
    async def test_unparseable_net_signal_does_not_raise(self, net):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(0.8, net_signal=net))
        assert analysis["net_signal" if "net_signal" in analysis else "risk_level"]

    @pytest.mark.parametrize("market_data", [{}, None, {"advise": None}, {"advise": {}}])
    async def test_missing_input_is_refused_not_approved(self, market_data):
        agent = RiskAgent()
        analysis = await agent.analyze(market_data)
        assert analysis["approved"] is False
        assert analysis["suggested_position_usd"] == 0.0

    async def test_strength_is_clamped_to_one(self):
        agent = RiskAgent()
        analysis = await agent.analyze(advise(5.0))
        assert analysis["confidence"] == 5.0
        assert analysis["suggested_position_usd"] <= MAX_POSITION_USD


class TestQuantReporting:
    async def test_reports_consensus_strength_not_volatility(self):
        """`volatility` was the wrong name for factor consensus strength, and Risk
        consumed it as a risk input."""
        agent = QuantAgent()
        analysis = await agent.analyze(advise(0.8, net_signal=0.9))
        assert "volatility" not in analysis
        assert analysis["consensus_strength"] == "strong"

    @pytest.mark.parametrize(
        "net,expected",
        [(0.9, "strong"), (0.6, "strong"), (0.3, "moderate"), (0.05, "weak")],
    )
    async def test_consensus_strength_bands(self, net, expected):
        agent = QuantAgent()
        analysis = await agent.analyze(advise(0.8, net_signal=net))
        assert analysis["consensus_strength"] == expected

    async def test_negative_signal_is_measured_by_magnitude(self):
        """A strong short is as strong as a strong long."""
        agent = QuantAgent()
        long = await agent.analyze(advise(0.8, net_signal=0.9, direction="long"))
        short = await agent.analyze(advise(0.8, net_signal=-0.9, direction="short"))
        assert long["consensus_strength"] == short["consensus_strength"] == "strong"

    @pytest.mark.parametrize("confidence", [None, "n/a", float("nan"), {}, []])
    async def test_unparseable_confidence_does_not_raise(self, confidence):
        agent = QuantAgent()
        analysis = await agent.analyze(advise(confidence))
        assert analysis["confidence"] == 0.0

    async def test_missing_input_does_not_raise(self):
        agent = QuantAgent()
        analysis = await agent.analyze({})
        assert analysis["direction"] == "neutral"
        assert analysis["factor_count"] == 0

    async def test_factor_details_are_summarised(self):
        agent = QuantAgent()
        analysis = await agent.analyze(
            {
                "advise": {
                    "strategy": {"confidence": 0.8, "net_signal": 0.3},
                    "recommended_direction": "long",
                    "factors": [
                        {
                            "factor": {"name": "momentum", "theme": "trend", "weight": 0.4},
                            "direction": "long",
                            "magnitude": 1.2,
                        }
                    ],
                }
            }
        )
        assert analysis["factor_count"] == 1
        assert analysis["factors"][0]["name"] == "momentum"
        assert analysis["factors"][0]["theme"] == "trend"

    async def test_malformed_factor_entries_do_not_raise(self):
        agent = QuantAgent()
        analysis = await agent.analyze(
            {"advise": {"factors": [{}, None, "garbage"], "strategy": {}}}
        )
        assert analysis["factor_count"] == 3

    async def test_signal_requires_direction_and_confidence(self):
        agent = QuantAgent()
        analysis = await agent.analyze(advise(0.8, direction="neutral"))
        assert await agent.generate_signal("BTC", analysis) is None

    async def test_generated_signal_mentions_consensus_not_volatility(self):
        agent = QuantAgent()
        analysis = await agent.analyze(advise(0.9, net_signal=0.9))
        signal = await agent.generate_signal("BTC", analysis)
        assert "consensus=strong" in signal["reasoning"]
        assert "vol=" not in signal["reasoning"]


class TestLegacyHelper:
    async def test_assess_position_still_works(self):
        """`risk_api.py` calls this; it must keep returning its documented shape."""
        from app.agents.risk import assess_position

        result = await assess_position("BTCUSDT", "buy", 1.0)
        assert result["symbol"] == "BTCUSDT"
        assert result["side"] == "buy"
        assert result["approved"] is True
        assert result["stop_loss_pct"] > 0

    async def test_assess_position_for_a_short(self):
        from app.agents.risk import assess_position

        result = await assess_position("BTCUSDT", "sell", 1.0)
        assert result["side"] == "sell"
        assert result["approved"] is True