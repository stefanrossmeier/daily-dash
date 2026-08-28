from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class PromptAssetError(ValueError):
    """Raised when a versioned prompt asset cannot be loaded."""


@dataclass(frozen=True, slots=True)
class PromptAsset:
    prompt_id: str
    version: str
    profile: str

    system: str
    profile_text: str

    system_sha256: str
    profile_sha256: str
    combined_sha256: str


def default_assets_dir() -> Path:
    configured = os.getenv("DAILY_DASH_ASSETS_DIR")
    if configured:
        return Path(configured)

    home = os.getenv("DAILY_DASH_HOME")
    if home:
        return Path(home) / "assets"

    return Path("assets")


def _validate_name(value: str, field: str) -> None:
    if not _SAFE_NAME.fullmatch(value):
        raise PromptAssetError(f"invalid {field}: {value!r}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resolve_asset_file(root: Path, relative: str) -> Path:
    base = root.resolve()
    candidate = (root / relative).resolve()

    if candidate != base and base not in candidate.parents:
        raise PromptAssetError(f"prompt asset path escapes prompt directory: {relative}")

    if not candidate.is_file():
        raise PromptAssetError(f"prompt asset not found: {candidate}")

    return candidate


def _load_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise PromptAssetError(f"prompt manifest not found: {path}")

    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PromptAssetError(f"invalid prompt manifest YAML: {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PromptAssetError(f"prompt manifest must be a mapping: {path}")

    if not all(isinstance(key, str) for key in raw):
        raise PromptAssetError(f"prompt manifest keys must be strings: {path}")

    return cast(dict[str, object], raw)


def load_prompt_asset(
    prompt_id: str,
    version: str,
    profile: str,
    *,
    assets_dir: Path | None = None,
) -> PromptAsset:
    _validate_name(prompt_id, "prompt id")
    _validate_name(version, "prompt version")
    _validate_name(profile, "prompt profile")

    assets_root = assets_dir or default_assets_dir()
    prompt_root = assets_root / "prompts" / prompt_id / version
    manifest = _load_manifest(prompt_root / "prompt.yaml")

    if manifest.get("id") != prompt_id:
        raise PromptAssetError(f"prompt manifest id does not match {prompt_id!r}")

    if manifest.get("version") != version:
        raise PromptAssetError(f"prompt manifest version does not match {version!r}")

    system_value = manifest.get("system")
    if not isinstance(system_value, str):
        raise PromptAssetError("prompt manifest system must be a path")

    profiles_value = manifest.get("profiles")
    if not isinstance(profiles_value, dict):
        raise PromptAssetError("prompt manifest profiles must be a mapping")

    if not all(isinstance(key, str) for key in profiles_value):
        raise PromptAssetError("prompt manifest profile names must be strings")

    profiles = cast(dict[str, object], profiles_value)

    profile_value = profiles.get(profile)
    if not isinstance(profile_value, str):
        raise PromptAssetError(f"prompt profile not found in manifest: {profile}")

    system_path = _resolve_asset_file(prompt_root, system_value)
    profile_path = _resolve_asset_file(prompt_root, profile_value)

    system = system_path.read_text(encoding="utf-8").strip()
    profile_text = profile_path.read_text(encoding="utf-8").strip()

    combined = f"prompt-id: {prompt_id}\nprompt-version: {version}\n\n{system}\n\n{profile_text}\n"

    return PromptAsset(
        prompt_id=prompt_id,
        version=version,
        profile=profile,
        system=system,
        profile_text=profile_text,
        system_sha256=_sha256(system),
        profile_sha256=_sha256(profile_text),
        combined_sha256=_sha256(combined),
    )
