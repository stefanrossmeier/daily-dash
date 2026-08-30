from __future__ import annotations

import re
from typing import Any

from daily_dash.contracts.smart_news import (
    SmartNewsModelTheme,
    SmartNewsSupportingHeadline,
    SmartNewsTheme,
)
from daily_dash.contracts.source import SourceItem
from daily_dash.policies import SmartNewsPolicy


def select_smart_articles(items: list[SourceItem], *, limit: int) -> list[SourceItem]:
    """Legacy Smart News selection: exact-link dedupe, newest-first, then cap."""

    if limit < 1:
        raise ValueError("article limit must be positive")

    deduplicated: list[SourceItem] = []
    seen_links: set[str] = set()

    for item in items:
        link = str(item.url or "")
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)
        deduplicated.append(item)

    deduplicated.sort(
        key=lambda item: item.published_at or item.retrieved_at,
        reverse=True,
    )
    return deduplicated[:limit]


def _normalize_headline_indices(value: Any, *, max_index: int) -> list[int]:
    if not isinstance(value, list):
        return []

    indices: list[int] = []
    seen: set[int] = set()
    for item in value:
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue

        if index < 1 or index > max_index or index in seen:
            continue

        seen.add(index)
        indices.append(index)

    return indices


def _normalize_theme_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _count_term_hits(text: str, terms: tuple[str, ...]) -> int:
    normalized_text = _normalize_theme_text(text)
    if not normalized_text:
        return 0

    padded_text = f" {normalized_text} "
    hits = 0
    for term in terms:
        normalized_term = _normalize_theme_text(term)
        if normalized_term and f" {normalized_term} " in padded_text:
            hits += 1
    return hits


def _supporting_articles_for_theme(
    articles: list[SourceItem],
    theme: SmartNewsModelTheme,
) -> list[SourceItem]:
    return [
        articles[index - 1]
        for index in _normalize_headline_indices(
            theme.headline_indices,
            max_index=len(articles),
        )
    ]


def _macro_profile_for_theme(
    articles: list[SourceItem],
    theme: SmartNewsModelTheme,
    policy: SmartNewsPolicy,
) -> dict[str, int]:
    supporting_articles = _supporting_articles_for_theme(articles, theme)
    combined_text = " ".join(
        [theme.title, theme.summary]
        + [
            " ".join(
                [
                    article.title.strip(),
                    article.text.strip(),
                    article.source.strip(),
                ]
            )
            for article in supporting_articles
        ]
    )

    sources = {
        article.source.strip().casefold()
        for article in supporting_articles
        if article.source.strip()
    }
    macro_hits = _count_term_hits(combined_text, tuple(policy.macro_priority_terms))
    title_macro_hits = _count_term_hits(theme.title, tuple(policy.macro_priority_terms))
    narrow_hits = _count_term_hits(combined_text, tuple(policy.narrow_corporate_terms))
    title_narrow_hits = _count_term_hits(theme.title, tuple(policy.narrow_corporate_terms))
    support_count = len(supporting_articles)
    source_count = len(sources)
    scoring = policy.scoring
    score = (
        macro_hits * scoring.macro_hit_weight
        + title_macro_hits * scoring.title_macro_hit_weight
        + min(support_count, scoring.support_count_cap)
        + min(source_count, scoring.source_count_cap)
        - narrow_hits * scoring.narrow_hit_penalty
        - title_narrow_hits * scoring.title_narrow_hit_penalty
    )

    return {
        "macro_hits": macro_hits,
        "title_macro_hits": title_macro_hits,
        "narrow_hits": narrow_hits,
        "title_narrow_hits": title_narrow_hits,
        "support_count": support_count,
        "source_count": source_count,
        "score": score,
    }


def _is_macro_theme_relevant(profile: dict[str, int], policy: SmartNewsPolicy) -> bool:
    support_count = profile["support_count"]
    macro_hits = profile["macro_hits"]
    title_macro_hits = profile["title_macro_hits"]
    narrow_hits = profile["narrow_hits"]
    title_narrow_hits = profile["title_narrow_hits"]
    score = profile["score"]

    eligibility = policy.eligibility
    if support_count == 0:
        return (
            macro_hits >= eligibility.no_support_min_macro_hits
            and title_macro_hits >= eligibility.no_support_min_title_macro_hits
            and title_narrow_hits == 0
        )
    if support_count == 1:
        if (
            macro_hits < eligibility.one_support_min_macro_hits
            or title_macro_hits < eligibility.one_support_min_title_macro_hits
        ):
            return False
        if (
            title_narrow_hits > 0
            and macro_hits < eligibility.one_support_title_narrow_override_macro_hits
        ):
            return False
    if support_count == 2 and macro_hits < eligibility.two_support_min_macro_hits:
        return False
    if macro_hits < eligibility.title_narrow_min_macro_hits and title_narrow_hits > 0:
        return False
    if (
        macro_hits < eligibility.narrow_cluster_min_macro_hits
        and narrow_hits >= eligibility.narrow_cluster_min_narrow_hits
        and support_count <= eligibility.narrow_cluster_max_support_count
    ):
        return False
    return score >= eligibility.minimum_score


def select_macro_themes(
    articles: list[SourceItem],
    themes: list[SmartNewsModelTheme],
    *,
    max_themes: int,
    policy: SmartNewsPolicy,
) -> list[SmartNewsModelTheme]:
    """Port of the legacy deterministic Smart News macro-theme filter."""

    ranked: list[tuple[int, int, SmartNewsModelTheme]] = []

    for original_index, theme in enumerate(themes):
        sanitized_theme = SmartNewsModelTheme(
            title=theme.title.strip(),
            summary=theme.summary.strip(),
            headline_indices=_normalize_headline_indices(
                theme.headline_indices,
                max_index=len(articles),
            ),
        )
        profile = _macro_profile_for_theme(articles, sanitized_theme, policy)
        if _is_macro_theme_relevant(profile, policy):
            ranked.append((profile["score"], original_index, sanitized_theme))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [theme for _, _, theme in ranked[:max_themes]]


def materialize_smart_themes(
    articles: list[SourceItem],
    themes: list[SmartNewsModelTheme],
) -> list[SmartNewsTheme]:
    result: list[SmartNewsTheme] = []

    for theme in themes:
        supporting_headlines: list[SmartNewsSupportingHeadline] = []
        for index in _normalize_headline_indices(
            theme.headline_indices,
            max_index=len(articles),
        ):
            article = articles[index - 1]
            supporting_headlines.append(
                SmartNewsSupportingHeadline(
                    headline_text=article.title.strip(),
                    headline_link=str(article.url or ""),
                )
            )

        result.append(
            SmartNewsTheme(
                title=theme.title.strip(),
                llm_message=theme.summary.strip(),
                supporting_headlines=supporting_headlines,
            )
        )

    return result
