from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pydantic import ValidationError

from daily_dash.config import (
    ConfigurationError,
    TelegramSettings,
    default_config_dir,
    load_market_source_set,
    load_markets_profile,
)
from daily_dash.contracts import DeliveryStatus
from daily_dash.delivery.telegram import TelegramDelivery
from daily_dash.pipelines.markets import run_markets_pipeline
from daily_dash.presentation.markets import render_markets_report
from daily_dash.retrieval.markets import YahooFinanceRetriever
from daily_dash.storage import JsonFileMarketSnapshotStore


def _run(args: argparse.Namespace) -> None:
    try:
        profile = load_markets_profile(args.config_dir / "profiles" / f"{args.profile}.yaml")
        source_set = load_market_source_set(
            args.config_dir / "sources" / f"{profile.source_set}.yaml"
        )
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration invalid: {exc}") from exc

    document, output_path = run_markets_pipeline(
        profile,
        source_set,
        YahooFinanceRetriever(),
        snapshot_store=JsonFileMarketSnapshotStore(args.data_repo),
    )

    print(
        json.dumps(
            {
                "artifact_path": str(output_path),
                "profile": document.report.profile,
                "asset_count": len(document.report.assets),
                "issue_count": len(document.report.issues),
                "retrieved_at": document.raw.retrieved_at.isoformat(),
            }
        )
    )


def _deliver(args: argparse.Namespace) -> None:
    document = JsonFileMarketSnapshotStore.read(args.artifact)
    profile = load_markets_profile(args.config_dir / "profiles" / f"{document.report.profile}.yaml")
    report = render_markets_report(document.report, profile)

    try:
        settings = TelegramSettings(
            telegram_token=os.environ.get("DAILY_DASH_TELEGRAM_TOKEN", ""),
            telegram_chat_id=os.environ.get("DAILY_DASH_TELEGRAM_CHAT_ID", ""),
        )
    except ValidationError as exc:
        raise SystemExit(f"Telegram configuration invalid: {exc}") from exc

    result = TelegramDelivery(
        token=settings.telegram_token,
        chat_id=settings.telegram_chat_id,
    ).send(report)

    if result.status is DeliveryStatus.FAILED:
        raise SystemExit(f"Telegram delivery failed: {result.error}")

    print(
        json.dumps(
            {
                "artifact_path": str(args.artifact),
                "profile": document.report.profile,
                "telegram_message_id": result.external_id,
            }
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DailyDash Markets runtime command")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--profile", choices=("markets",), default="markets")
    run_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    run_parser.add_argument("--data-repo", type=Path, required=True)
    run_parser.set_defaults(handler=_run)

    deliver_parser = subparsers.add_parser("deliver")
    deliver_parser.add_argument("--artifact", type=Path, required=True)
    deliver_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    deliver_parser.set_defaults(handler=_deliver)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
