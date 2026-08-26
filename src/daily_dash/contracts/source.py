from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from daily_dash.contracts.common import JsonValue, SourceKind


class SourceItem(BaseModel):
    """Normalized item retrieved from an external source."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_kind: SourceKind

    title: str = ""
    text: str = ""
    url: HttpUrl | None = None
    author: str | None = None

    published_at: datetime | None = None
    retrieved_at: datetime

    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class CandidateBatch(BaseModel):
    """Normalized candidates passed into ranking."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    items: list[SourceItem]
