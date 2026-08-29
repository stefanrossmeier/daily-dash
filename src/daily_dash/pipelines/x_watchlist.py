from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config.loader import (
    load_schedule_registry,
    load_x_watchlist_profile,
    load_x_watchlist_source_set,
)
from daily_dash.contracts.news import NewsModelSummary, NewsModelUsage
from daily_dash.contracts.x_watchlist import (
    XWatchlistModelEvaluation,
    XWatchlistModelTrace,
    XWatchlistRunDocument,
)
from daily_dash.llm.gateway import ModelGatewayClient
from daily_dash.llm.x_watchlist import GatewayXWatchlistClassifier
from daily_dash.processing.x_watchlist import (
    score_x_watchlist_evaluations,
    select_x_watchlist_ids,
)
from daily_dash.retrieval.x_watchlist import retrieve_x_watchlist_posts
from daily_dash.scheduling import resolve_schedule_window
from daily_dash.storage.x_watchlist import JsonXWatchlistRunStore


def _model_summary(traces: list[XWatchlistModelTrace]) -> NewsModelSummary | None:
    if not traces:
        return None
    return NewsModelSummary(
        usage=NewsModelUsage(
            input_tokens=sum(trace.usage.input_tokens for trace in traces),
            output_tokens=sum(trace.usage.output_tokens for trace in traces),
            total_tokens=sum(trace.usage.total_tokens for trace in traces),
            cost_usd=sum(trace.usage.cost_usd for trace in traces),
        ),
        latency_ms=sum(trace.latency_ms for trace in traces),
        calls=len(traces),
        attempts=sum(trace.attempts for trace in traces),
        retries=sum(max(trace.attempts - 1, 0) for trace in traces),
        usage_complete=all(trace.usage_complete for trace in traces),
    )


def run_x_watchlist_pipeline(
    *,
    config_dir: Path,
    data_repo: Path,
    gateway_url: str | None = None,
    retrieved_at: datetime | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[XWatchlistRunDocument, Path]:
    now = retrieved_at or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    now = now.astimezone(UTC)

    profile = load_x_watchlist_profile(config_dir / "profiles" / "x-watchlist.yaml")
    source_set = load_x_watchlist_source_set(config_dir / "sources" / f"{profile.source_set}.yaml")
    registry = load_schedule_registry(config_dir / "schedules.yaml")
    window = resolve_schedule_window(
        registry,
        profile.profile_id,
        now,
        explicit_start=window_start,
        explicit_end=window_end,
    )

    posts, diagnostic, retrieval_trace = retrieve_x_watchlist_posts(
        source_set,
        profile,
        window_start=window.window_start,
        window_end=window.window_end,
        gateway_url=gateway_url,
    )
    candidates = posts[: profile.retrieval.max_items]

    model_evaluations: list[XWatchlistModelEvaluation] = []
    traces: list[XWatchlistModelTrace] = [retrieval_trace]
    if profile.ranking.llm_enabled and candidates:
        classifier = GatewayXWatchlistClassifier(ModelGatewayClient(gateway_url))
        for start in range(0, len(candidates), profile.ranking.batch_size):
            batch = candidates[start : start + profile.ranking.batch_size]
            batch_evaluations, trace = classifier.classify_batch(batch, profile)
            model_evaluations.extend(batch_evaluations)
            traces.append(trace)

    evaluations = score_x_watchlist_evaluations(model_evaluations, profile.ranking)
    selected_ids = select_x_watchlist_ids(
        evaluations,
        limit=profile.presentation.max_items,
        max_items_per_topic=profile.ranking.max_items_per_topic,
    )
    document = XWatchlistRunDocument(
        run_id=uuid4().hex,
        retrieved_at=now,
        window_start=window.window_start,
        window_end=window.window_end,
        timezone=window.timezone,
        previous_scheduled_for=window.previous_scheduled_for,
        scheduled_for=window.scheduled_for,
        retrieval_diagnostic=diagnostic,
        retrieved_count=len(posts),
        candidate_count=len(candidates),
        candidates=candidates,
        evaluations=evaluations,
        selected_ids=selected_ids,
        model_traces=traces,
        model_summary=_model_summary(traces),
    )
    output_path = JsonXWatchlistRunStore(data_repo).write(document)
    return document, output_path
