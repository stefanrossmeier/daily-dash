from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RawWeekendMarketQuote(BaseModel):
    """Raw quote facts retrieved from one public IG weekend market page."""

    model_config = ConfigDict(extra="forbid")

    quote_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    price_decimals: int = Field(default=2, ge=0, le=8)
    bid: float | None = None
    ask: float | None = None
    change_pct: float | None = None
    error: str | None = None


class RawWeekendMarketSnapshot(BaseModel):
    """Complete raw retrieval result for one weekend markets run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    source_set: str = Field(min_length=1)
    retrieved_at: datetime
    quotes: list[RawWeekendMarketQuote]


class WeekendMarketQuote(BaseModel):
    """Weekend quote consumed by presentation adapters."""

    model_config = ConfigDict(extra="forbid")

    quote_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price_decimals: int = Field(default=2, ge=0, le=8)
    bid: float | None = None
    ask: float | None = None
    change_pct: float | None = None


class WeekendMarketReportData(BaseModel):
    """Processed data consumed by weekend market presentation adapters."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    generated_at: datetime
    quotes: list[WeekendMarketQuote]
    issues: list[str] = Field(default_factory=list)


class WeekendMarketSnapshotDocument(BaseModel):
    """Versioned document persisted for one weekend markets run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["markets-weekend"] = "markets-weekend"
    raw: RawWeekendMarketSnapshot
    report: WeekendMarketReportData
