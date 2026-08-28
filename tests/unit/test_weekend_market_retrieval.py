from datetime import UTC, datetime

from daily_dash.config import WeekendMarketSourceSet
from daily_dash.retrieval.weekend_markets import IgWeekendMarketRetriever, parse_ig_weekend_quote


def test_visible_ig_weekend_quote_parser() -> None:
    html = "<div>Verkauf 26361.9 Kauf 26396.9 61.9(0.24%) Hoch 26409.9</div>"
    assert parse_ig_weekend_quote(html) == (26361.9, 26396.9, 0.24)


def test_ig_weekend_retriever_preserves_partial_failures() -> None:
    source_set = WeekendMarketSourceSet.model_validate(
        {
            "pipeline": "markets-weekend",
            "source_set_id": "markets-weekend",
            "provider": "ig-weekend",
            "quotes": [
                {
                    "id": "dax",
                    "name": "Germany 40",
                    "url": "https://example.test/dax",
                    "price_decimals": 1,
                },
                {
                    "id": "gold",
                    "name": "Gold",
                    "url": "https://example.test/gold",
                    "price_decimals": 1,
                },
            ],
        }
    )

    pages = {
        "https://example.test/dax": "Verkauf 100.0 Kauf 101.0 2.0(2.02%)",
        "https://example.test/gold": "temporarily unavailable",
    }
    retriever = IgWeekendMarketRetriever(fetcher=lambda url: pages[url])
    snapshot = retriever.retrieve(
        source_set,
        run_id="run-1",
        retrieved_at=datetime(2026, 8, 29, 8, 30, tzinfo=UTC),
    )

    assert snapshot.quotes[0].bid == 100.0
    assert snapshot.quotes[0].ask == 101.0
    assert snapshot.quotes[0].change_pct == 2.02
    assert snapshot.quotes[0].error is None
    assert snapshot.quotes[1].error == "missing bid, ask, change"
