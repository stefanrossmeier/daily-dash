from __future__ import annotations

import html
import re
from typing import Any

from daily_dash.contracts.smart_news import (
    SmartNewsModelTheme,
    SmartNewsSupportingHeadline,
    SmartNewsTheme,
)
from daily_dash.contracts.source import SourceItem

MACRO_PRIORITY_TERMS = (
    "ai",
    "airline",
    "airlines",
    "antitrust",
    "banking",
    "banks",
    "bond",
    "bonds",
    "budget",
    "ceasefire",
    "central bank",
    "china",
    "commodity",
    "competition",
    "conflict",
    "credit",
    "crude",
    "currency",
    "currencies",
    "cyber",
    "data center",
    "diplomacy",
    "dollar",
    "ecb",
    "economic",
    "economy",
    "electricity",
    "energy",
    "equities",
    "equity",
    "eu",
    "europe",
    "european union",
    "fed",
    "fiscal",
    "fx",
    "gas",
    "gdp",
    "geopolitics",
    "government",
    "growth",
    "hormuz",
    "inflation",
    "iran",
    "israel",
    "lebanon",
    "liquidity",
    "market",
    "markets",
    "middle east",
    "monetary",
    "nuclear",
    "oil",
    "pboc",
    "peace",
    "policy",
    "power",
    "rates",
    "rate cut",
    "rate cuts",
    "regulation",
    "regulatory",
    "regulator",
    "regulators",
    "recession",
    "risk sentiment",
    "sanction",
    "sanctions",
    "semiconductor",
    "shipping",
    "solar",
    "supply",
    "supply chain",
    "tariff",
    "tech",
    "technology",
    "trade",
    "transport",
    "treasuries",
    "treasury",
    "truce",
    "utilities",
    "volatility",
    "war",
    "wind",
    "yield",
    "yields",
)

NARROW_CORPORATE_TERMS = (
    "acquisition",
    "app",
    "bankruptcy",
    "bankruptcy exit",
    "buyback",
    "buyout",
    "dividend",
    "earnings",
    "feature",
    "fundraising",
    "guidance",
    "ipo",
    "liquidation",
    "m a",
    "merger",
    "product",
    "rollout",
    "shareholder",
    "stake",
    "takeover",
    "transaction",
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def clean_smart_text(value: Any, max_len: int | None = None) -> str:
    """Preserve the legacy Smart News input cleaning/truncation behavior."""

    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if max_len and len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


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


def build_llm_input_for_themes(articles: list[SourceItem]) -> str:
    lines: list[str] = []
    for index, article in enumerate(articles, start=1):
        source = clean_smart_text(article.source, max_len=80)
        title = clean_smart_text(article.title, max_len=220)
        summary = clean_smart_text(article.text, max_len=320)
        lines.append(f"{index}) [{source}] {title}")
        if summary and summary.casefold() != title.casefold():
            lines.append(f"   Summary: {summary}")
    return "\n".join(lines)


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
    macro_hits = _count_term_hits(combined_text, MACRO_PRIORITY_TERMS)
    title_macro_hits = _count_term_hits(theme.title, MACRO_PRIORITY_TERMS)
    narrow_hits = _count_term_hits(combined_text, NARROW_CORPORATE_TERMS)
    title_narrow_hits = _count_term_hits(theme.title, NARROW_CORPORATE_TERMS)
    support_count = len(supporting_articles)
    source_count = len(sources)
    score = (
        macro_hits * 3
        + title_macro_hits * 2
        + min(support_count, 4)
        + min(source_count, 3)
        - narrow_hits * 2
        - title_narrow_hits * 2
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


def _is_macro_theme_relevant(profile: dict[str, int]) -> bool:
    support_count = profile["support_count"]
    macro_hits = profile["macro_hits"]
    title_macro_hits = profile["title_macro_hits"]
    narrow_hits = profile["narrow_hits"]
    title_narrow_hits = profile["title_narrow_hits"]
    score = profile["score"]

    if support_count == 0:
        return macro_hits >= 5 and title_macro_hits >= 1 and title_narrow_hits == 0
    if support_count == 1:
        if macro_hits < 3 or title_macro_hits == 0:
            return False
        if title_narrow_hits > 0 and macro_hits < 4:
            return False
    if support_count == 2 and macro_hits < 3:
        return False
    if macro_hits < 3 and title_narrow_hits > 0:
        return False
    if macro_hits < 4 and narrow_hits >= 2 and support_count <= 2:
        return False
    return score >= 8


def select_macro_themes(
    articles: list[SourceItem],
    themes: list[SmartNewsModelTheme],
    *,
    max_themes: int,
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
        profile = _macro_profile_for_theme(articles, sanitized_theme)
        if _is_macro_theme_relevant(profile):
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
