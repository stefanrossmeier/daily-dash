from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class YieldObservation(BaseModel):
    """One dated yield observation in percent per annum."""

    model_config = ConfigDict(extra="forbid")

    observed_on: date
    value_pct: float


class RawYieldSeries(BaseModel):
    """Raw observations and retrieval diagnostics for one configured series."""

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    observations: list[YieldObservation] = Field(default_factory=list)
    error: str | None = None


class RawYieldSnapshot(BaseModel):
    """Complete raw retrieval result for one Yield Report run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    source_set: str = Field(min_length=1)
    retrieved_at: datetime
    series: list[RawYieldSeries]


class YieldLevel(BaseModel):
    """Latest level plus one-observation change for a yield series."""

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    observed_on: date | None = None
    value_pct: float | None = None
    change_bp: float | None = None


class YieldSpread(BaseModel):
    """Date-aligned spread between two yield series."""

    model_config = ConfigDict(extra="forbid")

    spread_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    observed_on: date | None = None
    value_pp: float | None = None
    change_bp: float | None = None
    signal: Literal["green", "orange", "red", "neutral"] = "neutral"


class YieldCurveRegime(BaseModel):
    """Deterministic US 2Y/10Y curve-regime classification."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    delta_2y_pp: float
    delta_10y_pp: float
    description: str = Field(min_length=1)


class YieldReportData(BaseModel):
    """Processed data consumed by Yield Report presentation adapters."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    generated_at: datetime
    levels: list[YieldLevel]
    spreads: list[YieldSpread]
    curve_regime: YieldCurveRegime | None = None
    issues: list[str] = Field(default_factory=list)


class YieldSnapshotDocument(BaseModel):
    """Versioned immutable artifact for one Yield Report run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["yields"] = "yields"
    raw: RawYieldSnapshot
    report: YieldReportData
