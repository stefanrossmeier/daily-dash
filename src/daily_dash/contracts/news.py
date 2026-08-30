from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from daily_dash.contracts.source import SourceItem


class NewsSourceDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    ok: bool
    item_count: int = Field(ge=0)
    error: str | None = None


class NewsRetrievalWindow(BaseModel):
    """Auditable interval used for one scheduled or replayed News retrieval."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["schedule", "explicit"]
    schedule_id: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    previous_scheduled_for: datetime | None = None
    scheduled_for: datetime | None = None
    window_start: datetime
    window_end: datetime
    grace_minutes: int = Field(default=0, ge=0)


class NewsScreeningEvaluation(BaseModel):
    """Minimal model judgments used to choose rich-ranking finalists."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=100)
    market_impact: int = Field(ge=0, le=100)
    market_breadth: int = Field(ge=0, le=100)
    screening_score: float = Field(default=0.0, ge=0.0, le=1.0)


class NewsScreeningContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: list[NewsScreeningEvaluation]
    finalist_ids: list[str]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        evaluation_ids = [item.id for item in self.evaluations]
        if len(evaluation_ids) != len(set(evaluation_ids)):
            raise ValueError("screening evaluations must have unique ids")
        if len(self.finalist_ids) != len(set(self.finalist_ids)):
            raise ValueError("screening finalist ids must be unique")
        return self


class NewsRankingEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    event_key: str = Field(default="unclassified", min_length=1)
    duplicate_of_id: str | None = None
    rank_score: int = Field(default=0, ge=0, le=100)
    tier: int = Field(ge=1, le=5)
    priority: int = Field(default=0, ge=0, le=100)
    relevance: int = Field(ge=0, le=100)
    market_impact: int = Field(ge=0, le=100)
    market_breadth: int = Field(default=0, ge=0, le=100)
    surprise: int = Field(ge=0, le=100)
    quality: int = Field(ge=0, le=100)
    novelty: int = Field(ge=0, le=100)
    selected: bool
    selection_score: float = Field(default=0.0, ge=0.0, le=1.0)
    selection_eligible: bool = True
    rationale: str = Field(min_length=1)


class NewsRankingContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: list[NewsRankingEvaluation]
    ranking: list[str]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        evaluation_ids = [item.id for item in self.evaluations]

        if len(evaluation_ids) != len(set(evaluation_ids)):
            raise ValueError("ranking evaluations must have unique ids")

        if len(self.ranking) != len(set(self.ranking)):
            raise ValueError("ranking ids must be unique")

        return self


class NewsModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)


class NewsRankingTrace(BaseModel):
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


class NewsModelSummary(BaseModel):
    """Aggregate logical model calls and provider attempts for one News run."""

    model_config = ConfigDict(extra="forbid")

    usage: NewsModelUsage
    latency_ms: int = Field(ge=0)
    calls: int = Field(ge=1)
    attempts: int = Field(ge=1)
    retries: int = Field(default=0, ge=0)
    usage_complete: bool = True

    @model_validator(mode="before")
    @classmethod
    def derive_retries(cls, value: object) -> object:
        if isinstance(value, dict) and "retries" not in value:
            attempts = value.get("attempts")
            calls = value.get("calls")
            if isinstance(attempts, int) and isinstance(calls, int):
                value = {**value, "retries": max(attempts - calls, 0)}
        return value

    @model_validator(mode="after")
    def validate_retry_count(self) -> Self:
        expected = max(self.attempts - self.calls, 0)
        if self.retries != expected:
            raise ValueError("retries must equal attempts minus logical calls")
        return self


class NewsDuplicateSuppression(BaseModel):
    """A lower-ranked article suppressed because the event is already present."""

    model_config = ConfigDict(extra="forbid")

    suppressed_id: str = Field(min_length=1)
    kept_id: str = Field(min_length=1)
    event_key: str = Field(min_length=1)


class NewsRunDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["news"] = "news"

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    retrieved_at: datetime
    retrieval_window: NewsRetrievalWindow | None = None

    source_diagnostics: list[NewsSourceDiagnostic]
    retrieved_items: list[SourceItem] = Field(default_factory=list)
    retrieved_count: int = Field(ge=0)
    deduplicated_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    finalist_count: int | None = Field(default=None, ge=0)

    candidates: list[SourceItem]
    screening: NewsScreeningContent | None = None
    screening_traces: list[NewsRankingTrace] = Field(default_factory=list)
    ranking: NewsRankingContent
    ranking_trace: NewsRankingTrace
    model_summary: NewsModelSummary | None = None
    selected_ids: list[str]
    duplicate_suppressions: list[NewsDuplicateSuppression] = Field(
        default_factory=list,
    )
