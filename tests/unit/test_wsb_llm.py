from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_wsb_profile
from daily_dash.contracts.wsb import WsbPost
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.llm.wsb import GatewayWsbClassifier

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
            generation_id="wsb-test",
            content={
                "evaluations": {
                    "W001": {
                        "relevance": 90,
                        "market_impact": 85,
                        "market_breadth": 80,
                        "positioning_signal": 20,
                        "signal_type": "broad-market",
                        "rationale": "Macro transmission",
                    }
                }
            },
            usage=GatewayUsage(
                input_tokens=50,
                output_tokens=20,
                total_tokens=70,
                cost_usd=0.0005,
            ),
            latency_ms=700,
            attempts=1,
        )


def test_wsb_classifier_uses_prompt_asset_and_hides_popularity_metrics() -> None:
    profile = load_wsb_profile(ROOT / "config/profiles/wsb.yaml")
    post = WsbPost(
        id="macro",
        title="Rates shock reprices the entire market",
        text="Treasury yields jump and equity multiples compress.",
        url="https://reddit.test/macro",
        created_at=datetime(2026, 8, 28, 17, 0, tzinfo=UTC),
        num_comments=9999,
        score=50000,
        heat=1200.0,
    )
    client = FakeClient()

    evaluations, trace = GatewayWsbClassifier(client).classify_batch([post], profile)

    assert evaluations[0].id == "macro"
    assert trace.prompt_id == "wsb-ranking"
    assert trace.prompt_version == "v2"
    assert trace.resolved_model == "openai/gpt-5.4-nano"
    assert client.request is not None
    assert client.request["alias"] == "rank-cheap"
    user = str(client.request["user"])
    assert "Rates shock" in user
    assert "Treasury yields" in user
    assert "9999" not in user
    assert "50000" not in user
    assert "num_comments" not in user
    assert "score" not in user
