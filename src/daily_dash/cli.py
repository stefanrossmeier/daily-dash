from __future__ import annotations

import argparse
from pathlib import Path

from daily_dash.config import ConfigurationError, validate_config_tree


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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        try:
            result = validate_config_tree(args.config_dir)
        except ConfigurationError as exc:
            parser.exit(
                status=1,
                message=f"Configuration invalid: {exc}\n",
            )

        print(
            "Configuration valid: "
            f"{result.profile_count} profiles, "
            f"{result.source_set_count} source sets"
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
