from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class RetrievalConfig(BaseModel):
    """Retrieval limits shared by news profiles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lookback_hours: int = Field(default=24, ge=1, le=168)
    max_items_per_source: int = Field(default=50, ge=1, le=500)


class KeywordConfig(BaseModel):
    """Profile-specific keyword selection hints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class RankingConfig(BaseModel):
    """Candidate reduction and semantic ranking configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prefilter_limit: int = Field(default=40, ge=1, le=500)
    top_k: int = Field(default=10, ge=1, le=100)

    llm_enabled: bool = True
    model_alias: str = Field(default="rank-cheap", min_length=1)

    min_score: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.top_k > self.prefilter_limit:
            raise ValueError("top_k must not exceed prefilter_limit")
        return self


class PresentationConfig(BaseModel):
    """Presentation policy independent of delivery destination."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1)
    language: str = Field(default="en", min_length=2, max_length=16)
    max_items: int = Field(default=10, ge=1, le=100)


class NewsProfile(BaseModel):
    """Configuration for one instance of the generic news pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1

    profile_id: str = Field(
        min_length=1,
        pattern=IDENTIFIER_PATTERN,
    )

    pipeline: Literal["news"] = "news"

    source_set: str = Field(
        min_length=1,
        pattern=IDENTIFIER_PATTERN,
    )

    retrieval: RetrievalConfig
    keywords: KeywordConfig
    ranking: RankingConfig
    presentation: PresentationConfig

    @model_validator(mode="after")
    def validate_pipeline_limits(self) -> Self:
        if self.presentation.max_items > self.ranking.top_k:
            raise ValueError("presentation.max_items must not exceed ranking.top_k")
        return self


class RssSourceConfig(BaseModel):
    """Configuration for one RSS or Atom feed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        min_length=1,
        pattern=IDENTIFIER_PATTERN,
    )

    name: str = Field(min_length=1)

    kind: Literal["rss"] = "rss"

    url: HttpUrl

    enabled: bool = True

    weight: float = Field(default=1.0, ge=0.0, le=5.0)

    tags: list[str] = Field(default_factory=list)


class NewsSourceSet(BaseModel):
    """Named set of feeds consumed by a news profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1

    source_set_id: str = Field(
        min_length=1,
        pattern=IDENTIFIER_PATTERN,
    )

    sources: list[RssSourceConfig]

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> Self:
        ids = [source.id for source in self.sources]

        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique within a source set")

        return self
