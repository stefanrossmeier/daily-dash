from __future__ import annotations

from daily_dash.config.models import PolymarketHotConfig, PolymarketRankingConfig
from daily_dash.contracts.polymarket import (
    PolymarketEvaluation,
    PolymarketEvent,
    PolymarketEventMarket,
    PolymarketEventSnapshot,
    PolymarketHotSelection,
    PolymarketModelEvaluation,
)


def _pctile_scale(values: list[float], value: float) -> float:
    positive = sorted(item for item in values if item > 0.0)
    if not positive or value <= 0.0:
        return 0.0
    index = int(0.9 * (len(positive) - 1))
    p90 = positive[index]
    if p90 <= 0.0:
        return 0.0
    return min(value / p90, 1.0)


def polymarket_activity_scores(events: list[PolymarketEvent]) -> dict[str, float]:
    """Score global event activity without using an LLM.

    Recent volume and trades dominate. Total comments are deliberately a smaller signal because
    the public event API exposes cumulative comment count rather than a 24-hour comment count.
    """

    if not events:
        return {}
    volumes = [item.volume_24h for item in events]
    trades = [float(item.recent_trades) for item in events]
    comments = [float(item.comment_count) for item in events]
    hour_moves = [item.max_abs_one_hour_price_change for item in events]
    day_moves = [item.max_abs_one_day_price_change for item in events]
    scores: dict[str, float] = {}
    for item in events:
        score = (
            0.40 * _pctile_scale(volumes, item.volume_24h)
            + 0.25 * _pctile_scale(trades, float(item.recent_trades))
            + 0.15 * _pctile_scale(comments, float(item.comment_count))
            + 0.12 * _pctile_scale(hour_moves, item.max_abs_one_hour_price_change)
            + 0.08 * _pctile_scale(day_moves, item.max_abs_one_day_price_change)
        )
        scores[item.id] = min(max(score, 0.0), 1.0)
    return scores


def score_polymarket_evaluations(
    events: list[PolymarketEvent],
    model_evaluations: list[PolymarketModelEvaluation],
    config: PolymarketRankingConfig,
) -> list[PolymarketEvaluation]:
    """Apply deterministic eligibility floors around the model's final ranking score."""

    events_by_id = {item.id: item for item in events}
    scored: list[PolymarketEvaluation] = []
    for item in model_evaluations:
        event = events_by_id.get(item.id)
        market_eligible = (
            event is not None
            and item.signal_type != "narrow-or-irrelevant"
            and item.ranking_score >= config.min_ranking_score
            and item.relevance >= config.min_relevance
            and item.market_impact >= config.min_market_impact
            and (
                item.market_breadth >= config.min_market_breadth
                or item.prediction_signal >= config.min_prediction_signal
            )
        )
        scored.append(
            PolymarketEvaluation(
                **item.model_dump(),
                event_slug=event.slug if event else None,
                selection_score=item.ranking_score / 100.0,
                market_eligible=market_eligible,
                eligible=market_eligible,
            )
        )

    scored.sort(
        key=lambda item: (
            item.market_eligible,
            item.ranking_score,
            item.market_impact,
            item.market_breadth,
            item.prediction_signal,
        ),
        reverse=True,
    )
    return scored


def select_polymarket_signal_ids(
    evaluations: list[PolymarketEvaluation],
    *,
    limit: int,
    max_items_per_topic: int,
    max_items_per_theme: int,
) -> list[str]:
    if limit <= 0:
        return []
    selected: list[str] = []
    topic_counts: dict[str, int] = {}
    theme_counts: dict[str, int] = {}
    for item in sorted(evaluations, key=lambda row: row.ranking_score, reverse=True):
        if not item.market_eligible:
            continue
        if topic_counts.get(item.topic_key, 0) >= max_items_per_topic:
            continue
        if theme_counts.get(item.theme, 0) >= max_items_per_theme:
            continue
        selected.append(item.id)
        topic_counts[item.topic_key] = topic_counts.get(item.topic_key, 0) + 1
        theme_counts[item.theme] = theme_counts.get(item.theme, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def _representative_market(event: PolymarketEvent) -> PolymarketEventMarket | None:
    if not event.markets:
        return None
    return max(event.markets, key=lambda item: item.volume_24h)


def snapshot_polymarket_event(event: PolymarketEvent) -> PolymarketEventSnapshot:
    representative = _representative_market(event)
    return PolymarketEventSnapshot(
        id=event.id,
        event_id=event.event_id,
        title=event.title[:240],
        url=event.url,
        slug=event.slug,
        tags=event.tags[:8],
        end_at=event.end_at,
        volume_24h=event.volume_24h,
        liquidity=event.liquidity,
        comment_count=event.comment_count,
        recent_trades=event.recent_trades,
        max_abs_one_hour_price_change=event.max_abs_one_hour_price_change,
        max_abs_one_day_price_change=event.max_abs_one_day_price_change,
        representative_question=(representative.question[:180] if representative else None),
        representative_outcome=representative.top_outcome if representative else None,
        representative_probability=representative.top_probability if representative else None,
    )


def select_polymarket_hot_events(
    events: list[PolymarketEvent],
    config: PolymarketHotConfig,
    *,
    limit: int,
) -> list[PolymarketHotSelection]:
    if limit <= 0 or config.max_items <= 0:
        return []
    activity = polymarket_activity_scores(events)
    eligible = [
        item
        for item in events
        if item.volume_24h >= config.min_volume_24h
        and (
            item.recent_trades >= config.min_recent_trades
            or item.comment_count >= config.min_comments
            or item.max_abs_one_hour_price_change >= config.min_abs_1h_change
            or item.max_abs_one_day_price_change >= config.min_abs_1d_change
        )
    ]
    eligible.sort(
        key=lambda item: (
            activity.get(item.id, 0.0),
            item.volume_24h,
            item.recent_trades,
            item.comment_count,
        ),
        reverse=True,
    )
    return [
        PolymarketHotSelection(
            event=snapshot_polymarket_event(item),
            activity_score=activity.get(item.id, 0.0),
        )
        for item in eligible[: min(limit, config.max_items)]
    ]
