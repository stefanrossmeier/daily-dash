from __future__ import annotations

import math

from daily_dash.config.models import WsbRankingConfig
from daily_dash.contracts.wsb import WsbEvaluation, WsbModelEvaluation, WsbPost


def select_wsb_candidates(posts: list[WsbPost], *, limit: int) -> list[WsbPost]:
    """Diversify candidates across heat, discussion depth and recency without keywords."""

    if limit <= 0:
        return []

    views = [
        sorted(posts, key=lambda p: (p.heat, p.num_comments, p.score), reverse=True),
        sorted(posts, key=lambda p: (p.num_comments, p.heat, p.score), reverse=True),
        sorted(posts, key=lambda p: p.created_at, reverse=True),
    ]
    out: list[WsbPost] = []
    seen: set[str] = set()
    index = 0
    while len(out) < limit:
        added = False
        for view in views:
            if index < len(view):
                post = view[index]
                if post.id not in seen:
                    seen.add(post.id)
                    out.append(post)
                    added = True
                    if len(out) >= limit:
                        break
        if not added and all(index >= len(view) - 1 for view in views):
            break
        index += 1
    return out


def _harmonic(left: float, right: float) -> float:
    if left <= 0.0 or right <= 0.0:
        return 0.0
    return 2.0 * left * right / (left + right)


def _activity_scores(posts: list[WsbPost]) -> dict[str, float]:
    if not posts:
        return {}
    transformed = {post.id: math.log1p(max(post.heat, 0.0)) for post in posts}
    ceiling = max(transformed.values(), default=0.0)
    if ceiling <= 0.0:
        return {post.id: 0.0 for post in posts}
    return {post_id: value / ceiling for post_id, value in transformed.items()}


def score_wsb_evaluations(
    posts: list[WsbPost],
    model_evaluations: list[WsbModelEvaluation],
    config: WsbRankingConfig,
) -> list[WsbEvaluation]:
    activities = _activity_scores(posts)
    posts_by_id = {post.id: post for post in posts}
    scored: list[WsbEvaluation] = []

    for item in model_evaluations:
        relevance = item.relevance / 100.0
        impact = item.market_impact / 100.0
        breadth = item.market_breadth / 100.0
        positioning = item.positioning_signal / 100.0
        broad_path = _harmonic(impact, breadth)
        bet_path = _harmonic(impact, positioning)
        semantic = 0.8 * max(broad_path, bet_path) + 0.2 * relevance
        activity = activities.get(item.id, 0.0)
        selection = config.semantic_weight * semantic + config.activity_weight * activity
        post = posts_by_id.get(item.id)
        market_eligible = (
            item.signal_type != "narrow-or-irrelevant"
            and semantic >= config.min_semantic_score
            and item.relevance >= config.min_relevance
            and item.market_impact >= config.min_market_impact
            and (
                item.market_breadth >= config.min_market_breadth
                or item.positioning_signal >= config.min_positioning_signal
            )
        )
        extreme_activity_eligible = bool(
            post
            and config.extreme_activity_max_items > 0
            and post.heat >= config.extreme_activity_min_heat
            and (
                post.score >= config.extreme_activity_min_score
                or post.num_comments >= config.extreme_activity_min_comments
            )
        )
        scored.append(
            WsbEvaluation(
                **item.model_dump(),
                semantic_score=min(max(semantic, 0.0), 1.0),
                activity_score=min(max(activity, 0.0), 1.0),
                selection_score=min(max(selection, 0.0), 1.0),
                market_eligible=market_eligible,
                extreme_activity_eligible=extreme_activity_eligible,
                eligible=market_eligible or extreme_activity_eligible,
            )
        )

    scored.sort(
        key=lambda item: (
            item.eligible,
            item.selection_score,
            item.semantic_score,
            item.market_impact,
            item.market_breadth,
            item.positioning_signal,
        ),
        reverse=True,
    )
    return scored


def select_wsb_ids(
    evaluations: list[WsbEvaluation],
    *,
    limit: int,
    extreme_activity_max_items: int = 0,
) -> list[str]:
    if limit <= 0:
        return []

    extreme_only = [
        item for item in evaluations if item.extreme_activity_eligible and not item.market_eligible
    ][: max(extreme_activity_max_items, 0)]
    reserved = min(len(extreme_only), limit)
    market = [item for item in evaluations if item.market_eligible][: limit - reserved]

    selected = [item.id for item in market]
    selected.extend(item.id for item in extreme_only[:reserved] if item.id not in selected)
    return selected
