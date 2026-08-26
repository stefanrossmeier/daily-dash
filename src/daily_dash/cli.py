from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from daily_dash.config import (
    ConfigurationError,
    TelegramSettings,
    load_market_source_set,
    load_markets_profile,
    validate_config_tree,
)
from daily_dash.contracts import DeliveryStatus
from daily_dash.delivery.telegram import TelegramDelivery
from daily_dash.pipelines.markets import run_markets
from daily_dash.retrieval.markets import YahooFinanceRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily-dash",
        description="DailyDash data intelligence pipelines",
    )

    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="validate DailyDash configuration",
    )
    validate_parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="configuration directory",
    )

    markets_parser = subparsers.add_parser(
        "markets",
        help="build the market snapshot",
    )
    markets_parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="configuration directory",
    )
    markets_parser.add_argument(
        "--profile",
        default="markets",
        help="markets profile id",
    )
    markets_parser.add_argument(
        "--delivery",
        choices=("stdout", "telegram"),
        default="stdout",
        help="delivery destination",
    )

    return parser


def _run_validate_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        result = validate_config_tree(args.config_dir)
    except ConfigurationError as exc:
        parser.exit(status=1, message=f"Configuration invalid: {exc}\n")

    print(
        "Configuration valid: "
        f"{result.profile_count} profiles, "
        f"{result.source_set_count} source sets"
    )


def _run_markets(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        profile = load_markets_profile(args.config_dir / "profiles" / f"{args.profile}.yaml")
        source_set = load_market_source_set(
            args.config_dir / "sources" / f"{profile.source_set}.yaml"
        )
    except ConfigurationError as exc:
        parser.exit(status=1, message=f"Configuration invalid: {exc}\n")

    artifact = run_markets(profile, source_set, YahooFinanceRetriever())

    if args.delivery == "stdout":
        print(artifact.content)
        return

    try:
        settings = TelegramSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        parser.exit(status=1, message=f"Telegram configuration invalid: {exc}\n")

    result = TelegramDelivery(
        token=settings.telegram_token,
        chat_id=settings.telegram_chat_id,
    ).send(artifact)

    if result.status is DeliveryStatus.FAILED:
        parser.exit(status=1, message=f"Telegram delivery failed: {result.error}\n")

    print(f"Telegram delivery succeeded: message_id={result.external_id or 'unknown'}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        _run_validate_config(args, parser)
        return

    if args.command == "markets":
        _run_markets(args, parser)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
