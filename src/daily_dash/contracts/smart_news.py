from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from daily_dash.contracts.news import NewsRankingTrace, NewsSourceDiagnostic
from daily_dash.contracts.source import SourceItem


class SmartNewsRetrievalWindow(BaseModel):
    """Auditable rolling or explicit retrieval interval for Smart News."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["rolling", "explicit"]
    schedule_id: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    scheduled_for: datetime | None = None
    window_start: datetime
    window_end: datetime
    lookback_hours: int | None = Field(default=None, ge=1, le=168)


class SmartNewsModelTheme(BaseModel):
    """One structured theme returned by the Smart News model call."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    headline_indices: list[int]


class SmartNewsSupportingHeadline(BaseModel):
    """Original headline evidence retained in the immutable run artifact."""

    model_config = ConfigDict(extra="forbid")

    headline_text: str
    headline_link: str


class SmartNewsTheme(BaseModel):
    """Theme surviving the legacy deterministic macro-theme filter."""

    model_config = ConfigDict(extra="forbid")

    title: str
    llm_message: str
    supporting_headlines: list[SmartNewsSupportingHeadline]


class SmartNewsRunDocument(BaseModel):
    """Immutable Smart News run artifact persisted before delivery."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    pipeline: Literal["news-smart"] = "news-smart"

    run_id: str = Field(min_length=1)
    profile: Literal["news-smart"] = "news-smart"
    retrieved_at: datetime
    retrieval_window: SmartNewsRetrievalWindow

    source_diagnostics: list[NewsSourceDiagnostic]
    retrieved_items: list[SourceItem] = Field(default_factory=list)
    retrieved_count: int = Field(ge=0)
    articles: list[SourceItem] = Field(default_factory=list)
    article_count: int = Field(ge=0)

    model_themes: list[SmartNewsModelTheme] = Field(default_factory=list)
    themes: list[SmartNewsTheme] = Field(default_factory=list)
    theme_count: int = Field(ge=0)
    model_trace: NewsRankingTrace | None = None
