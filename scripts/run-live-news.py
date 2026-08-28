#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from daily_dash.pipelines.news import run_news_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one DailyDash News profile through retrieval, LLM ranking and JSON persistence."
        )
    )
    parser.add_argument(
        "--profile",
        choices=["news-top", "news-alternative", "news-german"],
        required=True,
    )
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--data-repo", type=Path, required=True)
    parser.add_argument("--gateway-url", default=None)
    args = parser.parse_args()

    document, output_path = run_news_pipeline(
        profile_id=args.profile,
        config_dir=args.config_dir,
        data_repo=args.data_repo,
        gateway_url=args.gateway_url,
    )

    evaluations = {item.id: item for item in document.ranking.evaluations}
    candidates = {item.id: item for item in document.candidates}

    print(
        f"profile={document.profile} "
        f"retrieved={document.retrieved_count} "
        f"deduplicated={document.deduplicated_count} "
        f"candidates={document.candidate_count} "
        f"duplicates_suppressed={len(document.duplicate_suppressions)}"
    )
    print(
        f"model={document.ranking_trace.resolved_model} "
        f"cost=${document.ranking_trace.usage.cost_usd:.8f} "
        f"latency={document.ranking_trace.latency_ms}ms"
    )
    print(
        "prompt="
        f"{document.ranking_trace.prompt_id}/"
        f"{document.ranking_trace.prompt_version} "
        f"sha256={document.ranking_trace.combined_sha256}"
    )
    print()

    for position, item_id in enumerate(document.selected_ids, start=1):
        evaluation = evaluations[item_id]
        candidate = candidates[item_id]
        print(
            f"{position:2}. T{evaluation.tier} "
            f"impact={evaluation.market_impact:3} "
            f"surprise={evaluation.surprise:3} "
            f"[{candidate.source}] {candidate.title}"
        )
        print(f"      {evaluation.rationale}")

    print()
    print(f"artifact={output_path}")


if __name__ == "__main__":
    main()
