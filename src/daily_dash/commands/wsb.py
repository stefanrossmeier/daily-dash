from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from daily_dash.config.loader import load_wsb_source_set
from daily_dash.config.paths import default_config_dir
from daily_dash.config.settings import TelegramSettings
from daily_dash.contracts.common import DeliveryStatus
from daily_dash.delivery.telegram import TelegramDelivery
from daily_dash.pipelines.wsb import run_wsb_pipeline
from daily_dash.presentation.wsb import render_wsb_report
from daily_dash.retrieval.wsb import check_wsb_reddit_access
from daily_dash.storage.wsb import JsonWsbRunStore


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("datetime must include a timezone offset")
    return parsed


def _run(args: argparse.Namespace) -> None:
    document, output_path = run_wsb_pipeline(
        config_dir=args.config_dir,
        data_repo=args.data_repo,
        gateway_url=args.gateway_url,
        window_start=args.window_start,
        window_end=args.window_end,
    )
    summary = document.model_summary
    print(
        json.dumps(
            {
                "artifact_path": str(output_path),
                "profile": document.profile,
                "retrieved_count": document.retrieved_count,
                "candidate_count": document.candidate_count,
                "selected_count": len(document.selected_ids),
                "cost_usd": summary.usage.cost_usd if summary else 0.0,
                "model_calls": summary.calls if summary else 0,
                "model_attempts": summary.attempts if summary else 0,
                "model_retries": summary.retries if summary else 0,
                "model_usage_complete": summary.usage_complete if summary else True,
                "window_start": document.window_start.isoformat(),
                "window_end": document.window_end.isoformat(),
            }
        )
    )


def _check_reddit(args: argparse.Namespace) -> None:
    source_set = load_wsb_source_set(args.config_dir / "sources" / "wsb.yaml")
    item_count = check_wsb_reddit_access(source_set)
    print(json.dumps({"status": "ok", "provider": "reddit-oauth", "sample_items": item_count}))


def _deliver(args: argparse.Namespace) -> None:
    document = JsonWsbRunStore.read(args.artifact)
    report = render_wsb_report(document)
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
        parse_mode="HTML",
    ).send(report)
    if result.status is DeliveryStatus.FAILED:
        raise SystemExit(f"Telegram delivery failed: {result.error}")
    print(
        json.dumps(
            {
                "artifact_path": str(args.artifact),
                "profile": document.profile,
                "telegram_message_id": result.external_id,
            }
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DailyDash WallStreetBets report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    run_parser.add_argument("--data-repo", type=Path, required=True)
    run_parser.add_argument("--gateway-url", default=None)
    run_parser.add_argument("--window-start", type=_aware_datetime, default=None)
    run_parser.add_argument("--window-end", type=_aware_datetime, default=None)
    run_parser.set_defaults(handler=_run)
    check_parser = subparsers.add_parser("check-reddit")
    check_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    check_parser.set_defaults(handler=_check_reddit)
    deliver_parser = subparsers.add_parser("deliver")
    deliver_parser.add_argument("--artifact", type=Path, required=True)
    deliver_parser.set_defaults(handler=_deliver)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
