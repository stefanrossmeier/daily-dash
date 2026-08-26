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
