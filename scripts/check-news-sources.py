#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_news_profile, load_news_source_set
from daily_dash.retrieval.rss import retrieve_source_set


def main() -> None:
    parser = argparse.ArgumentParser(description="Check configured DailyDash RSS/Atom sources.")
    parser.add_argument(
        "--profile",
        choices=["news-top", "news-alternative", "news-german"],
        required=True,
    )
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any enabled source fails",
    )
    args = parser.parse_args()

    profile = load_news_profile(args.config_dir / "profiles" / f"{args.profile}.yaml")
    source_set = load_news_source_set(args.config_dir / "sources" / f"{profile.source_set}.yaml")
    _, diagnostics = retrieve_source_set(
        source_set,
        lookback_hours=profile.retrieval.lookback_hours,
        max_items_per_source=5,
        retrieved_at=datetime.now(UTC),
    )

    failed = 0

    for item in diagnostics:
        status = "OK" if item.ok else "ERROR"
        print(f"{status:5} {item.source_id:24} items={item.item_count:2} {item.source_name}")
        if item.error:
            print(f"      {item.error}")
        if not item.ok:
            failed += 1

    print()
    print(f"{len(diagnostics) - failed}/{len(diagnostics)} enabled sources reachable")

    if args.strict and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
