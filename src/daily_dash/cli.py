from __future__ import annotations

import argparse
from pathlib import Path

from daily_dash.config import ConfigurationError, default_config_dir, validate_config_tree


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
        default=default_config_dir(),
        help="configuration directory",
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
        f"{result.source_set_count} source sets, "
        f"{result.schedule_count} schedules"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "validate-config":
        _run_validate_config(args, parser)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
