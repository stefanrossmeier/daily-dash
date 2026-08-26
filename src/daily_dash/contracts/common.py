from __future__ import annotations

from enum import StrEnum

from pydantic import JsonValue as JsonValue

type JsonPrimitive = str | int | float | bool | None


class SourceKind(StrEnum):
    RSS = "rss"
    WEB = "web"
    REDDIT = "reddit"
    POLYMARKET = "polymarket"
    X_SEARCH = "x_search"


class ArtifactFormat(StrEnum):
    MARKDOWN = "markdown"
    TELEGRAM = "telegram"
    JSON = "json"


class DeliveryStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
