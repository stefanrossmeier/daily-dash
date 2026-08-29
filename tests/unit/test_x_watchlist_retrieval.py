from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_x_watchlist_profile, load_x_watchlist_source_set
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.retrieval.x_watchlist import retrieve_x_watchlist_posts

ROOT = Path(__file__).resolve().parents[2]


class _FakeGatewayClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def x_search_structured(self, **kwargs: object) -> GatewayResponse:
        assert kwargs["allowed_x_handles"] == [
            "KobeissiLetter",
            "AndreasSteno",
            "markoinny",
            "NickTimiraos",
            "DeItaone",
            "elerianm",
        ]
        assert kwargs["from_date"] == "2026-08-28"
        assert kwargs["to_date"] == "2026-08-28"
        return GatewayResponse(
            alias="x-retrieve",
            provider="openrouter",
            model="x-ai/grok-4.3",
            generation_id="gen-x",
            content={
                "posts": [
                    {
                        "author_handle": "NickTimiraos",
                        "publication_time": "Fri, 28 Aug 2026 18:53:47 GMT",
                        "post_text": "Fed signal",
                        "post_url": "https://x.com/NickTimiraos/status/123",
                        "linked_urls": [],
                    },
                    {
                        "author_handle": "SomeoneElse",
                        "publication_time": "Fri, 28 Aug 2026 18:00:00 GMT",
                        "post_text": "not allowed",
                        "post_url": "https://x.com/SomeoneElse/status/999",
                        "linked_urls": [],
                    },
                    {
                        "author_handle": "DeItaone",
                        "publication_time": "Fri, 28 Aug 2026 06:00:00 GMT",
                        "post_text": "outside exact window",
                        "post_url": "https://x.com/DeItaone/status/456",
                        "linked_urls": [],
                    },
                ]
            },
            usage=GatewayUsage(input_tokens=100, output_tokens=20, total_tokens=120, cost_usd=0.01),
            latency_ms=1000,
            provider_metadata={
                "x_search_call_count": 2,
                "x_search_queries": ["query1", "query2"],
                "citation_urls": [
                    "https://x.com/i/status/123",
                    "https://x.com/i/status/456",
                ],
            },
        )


def test_all_handles_are_retrieved_once_then_exact_window_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr("daily_dash.retrieval.x_watchlist.ModelGatewayClient", _FakeGatewayClient)
    profile = load_x_watchlist_profile(ROOT / "config/profiles/x-watchlist.yaml")
    source_set = load_x_watchlist_source_set(ROOT / "config/sources/x-watchlist.yaml")
    posts, diagnostic, trace = retrieve_x_watchlist_posts(
        source_set,
        profile,
        window_start=datetime(2026, 8, 28, 8, 20, tzinfo=UTC),
        window_end=datetime(2026, 8, 28, 20, 20, tzinfo=UTC),
    )
    assert [post.id for post in posts] == ["123"]
    assert diagnostic.returned_count == 3
    assert diagnostic.validated_count == 1
    assert diagnostic.rejected_invalid_author == 1
    assert diagnostic.rejected_outside_window == 1
    assert diagnostic.search_call_count == 2
    assert trace.x_search_call_count == 2
    assert trace.usage.cost_usd == 0.01


def test_overnight_window_uses_only_covering_local_dates(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class _CaptureGatewayClient(_FakeGatewayClient):
        def x_search_structured(self, **kwargs: object) -> GatewayResponse:
            seen.update(kwargs)
            return GatewayResponse(
                alias="x-retrieve",
                provider="openrouter",
                model="x-ai/grok-4.3",
                generation_id="gen-x",
                content={"posts": []},
                usage=GatewayUsage(input_tokens=1, output_tokens=1, total_tokens=2, cost_usd=0.0),
                latency_ms=1,
                provider_metadata={
                    "x_search_call_count": 0,
                    "x_search_queries": [],
                    "citation_urls": [],
                },
            )

    monkeypatch.setattr(
        "daily_dash.retrieval.x_watchlist.ModelGatewayClient", _CaptureGatewayClient
    )
    profile = load_x_watchlist_profile(ROOT / "config/profiles/x-watchlist.yaml")
    source_set = load_x_watchlist_source_set(ROOT / "config/sources/x-watchlist.yaml")
    retrieve_x_watchlist_posts(
        source_set,
        profile,
        window_start=datetime(2026, 8, 28, 18, 20, tzinfo=UTC),
        window_end=datetime(2026, 8, 29, 6, 20, tzinfo=UTC),
    )
    assert seen["from_date"] == "2026-08-28"
    assert seen["to_date"] == "2026-08-29"
