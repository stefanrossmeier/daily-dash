from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from daily_dash.commands import news
from daily_dash.contracts.common import DeliveryStatus


class FakeDocument:
    profile = "news-top"


class FakeStore:
    @staticmethod
    def read(path: Path) -> FakeDocument:
        assert path == Path("/tmp/news.json")
        return FakeDocument()


class FakeDeliveryResult:
    status = DeliveryStatus.SUCCESS
    error = None
    external_id = "123"


class FakeTelegramDelivery:
    token: str | None = None
    chat_id: str | None = None
    parse_mode: str | None = None
    report: object | None = None

    def __init__(
        self,
        *,
        token: str,
        chat_id: str,
        parse_mode: str,
    ) -> None:
        FakeTelegramDelivery.token = token
        FakeTelegramDelivery.chat_id = chat_id
        FakeTelegramDelivery.parse_mode = parse_mode

    def send(
        self,
        report: object,
    ) -> FakeDeliveryResult:
        FakeTelegramDelivery.report = report
        return FakeDeliveryResult()


def test_news_delivery_uses_explicit_telegram_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "DAILY_DASH_TELEGRAM_TOKEN",
        "fixture-token",
    )
    monkeypatch.setenv(
        "DAILY_DASH_TELEGRAM_CHAT_ID",
        "-123456",
    )

    monkeypatch.setattr(
        news,
        "JsonNewsRunStore",
        FakeStore,
    )

    monkeypatch.setattr(
        news,
        "load_news_profile",
        lambda path: object(),
    )

    fake_report = object()

    monkeypatch.setattr(
        news,
        "render_news_report",
        lambda document, profile: fake_report,
    )

    monkeypatch.setattr(
        news,
        "TelegramDelivery",
        FakeTelegramDelivery,
    )

    news._deliver(
        Namespace(
            artifact=Path("/tmp/news.json"),
            config_dir=tmp_path,
        )
    )

    assert FakeTelegramDelivery.token == "fixture-token"
    assert FakeTelegramDelivery.chat_id == "-123456"
    assert FakeTelegramDelivery.parse_mode == "HTML"
    assert FakeTelegramDelivery.report is fake_report
