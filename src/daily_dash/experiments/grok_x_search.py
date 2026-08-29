from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from daily_dash.llm.gateway import GatewayResponse, ModelGatewayClient
from daily_dash.prompts.loader import PromptAsset, load_prompt_asset

DEFAULT_ALIAS = "x-retrieve"
DEFAULT_HANDLE = "NickTimiraos"
DEFAULT_TIMEOUT_SECONDS = 240.0
BERLIN = ZoneInfo("Europe/Berlin")
WATCHLIST_HANDLES = (
    "KobeissiLetter",
    "AndreasSteno",
    "markoinny",
    "NickTimiraos",
    "DeItaone",
    "elerianm",
)

X_SEARCH_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["posts"],
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "author_handle",
                    "publication_time",
                    "post_text",
                    "post_url",
                    "linked_urls",
                    "significance",
                    "short_summary",
                ],
                "properties": {
                    "author_handle": {"type": "string"},
                    "publication_time": {"type": ["string", "null"]},
                    "post_text": {"type": "string"},
                    "post_url": {"type": ["string", "null"]},
                    "linked_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "significance": {"type": "string"},
                    "short_summary": {"type": "string"},
                },
            },
        }
    },
}


def default_date_range(now: datetime | None = None) -> tuple[date, date]:
    current = now.astimezone(BERLIN) if now is not None else datetime.now(BERLIN)
    today = current.date()
    return today - timedelta(days=1), today


def build_input(
    *,
    prompt: PromptAsset,
    handle: str,
    from_date: date,
    to_date: date,
) -> str:
    return (
        f"{prompt.system}\n\n"
        f"{prompt.profile_text}\n\n"
        "Retrieval request:\n"
        f"- allowed X handle: {handle}\n"
        f"- from_date: {from_date.isoformat()}\n"
        f"- to_date: {to_date.isoformat()}\n\n"
        "Search X now and return the JSON object described above."
    )


def build_gateway_request(
    *,
    alias: str,
    prompt: PromptAsset,
    handle: str,
    from_date: date,
    to_date: date,
) -> dict[str, object]:
    if handle not in WATCHLIST_HANDLES:
        raise ValueError(f"handle is not in the DailyDash X watchlist: {handle}")
    if to_date < from_date:
        raise ValueError("to_date must be on or after from_date")

    return {
        "alias": alias,
        "purpose": "x-retrieval-compatibility",
        "profile": "x-watchlist-spike",
        "input": build_input(
            prompt=prompt,
            handle=handle,
            from_date=from_date,
            to_date=to_date,
        ),
        "allowed_x_handles": [handle],
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "response_schema_name": "daily_dash_x_watchlist_retrieval",
        "response_schema": X_SEARCH_RESPONSE_SCHEMA,
    }


def build_artifact(
    *,
    alias: str,
    handle: str,
    from_date: date,
    to_date: date,
    prompt: PromptAsset,
    gateway_request: dict[str, object],
    gateway_response: GatewayResponse,
) -> dict[str, object]:
    return {
        "experiment": "grok-x-search-compatibility",
        "schema_version": 2,
        "created_at": datetime.now(BERLIN).isoformat(),
        "request": {
            "gateway_alias": alias,
            "handle": handle,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "payload": gateway_request,
        },
        "prompt": {
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.version,
            "prompt_profile": prompt.profile,
            "system_sha256": prompt.system_sha256,
            "profile_sha256": prompt.profile_sha256,
            "combined_sha256": prompt.combined_sha256,
        },
        "response": gateway_response.model_dump(mode="json"),
    }


def _default_output_path(handle: str) -> Path:
    stamp = datetime.now(BERLIN).strftime("%Y%m%dT%H%M%S%z")
    return Path(f"/tmp/daily-dash-grok-x-spike-{handle}-{stamp}.json")


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def run_live(
    *,
    alias: str,
    handle: str,
    from_date: date,
    to_date: date,
    output_path: Path,
    timeout_seconds: float,
    assets_dir: Path,
) -> Path:
    prompt = load_prompt_asset(
        "x-watchlist-retrieval",
        "v1",
        "spike",
        assets_dir=assets_dir,
    )
    gateway_request = build_gateway_request(
        alias=alias,
        prompt=prompt,
        handle=handle,
        from_date=from_date,
        to_date=to_date,
    )

    client = ModelGatewayClient(timeout_seconds=timeout_seconds)
    gateway_response = client.x_search_structured(
        alias=alias,
        purpose="x-retrieval-compatibility",
        profile="x-watchlist-spike",
        input_text=str(gateway_request["input"]),
        allowed_x_handles=[handle],
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        response_schema_name="daily_dash_x_watchlist_retrieval",
        response_schema=X_SEARCH_RESPONSE_SCHEMA,
    )

    artifact = build_artifact(
        alias=alias,
        handle=handle,
        from_date=from_date,
        to_date=to_date,
        prompt=prompt,
        gateway_request=gateway_request,
        gateway_response=gateway_response,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    default_from, default_to = default_date_range()
    parser = argparse.ArgumentParser(
        description="Run one isolated Grok X-search request through the DailyDash model gateway."
    )
    parser.add_argument("--handle", choices=WATCHLIST_HANDLES, default=DEFAULT_HANDLE)
    parser.add_argument(
        "--alias",
        default=os.getenv("DAILY_DASH_GROK_X_SPIKE_ALIAS", DEFAULT_ALIAS),
    )
    parser.add_argument("--from-date", type=_parse_iso_date, default=default_from)
    parser.add_argument("--to-date", type=_parse_iso_date, default=default_to)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request sent to the local model gateway without making a paid call.",
    )
    args = parser.parse_args()

    assets_dir = Path(os.getenv("DAILY_DASH_ASSETS_DIR", "assets"))
    prompt = load_prompt_asset(
        "x-watchlist-retrieval",
        "v1",
        "spike",
        assets_dir=assets_dir,
    )
    gateway_request = build_gateway_request(
        alias=args.alias,
        prompt=prompt,
        handle=args.handle,
        from_date=args.from_date,
        to_date=args.to_date,
    )

    if args.dry_run:
        print(json.dumps(gateway_request, indent=2, sort_keys=True, ensure_ascii=False))
        return

    output = args.output or _default_output_path(args.handle)
    written = run_live(
        alias=args.alias,
        handle=args.handle,
        from_date=args.from_date,
        to_date=args.to_date,
        output_path=output,
        timeout_seconds=args.timeout,
        assets_dir=assets_dir,
    )
    print(written)


if __name__ == "__main__":
    main()
