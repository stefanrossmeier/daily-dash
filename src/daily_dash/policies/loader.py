from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, ConfigDict, Field

from daily_dash.config.paths import default_assets_dir


class SmartNewsPolicyScoring(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    macro_hit_weight: int = Field(ge=0)
    title_macro_hit_weight: int = Field(ge=0)
    support_count_cap: int = Field(ge=0)
    source_count_cap: int = Field(ge=0)
    narrow_hit_penalty: int = Field(ge=0)
    title_narrow_hit_penalty: int = Field(ge=0)


class SmartNewsPolicyEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_score: int
    no_support_min_macro_hits: int = Field(ge=0)
    no_support_min_title_macro_hits: int = Field(ge=0)
    one_support_min_macro_hits: int = Field(ge=0)
    one_support_min_title_macro_hits: int = Field(ge=0)
    one_support_title_narrow_override_macro_hits: int = Field(ge=0)
    two_support_min_macro_hits: int = Field(ge=0)
    title_narrow_min_macro_hits: int = Field(ge=0)
    narrow_cluster_min_macro_hits: int = Field(ge=0)
    narrow_cluster_min_narrow_hits: int = Field(ge=0)
    narrow_cluster_max_support_count: int = Field(ge=0)


class SmartNewsPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str
    macro_priority_terms: list[str]
    narrow_corporate_terms: list[str]
    scoring: SmartNewsPolicyScoring
    eligibility: SmartNewsPolicyEligibility


@dataclass(frozen=True, slots=True)
class SmartNewsPolicyAsset:
    policy: SmartNewsPolicy
    sha256: str


def load_smart_news_policy(
    policy_id: str,
    version: str,
    *,
    assets_dir: Path | None = None,
) -> SmartNewsPolicyAsset:
    root = (assets_dir or default_assets_dir()) / "policies" / policy_id / version
    path = root / "policy.yaml"
    if not path.is_file():
        raise ValueError(f"Smart News policy asset not found: {path}")
    text = path.read_text(encoding="utf-8")
    raw: object = yaml.safe_load(text)
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"Smart News policy must be a string-keyed mapping: {path}")
    policy = SmartNewsPolicy.model_validate(cast(dict[str, object], raw))
    if policy.id != policy_id or policy.version != version:
        raise ValueError(f"Smart News policy identity does not match {policy_id}/{version}")
    return SmartNewsPolicyAsset(
        policy=policy,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
