from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from daily_dash.contracts.news import NewsModelSummary, NewsRankingTrace

PolymarketSignalType = Literal[
    "broad-market",
    "market-moving-bet",
    "both",
    "narrow-or-irrelevant",
]

PolymarketTheme = Literal[
    "monetary-policy",
    "macro-economy",
    "geopolitics-security",
    "energy-shipping",
    "crypto-digital-assets",
    "regulation-policy",
    "equities-corporate",
    "technology",
    "other",
]


class PolymarketEventMarket(BaseModel):
    """One child contract summarized under a Polymarket event."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    condition_id: str = Field(min_length=1)
    slug: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    outcome_prices: list[float] = Field(default_factory=list)
    top_outcome: str | None = None
    top_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    volume_24h: float = Field(default=0.0, ge=0.0)
    one_hour_price_change: float = 0.0
    one_day_price_change: float = 0.0


class PolymarketEvent(BaseModel):
    """Normalized event used transiently by semantic and hot-event lanes."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    event_id: int = Field(ge=1)
    title: str = Field(min_length=1)
    description: str = ""
    url: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    start_at: datetime | None = None
    end_at: datetime | None = None
    volume_24h: float = Field(default=0.0, ge=0.0)
    liquidity: float = Field(default=0.0, ge=0.0)
    comment_count: int = Field(default=0, ge=0)
    recent_trades: int = Field(default=0, ge=0)
    max_abs_one_hour_price_change: float = Field(default=0.0, ge=0.0)
    max_abs_one_day_price_change: float = Field(default=0.0, ge=0.0)
    markets: list[PolymarketEventMarket] = Field(default_factory=list)


class PolymarketEventSnapshot(BaseModel):
    """Compact selected-event representation safe to persist in daily artifacts."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    event_id: int = Field(ge=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    end_at: datetime | None = None
    volume_24h: float = Field(default=0.0, ge=0.0)
    liquidity: float = Field(default=0.0, ge=0.0)
    comment_count: int = Field(default=0, ge=0)
    recent_trades: int = Field(default=0, ge=0)
    max_abs_one_hour_price_change: float = Field(default=0.0, ge=0.0)
    max_abs_one_day_price_change: float = Field(default=0.0, ge=0.0)
    representative_question: str | None = None
    representative_outcome: str | None = None
    representative_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class PolymarketRetrievalDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events_ok: bool
    trades_ok: bool
    semantic_tag_requests: int = Field(ge=0)
    semantic_event_count: int = Field(ge=0)
    global_event_count: int = Field(ge=0)
    unique_event_count: int = Field(ge=0)
    trade_scope_event_count: int = Field(ge=0)
    trade_count: int = Field(ge=0)
    trade_pages: int = Field(ge=0)
    trade_window_minutes: int = Field(ge=1)
    trade_window_complete: bool
    errors: list[str] = Field(default_factory=list)


class PolymarketModelEvaluation(BaseModel):
    """Semantic event-classifier output before deterministic eligibility."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=100)
    market_impact: int = Field(ge=0, le=100)
    market_breadth: int = Field(ge=0, le=100)
    prediction_signal: int = Field(ge=0, le=100)
    ranking_score: int = Field(ge=0, le=100)
    topic_key: str = Field(min_length=1, max_length=120)
    theme: PolymarketTheme = "other"
    signal_type: PolymarketSignalType
    rationale: str = Field(min_length=1, max_length=500)


class PolymarketEvaluation(PolymarketModelEvaluation):
    """LLM event ranking plus deterministic financial-signal eligibility."""

    event_slug: str | None = None
    selection_score: float = Field(ge=0.0, le=1.0)
    market_eligible: bool
    eligible: bool


class PolymarketCandidateAudit(BaseModel):
    """Compact rejected/selected score record; no descriptions or rationale."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    ranking_score: int = Field(ge=0, le=100)
    relevance: int = Field(ge=0, le=100)
    market_impact: int = Field(ge=0, le=100)
    market_breadth: int = Field(ge=0, le=100)
    prediction_signal: int = Field(ge=0, le=100)
    topic_key: str = Field(min_length=1, max_length=120)
    theme: PolymarketTheme = "other"
    signal_type: PolymarketSignalType
    market_eligible: bool


class PolymarketSignalSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: PolymarketEventSnapshot
    evaluation: PolymarketEvaluation


class PolymarketHotSelection(BaseModel):
    """Deterministic no-LLM global activity selection."""

    model_config = ConfigDict(extra="forbid")

    event: PolymarketEventSnapshot
    activity_score: float = Field(ge=0.0, le=1.0)


class PolymarketRunDocument(BaseModel):
    """Compact immutable Polymarket artifact persisted before Telegram delivery."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    pipeline: Literal["polymarket"] = "polymarket"
    run_id: str = Field(min_length=1)
    profile: Literal["polymarket"] = "polymarket"
    retrieved_at: datetime
    timezone: str = Field(min_length=1)
    previous_scheduled_for: datetime | None = None
    scheduled_for: datetime | None = None
    window_start: datetime
    window_end: datetime

    retrieval_diagnostics: list[PolymarketRetrievalDiagnostic]
    retrieved_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    hot_candidate_count: int = Field(ge=0)
    signals: list[PolymarketSignalSelection] = Field(default_factory=list)
    hot: list[PolymarketHotSelection] = Field(default_factory=list)
    candidate_audit: list[PolymarketCandidateAudit] = Field(default_factory=list)
    model_traces: list[NewsRankingTrace] = Field(default_factory=list)
    model_summary: NewsModelSummary | None = None

    @model_validator(mode="after")
    def validate_ids(self) -> Self:
        signal_ids = [item.event.id for item in self.signals]
        hot_ids = [item.event.id for item in self.hot]
        audit_ids = [item.id for item in self.candidate_audit]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("Polymarket signal events must have unique ids")
        if len(hot_ids) != len(set(hot_ids)):
            raise ValueError("Polymarket hot events must have unique ids")
        if len(audit_ids) != len(set(audit_ids)):
            raise ValueError("Polymarket candidate audit ids must be unique")
        unknown_signals = set(signal_ids) - set(audit_ids)
        if unknown_signals:
            raise ValueError(
                f"Polymarket signal ids missing candidate audit: {sorted(unknown_signals)}"
            )
        return self
