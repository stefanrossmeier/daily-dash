from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config.loader import (
    load_news_profile,
    load_news_source_set,
    load_schedule_registry,
)
from daily_dash.contracts.news import (
    NewsModelSummary,
    NewsModelUsage,
    NewsRankingTrace,
    NewsRunDocument,
)
from daily_dash.contracts.source import CandidateBatch
from daily_dash.llm.gateway import ModelGatewayClient
from daily_dash.processing.news import (
    apply_top_market_policy,
    deduplicate_news_items,
    select_distinct_events,
    source_neutral_prefilter,
)
from daily_dash.ranking.news import GatewayNewsRanker, GatewayNewsScreener
from daily_dash.retrieval.rss import retrieve_source_set
from daily_dash.scheduling import resolve_schedule_window
from daily_dash.storage.news import JsonNewsRunStore


def _model_summary(traces: list[NewsRankingTrace]) -> NewsModelSummary:
    if not traces:
        raise ValueError("at least one model trace is required")

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
        usage_complete=all(trace.usage_complete for trace in traces),
    )


def run_news_pipeline(
    *,
    profile_id: str,
    config_dir: Path,
    data_repo: Path,
    gateway_url: str | None = None,
    retrieved_at: datetime | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[NewsRunDocument, Path]:
    now = retrieved_at or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")

    profile = load_news_profile(config_dir / "profiles" / f"{profile_id}.yaml")
    source_set = load_news_source_set(config_dir / "sources" / f"{profile.source_set}.yaml")
    schedules = load_schedule_registry(config_dir / "schedules.yaml")
    retrieval_window = resolve_schedule_window(
        schedules,
        profile_id,
        now,
        explicit_start=window_start,
        explicit_end=window_end,
    )

    retrieved, diagnostics = retrieve_source_set(
        source_set,
        window_start=retrieval_window.window_start,
        window_end=retrieval_window.window_end,
        max_items_per_source=profile.retrieval.max_items_per_source,
        retrieved_at=now,
    )

    if not any(item.ok for item in diagnostics):
        raise RuntimeError(f"all enabled news sources failed for {profile_id}")

    deduplicated = deduplicate_news_items(retrieved)
    candidates = source_neutral_prefilter(
        deduplicated,
        limit=profile.ranking.prefilter_limit,
    )

    if not candidates:
        raise RuntimeError(f"no news candidates available for {profile_id}")

    run_id = uuid4().hex
    client = ModelGatewayClient(gateway_url)
    screening = None
    screening_traces: list[NewsRankingTrace] = []
    ranking_candidates = candidates

    uses_top_market_policy = (
        profile.profile_id == "news-top" and profile.ranking.prompt.version == "v8"
    )
    if uses_top_market_policy and profile.ranking.screening is not None:
        screening, screening_traces, ranking_candidates = GatewayNewsScreener(client).screen(
            candidates,
            profile,
        )

    batch = CandidateBatch(
        run_id=run_id,
        profile=profile_id,
        items=ranking_candidates,
    )
    ranking, trace = GatewayNewsRanker(client).rank(batch, profile)

    if uses_top_market_policy:
        ranking = apply_top_market_policy(
            ranking,
            min_score=profile.ranking.min_score,
        )

    selected_ids, duplicate_suppressions = select_distinct_events(
        ranking,
        limit=profile.presentation.max_items,
        eligible_only=uses_top_market_policy,
    )
    model_summary = _model_summary([*screening_traces, trace])
    document = NewsRunDocument(
        run_id=run_id,
        profile=profile_id,
        retrieved_at=now,
        retrieval_window=retrieval_window,
        source_diagnostics=diagnostics,
        retrieved_count=len(retrieved),
        deduplicated_count=len(deduplicated),
        candidate_count=len(candidates),
        finalist_count=len(ranking_candidates),
        candidates=candidates,
        screening=screening,
        screening_traces=screening_traces,
        ranking=ranking,
        ranking_trace=trace,
        model_summary=model_summary,
        selected_ids=selected_ids,
        duplicate_suppressions=duplicate_suppressions,
    )
    output_path = JsonNewsRunStore(data_repo).write(document)
    return document, output_path
