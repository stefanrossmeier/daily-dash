from daily_dash.delivery.telegram import split_markdown_message


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
