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
from daily_dash.pipelines.smart_news import run_smart_news_pipeline
from daily_dash.presentation.smart_news import render_smart_news_report
from daily_dash.storage.smart_news import JsonSmartNewsRunStore


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("datetime must include a timezone offset")
    return parsed


def _run(args: argparse.Namespace) -> None:
    document, output_path = run_smart_news_pipeline(
        config_dir=args.config_dir,
        data_repo=args.data_repo,
        gateway_url=args.gateway_url,
        window_start=args.window_start,
        window_end=args.window_end,
    )

    trace = document.model_trace
    print(
        json.dumps(
            {
                "artifact_path": str(output_path),
                "profile": document.profile,
                "article_count": document.article_count,
                "theme_count": document.theme_count,
                "cost_usd": trace.usage.cost_usd if trace is not None else 0.0,
                "model_calls": 1 if trace is not None else 0,
                "model_attempts": trace.attempts if trace is not None else 0,
                "model_retries": max(trace.attempts - 1, 0) if trace is not None else 0,
                "model_usage_complete": trace.usage_complete if trace is not None else True,
                "window_start": document.retrieval_window.window_start.isoformat(),
                "window_end": document.retrieval_window.window_end.isoformat(),
            }
        )
    )


def _deliver(args: argparse.Namespace) -> None:
    document = JsonSmartNewsRunStore.read(args.artifact)
    profile = load_news_profile(args.config_dir / "profiles/news-smart.yaml")
    report = render_smart_news_report(document, profile)

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
    parser = argparse.ArgumentParser(description="DailyDash Smart News runtime command")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
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
