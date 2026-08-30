from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pydantic import ValidationError

from daily_dash.config.loader import load_polymarket_profile, load_polymarket_source_set
from daily_dash.config.paths import default_config_dir
from daily_dash.config.settings import TelegramSettings
from daily_dash.contracts.common import DeliveryStatus
from daily_dash.delivery.telegram import TelegramDelivery
from daily_dash.pipelines.polymarket import run_polymarket_pipeline
from daily_dash.presentation.polymarket import render_polymarket_report
from daily_dash.retrieval.polymarket import check_polymarket_access
from daily_dash.storage.polymarket import JsonPolymarketRunStore


def _run(args: argparse.Namespace) -> None:
    document, output_path = run_polymarket_pipeline(
        config_dir=args.config_dir,
        data_repo=args.data_repo,
        gateway_url=args.gateway_url,
    )
    summary = document.model_summary
    print(
        json.dumps(
            {
                "artifact_path": str(output_path),
                "artifact_size_bytes": output_path.stat().st_size,
                "profile": document.profile,
                "retrieved_count": document.retrieved_count,
                "candidate_count": document.candidate_count,
                "selected_count": len(document.signals),
                "hot_count": len(document.hot),
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


def _check_api(args: argparse.Namespace) -> None:
    profile = load_polymarket_profile(args.config_dir / "profiles" / "polymarket.yaml")
    source_set = load_polymarket_source_set(
        args.config_dir / "sources" / f"{profile.source_set}.yaml"
    )
    print(json.dumps(check_polymarket_access(source_set, profile.retrieval)))


def _deliver(args: argparse.Namespace) -> None:
    document = JsonPolymarketRunStore.read(args.artifact)
    profile = load_polymarket_profile(args.config_dir / "profiles/polymarket.yaml")
    report = render_polymarket_report(document, profile)
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
    parser = argparse.ArgumentParser(description="DailyDash Polymarket report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    run_parser.add_argument("--data-repo", type=Path, required=True)
    run_parser.add_argument("--gateway-url", default=None)
    run_parser.set_defaults(handler=_run)
    check_parser = subparsers.add_parser("check-api")
    check_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    check_parser.set_defaults(handler=_check_api)
    deliver_parser = subparsers.add_parser("deliver")
    deliver_parser.add_argument("--artifact", type=Path, required=True)
    deliver_parser.add_argument("--config-dir", type=Path, default=default_config_dir())
    deliver_parser.set_defaults(handler=_deliver)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
