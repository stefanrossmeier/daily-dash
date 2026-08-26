from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from daily_dash.contracts.source import SourceItem


class RankingDecision(BaseModel):
    """Semantic ranking result for one candidate."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)

    relevance: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    quality: float = Field(ge=0.0, le=1.0)

    score: float = Field(ge=0.0, le=1.0)

    selected: bool
    rationale: str = ""


class RankedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: SourceItem
    ranking: RankingDecision


class RankedBatch(BaseModel):
    """Ranked candidates produced by a ranking stage."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    items: list[RankedItem]
