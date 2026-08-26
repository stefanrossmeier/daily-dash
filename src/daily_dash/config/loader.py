from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from daily_dash.config.errors import ConfigurationError
from daily_dash.config.models import NewsProfile, NewsSourceSet


def _read_yaml(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ConfigurationError(f"configuration file not found: {path}")

    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(f"configuration root must be a mapping: {path}")

    if not all(isinstance(key, str) for key in raw):
        raise ConfigurationError(f"configuration keys must be strings: {path}")

    return cast(dict[str, object], raw)


def load_news_profile(path: Path) -> NewsProfile:
    raw = _read_yaml(path)

    try:
        return NewsProfile.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"invalid news profile {path}: {exc}") from exc


def load_news_source_set(path: Path) -> NewsSourceSet:
    raw = _read_yaml(path)

    try:
        return NewsSourceSet.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"invalid news source set {path}: {exc}") from exc
