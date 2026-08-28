from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from daily_dash.config.loader import load_news_profile
from daily_dash.config.paths import default_config_dir
from daily_dash.config.settings import TelegramSettings
from daily_dash.contracts.common import DeliveryStatus
from daily_dash.delivery.telegram import TelegramDelivery
from daily_dash.pipelines.news import run_news_pipeline
from daily_dash.presentation.news import render_news_report
from daily_dash.storage.news import JsonNewsRunStore


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("datetime must include a timezone offset")
    return parsed


def _run(args: argparse.Namespace) -> None:
    document, output_path = run_news_pipeline(
        profile_id=args.profile,
        config_dir=args.config_dir,
        data_repo=args.data_repo,
        gateway_url=args.gateway_url,
        window_start=args.window_start,
        window_end=args.window_end,
    )

    print(
        json.dumps(
            {
                "artifact_path": str(output_path),
                "profile": document.profile,
                "selected_count": len(document.selected_ids),
                "duplicate_suppressions": len(document.duplicate_suppressions),
                "cost_usd": (
                    document.model_summary.usage.cost_usd
                    if document.model_summary is not None
                    else document.ranking_trace.usage.cost_usd
                ),
                "model_calls": (
                    document.model_summary.calls if document.model_summary is not None else 1
                ),
                "model_attempts": (
                    document.model_summary.attempts
                    if document.model_summary is not None
                    else document.ranking_trace.attempts
                ),
                "model_retries": (
                    document.model_summary.retries
                    if document.model_summary is not None
                    else max(document.ranking_trace.attempts - 1, 0)
                ),
                "model_usage_complete": (
                    document.model_summary.usage_complete
                    if document.model_summary is not None
                    else document.ranking_trace.usage_complete
                ),
                "window_start": (
                    document.retrieval_window.window_start.isoformat()
                    if document.retrieval_window is not None
                    else None
                ),
                "window_end": (
                    document.retrieval_window.window_end.isoformat()
                    if document.retrieval_window is not None
                    else None
                ),
            }
        )
    )


def _deliver(args: argparse.Namespace) -> None:
    document = JsonNewsRunStore.read(args.artifact)
    profile = load_news_profile(args.config_dir / "profiles" / f"{document.profile}.yaml")
    report = render_news_report(document, profile)

    try:
        settings = TelegramSettings(
            telegram_token=os.environ.get(
                "DAILY_DASH_TELEGRAM_TOKEN",
                "",
            ),
            telegram_chat_id=os.environ.get(
                "DAILY_DASH_TELEGRAM_CHAT_ID",
                "",
            ),
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
    parser = argparse.ArgumentParser(description="DailyDash News runtime command")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument(
        "--profile",
        choices=("news-top", "news-alternative", "news-german"),
        required=True,
    )
    run_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    run_parser.add_argument("--data-repo", type=Path, required=True)
    run_parser.add_argument("--gateway-url", default=None)
    run_parser.add_argument(
        "--window-start",
        type=_aware_datetime,
        default=None,
        help="explicit inclusive retrieval-window start for replay/testing",
    )
    run_parser.add_argument(
        "--window-end",
        type=_aware_datetime,
        default=None,
        help="explicit exclusive retrieval-window end for replay/testing",
    )
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
