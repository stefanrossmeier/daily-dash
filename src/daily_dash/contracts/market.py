from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MarketGroup(StrEnum):
    INDICES = "indices"
    FX = "fx"
    VOLATILITY = "volatility"
    COMMODITIES = "commodities"
    CRYPTO = "crypto"


class RawMarketAsset(BaseModel):
    """Raw market facts produced by a market data adapter."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    group: MarketGroup
    price_decimals: int = Field(default=2, ge=0, le=8)

    last: float | None = None
    previous_close: float | None = None
    error: str | None = None

    ath_label: str | None = None
    ath_symbol: str | None = None
    ath_period: str | None = None
    ath_last: float | None = None
    ath_high: float | None = None
    ath_error: str | None = None


class RawMarketSnapshot(BaseModel):
    """Complete raw retrieval result for one markets run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    source_set: str = Field(min_length=1)
    retrieved_at: datetime
    assets: list[RawMarketAsset]


class ProcessedMarketAsset(BaseModel):
    """Market asset after deterministic calculations."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    group: MarketGroup
    price_decimals: int = Field(default=2, ge=0, le=8)

    last: float | None = None
    change_pct: float | None = None

    ath_label: str | None = None
    ath_symbol: str | None = None
    ath_distance_pct: float | None = None


class MarketReportData(BaseModel):
    """Processed data consumed by market presentation adapters."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    generated_at: datetime
    assets: list[ProcessedMarketAsset]
    issues: list[str] = Field(default_factory=list)
