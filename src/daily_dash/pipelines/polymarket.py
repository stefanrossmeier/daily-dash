from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config.loader import (
    load_polymarket_profile,
    load_polymarket_source_set,
    load_schedule_registry,
)
from daily_dash.contracts.news import NewsModelSummary, NewsModelUsage, NewsRankingTrace
from daily_dash.contracts.polymarket import (
    PolymarketCandidateAudit,
    PolymarketModelEvaluation,
    PolymarketRunDocument,
    PolymarketSignalSelection,
)
from daily_dash.llm.gateway import ModelGatewayClient
from daily_dash.llm.polymarket import GatewayPolymarketClassifier
from daily_dash.processing.polymarket import (
    score_polymarket_evaluations,
    select_polymarket_hot_events,
    select_polymarket_signal_ids,
    snapshot_polymarket_event,
)
from daily_dash.retrieval.polymarket import retrieve_polymarket_events
from daily_dash.scheduling import resolve_daily_cycle_window
from daily_dash.storage.polymarket import JsonPolymarketRunStore


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


def run_polymarket_pipeline(
    *,
    config_dir: Path,
    data_repo: Path,
    gateway_url: str | None = None,
    retrieved_at: datetime | None = None,
) -> tuple[PolymarketRunDocument, Path]:
    now = retrieved_at or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    now = now.astimezone(UTC)
    profile = load_polymarket_profile(config_dir / "profiles" / "polymarket.yaml")
    source_set = load_polymarket_source_set(config_dir / "sources" / f"{profile.source_set}.yaml")
    registry = load_schedule_registry(config_dir / "schedules.yaml")
    cycle = resolve_daily_cycle_window(registry, profile.profile_id, now)

    candidates, hot_candidates, diagnostics = retrieve_polymarket_events(
        source_set,
        profile.retrieval,
        retrieved_at=now,
    )
    if not candidates and not hot_candidates:
        errors = "; ".join(error for item in diagnostics for error in item.errors)
        raise RuntimeError(f"Polymarket retrieval returned no active events: {errors}")

    # Reuse event-scoped recent-trade counts in the semantic lane when an event is also
    # present in the global hot pool. No activity fields are passed to the model.
    hot_by_id = {item.id: item for item in hot_candidates}
    candidates = [hot_by_id.get(item.id, item) for item in candidates]

    model_evaluations: list[PolymarketModelEvaluation] = []
    traces: list[NewsRankingTrace] = []
    if profile.ranking.llm_enabled and candidates:
        classifier = GatewayPolymarketClassifier(ModelGatewayClient(gateway_url))
        for start in range(0, len(candidates), profile.ranking.batch_size):
            batch = candidates[start : start + profile.ranking.batch_size]
            batch_evaluations, trace = classifier.classify_batch(batch, profile)
            model_evaluations.extend(batch_evaluations)
            traces.append(trace)

    evaluations = score_polymarket_evaluations(candidates, model_evaluations, profile.ranking)
    selected_ids = select_polymarket_signal_ids(
        evaluations,
        limit=profile.presentation.max_signal_items,
        max_items_per_topic=profile.ranking.max_items_per_topic,
        max_items_per_theme=profile.ranking.max_items_per_theme,
    )
    events_by_id = {item.id: item for item in candidates}
    evaluations_by_id = {item.id: item for item in evaluations}
    signals = [
        PolymarketSignalSelection(
            event=snapshot_polymarket_event(events_by_id[event_id]),
            evaluation=evaluations_by_id[event_id],
        )
        for event_id in selected_ids
    ]
    hot = select_polymarket_hot_events(
        hot_candidates,
        profile.hot,
        limit=profile.presentation.max_hot_items,
    )
    candidate_audit = [
        PolymarketCandidateAudit(
            id=item.id,
            title=events_by_id[item.id].title[:240],
            ranking_score=item.ranking_score,
            relevance=item.relevance,
            market_impact=item.market_impact,
            market_breadth=item.market_breadth,
            prediction_signal=item.prediction_signal,
            topic_key=item.topic_key,
            theme=item.theme,
            signal_type=item.signal_type,
            market_eligible=item.market_eligible,
        )
        for item in evaluations
    ]
    retrieved_count = max(
        (item.unique_event_count for item in diagnostics),
        default=len({item.id for item in candidates + hot_candidates}),
    )
    document = PolymarketRunDocument(
        run_id=uuid4().hex,
        retrieved_at=now,
        timezone=cycle.timezone,
        previous_scheduled_for=cycle.previous_scheduled_for,
        scheduled_for=cycle.scheduled_for,
        window_start=cycle.window_start,
        window_end=cycle.window_end,
        retrieval_diagnostics=diagnostics,
        retrieved_count=retrieved_count,
        candidate_count=len(candidates),
        hot_candidate_count=len(hot_candidates),
        signals=signals,
        hot=hot,
        candidate_audit=candidate_audit,
        model_traces=traces,
        model_summary=_model_summary(traces),
    )
    output_path = JsonPolymarketRunStore(data_repo).write(document)
    return document, output_path
