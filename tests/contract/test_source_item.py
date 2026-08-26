from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from daily_dash.contracts import SourceItem, SourceKind


def test_source_item_can_be_created() -> None:
    item = SourceItem(
        id="example-1",
        source="example",
        source_kind=SourceKind.RSS,
        title="Example story",
        url="https://example.com/story",
        retrieved_at=datetime.now(UTC),
    )

    assert item.id == "example-1"
    assert item.source_kind is SourceKind.RSS


def test_source_item_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SourceItem(
            id="example-1",
            source="example",
            source_kind=SourceKind.RSS,
            retrieved_at=datetime.now(UTC),
            unexpected="value",
        )
