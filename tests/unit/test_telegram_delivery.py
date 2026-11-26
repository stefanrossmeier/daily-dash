from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from daily_dash.contracts import ArtifactFormat, DeliveryStatus, ReportArtifact
from daily_dash.delivery.telegram import (
    TELEGRAM_SAFE_MESSAGE_LIMIT,
    TelegramDelivery,
    split_markdown_message,
)


def _artifact(content: str) -> ReportArtifact:
    return ReportArtifact(
        run_id="run-retry",
        profile="news-top",
        format=ArtifactFormat.TELEGRAM,
        content=content,
        created_at=datetime(2026, 11, 26, 15, 0, tzinfo=UTC),
    )


def test_split_markdown_message_keeps_short_report_intact() -> None:
    text = "*Market Snapshot*\n\n```\nAsset  Last\nDAX    100\n```"

    assert split_markdown_message(text) == [text]


def test_split_markdown_message_splits_long_paragraphs() -> None:
    text = "a" * 9000

    parts = split_markdown_message(text, limit=4000)

    assert len(parts) == 3
    assert all(len(part) <= 4000 for part in parts)
    assert "".join(parts) == text


def test_telegram_delivery_can_use_html_parse_mode() -> None:
    from datetime import UTC, datetime

    import httpx

    from daily_dash.contracts import ArtifactFormat, DeliveryStatus, ReportArtifact
    from daily_dash.delivery.telegram import TelegramDelivery

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 123}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    artifact = ReportArtifact(
        run_id="run-html",
        profile="news-top",
        format=ArtifactFormat.TELEGRAM,
        content='<a href="https://example.test/story">Story</a>',
        created_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
    )

    result = TelegramDelivery(
        token="token",
        chat_id="123",
        client=client,
        parse_mode="HTML",
    ).send(artifact)

    assert result.status is DeliveryStatus.SUCCESS
    assert result.external_id == "123"
    body = requests[0].content.decode()
    assert "parse_mode=HTML" in body


def test_telegram_delivery_splits_long_html_report_at_safe_limit() -> None:
    from datetime import UTC, datetime
    from urllib.parse import parse_qs

    import httpx

    from daily_dash.contracts import ArtifactFormat, DeliveryStatus, ReportArtifact
    from daily_dash.delivery.telegram import TelegramDelivery

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": len(requests)}},
        )

    paragraphs = [
        f'<a href="https://example.test/{index}">Story {index} {"x" * 230}</a> — <i>Source</i>'
        for index in range(20)
    ]
    content = "<b>News</b>\n\n" + "\n\n".join(paragraphs)
    assert len(content) > TELEGRAM_SAFE_MESSAGE_LIMIT

    client = httpx.Client(transport=httpx.MockTransport(handler))
    artifact = ReportArtifact(
        run_id="run-long-html",
        profile="news-german",
        format=ArtifactFormat.TELEGRAM,
        content=content,
        created_at=datetime(2026, 8, 28, 15, 0, tzinfo=UTC),
    )

    result = TelegramDelivery(
        token="token",
        chat_id="123",
        client=client,
        parse_mode="HTML",
    ).send(artifact)

    assert result.status is DeliveryStatus.SUCCESS
    assert result.external_id == str(len(requests))
    assert len(requests) > 1

    for request in requests:
        body = request.content.decode()
        fields = parse_qs(body)
        assert fields["parse_mode"] == ["HTML"]
        assert len(fields["text"][0]) <= TELEGRAM_SAFE_MESSAGE_LIMIT


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadError])
def test_telegram_delivery_retries_transport_error(
    error_type: type[httpx.TransportError],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            raise error_type("temporary failure", request=request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 123}})

    monkeypatch.setattr("daily_dash.delivery.telegram.time.sleep", sleeps.append)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = TelegramDelivery("token", "123", client=client).send(_artifact("report"))

    assert result.status is DeliveryStatus.SUCCESS
    assert len(requests) == 2
    assert sleeps == [pytest.approx(1.0, rel=0.25)]


def test_telegram_delivery_honours_retry_after_for_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2.5"},
                json={"ok": False, "description": "Too Many Requests"},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 456}})

    monkeypatch.setattr("daily_dash.delivery.telegram.time.sleep", sleeps.append)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = TelegramDelivery("token", "123", client=client).send(_artifact("report"))

    assert result.status is DeliveryStatus.SUCCESS
    assert len(requests) == 2
    assert sleeps == [2.5]


def test_telegram_delivery_does_not_retry_bad_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            400,
            json={"ok": False, "description": "Bad Request: chat not found"},
        )

    monkeypatch.setattr("daily_dash.delivery.telegram.time.sleep", sleeps.append)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = TelegramDelivery("token", "123", client=client).send(_artifact("report"))

    assert result.status is DeliveryStatus.FAILED
    assert len(requests) == 1
    assert not sleeps
    assert "Bad Request: chat not found" in (result.error or "")
    assert "1 attempt" in (result.error or "")


def test_telegram_delivery_stops_after_three_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ConnectError("connection reset", request=request)

    monkeypatch.setattr("daily_dash.delivery.telegram.time.sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = TelegramDelivery("token", "123", client=client).send(_artifact("report"))

    assert result.status is DeliveryStatus.FAILED
    assert len(requests) == 3
    assert "after 3 attempts" in (result.error or "")


def test_telegram_delivery_resumes_at_first_unsent_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posted_parts: list[str] = []
    part_two_attempts = 0
    first_part = f"FIRST\n{'x' * 3790}"
    second_part = f"SECOND\n{'y' * 3790}"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal part_two_attempts
        fields = parse_qs(request.content.decode())
        text = fields["text"][0]
        posted_parts.append(text)
        if text == second_part:
            part_two_attempts += 1
            if part_two_attempts < 3:
                raise httpx.ReadError("connection reset", request=request)
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": len(posted_parts)}},
        )

    monkeypatch.setattr("daily_dash.delivery.telegram.time.sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    artifact = _artifact(f"{first_part}\n\n{second_part}")

    result = TelegramDelivery("token", "123", client=client).send(artifact)

    assert result.status is DeliveryStatus.SUCCESS
    assert posted_parts == [first_part, second_part, second_part, second_part]
    assert result.external_id == "4"
