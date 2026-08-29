from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from daily_dash.config.loader import (
    load_news_profile,
    load_news_source_set,
    load_schedule_registry,
)
from daily_dash.contracts.news import NewsRankingTrace
from daily_dash.contracts.smart_news import (
    SmartNewsModelTheme,
    SmartNewsRetrievalWindow,
    SmartNewsRunDocument,
    SmartNewsTheme,
)
from daily_dash.llm.gateway import ModelGatewayClient
from daily_dash.llm.smart_news import GatewaySmartNewsAnalyzer
from daily_dash.processing.smart_news import (
    materialize_smart_themes,
    select_macro_themes,
    select_smart_articles,
)
from daily_dash.retrieval.smart_news import retrieve_smart_source_set
from daily_dash.scheduling import scheduled_slots_before_or_at
from daily_dash.storage.smart_news import JsonSmartNewsRunStore


def _resolve_smart_window(
    *,
    profile_id: str,
    config_dir: Path,
    retrieved_at: datetime,
    lookback_hours: int,
    explicit_start: datetime | None,
    explicit_end: datetime | None,
) -> SmartNewsRetrievalWindow:
    if (explicit_start is None) != (explicit_end is None):
        raise ValueError("explicit window start and end must be supplied together")

    registry = load_schedule_registry(config_dir / "schedules.yaml")
    schedule = registry.schedules.get(profile_id)
    if schedule is None:
        raise ValueError(f"unknown Smart News schedule: {profile_id}")

    if explicit_start is not None and explicit_end is not None:
        if explicit_start.tzinfo is None or explicit_end.tzinfo is None:
            raise ValueError("explicit window bounds must be timezone-aware")
        start = explicit_start.astimezone(UTC)
        end = explicit_end.astimezone(UTC)
        if start >= end:
            raise ValueError("explicit window start must be before end")
        return SmartNewsRetrievalWindow(
            source="explicit",
            schedule_id=profile_id,
            timezone=schedule.timezone,
            window_start=start,
            window_end=end,
        )

    scheduled_for = scheduled_slots_before_or_at(
        schedule,
        retrieved_at,
        count=1,
    )[0]
    return SmartNewsRetrievalWindow(
        source="rolling",
        schedule_id=profile_id,
        timezone=schedule.timezone,
        scheduled_for=scheduled_for.astimezone(UTC),
        window_start=retrieved_at - timedelta(hours=lookback_hours),
        window_end=retrieved_at,
        lookback_hours=lookback_hours,
    )


def run_smart_news_pipeline(
    *,
    config_dir: Path,
    data_repo: Path,
    gateway_url: str | None = None,
    retrieved_at: datetime | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[SmartNewsRunDocument, Path]:
    now = retrieved_at or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    now = now.astimezone(UTC)

    profile = load_news_profile(config_dir / "profiles" / "news-smart.yaml")
    source_set = load_news_source_set(config_dir / "sources" / f"{profile.source_set}.yaml")
    retrieval_window = _resolve_smart_window(
        profile_id=profile.profile_id,
        config_dir=config_dir,
        retrieved_at=now,
        lookback_hours=profile.retrieval.lookback_hours,
        explicit_start=window_start,
        explicit_end=window_end,
    )

    if retrieval_window.source == "explicit":
        retrieved, diagnostics = retrieve_smart_source_set(
            source_set,
            max_items_per_source=profile.retrieval.max_items_per_source,
            lookback_hours=None,
            retrieved_at=now,
            window_start=retrieval_window.window_start,
            window_end=retrieval_window.window_end,
        )
    else:
        retrieved, diagnostics = retrieve_smart_source_set(
            source_set,
            max_items_per_source=profile.retrieval.max_items_per_source,
            lookback_hours=profile.retrieval.lookback_hours,
            retrieved_at=now,
        )

    if not any(item.ok for item in diagnostics):
        raise RuntimeError("all enabled Smart News sources failed")

    articles = select_smart_articles(
        retrieved,
        limit=profile.ranking.candidate_limit,
    )
    run_id = uuid4().hex
    model_themes: list[SmartNewsModelTheme]
    trace: NewsRankingTrace | None
    themes: list[SmartNewsTheme]

    if articles:
        model_themes, trace = GatewaySmartNewsAnalyzer(ModelGatewayClient(gateway_url)).analyze(
            articles,
            profile,
        )
        selected_model_themes = select_macro_themes(
            articles,
            model_themes,
            max_themes=profile.presentation.max_items,
        )
        themes = materialize_smart_themes(articles, selected_model_themes)
    else:
        model_themes = []
        trace = None
        themes = []

    document = SmartNewsRunDocument(
        run_id=run_id,
        retrieved_at=now,
        retrieval_window=retrieval_window,
        source_diagnostics=diagnostics,
        retrieved_items=retrieved,
        retrieved_count=len(retrieved),
        articles=articles,
        article_count=len(articles),
        model_themes=model_themes,
        themes=themes,
        theme_count=len(themes),
        model_trace=trace,
    )
    output_path = JsonSmartNewsRunStore(data_repo).write(document)
    return document, output_path
