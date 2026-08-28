from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from daily_dash.config.errors import ConfigurationError
from daily_dash.config.models import (
    MarketSourceSet,
    MarketsProfile,
    NewsProfile,
    NewsSourceSet,
    Profile,
    ScheduleRegistry,
    SourceSet,
    WeekendMarketSourceSet,
    WeekendMarketsProfile,
)


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


def load_profile(path: Path) -> Profile:
    raw = _read_yaml(path)
    pipeline = raw.get("pipeline")

    model: type[NewsProfile] | type[MarketsProfile] | type[WeekendMarketsProfile]
    if pipeline == "news":
        model = NewsProfile
    elif pipeline == "markets":
        model = MarketsProfile
    elif pipeline == "markets-weekend":
        model = WeekendMarketsProfile
    else:
        raise ConfigurationError(f"unknown profile pipeline in {path}: {pipeline!r}")

    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"invalid profile {path}: {exc}") from exc


def load_source_set(path: Path) -> SourceSet:
    raw = _read_yaml(path)
    pipeline = raw.get("pipeline")

    model: type[NewsSourceSet] | type[MarketSourceSet] | type[WeekendMarketSourceSet]
    if pipeline == "news":
        model = NewsSourceSet
    elif pipeline == "markets":
        model = MarketSourceSet
    elif pipeline == "markets-weekend":
        model = WeekendMarketSourceSet
    else:
        raise ConfigurationError(f"unknown source-set pipeline in {path}: {pipeline!r}")

    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"invalid source set {path}: {exc}") from exc


def load_news_profile(path: Path) -> NewsProfile:
    profile = load_profile(path)
    if not isinstance(profile, NewsProfile):
        raise ConfigurationError(f"expected news profile: {path}")
    return profile


def load_markets_profile(path: Path) -> MarketsProfile:
    profile = load_profile(path)
    if not isinstance(profile, MarketsProfile):
        raise ConfigurationError(f"expected markets profile: {path}")
    return profile


def load_news_source_set(path: Path) -> NewsSourceSet:
    source_set = load_source_set(path)
    if not isinstance(source_set, NewsSourceSet):
        raise ConfigurationError(f"expected news source set: {path}")
    return source_set


def load_market_source_set(path: Path) -> MarketSourceSet:
    source_set = load_source_set(path)
    if not isinstance(source_set, MarketSourceSet):
        raise ConfigurationError(f"expected market source set: {path}")
    return source_set


def load_schedule_registry(path: Path) -> ScheduleRegistry:
    raw = _read_yaml(path)
    try:
        return ScheduleRegistry.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"invalid schedule registry {path}: {exc}") from exc


def load_weekend_markets_profile(path: Path) -> WeekendMarketsProfile:
    profile = load_profile(path)
    if not isinstance(profile, WeekendMarketsProfile):
        raise ConfigurationError(f"expected weekend markets profile: {path}")
    return profile


def load_weekend_market_source_set(path: Path) -> WeekendMarketSourceSet:
    source_set = load_source_set(path)
    if not isinstance(source_set, WeekendMarketSourceSet):
        raise ConfigurationError(f"expected weekend market source set: {path}")
    return source_set
