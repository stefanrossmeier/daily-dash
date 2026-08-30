from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from daily_dash.config.paths import default_assets_dir

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TEMPLATE_TOKEN = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


class PromptAssetError(ValueError):
    """Raised when a versioned prompt asset cannot be loaded or rendered."""


@dataclass(frozen=True, slots=True)
class PromptAsset:
    prompt_id: str
    version: str
    profile: str

    system: str
    profile_text: str
    task_template: str | None
    contract: dict[str, object]

    system_sha256: str
    profile_sha256: str
    task_sha256: str | None
    combined_sha256: str

    def render_system(self, **values: object) -> str:
        return _render_template(self.system, values)

    def render_task(self, **values: object) -> str:
        if self.task_template is None:
            raise PromptAssetError(
                f"prompt {self.prompt_id}/{self.version} has no versioned task template"
            )
        return _render_template(self.task_template, values)

    def contract_bool(self, key: str) -> bool:
        value = self.contract.get(key)
        if not isinstance(value, bool):
            raise PromptAssetError(
                f"prompt {self.prompt_id}/{self.version} contract {key!r} must be boolean"
            )
        return value

    def contract_str(self, key: str) -> str:
        value = self.contract.get(key)
        if not isinstance(value, str) or not value:
            raise PromptAssetError(
                f"prompt {self.prompt_id}/{self.version} contract {key!r} must be a string"
            )
        return value


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


def _render_template(template: str, values: dict[str, object]) -> str:
    required = set(_TEMPLATE_TOKEN.findall(template))
    missing = sorted(required - values.keys())
    if missing:
        raise PromptAssetError(f"missing prompt template values: {', '.join(missing)}")

    def replace(match: re.Match[str]) -> str:
        return str(values[match.group(1)])

    return _TEMPLATE_TOKEN.sub(replace, template).strip()


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

    task_value = manifest.get("task")
    if task_value is not None and not isinstance(task_value, str):
        raise PromptAssetError("prompt manifest task must be a path when present")

    contract_value = manifest.get("contract", {})
    if not isinstance(contract_value, dict) or not all(
        isinstance(key, str) for key in contract_value
    ):
        raise PromptAssetError("prompt manifest contract must be a string-keyed mapping")
    contract = cast(dict[str, object], contract_value)

    system_path = _resolve_asset_file(prompt_root, system_value)
    profile_path = _resolve_asset_file(prompt_root, profile_value)
    task_path = _resolve_asset_file(prompt_root, task_value) if task_value else None

    system = system_path.read_text(encoding="utf-8").strip()
    profile_text = profile_path.read_text(encoding="utf-8").strip()
    task_template = task_path.read_text(encoding="utf-8").strip() if task_path else None

    combined_parts = [
        f"prompt-id: {prompt_id}",
        f"prompt-version: {version}",
        "",
        system,
        "",
        profile_text,
    ]
    if task_template is not None:
        combined_parts.extend(["", task_template])
    combined = "\n".join(combined_parts) + "\n"

    return PromptAsset(
        prompt_id=prompt_id,
        version=version,
        profile=profile,
        system=system,
        profile_text=profile_text,
        task_template=task_template,
        contract=contract,
        system_sha256=_sha256(system),
        profile_sha256=_sha256(profile_text),
        task_sha256=_sha256(task_template) if task_template is not None else None,
        combined_sha256=_sha256(combined),
    )
