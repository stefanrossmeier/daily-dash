from datetime import UTC, datetime
from pathlib import Path

from pydantic import HttpUrl

from daily_dash.config.loader import load_news_profile
from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.source import SourceItem
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.llm.smart_news import GatewaySmartNewsAnalyzer

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
            generation_id="gen-smart",
            content={
                "themes": [
                    {
                        "title": "Oil and ceasefire talks dominate markets",
                        "summary": "Oil prices fell as ceasefire talks advanced.",
                        "headline_indices": [1],
                    }
                ]
            },
            usage=GatewayUsage(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                cost_usd=0.001,
            ),
            latency_ms=1234,
            attempts=1,
        )


def test_smart_news_uses_versioned_prompt_asset_and_gpt54_alias() -> None:
    profile = load_news_profile(ROOT / "config/profiles/news-smart.yaml")
    article = SourceItem(
        id="oil",
        source="FT World",
        source_kind=SourceKind.RSS,
        title="Oil falls as ceasefire talks advance",
        text="Crude prices declined during Middle East negotiations.",
        url=HttpUrl("https://example.test/oil"),
        published_at=datetime(2026, 8, 28, 10, 0, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )
    client = FakeClient()

    themes, trace = GatewaySmartNewsAnalyzer(client).analyze([article], profile)

    assert themes[0].headline_indices == [1]
    assert trace.prompt_id == "news-smart"
    assert trace.prompt_version == "v2"
    assert trace.resolved_model == "openai/gpt-5.4-nano"
    assert trace.usage.cost_usd == 0.001

    assert client.request is not None
    assert client.request["alias"] == "rank-cheap"
    assert client.request["purpose"] == "news-smart-theme-clustering"
    assert "experienced financial market editor" in str(client.request["system"])
    assert "Use at most 5 themes" in str(client.request["system"])
    assert "[FT World] Oil falls" in str(client.request["user"])
    assert "Generate the JSON object exactly as specified" in str(client.request["user"])
