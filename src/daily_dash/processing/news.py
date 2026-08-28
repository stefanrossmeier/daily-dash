from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from daily_dash.contracts.source import SourceItem

if TYPE_CHECKING:
    from daily_dash.contracts.news import (
        NewsDuplicateSuppression,
        NewsRankingContent,
        NewsRankingEvaluation,
    )

_SPACE_RE = re.compile(r"\s+")
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_title(title: str) -> str:
    return _SPACE_RE.sub(" ", title).strip().casefold()


def canonical_url(value: str) -> str:
    parts = urlsplit(value)

    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_KEYS
    ]

    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            urlencode(query),
            "",
        )
    )


def deduplicate_news_items(items: list[SourceItem]) -> list[SourceItem]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[SourceItem] = []

    ordered = sorted(
        items,
        key=lambda item: item.published_at or item.retrieved_at,
        reverse=True,
    )

    for item in ordered:
        title_key = normalize_title(item.title)
        url_key = canonical_url(str(item.url)) if item.url is not None else ""

        if title_key and title_key in seen_titles:
            continue

        if url_key and url_key in seen_urls:
            continue

        if title_key:
            seen_titles.add(title_key)

        if url_key:
            seen_urls.add(url_key)

        result.append(item)

    return result


def source_neutral_prefilter(
    items: list[SourceItem],
    *,
    limit: int,
) -> list[SourceItem]:
    """Cap candidates without using publisher identity or source weights."""

    if limit < 1:
        raise ValueError("prefilter limit must be positive")

    ordered = sorted(
        items,
        key=lambda item: (
            item.published_at or item.retrieved_at,
            item.id,
        ),
        reverse=True,
    )
    return ordered[:limit]


def top_market_selection_score(
    evaluation: NewsRankingEvaluation,
) -> float:
    """Combine model judgments into an auditable Top-News selection score.

    The harmonic mean makes breadth and impact jointly important: a high value
    on one cannot fully compensate for a low value on the other. The remaining
    model judgments contribute secondary evidence. No publisher/source signal is
    used.
    """

    impact = float(evaluation.market_impact)
    breadth = float(evaluation.market_breadth)

    if impact <= 0.0 or breadth <= 0.0:
        market_core = 0.0
    else:
        market_core = 2.0 * impact * breadth / (impact + breadth)

    score = (
        0.65 * market_core
        + 0.10 * evaluation.rank_score
        + 0.10 * evaluation.relevance
        + 0.05 * evaluation.surprise
        + 0.05 * evaluation.novelty
        + 0.05 * evaluation.quality
    ) / 100.0

    return round(min(max(score, 0.0), 1.0), 6)


def apply_top_market_policy(
    ranking: NewsRankingContent,
    *,
    min_score: float,
) -> NewsRankingContent:
    """Apply deterministic Top-News policy to LLM-provided semantic values."""

    if not 0.0 <= min_score <= 1.0:
        raise ValueError("minimum score must be between zero and one")

    scored: list[NewsRankingEvaluation] = []

    for evaluation in ranking.evaluations:
        selection_score = top_market_selection_score(evaluation)
        selection_eligible = (
            selection_score >= min_score
            and evaluation.market_breadth >= 40
            and evaluation.market_impact >= 35
        )
        scored.append(
            evaluation.model_copy(
                update={
                    "selection_score": selection_score,
                    "selection_eligible": selection_eligible,
                }
            )
        )

    scored.sort(
        key=lambda evaluation: (
            -evaluation.selection_score,
            -evaluation.market_breadth,
            -evaluation.market_impact,
            -evaluation.rank_score,
            evaluation.id,
        )
    )

    return ranking.model_copy(
        update={
            "evaluations": scored,
            "ranking": [evaluation.id for evaluation in scored],
        }
    )


def normalize_event_key(value: str) -> str:
    """Normalize a model-supplied event identity for deterministic comparison."""

    normalized = value.strip().casefold()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


def select_distinct_events(
    ranking: NewsRankingContent,
    *,
    limit: int,
    eligible_only: bool = False,
) -> tuple[
    list[str],
    list[NewsDuplicateSuppression],
]:
    """Keep the highest LLM-ranked article per event group."""

    if limit < 1:
        raise ValueError("selection limit must be positive")

    from daily_dash.contracts.news import (
        NewsDuplicateSuppression,
    )

    evaluations = {item.id: item for item in ranking.evaluations}

    parent = {item_id: item_id for item_id in evaluations}

    def find(item_id: str) -> str:
        while parent[item_id] != item_id:
            parent[item_id] = parent[parent[item_id]]
            item_id = parent[item_id]

        return item_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)

        if left_root != right_root:
            parent[right_root] = left_root

    # Explicit LLM duplicate relationships are authoritative.
    for evaluation in ranking.evaluations:
        duplicate_id = evaluation.duplicate_of_id

        if duplicate_id is None:
            continue

        if duplicate_id not in evaluations:
            raise ValueError(f"unknown duplicate target: {duplicate_id}")

        union(
            evaluation.id,
            duplicate_id,
        )

    # Exact event-key matches remain an additional
    # LLM-provided same-event signal.
    event_owner: dict[str, str] = {}

    for evaluation in ranking.evaluations:
        event_key = normalize_event_key(evaluation.event_key)

        if not event_key or event_key == "unclassified":
            continue

        existing = event_owner.get(event_key)

        if existing is None:
            event_owner[event_key] = evaluation.id
        else:
            union(
                evaluation.id,
                existing,
            )

    selected: list[str] = []
    suppressions: list[NewsDuplicateSuppression] = []

    kept_by_group: dict[str, str] = {}

    # ranking.ranking is already ordered by the active ranking policy.
    for item_id in ranking.ranking:
        if eligible_only and not evaluations[item_id].selection_eligible:
            continue

        group = find(item_id)
        kept_id = kept_by_group.get(group)

        if kept_id is not None:
            kept = evaluations[kept_id]
            suppressed = evaluations[item_id]

            event_key = normalize_event_key(kept.event_key)

            if not event_key or event_key == "unclassified":
                event_key = normalize_event_key(suppressed.event_key)

            if not event_key:
                event_key = "llm-duplicate-group"

            suppressions.append(
                NewsDuplicateSuppression(
                    suppressed_id=item_id,
                    kept_id=kept_id,
                    event_key=event_key,
                )
            )
            continue

        kept_by_group[group] = item_id

        if len(selected) < limit:
            selected.append(item_id)

    return selected, suppressions
