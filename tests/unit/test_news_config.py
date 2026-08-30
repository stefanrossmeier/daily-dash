from pathlib import Path

from daily_dash.config.loader import load_news_profile, load_news_source_set

_REPO_ROOT = Path(__file__).parents[2]


def test_news_profiles_reference_versioned_prompt() -> None:
    expected_versions = {
        "news-top": "v11",
        "news-alternative": "v11",
        "news-german": "v11",
    }

    for profile_id, expected_version in expected_versions.items():
        profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / f"{profile_id}.yaml")
        assert profile.ranking.prompt.id == "news-ranking"
        assert profile.ranking.prompt.version == expected_version
        assert profile.keywords.include == []
        assert profile.keywords.exclude == []


def test_news_source_sets_have_enabled_real_sources() -> None:
    for source_set_id in ("news-top", "news-alternative", "news-german"):
        source_set = load_news_source_set(
            _REPO_ROOT / "config" / "sources" / f"{source_set_id}.yaml"
        )
        enabled = [source for source in source_set.sources if source.enabled]
        assert len(enabled) >= 5
        assert all("example.com" not in str(source.url) for source in enabled)


def test_all_news_profiles_use_shared_150_candidate_cap() -> None:
    for profile_id in ("news-top", "news-alternative", "news-german"):
        profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / f"{profile_id}.yaml")
        assert profile.ranking.candidate_limit == 150


def test_news_profiles_allow_up_to_20_selected_items() -> None:
    for profile_id in ("news-top", "news-alternative", "news-german"):
        profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / f"{profile_id}.yaml")
        assert profile.ranking.top_k == 20
        assert profile.presentation.max_items == 20


def test_top_news_keeps_source_neutral_weights_and_market_threshold() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    source_set = load_news_source_set(_REPO_ROOT / "config" / "sources" / "news-top.yaml")

    assert profile.ranking.min_score == 0.50
    assert all(source.weight == 1.0 for source in source_set.sources)
