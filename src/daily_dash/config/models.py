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


class VersionedAssetRefConfig(BaseModel):
    """Reference to a versioned non-code asset."""

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


class PromptRefConfig(VersionedAssetRefConfig):
    """Reference to a versioned prompt asset."""


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
    selection_mode: Literal["model-selected", "top-market-policy"] = "model-selected"

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
    processing_policy: VersionedAssetRefConfig | None = None

    @model_validator(mode="after")
    def validate_pipeline_limits(self) -> Self:
        if self.presentation.max_items > self.ranking.top_k:
            raise ValueError("presentation.max_items must not exceed ranking.top_k")
        return self


class WsbRetrievalConfig(BaseModel):
    """Candidate-pool limits for the WallStreetBets pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_limit: int = Field(default=80, ge=1, le=300)
    listing_limit: int = Field(default=100, ge=10, le=100)
    max_new_pages: int = Field(default=10, ge=1, le=20)
    text_limit_chars: int = Field(default=1800, ge=200, le=10000)


class WsbRankingConfig(BaseModel):
    """Semantic WSB classification plus bounded activity tie-breaking."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_size: int = Field(default=20, ge=1, le=50)
    top_k: int = Field(default=10, ge=1, le=50)
    llm_enabled: bool = True
    model_alias: str = Field(default="rank-cheap", min_length=1)
    prompt: PromptRefConfig = Field(
        default_factory=lambda: PromptRefConfig(id="wsb-ranking", version="v2")
    )
    semantic_weight: float = Field(default=0.85, ge=0.0, le=1.0)
    activity_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    min_semantic_score: float = Field(default=0.50, ge=0.0, le=1.0)
    min_relevance: int = Field(default=55, ge=0, le=100)
    min_market_impact: int = Field(default=35, ge=0, le=100)
    min_market_breadth: int = Field(default=45, ge=0, le=100)
    min_positioning_signal: int = Field(default=60, ge=0, le=100)
    extreme_activity_max_items: int = Field(default=1, ge=0, le=5)
    extreme_activity_min_heat: float = Field(default=75.0, ge=0.0)
    extreme_activity_min_score: int = Field(default=2500, ge=0)
    extreme_activity_min_comments: int = Field(default=300, ge=0)

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if abs((self.semantic_weight + self.activity_weight) - 1.0) > 1e-9:
            raise ValueError("WSB semantic_weight + activity_weight must equal 1")
        return self


class WsbPresentationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(default="WSB — Market-Relevant Bets", min_length=1)
    timezone: str = Field(default="Europe/Berlin", min_length=1)
    max_items: int = Field(default=10, ge=1, le=50)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


class WsbProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_id: Literal["wsb"] = "wsb"
    pipeline: Literal["wsb"] = "wsb"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    retrieval: WsbRetrievalConfig
    ranking: WsbRankingConfig
    presentation: WsbPresentationConfig

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.presentation.max_items > self.ranking.top_k:
            raise ValueError("WSB presentation.max_items must not exceed ranking.top_k")
        if self.ranking.top_k > self.retrieval.candidate_limit:
            raise ValueError("WSB ranking.top_k must not exceed retrieval.candidate_limit")
        return self


class XWatchlistRetrievalConfig(BaseModel):
    """Grok-native X retrieval configuration for the curated watchlist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_alias: str = Field(default="x-retrieve", min_length=1)
    prompt: PromptRefConfig = Field(
        default_factory=lambda: PromptRefConfig(id="x-watchlist-retrieval", version="v4")
    )
    max_items: int = Field(default=80, ge=1, le=200)
    require_citation_evidence: bool = True


class XWatchlistRankingConfig(BaseModel):
    """Semantic market-signal ranking for retrieved X posts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_size: int = Field(default=20, ge=1, le=50)
    top_k: int = Field(default=12, ge=1, le=50)
    llm_enabled: bool = True
    model_alias: str = Field(default="rank-cheap", min_length=1)
    prompt: PromptRefConfig = Field(
        default_factory=lambda: PromptRefConfig(id="x-watchlist-ranking", version="v4")
    )
    min_semantic_score: float = Field(default=0.35, ge=0.0, le=1.0)
    min_relevance: int = Field(default=35, ge=0, le=100)
    min_market_impact: int = Field(default=15, ge=0, le=100)
    min_information_value: int = Field(default=30, ge=0, le=100)
    max_items_per_topic: int = Field(default=1, ge=1, le=5)


class XWatchlistPresentationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(default="X Watchlist", min_length=1)
    timezone: str = Field(default="Europe/Berlin", min_length=1)
    max_items: int = Field(default=12, ge=1, le=50)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


class XWatchlistProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_id: Literal["x-watchlist"] = "x-watchlist"
    pipeline: Literal["x-watchlist"] = "x-watchlist"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    retrieval: XWatchlistRetrievalConfig
    ranking: XWatchlistRankingConfig
    presentation: XWatchlistPresentationConfig

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.presentation.max_items > self.ranking.top_k:
            raise ValueError("X Watchlist presentation.max_items must not exceed ranking.top_k")
        if self.ranking.top_k > self.retrieval.max_items:
            raise ValueError("X Watchlist ranking.top_k must not exceed retrieval.max_items")
        return self


class PolymarketRetrievalConfig(BaseModel):
    """Event-level Polymarket retrieval limits for semantic and hot lanes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_limit: int = Field(default=30, ge=1, le=100)
    semantic_event_limit_per_tag: int = Field(default=60, ge=5, le=200)
    global_event_limit: int = Field(default=100, ge=10, le=500)
    hot_activity_pool_limit: int = Field(default=30, ge=5, le=100)
    liquidity_min: float = Field(default=5000.0, ge=0.0)
    semantic_tag_slugs: list[str] = Field(
        default_factory=lambda: [
            "finance",
            "crypto",
            "politics",
            "geopolitics",
            "economy",
            "tech",
        ],
        min_length=1,
    )
    trade_window_minutes: int = Field(default=120, ge=15, le=1440)
    trade_event_batch_size: int = Field(default=10, ge=1, le=30)
    trade_page_limit: int = Field(default=1000, ge=100, le=10000)
    max_trade_pages: int = Field(default=2, ge=1, le=2)
    description_limit_chars: int = Field(default=1200, ge=200, le=10000)
    event_market_question_limit: int = Field(default=6, ge=1, le=20)

    @field_validator("semantic_tag_slugs")
    @classmethod
    def validate_semantic_tag_slugs(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        if not normalized:
            raise ValueError("Polymarket semantic_tag_slugs must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Polymarket semantic_tag_slugs must be unique")
        return normalized


class PolymarketRankingConfig(BaseModel):
    """LLM ranking of financially material Polymarket events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_size: int = Field(default=20, ge=1, le=50)
    top_k: int = Field(default=7, ge=1, le=30)
    llm_enabled: bool = True
    model_alias: str = Field(default="rank-cheap", min_length=1)
    prompt: PromptRefConfig = Field(
        default_factory=lambda: PromptRefConfig(id="polymarket-ranking", version="v6")
    )
    min_ranking_score: int = Field(default=50, ge=0, le=100)
    min_relevance: int = Field(default=55, ge=0, le=100)
    min_market_impact: int = Field(default=35, ge=0, le=100)
    min_market_breadth: int = Field(default=45, ge=0, le=100)
    min_prediction_signal: int = Field(default=60, ge=0, le=100)
    max_items_per_topic: int = Field(default=1, ge=1, le=5)
    max_items_per_theme: int = Field(default=2, ge=1, le=5)


class PolymarketHotConfig(BaseModel):
    """Deterministic global Polymarket activity lane; no LLM is used."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_items: int = Field(default=3, ge=0, le=10)
    min_volume_24h: float = Field(default=500000.0, ge=0.0)
    min_recent_trades: int = Field(default=100, ge=0)
    min_comments: int = Field(default=50, ge=0)
    min_abs_1h_change: float = Field(default=0.05, ge=0.0, le=1.0)
    min_abs_1d_change: float = Field(default=0.10, ge=0.0, le=1.0)


class PolymarketPresentationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(default="Polymarket — Signals & Hot Topics", min_length=1)
    timezone: str = Field(default="Europe/Berlin", min_length=1)
    max_signal_items: int = Field(default=7, ge=1, le=30)
    max_hot_items: int = Field(default=3, ge=0, le=10)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


class PolymarketProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_id: Literal["polymarket"] = "polymarket"
    pipeline: Literal["polymarket"] = "polymarket"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    retrieval: PolymarketRetrievalConfig
    ranking: PolymarketRankingConfig
    hot: PolymarketHotConfig
    presentation: PolymarketPresentationConfig

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.presentation.max_signal_items > self.ranking.top_k:
            raise ValueError(
                "Polymarket presentation.max_signal_items must not exceed ranking.top_k"
            )
        if self.ranking.top_k > self.retrieval.candidate_limit:
            raise ValueError("Polymarket ranking.top_k must not exceed retrieval.candidate_limit")
        if self.presentation.max_hot_items > self.hot.max_items:
            raise ValueError("Polymarket presentation.max_hot_items must not exceed hot.max_items")
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


class YieldPresentationConfig(BaseModel):
    """Presentation policy for the deterministic yield report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(default="Yield Report", min_length=1)
    timezone: str = Field(default="Europe/Berlin", min_length=1)
    data_issue_limit: int = Field(default=8, ge=0, le=100)
    curve_lookback_points: int = Field(default=5, ge=2, le=20)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


class YieldProfile(BaseModel):
    """Configuration for the official-source yield pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    pipeline: Literal["yields"] = "yields"
    source_set: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    presentation: YieldPresentationConfig


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


class WsbSourceSet(BaseModel):
    """Reddit listing configuration for the WallStreetBets report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pipeline: Literal["wsb"] = "wsb"
    source_set_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    provider: Literal["reddit"] = "reddit"
    subreddit: str = Field(default="wallstreetbets", min_length=1)
    listings: list[Literal["hot", "rising", "new", "top_day", "top_week"]]
    rss_url: HttpUrl

    @field_validator("listings")
    @classmethod
    def validate_unique_listings(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("WSB listings must be unique")
        return value


class XWatchlistSourceSet(BaseModel):
    """Curated X handles discoverable only through Grok-native X search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pipeline: Literal["x-watchlist"] = "x-watchlist"
    source_set_id: Literal["x-watchlist"] = "x-watchlist"
    provider: Literal["grok-x-search"] = "grok-x-search"
    handles: list[str] = Field(min_length=1, max_length=20)

    @field_validator("handles")
    @classmethod
    def validate_handles(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lstrip("@") for item in value if item.strip()]
        if not normalized:
            raise ValueError("X Watchlist handles must not be empty")
        folded = [item.casefold() for item in normalized]
        if len(folded) != len(set(folded)):
            raise ValueError("X Watchlist handles must be unique")
        return normalized


class PolymarketSourceSet(BaseModel):
    """Public Polymarket API endpoints used by the report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pipeline: Literal["polymarket"] = "polymarket"
    source_set_id: Literal["polymarket"] = "polymarket"
    provider: Literal["polymarket-public-api"] = "polymarket-public-api"
    gamma_events_url: HttpUrl
    data_trades_url: HttpUrl
    user_agent: str = Field(min_length=1)


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


class YieldSeriesConfig(BaseModel):
    """One official yield series or benchmark table lookup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    provider: Literal["fred", "bundesbank", "ecb"]
    dataset: str | None = None
    key: str | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_provider_fields(self) -> Self:
        if self.provider == "fred" and not self.key:
            raise ValueError("FRED yield series require key")
        if self.provider in {"bundesbank", "ecb"} and (not self.dataset or not self.key):
            raise ValueError(f"{self.provider} yield series require dataset and key")
        return self


class YieldSourceSet(BaseModel):
    """Official statistical series consumed by the yield report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    pipeline: Literal["yields"] = "yields"
    source_set_id: str = Field(min_length=1, pattern=IDENTIFIER_PATTERN)
    observation_limit: int = Field(default=12, ge=5, le=60)
    series: list[YieldSeriesConfig]

    @model_validator(mode="after")
    def validate_unique_series_ids(self) -> Self:
        ids = [series.id for series in self.series]
        if len(ids) != len(set(ids)):
            raise ValueError("series ids must be unique within a yield source set")
        return self


type Profile = (
    NewsProfile
    | WsbProfile
    | XWatchlistProfile
    | PolymarketProfile
    | MarketsProfile
    | WeekendMarketsProfile
    | YieldProfile
)
type SourceSet = (
    NewsSourceSet
    | WsbSourceSet
    | XWatchlistSourceSet
    | PolymarketSourceSet
    | MarketSourceSet
    | WeekendMarketSourceSet
    | YieldSourceSet
)
