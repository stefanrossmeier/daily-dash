from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelCall(BaseModel):
    """Metadata and cost information for one model invocation."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    purpose: str = Field(min_length=1)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: int | None = Field(default=None, ge=0)


class CostSummary(BaseModel):
    """Aggregated model cost for one pipeline run."""

    model_config = ConfigDict(extra="forbid")

    model_calls: list[ModelCall] = Field(default_factory=list)
    total_cost_usd: float = Field(default=0.0, ge=0.0)


class RunManifest(BaseModel):
    """Audit metadata describing one DailyDash pipeline execution."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)

    started_at: datetime
    finished_at: datetime | None = None

    retrieved_items: int = Field(default=0, ge=0)
    candidate_items: int = Field(default=0, ge=0)
    selected_items: int = Field(default=0, ge=0)

    cost: CostSummary = Field(default_factory=CostSummary)
