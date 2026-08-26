from pathlib import Path

from daily_dash.config import (
    load_news_profile,
    validate_config_tree,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPOSITORY_ROOT / "config"


def test_repository_configuration_is_valid() -> None:
    result = validate_config_tree(CONFIG_DIR)

    assert result.profile_ids == (
        "markets",
        "news-alternative",
        "news-german",
        "news-top",
    )

    assert result.source_set_ids == (
        "markets",
        "news-alternative",
        "news-german",
        "news-top",
    )


def test_all_news_variants_use_same_pipeline() -> None:
    profiles = [
        load_news_profile(CONFIG_DIR / "profiles" / "news-top.yaml"),
        load_news_profile(CONFIG_DIR / "profiles" / "news-alternative.yaml"),
        load_news_profile(CONFIG_DIR / "profiles" / "news-german.yaml"),
    ]

    assert {profile.pipeline for profile in profiles} == {"news"}


def test_news_profiles_use_cheap_ranker_alias() -> None:
    profiles = [
        load_news_profile(path) for path in sorted((CONFIG_DIR / "profiles").glob("news-*.yaml"))
    ]

    assert all(profile.ranking.model_alias == "rank-cheap" for profile in profiles)
