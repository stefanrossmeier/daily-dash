from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from daily_dash.config.models import WsbSourceSet
from daily_dash.retrieval import wsb as wsb_retrieval


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = list(pages)
        self.get_urls: list[str] = []

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def post(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse({"access_token": "token"})

    def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        self.get_urls.append(url)
        if not self.pages:
            raise AssertionError(f"unexpected extra Reddit request: {url}")
        return _FakeResponse(self.pages.pop(0))


def _source_set() -> WsbSourceSet:
    return WsbSourceSet.model_validate(
        {
            "pipeline": "wsb",
            "source_set_id": "wsb",
            "provider": "reddit",
            "subreddit": "wallstreetbets",
            "listings": ["new"],
            "rss_url": "https://example.test/wsb.rss",
        }
    )


def _child(created_at: datetime, title: str) -> dict[str, Any]:
    slug = title.lower().replace(" ", "-")
    return {
        "data": {
            "created_utc": created_at.timestamp(),
            "title": title,
            "permalink": f"/r/wallstreetbets/comments/{slug}/post/",
            "num_comments": 1,
            "score": 1,
            "selftext": "body",
            "author": "tester",
        }
    }


def _page(children: list[dict[str, Any]], *, after: str | None) -> dict[str, Any]:
    return {"data": {"children": children, "after": after}}


def test_new_listing_paginates_past_posts_newer_than_explicit_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window_start = datetime(2026, 8, 28, 6, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 29, 6, 0, tzinfo=UTC)
    retrieved_at = datetime(2026, 8, 29, 8, 41, tzinfo=UTC)
    pages = [
        _page(
            [
                _child(datetime(2026, 8, 29, 8, 30, tzinfo=UTC), "too new 1"),
                _child(datetime(2026, 8, 29, 7, 30, tzinfo=UTC), "too new 2"),
            ],
            after="t3_page_1",
        ),
        _page(
            [
                _child(datetime(2026, 8, 29, 5, 30, tzinfo=UTC), "in window"),
                _child(datetime(2026, 8, 28, 5, 30, tzinfo=UTC), "too old"),
            ],
            after="t3_page_2",
        ),
    ]
    fake_client = _FakeClient(pages)
    monkeypatch.setattr(wsb_retrieval.httpx, "Client", lambda **_: fake_client)
    monkeypatch.setenv("DAILY_DASH_REDDIT_CLIENT_ID", "client")
    monkeypatch.setenv("DAILY_DASH_REDDIT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DAILY_DASH_REDDIT_USER_AGENT", "agent")

    posts, diagnostics = wsb_retrieval.retrieve_wsb_posts(
        _source_set(),
        listing_limit=100,
        max_new_pages=50,
        window_start=window_start,
        window_end=window_end,
        retrieved_at=retrieved_at,
    )

    assert [post.title for post in posts] == ["in window"]
    assert diagnostics[0].ok is True
    assert diagnostics[0].item_count == 1
    assert diagnostics[0].listing_pages == {"new": 2}
    assert diagnostics[0].window_complete is True
    assert len(fake_client.get_urls) == 2
    assert "after=t3_page_1" in fake_client.get_urls[1]
    assert "count=2" in fake_client.get_urls[1]


def test_new_listing_pagination_respects_page_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    window_start = datetime(2026, 8, 28, 6, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 29, 6, 0, tzinfo=UTC)
    retrieved_at = datetime(2026, 8, 29, 8, 41, tzinfo=UTC)
    pages = [
        _page(
            [_child(datetime(2026, 8, 29, 8, 30, tzinfo=UTC), "too new 1")],
            after="t3_page_1",
        ),
        _page(
            [_child(datetime(2026, 8, 29, 7, 30, tzinfo=UTC), "too new 2")],
            after="t3_page_2",
        ),
    ]
    fake_client = _FakeClient(pages)
    monkeypatch.setattr(wsb_retrieval.httpx, "Client", lambda **_: fake_client)
    monkeypatch.setenv("DAILY_DASH_REDDIT_CLIENT_ID", "client")
    monkeypatch.setenv("DAILY_DASH_REDDIT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DAILY_DASH_REDDIT_USER_AGENT", "agent")

    posts, diagnostics = wsb_retrieval.retrieve_wsb_posts(
        _source_set(),
        listing_limit=100,
        max_new_pages=2,
        window_start=window_start,
        window_end=window_end,
        retrieved_at=retrieved_at,
    )

    assert posts == []
    assert diagnostics[0].ok is False
    assert diagnostics[0].listing_pages == {"new": 2}
    assert diagnostics[0].window_complete is False
    assert diagnostics[0].error is not None
    assert "chronological recall may be incomplete" in diagnostics[0].error
    assert len(fake_client.get_urls) == 2
