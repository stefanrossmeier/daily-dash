from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from daily_dash.config.errors import ConfigurationError
from daily_dash.config.loader import (
    load_news_profile,
    load_news_source_set,
)


@dataclass(frozen=True)
class ConfigValidationResult:
    profile_ids: tuple[str, ...]
    source_set_ids: tuple[str, ...]

    @property
    def profile_count(self) -> int:
        return len(self.profile_ids)

    @property
    def source_set_count(self) -> int:
        return len(self.source_set_ids)


def validate_config_tree(config_dir: Path) -> ConfigValidationResult:
    profiles_dir = config_dir / "profiles"
    sources_dir = config_dir / "sources"

    if not profiles_dir.is_dir():
        raise ConfigurationError(
            f"profiles directory not found: {profiles_dir}"
        )

    if not sources_dir.is_dir():
        raise ConfigurationError(
            f"sources directory not found: {sources_dir}"
        )

    profiles = {}
    source_sets = {}

    for path in sorted(profiles_dir.glob("*.yaml")):
        profile = load_news_profile(path)

        if path.stem != profile.profile_id:
            raise ConfigurationError(
                f"profile filename '{path.stem}' does not match "
                f"profile_id '{profile.profile_id}'"
            )

        if profile.profile_id in profiles:
            raise ConfigurationError(
                f"duplicate profile id: {profile.profile_id}"
            )

        profiles[profile.profile_id] = profile

    for path in sorted(sources_dir.glob("*.yaml")):
        source_set = load_news_source_set(path)

        if path.stem != source_set.source_set_id:
            raise ConfigurationError(
                f"source filename '{path.stem}' does not match "
                f"source_set_id '{source_set.source_set_id}'"
            )

        if source_set.source_set_id in source_sets:
            raise ConfigurationError(
                f"duplicate source set id: {source_set.source_set_id}"
            )

        source_sets[source_set.source_set_id] = source_set

    for profile in profiles.values():
        if profile.source_set not in source_sets:
            raise ConfigurationError(
                f"profile '{profile.profile_id}' references missing "
                f"source set '{profile.source_set}'"
            )

    return ConfigValidationResult(
        profile_ids=tuple(sorted(profiles)),
        source_set_ids=tuple(sorted(source_sets)),
    )
