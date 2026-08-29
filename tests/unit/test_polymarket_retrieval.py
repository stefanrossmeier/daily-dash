from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from daily_dash.config.loader import load_polymarket_profile, load_polymarket_source_set
from daily_dash.retrieval import polymarket as retrieval

ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeClient:
    def __init__(self, responder: Callable[[str, dict[str, object]], object], **_: object) -> None:
        self.responder = responder
        self.requests: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str, params: dict[str, object] | None = None) -> FakeResponse:
        actual = params or {}
        self.requests.append((url, actual))
        return FakeResponse(self.responder(url, actual))


def _market(condition_id: str, question: str, *, volume: float, h1: float = 0.0) -> dict[str, Any]:
    return {
        "question": question,
        "conditionId": condition_id,
        "slug": question.lower().replace(" ", "-"),
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "liquidityNum": 10000,
        "volume24hr": volume,
        "oneHourPriceChange": h1,
        "oneDayPriceChange": 0.0,
        "outcomes": '["Yes","No"]',
        "outcomePrices": '["0.6","0.4"]',
    }


def _event(
    event_id: int,
    slug: str,
    title: str,
    tag: str,
    *,
    volume: float,
    market: dict[str, Any],
    comments: int = 0,
) -> dict[str, Any]:
    return {
        "id": str(event_id),
        "slug": slug,
        "title": title,
        "description": f"Description for {title}",
        "active": True,
        "closed": False,
        "liquidity": 50000,
        "volume24hr": volume,
        "commentCount": comments,
        "tags": [{"slug": tag, "label": tag.title()}],
        "markets": [market],
    }


def test_event_retrieval_builds_small_semantic_pool_and_event_scoped_hot_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    source = load_polymarket_source_set(ROOT / "config/sources/polymarket.yaml")
    now = datetime(2026, 8, 29, 18, 45, tzinfo=UTC)
    fed = _event(
        101,
        "fed-september-2026",
        "Fed decision in September",
        "finance",
        volume=2_000_000,
        comments=80,
        market=_market("0x" + "1" * 64, "Fed no change", volume=2_000_000),
    )
    btc = _event(
        102,
        "bitcoin-august",
        "Bitcoin in August",
        "crypto",
        volume=500_000,
        market=_market("0x" + "2" * 64, "Bitcoin above 80k", volume=500_000),
    )
    lol = _event(
        103,
        "lol-t1-vs-fox",
        "T1 vs BNK FEARX",
        "sports",
        volume=3_000_000,
        comments=200,
        market=_market("0x" + "3" * 64, "T1 wins", volume=3_000_000, h1=0.2),
    )

    def responder(url: str, params: dict[str, object]) -> object:
        if "gamma-api" in url:
            tag = params.get("tag_slug")
            if tag == "finance":
                return [fed]
            if tag == "crypto":
                return [btc]
            if tag:
                return []
            return [lol, fed]
        assert "eventId" in params
        assert "103" in str(params["eventId"])
        return [
            {
                "eventSlug": "lol-t1-vs-fox",
                "conditionId": "0x" + "3" * 64,
                "timestamp": int(now.timestamp()),
            },
            {
                "eventSlug": "lol-t1-vs-fox",
                "conditionId": "0x" + "3" * 64,
                "timestamp": int(now.replace(hour=15).timestamp()),
            },
        ]

    fake = FakeClient(responder)
    monkeypatch.setattr(retrieval.httpx, "Client", lambda **kwargs: fake)

    semantic, hot, diagnostics = retrieval.retrieve_polymarket_events(
        source,
        profile.retrieval,
        retrieved_at=now,
    )

    assert {item.title for item in semantic} == {"Fed decision in September", "Bitcoin in August"}
    assert [item.title for item in hot] == ["T1 vs BNK FEARX", "Fed decision in September"]
    assert hot[0].recent_trades == 1
    assert hot[0].comment_count == 200
    assert hot[0].max_abs_one_hour_price_change == 0.2
    assert diagnostics[0].events_ok is True
    assert diagnostics[0].trades_ok is True
    assert diagnostics[0].semantic_tag_requests == len(profile.retrieval.semantic_tag_slugs)
    assert diagnostics[0].trade_scope_event_count == 2
    assert diagnostics[0].trade_window_complete is True
    trade_requests = [params for url, params in fake.requests if "data-api" in url]
    assert trade_requests
    assert all("eventId" in params for params in trade_requests)
    assert all(params["limit"] == 1000 for params in trade_requests)
    assert all(params["start"] == int(now.timestamp() - 120 * 60) for params in trade_requests)
    assert all(params["end"] == int(now.timestamp()) for params in trade_requests)


def test_recent_trade_counts_batch_event_ids_and_use_explicit_window() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    source = load_polymarket_source_set(ROOT / "config/sources/polymarket.yaml")
    now = datetime(2026, 8, 29, 18, 45, tzinfo=UTC)
    events = []
    for index in range(12):
        raw = _event(
            200 + index,
            f"event-{index}",
            f"Event {index}",
            "sports",
            volume=1_000_000,
            market=_market(
                "0x" + f"{index + 1:064x}",
                f"Market {index}",
                volume=1_000_000,
            ),
        )
        event = retrieval._normalize_event(raw)
        assert event is not None
        events.append(event)

    fake = FakeClient(lambda _url, _params: [])
    config = profile.retrieval.model_copy(
        update={"trade_event_batch_size": 5, "trade_page_limit": 100}
    )

    counts, total, pages, complete, ok, errors = retrieval._fetch_recent_event_trade_counts(
        fake,
        source,
        config,
        events,
        retrieved_at=now,
    )

    trade_requests = [params for url, params in fake.requests if "data-api" in url]
    assert len(trade_requests) == 3
    assert [len(str(params["eventId"]).split(",")) for params in trade_requests] == [5, 5, 2]
    assert all(params["limit"] == 100 for params in trade_requests)
    assert all(params["start"] == int(now.timestamp()) - 120 * 60 for params in trade_requests)
    assert all(params["end"] == int(now.timestamp()) for params in trade_requests)
    assert counts == {event.id: 0 for event in events}
    assert total == 0
    assert pages == 3
    assert complete is True
    assert ok is True
    assert errors == []


def test_recent_trade_batch_failure_does_not_skip_remaining_batches() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    source = load_polymarket_source_set(ROOT / "config/sources/polymarket.yaml")
    now = datetime(2026, 8, 29, 18, 45, tzinfo=UTC)
    events = []
    for index in range(6):
        raw = _event(
            300 + index,
            f"event-failure-{index}",
            f"Event failure {index}",
            "sports",
            volume=1_000_000,
            market=_market(
                "0x" + f"{index + 20:064x}",
                f"Failure market {index}",
                volume=1_000_000,
            ),
        )
        event = retrieval._normalize_event(raw)
        assert event is not None
        events.append(event)

    def responder(_url: str, params: dict[str, object]) -> object:
        if str(params["eventId"]).startswith("300,"):
            raise RuntimeError("synthetic timeout")
        return []

    fake = FakeClient(responder)
    config = profile.retrieval.model_copy(
        update={"trade_event_batch_size": 3, "trade_page_limit": 100}
    )

    counts, total, pages, complete, ok, errors = retrieval._fetch_recent_event_trade_counts(
        fake,
        source,
        config,
        events,
        retrieved_at=now,
    )

    trade_requests = [params for url, params in fake.requests if "data-api" in url]
    assert len(trade_requests) == 2
    assert counts == {event.id: 0 for event in events}
    assert total == 0
    assert pages == 1
    assert complete is False
    assert ok is False
    assert len(errors) == 1
    assert "synthetic timeout" in errors[0]
