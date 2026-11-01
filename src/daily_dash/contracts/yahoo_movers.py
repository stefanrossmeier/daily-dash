from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RawMoverEntry(BaseModel):
    """One raw stock quote from a Yahoo Finance predefined screener."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: float
    change_pct: float
    volume: int | None = None


class RawMoverCategory(BaseModel):
    """Raw screener result and retrieval diagnostics for one category."""

    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    screener: str = Field(min_length=1)
    movers: list[RawMoverEntry] = Field(default_factory=list)
    error: str | None = None


class RawMoverSnapshot(BaseModel):
    """Complete raw retrieval result for one Yahoo Movers report run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    source_set: str = Field(min_length=1)
    retrieved_at: datetime
    categories: list[RawMoverCategory]


class MoverEntry(BaseModel):
    """Processed stock quote displayed in one movers section."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: float
    change_pct: float


class MoverSection(BaseModel):
    """Top movers of one screener category, limited to the configured rank."""

    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    movers: list[MoverEntry] = Field(default_factory=list)


class MoversReportData(BaseModel):
    """Processed data consumed by Yahoo Movers presentation adapters."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    generated_at: datetime
    sections: list[MoverSection]
    issues: list[str] = Field(default_factory=list)


class MoversSnapshotDocument(BaseModel):
    """Versioned immutable artifact for one Yahoo Movers report run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["yahoo-movers"] = "yahoo-movers"
    raw: RawMoverSnapshot
    report: MoversReportData
