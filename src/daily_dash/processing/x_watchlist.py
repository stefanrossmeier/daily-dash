from __future__ import annotations

from collections import defaultdict

from daily_dash.config.models import XWatchlistRankingConfig
from daily_dash.contracts.x_watchlist import (
    XWatchlistEvaluation,
    XWatchlistModelEvaluation,
)


def score_x_watchlist_evaluations(
    model_evaluations: list[XWatchlistModelEvaluation],
    config: XWatchlistRankingConfig,
) -> list[XWatchlistEvaluation]:
    scored: list[XWatchlistEvaluation] = []
    for item in model_evaluations:
        semantic = (
            0.30 * (item.relevance / 100.0)
            + 0.30 * (item.market_impact / 100.0)
            + 0.15 * (item.market_breadth / 100.0)
            + 0.25 * (item.information_value / 100.0)
        )
        eligible = (
            semantic >= config.min_semantic_score
            and item.relevance >= config.min_relevance
            and item.market_impact >= config.min_market_impact
            and item.information_value >= config.min_information_value
        )
        scored.append(
            XWatchlistEvaluation(
                **item.model_dump(),
                semantic_score=min(max(semantic, 0.0), 1.0),
                eligible=eligible,
            )
        )

    urgency_order = {"high": 2, "medium": 1, "low": 0}
    scored.sort(
        key=lambda item: (
            item.eligible,
            item.semantic_score,
            urgency_order[item.urgency],
            item.market_impact,
            item.information_value,
            item.market_breadth,
        ),
        reverse=True,
    )
    return scored


def select_x_watchlist_ids(
    evaluations: list[XWatchlistEvaluation],
    *,
    limit: int,
    max_items_per_topic: int,
) -> list[str]:
    if limit <= 0:
        return []
    selected: list[str] = []
    topic_counts: dict[str, int] = defaultdict(int)
    for item in evaluations:
        if not item.eligible:
            continue
        topic = item.topic_key.strip().casefold()
        if topic_counts[topic] >= max_items_per_topic:
            continue
        selected.append(item.id)
        topic_counts[topic] += 1
        if len(selected) >= limit:
            break
    return selected
