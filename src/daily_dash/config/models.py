from __future__ import annotations

from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from daily_dash.contracts.market import MarketGroup

IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


DayOfWeek = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class ScheduleWindowConfig(BaseModel):
    """Retrieval window policy derived from scheduled execution slots."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grace_minutes: int = Field(default=60, ge=0, le=360)


class PipelineScheduleConfig(BaseModel):
    """Schedule definition shared by DailyDash and Windmill."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schedule_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    enabled: bool = True
    flow_path: str = Field(min_length=1, pattern=r"^[fug]/[A-Za-z0-9_./-]+$")
    timezone: str = Field(default="Europe/Berlin", min_length=1)
    days: list[DayOfWeek] = Field(min_length=1)
    slots_local: list[str] = Field(min_length=1)
    window: ScheduleWindowConfig | None = None

    @field_validator("timezone")
    @classmethod
    def validate_schedule_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @field_validator("days")
    @classmethod
    def validate_unique_days(cls, value: list[DayOfWeek]) -> list[DayOfWeek]:
        if len(value) != len(set(value)):
            raise ValueError("schedule days must be unique")
        return value

    @field_validator("slots_local")
    @classmethod
    def validate_slots(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("schedule slots must be unique")

        for slot in value:
            try:
                hour_text, minute_text = slot.split(":", 1)
                hour = int(hour_text)
                minute = int(minute_text)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid schedule slot: {slot!r}") from exc

            if len(slot) != 5 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError(f"invalid schedule slot: {slot!r}")

        return value


class ScheduleRegistry(BaseModel):
    """Versioned registry of all DailyDash production schedules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    schedules: dict[str, PipelineScheduleConfig]

    @model_validator(mode="after")
    def validate_schedule_ids(self) -> Self:
        for key, schedule in self.schedules.items():
            if key != schedule.schedule_id:
                raise ValueError(
                    f"schedule key {key!r} does not match schedule_id {schedule.schedule_id!r}"
                )
        return self


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


class PromptRefConfig(BaseModel):
    """Reference to a versioned prompt asset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        default="news-ranking",
        min_length=1,
        pattern=IDENTIFIER_PATTERN,
    )

    version: str = Field(
        default="v1",
        min_length=1,
        pattern=IDENTIFIER_PATTERN,
    )


class RankingConfig(BaseModel):
    """Deterministic candidate cap and semantic ranking configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_limit: int = Field(default=150, ge=1, le=500)
    top_k: int = Field(default=10, ge=1, le=100)

    llm_enabled: bool = True
    model_alias: str = Field(default="rank-cheap", min_length=1)

    prompt: PromptRefConfig = Field(
        default_factory=PromptRefConfig,
    )

    min_score: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.top_k > self.candidate_limit:
            raise ValueError("top_k must not exceed candidate_limit")
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
    profile_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    pipeline: Literal["news"] = "news"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    retrieval: RetrievalConfig
    keywords: KeywordConfig
    ranking: RankingConfig
    presentation: PresentationConfig

    @model_validator(mode="after")
    def validate_pipeline_limits(self) -> Self:
        if self.presentation.max_items > self.ranking.top_k:
            raise ValueError("presentation.max_items must not exceed ranking.top_k")
        return self


class MarketPresentationConfig(BaseModel):
    """Presentation policy for the market snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(default="Market Snapshot", min_length=1)
    timezone: str = Field(default="Europe/Berlin", min_length=1)
    change_highlight_threshold_pct: float = Field(default=1.0, ge=0.0)
    data_issue_limit: int = Field(default=8, ge=0, le=100)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


class MarketsProfile(BaseModel):
    """Configuration for the markets pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    pipeline: Literal["markets"] = "markets"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    presentation: MarketPresentationConfig


class WeekendMarketsProfile(BaseModel):
    """Configuration for the weekend market-quotes pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    pipeline: Literal["markets-weekend"] = "markets-weekend"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    presentation: MarketPresentationConfig


class RssSourceConfig(BaseModel):
    """Configuration for one RSS or Atom feed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
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
    pipeline: Literal["news"] = "news"
    source_set_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    sources: list[RssSourceConfig]

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> Self:
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique within a source set")
        return self


class MarketAthConfig(BaseModel):
    """Optional ATH series used for one market asset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    period: Literal["10y", "max"] = "10y"
    label: str | None = None


class MarketAssetConfig(BaseModel):
    """One instrument displayed in the market snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    group: MarketGroup
    price_decimals: int = Field(default=2, ge=0, le=8)
    enabled: bool = True
    ath: MarketAthConfig | None = None


class MarketSourceSet(BaseModel):
    """Market instruments retrieved from one market-data provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pipeline: Literal["markets"] = "markets"
    source_set_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    provider: Literal["yfinance"] = "yfinance"
    assets: list[MarketAssetConfig]

    @model_validator(mode="after")
    def validate_unique_asset_ids(self) -> Self:
        ids = [asset.id for asset in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError("asset ids must be unique within a market source set")
        return self


class WeekendMarketQuoteConfig(BaseModel):
    """One public IG weekend market page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    url: HttpUrl
    price_decimals: int = Field(default=2, ge=0, le=8)
    enabled: bool = True


class WeekendMarketSourceSet(BaseModel):
    """IG weekend instruments retrieved from public no-login pages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pipeline: Literal["markets-weekend"] = "markets-weekend"
    source_set_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    provider: Literal["ig-weekend"] = "ig-weekend"
    quotes: list[WeekendMarketQuoteConfig]

    @model_validator(mode="after")
    def validate_unique_quote_ids(self) -> Self:
        ids = [quote.id for quote in self.quotes]
        if len(ids) != len(set(ids)):
            raise ValueError("quote ids must be unique within a weekend market source set")
        return self


type Profile = NewsProfile | MarketsProfile | WeekendMarketsProfile
type SourceSet = NewsSourceSet | MarketSourceSet | WeekendMarketSourceSet
