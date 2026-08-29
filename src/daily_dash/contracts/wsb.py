from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from daily_dash.contracts.news import NewsModelSummary, NewsRankingTrace

WsbSignalType = Literal[
    "broad-market",
    "market-moving-bet",
    "both",
    "narrow-or-irrelevant",
]


class WsbPost(BaseModel):
    """Normalized WallStreetBets thread with deterministic activity metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = ""
    url: str = Field(min_length=1)
    author: str | None = None
    created_at: datetime
    num_comments: int = Field(default=0, ge=0)
    score: int = Field(default=0)
    listing_sources: list[str] = Field(default_factory=list)
    heat: float = Field(default=0.0, ge=0.0)


class WsbRetrievalDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["oauth", "public-json", "rss"]
    ok: bool
    item_count: int = Field(ge=0)
    listing_pages: dict[str, int] = Field(default_factory=dict)
    window_complete: bool = True
    error: str | None = None


class WsbModelEvaluation(BaseModel):
    """Semantic classifier output before deterministic scoring."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=100)
    market_impact: int = Field(ge=0, le=100)
    market_breadth: int = Field(ge=0, le=100)
    positioning_signal: int = Field(ge=0, le=100)
    signal_type: WsbSignalType
    rationale: str = Field(min_length=1)


class WsbEvaluation(WsbModelEvaluation):
    """Semantic judgment plus deterministic activity/selection scores."""

    semantic_score: float = Field(ge=0.0, le=1.0)
    activity_score: float = Field(ge=0.0, le=1.0)
    selection_score: float = Field(ge=0.0, le=1.0)
    market_eligible: bool
    extreme_activity_eligible: bool
    eligible: bool


class WsbRunDocument(BaseModel):
    """Immutable WSB run artifact persisted before Telegram delivery."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["wsb"] = "wsb"
    run_id: str = Field(min_length=1)
    profile: Literal["wsb"] = "wsb"
    retrieved_at: datetime
    window_start: datetime
    window_end: datetime
    timezone: str = Field(min_length=1)
    previous_scheduled_for: datetime | None = None
    scheduled_for: datetime | None = None

    retrieval_diagnostics: list[WsbRetrievalDiagnostic]
    retrieved_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    candidates: list[WsbPost]
    evaluations: list[WsbEvaluation]
    selected_ids: list[str]
    model_traces: list[NewsRankingTrace] = Field(default_factory=list)
    model_summary: NewsModelSummary | None = None

    @model_validator(mode="after")
    def validate_selected_ids(self) -> Self:
        evaluation_ids = [item.id for item in self.evaluations]
        if len(evaluation_ids) != len(set(evaluation_ids)):
            raise ValueError("WSB evaluations must have unique ids")
        if len(self.selected_ids) != len(set(self.selected_ids)):
            raise ValueError("WSB selected ids must be unique")
        unknown = set(self.selected_ids) - set(evaluation_ids)
        if unknown:
            raise ValueError(f"WSB selected ids missing evaluations: {sorted(unknown)}")
        return self
