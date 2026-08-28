from pathlib import Path

import pytest

from daily_dash.prompts import (
    PromptAssetError,
    load_prompt_asset,
)

_REPO_ROOT = Path(__file__).parents[2]
_ASSETS_DIR = _REPO_ROOT / "assets"


def test_load_news_ranking_prompt() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v1",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    assert prompt.prompt_id == "news-ranking"
    assert prompt.version == "v1"
    assert prompt.profile == "news-top"

    assert "Tier 5" in prompt.system
    assert "Market-shaking" in prompt.system
    assert "Profile: Top News" in prompt.profile_text

    assert len(prompt.system_sha256) == 64
    assert len(prompt.profile_sha256) == 64
    assert len(prompt.combined_sha256) == 64


def test_unknown_prompt_profile_is_rejected() -> None:
    with pytest.raises(PromptAssetError):
        load_prompt_asset(
            "news-ranking",
            "v1",
            "does-not-exist",
            assets_dir=_ASSETS_DIR,
        )


def test_prompt_path_traversal_is_rejected() -> None:
    with pytest.raises(PromptAssetError):
        load_prompt_asset(
            "../news-ranking",
            "v1",
            "news-top",
            assets_dir=_ASSETS_DIR,
        )


def test_load_news_ranking_v2_prompt() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v2",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    assert prompt.version == "v2"
    assert "priority" in prompt.system
    assert "candidate slot" in prompt.system.lower()
    assert len(prompt.combined_sha256) == 64


def test_load_news_ranking_v3_prompt() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v3",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    assert prompt.version == "v3"

    normalized_system = " ".join(prompt.system.split())

    assert "event_key" in prompt.system
    assert "rank_score" in prompt.system
    assert "original publisher URL" in normalized_system
    assert len(prompt.combined_sha256) == 64


def test_load_news_ranking_v4_prompt() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v4",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    normalized = " ".join(prompt.system.split())

    assert prompt.version == "v4"
    assert "canonical event identity" in prompt.system
    assert "rank_score" in prompt.system
    assert "Wall Street reacts" in prompt.system
    assert "same event key" in normalized
    assert "original publisher URL" in normalized
    assert len(prompt.combined_sha256) == 64


def test_load_news_ranking_v5_prompt() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v5",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    normalized = " ".join(prompt.system.split())

    assert prompt.version == "v5"
    assert "duplicate_of_slot" in prompt.system
    assert "rank_score" in prompt.system
    assert "same underlying catalyst" in normalized
    assert "Do not return article URLs" in prompt.system
    assert len(prompt.combined_sha256) == 64


def test_load_news_ranking_v6_prompt_prioritizes_market_breadth() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v6",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    normalized_system = " ".join(prompt.system.split())
    normalized_profile = " ".join(prompt.profile_text.split())

    assert prompt.version == "v6"
    assert "market_breadth" in prompt.system
    assert "scope of plausible market transmission" in normalized_system
    assert "broad-market briefing" in normalized_profile
    assert "S&P 500" in prompt.profile_text
    assert "Single-company discipline" in prompt.profile_text
    assert len(prompt.combined_sha256) == 64


def test_load_news_ranking_v7_prompt_requires_material_transmission() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v7",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    normalized = " ".join(prompt.profile_text.split())

    assert prompt.version == "v7"
    assert "Material transmission discipline" in prompt.profile_text
    assert "measures how widely an event could transmit" in normalized
    assert "broad material repricing versus isolated repricing" in normalized
    assert "New information versus commentary" in prompt.profile_text
    assert "duplicate coverage" in prompt.profile_text
    assert len(prompt.combined_sha256) == 64


def test_load_news_ranking_v8_prompt_is_headline_only_and_policy_aware() -> None:
    prompt = load_prompt_asset(
        "news-ranking",
        "v8",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    normalized_system = " ".join(prompt.system.split())
    normalized_profile = " ".join(prompt.profile_text.split())

    assert prompt.version == "v8"
    assert "Headline-only evidence" in prompt.system
    assert (
        "Publisher identity and source reputation are deliberately not supplied"
        in normalized_system
    )
    assert "transparent, deterministic Top-News policy" in normalized_system
    assert "narrow breadth and weak market impact" in normalized_profile
    assert len(prompt.combined_sha256) == 64


def test_load_news_screening_v1_prompt() -> None:
    prompt = load_prompt_asset(
        "news-screening",
        "v1",
        "news-top",
        assets_dir=_ASSETS_DIR,
    )

    assert prompt.version == "v1"
    assert "three integer judgments" in prompt.system
    assert "Publisher, URL" in prompt.system
    assert "Top News Screening" in prompt.profile_text
    assert len(prompt.combined_sha256) == 64
