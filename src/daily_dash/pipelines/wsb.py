from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config.loader import (
    load_schedule_registry,
    load_wsb_profile,
    load_wsb_source_set,
)
from daily_dash.contracts.news import NewsModelSummary, NewsModelUsage, NewsRankingTrace
from daily_dash.contracts.wsb import WsbModelEvaluation, WsbRunDocument
from daily_dash.llm.gateway import ModelGatewayClient
from daily_dash.llm.wsb import GatewayWsbClassifier
from daily_dash.processing.wsb import (
    score_wsb_evaluations,
    select_wsb_candidates,
    select_wsb_ids,
)
from daily_dash.retrieval.wsb import retrieve_wsb_posts
from daily_dash.scheduling import resolve_daily_cycle_window
from daily_dash.storage.wsb import JsonWsbRunStore


def _model_summary(traces: list[NewsRankingTrace]) -> NewsModelSummary | None:
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


def run_wsb_pipeline(
    *,
    config_dir: Path,
    data_repo: Path,
    gateway_url: str | None = None,
    retrieved_at: datetime | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[WsbRunDocument, Path]:
    now = retrieved_at or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    now = now.astimezone(UTC)
    profile = load_wsb_profile(config_dir / "profiles" / "wsb.yaml")
    source_set = load_wsb_source_set(config_dir / "sources" / f"{profile.source_set}.yaml")
    registry = load_schedule_registry(config_dir / "schedules.yaml")
    window = resolve_daily_cycle_window(
        registry,
        profile.profile_id,
        now,
        explicit_start=window_start,
        explicit_end=window_end,
    )

    posts, diagnostics = retrieve_wsb_posts(
        source_set,
        listing_limit=profile.retrieval.listing_limit,
        max_new_pages=profile.retrieval.max_new_pages,
        window_start=window.window_start,
        window_end=window.window_end,
        retrieved_at=now,
    )
    if not posts:
        errors = "; ".join(item.error or item.mode for item in diagnostics)
        raise RuntimeError(f"WSB retrieval returned no posts: {errors}")

    candidates = select_wsb_candidates(posts, limit=profile.retrieval.candidate_limit)
    run_id = uuid4().hex
    model_evaluations: list[WsbModelEvaluation] = []
    traces: list[NewsRankingTrace] = []

    if profile.ranking.llm_enabled and candidates:
        classifier = GatewayWsbClassifier(ModelGatewayClient(gateway_url))
        for start in range(0, len(candidates), profile.ranking.batch_size):
            batch = candidates[start : start + profile.ranking.batch_size]
            batch_evaluations, trace = classifier.classify_batch(batch, profile)
            model_evaluations.extend(batch_evaluations)
            traces.append(trace)

    evaluations = score_wsb_evaluations(candidates, model_evaluations, profile.ranking)
    selected_ids = select_wsb_ids(
        evaluations,
        limit=profile.presentation.max_items,
        extreme_activity_max_items=profile.ranking.extreme_activity_max_items,
    )
    document = WsbRunDocument(
        run_id=run_id,
        retrieved_at=now,
        window_start=window.window_start,
        window_end=window.window_end,
        timezone=window.timezone,
        previous_scheduled_for=window.previous_scheduled_for,
        scheduled_for=window.scheduled_for,
        retrieval_diagnostics=diagnostics,
        retrieved_count=len(posts),
        candidate_count=len(candidates),
        candidates=candidates,
        evaluations=evaluations,
        selected_ids=selected_ids,
        model_traces=traces,
        model_summary=_model_summary(traces),
    )
    output_path = JsonWsbRunStore(data_repo).write(document)
    return document, output_path
