from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from daily_dash.contracts.news import NewsModelSummary, NewsModelUsage

XCategory = Literal[
    "macro",
    "monetary-policy",
    "rates",
    "fx",
    "equities",
    "commodities",
    "credit",
    "crypto",
    "geopolitics",
    "market-structure",
    "company-specific",
    "other",
]
XUrgency = Literal["low", "medium", "high"]


class XWatchlistPost(BaseModel):
    """Validated X post returned by Grok-native X search."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    author_handle: str = Field(min_length=1)
    publication_time: datetime
    post_text: str = Field(min_length=1)
    post_url: str = Field(min_length=1)
    linked_urls: list[str] = Field(default_factory=list)


class XWatchlistRetrievalDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    allowed_handles: list[str]
    returned_count: int = Field(ge=0)
    validated_count: int = Field(ge=0)
    rejected_invalid_author: int = Field(default=0, ge=0)
    rejected_invalid_url: int = Field(default=0, ge=0)
    rejected_invalid_timestamp: int = Field(default=0, ge=0)
    rejected_outside_window: int = Field(default=0, ge=0)
    rejected_missing_citation: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    search_call_count: int = Field(default=0, ge=0)
    search_queries: list[str] = Field(default_factory=list)
    citation_count: int = Field(default=0, ge=0)


class XWatchlistModelTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    prompt_version: str
    prompt_profile: str
    system_sha256: str
    profile_sha256: str
    task_sha256: str | None = None
    combined_sha256: str
    model_alias: str
    provider: str
    resolved_model: str
    generation_id: str | None = None
    usage: NewsModelUsage
    latency_ms: int = Field(ge=0)
    attempts: int = Field(default=1, ge=1)
    attempt_errors: list[str] = Field(default_factory=list)
    usage_complete: bool = True
    x_search_call_count: int = Field(default=0, ge=0)
    x_search_queries: list[str] = Field(default_factory=list)
    citation_urls: list[str] = Field(default_factory=list)


class XWatchlistModelEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=100)
    market_impact: int = Field(ge=0, le=100)
    market_breadth: int = Field(ge=0, le=100)
    information_value: int = Field(ge=0, le=100)
    category: XCategory
    urgency: XUrgency
    topic_key: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1)


class XWatchlistEvaluation(XWatchlistModelEvaluation):
    semantic_score: float = Field(ge=0.0, le=1.0)
    eligible: bool


class XWatchlistRunDocument(BaseModel):
    """Immutable X Watchlist run artifact persisted before Telegram delivery."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["x-watchlist"] = "x-watchlist"
    run_id: str = Field(min_length=1)
    profile: Literal["x-watchlist"] = "x-watchlist"
    retrieved_at: datetime
    window_start: datetime
    window_end: datetime
    timezone: str = Field(min_length=1)
    previous_scheduled_for: datetime | None = None
    scheduled_for: datetime | None = None

    retrieval_diagnostic: XWatchlistRetrievalDiagnostic
    retrieved_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    candidates: list[XWatchlistPost]
    evaluations: list[XWatchlistEvaluation]
    selected_ids: list[str]
    model_traces: list[XWatchlistModelTrace] = Field(default_factory=list)
    model_summary: NewsModelSummary | None = None

    @model_validator(mode="after")
    def validate_ids(self) -> Self:
        candidate_ids = [item.id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("X Watchlist candidate ids must be unique")
        evaluation_ids = [item.id for item in self.evaluations]
        if len(evaluation_ids) != len(set(evaluation_ids)):
            raise ValueError("X Watchlist evaluation ids must be unique")
        if len(self.selected_ids) != len(set(self.selected_ids)):
            raise ValueError("X Watchlist selected ids must be unique")
        unknown = set(self.selected_ids) - set(evaluation_ids)
        if unknown:
            raise ValueError(f"X Watchlist selected ids missing evaluations: {sorted(unknown)}")
        return self
