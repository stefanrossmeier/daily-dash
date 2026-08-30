from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FuturesDataType = Literal["tradingview_1h", "tradingview_daily"]
FuturesChangeBasis = Literal["previous_close", "unavailable"]
FuturesQuoteStatus = Literal["ok", "partial", "unavailable"]


class RawFuturesQuote(BaseModel):
    """TradingView-derived quote plus provenance for one configured dashboard row."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    price_decimals: int = Field(default=2, ge=0, le=8)
    contract: str | None = None
    last: float | None = None
    previous_value: float | None = None
    change_basis: FuturesChangeBasis = "unavailable"
    source: str | None = None
    source_ref: str | None = None
    source_timestamp: datetime | None = None
    data_type: FuturesDataType | None = None
    error: str | None = None


class RawFuturesSnapshot(BaseModel):
    """Complete TradingView retrieval result for one Futures Snapshot run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    source_set: str = Field(min_length=1)
    retrieved_at: datetime
    quotes: list[RawFuturesQuote]


class FuturesQuote(BaseModel):
    """Processed row consumed by presentation."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    price_decimals: int = Field(default=2, ge=0, le=8)
    contract: str | None = None
    last: float | None = None
    previous_value: float | None = None
    change_pct: float | None = None
    change_basis: FuturesChangeBasis = "unavailable"
    source: str | None = None
    source_ref: str | None = None
    source_timestamp: datetime | None = None
    data_type: FuturesDataType | None = None
    status: FuturesQuoteStatus


class FuturesReportData(BaseModel):
    """Processed deterministic data for the compact Futures Snapshot."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    generated_at: datetime
    quotes: list[FuturesQuote]
    issues: list[str] = Field(default_factory=list)


class FuturesSnapshotDocument(BaseModel):
    """Versioned immutable Futures Snapshot artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["futures"] = "futures"
    raw: RawFuturesSnapshot
    report: FuturesReportData
