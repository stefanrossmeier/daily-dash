from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_polymarket_profile
from daily_dash.contracts.polymarket import PolymarketEvent, PolymarketEventMarket
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.llm.polymarket import GatewayPolymarketClassifier

ROOT = Path(__file__).resolve().parents[2]


class FakeClient:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def chat_structured(self, **kwargs: object) -> GatewayResponse:
        self.request = kwargs
        return GatewayResponse(
            alias="rank-cheap",
            provider="openrouter",
            model="openai/gpt-5.4-nano",
            generation_id="poly-test",
            content={
                "evaluations": {
                    "P001": {
                        "relevance": 90,
                        "market_impact": 90,
                        "market_breadth": 85,
                        "prediction_signal": 95,
                        "ranking_score": 93,
                        "topic_key": "fed-september-2026-rate-decision",
                        "theme": "monetary-policy",
                        "signal_type": "both",
                        "rationale": "macro",
                    }
                }
            },
            usage=GatewayUsage(
                input_tokens=10,
                output_tokens=10,
                total_tokens=20,
                cost_usd=0.001,
            ),
            latency_ms=100,
            attempts=1,
        )


def test_classifier_ranks_event_once_and_hides_activity_prices_and_comments() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    event = PolymarketEvent(
        id="fed",
        event_id=101,
        title="Fed decision in September",
        description="Resolution from the FOMC decision.",
        url="https://polymarket.test/fed",
        slug="fed-september",
        category="finance",
        tags=["finance", "economy"],
        volume_24h=9_999_999,
        liquidity=5_000_000,
        comment_count=444,
        recent_trades=777,
        max_abs_one_hour_price_change=0.12,
        max_abs_one_day_price_change=0.20,
        end_at=datetime(2026, 9, 16, tzinfo=UTC),
        markets=[
            PolymarketEventMarket(
                question="Will there be no change?",
                condition_id="0x" + "1" * 64,
                outcomes=["Yes", "No"],
                outcome_prices=[0.91, 0.09],
                top_outcome="Yes",
                top_probability=0.91,
                volume_24h=8_000_000,
            ),
            PolymarketEventMarket(
                question="Will the Fed cut 25 bps?",
                condition_id="0x" + "2" * 64,
                outcomes=["Yes", "No"],
                outcome_prices=[0.08, 0.92],
                top_outcome="No",
                top_probability=0.92,
                volume_24h=1_000_000,
            ),
        ],
    )
    client = FakeClient()

    evaluations, trace = GatewayPolymarketClassifier(client).classify_batch([event], profile)

    assert evaluations[0].id == "fed"
    assert evaluations[0].ranking_score == 93
    assert evaluations[0].topic_key == "fed-september-2026-rate-decision"
    assert evaluations[0].theme == "monetary-policy"
    assert trace.prompt_version == "v5"
    user = str(client.request["user"] if client.request else "")
    assert "Fed decision in September" in user
    assert "Will there be no change?" in user
    assert "Will the Fed cut 25 bps?" in user
    assert "9999999" not in user
    assert "777" not in user
    assert "444" not in user
    assert "0.91" not in user
    assert "volume_24h" not in user
    assert "recent_trades" not in user
    assert "comment_count" not in user
