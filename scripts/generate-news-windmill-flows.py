#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path("workflows/windmill")
BASE_FLOW = ROOT / "f/daily_dash/markets__flow/flow.yaml"

PROFILES = {
    "news-top": ("news_top", "news/top", "Top News"),
    "news-alternative": (
        "news_alternative",
        "news/alternative",
        "Alternative News",
    ),
    "news-german": ("news_german", "news/german", "German News"),
}


def _script_path(module: dict[str, Any]) -> str | None:
    value = module.get("value")
    if not isinstance(value, dict):
        return None
    path = value.get("path")
    return path if isinstance(path, str) else None


def _replace_market_static_values(value: object, subtree: str) -> int:
    replacements = 0

    if isinstance(value, dict):
        for key, child in list(value.items()):
            if key == "value" and isinstance(child, str) and "markets" in child.casefold():
                value[key] = subtree
                replacements += 1
            else:
                replacements += _replace_market_static_values(child, subtree)

    elif isinstance(value, list):
        for child in value:
            replacements += _replace_market_static_values(child, subtree)

    return replacements


def _set_persist_subtree(module: dict[str, Any], subtree: str) -> None:
    value = module.get("value")
    if not isinstance(value, dict):
        raise ValueError("persist module has no value mapping")

    transforms = value.get("input_transforms")
    if not isinstance(transforms, dict):
        raise ValueError("persist module has no input_transforms")

    replacements = _replace_market_static_values(transforms, subtree)
    if replacements:
        return

    for name, transform in transforms.items():
        if not isinstance(transform, dict):
            continue
        lowered = str(name).casefold()
        if any(token in lowered for token in ("path", "subtree", "directory")):
            transform.clear()
            transform.update({"type": "static", "value": subtree})
            return

    raise ValueError(
        "could not identify the relative data subtree input in "
        "persist_data_repo; inspect the Markets flow"
    )


def generate() -> None:
    if not BASE_FLOW.is_file():
        raise SystemExit(f"ERROR: base Markets flow not found: {BASE_FLOW}")

    base = yaml.safe_load(BASE_FLOW.read_text(encoding="utf-8"))
    if not isinstance(base, dict):
        raise SystemExit("ERROR: Markets flow root must be a mapping")

    value = base.get("value")
    if not isinstance(value, dict):
        raise SystemExit("ERROR: Markets flow has no value mapping")

    modules = value.get("modules")
    if not isinstance(modules, list):
        raise SystemExit("ERROR: Markets flow has no modules list")

    run_template = next(
        (
            module
            for module in modules
            if isinstance(module, dict) and _script_path(module) == "f/daily_dash/run_markets"
        ),
        None,
    )
    persist_template = next(
        (
            module
            for module in modules
            if isinstance(module, dict) and _script_path(module) == "f/daily_dash/persist_data_repo"
        ),
        None,
    )

    if run_template is None:
        raise SystemExit("ERROR: run_markets module not found in Markets flow")
    if persist_template is None:
        raise SystemExit("ERROR: persist_data_repo module not found in Markets flow")

    for profile, (flow_name, subtree, title) in PROFILES.items():
        flow = copy.deepcopy(base)
        flow["summary"] = f"DailyDash {title}"
        flow["description"] = (
            "Retrieve and rank News, persist the immutable run artifact, "
            "then deliver original-article links to Telegram."
        )

        flow_value = flow["value"]
        assert isinstance(flow_value, dict)

        run_module = copy.deepcopy(run_template)
        run_module["id"] = "run_news"
        run_module["summary"] = f"Run {title}"
        run_value = run_module["value"]
        assert isinstance(run_value, dict)
        run_value["path"] = "f/daily_dash/run_news"
        run_value["input_transforms"] = {
            "profile": {
                "type": "static",
                "value": profile,
            }
        }

        persist_module = copy.deepcopy(persist_template)
        persist_module["id"] = "persist_data_repo"
        persist_module["summary"] = f"Persist {title} artifact"
        _set_persist_subtree(persist_module, subtree)

        deliver_module = copy.deepcopy(run_template)
        deliver_module["id"] = "deliver_news"
        deliver_module["summary"] = f"Deliver {title} to Telegram"
        deliver_value = deliver_module["value"]
        assert isinstance(deliver_value, dict)
        deliver_value["path"] = "f/daily_dash/deliver_news"
        deliver_value["input_transforms"] = {
            "artifact_path": {
                "type": "javascript",
                "expr": "results.run_news.artifact_path",
            },
            "telegram_token": {
                "type": "javascript",
                "expr": 'variable("f/daily_dash/telegram_token")',
            },
            "telegram_chat_id": {
                "type": "javascript",
                "expr": 'variable("f/daily_dash/telegram_chat_id")',
            },
        }

        flow_value["modules"] = [
            run_module,
            persist_module,
            deliver_module,
        ]

        output = ROOT / f"f/daily_dash/{flow_name}__flow/flow.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            yaml.safe_dump(flow, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(output)


if __name__ == "__main__":
    generate()
