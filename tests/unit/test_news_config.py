from pathlib import Path

from daily_dash.config.loader import load_news_profile, load_news_source_set

_REPO_ROOT = Path(__file__).parents[2]


def test_news_profiles_reference_versioned_prompt() -> None:
    expected_versions = {
        "news-top": "v8",
        "news-alternative": "v5",
        "news-german": "v5",
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


def test_top_news_uses_large_source_neutral_candidate_pool() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    source_set = load_news_source_set(_REPO_ROOT / "config" / "sources" / "news-top.yaml")

    assert profile.ranking.prefilter_limit == 100
    assert profile.ranking.min_score == 0.55
    assert profile.ranking.screening is not None
    assert profile.ranking.screening.batch_size == 25
    assert profile.ranking.screening.finalist_limit == 30
    assert profile.ranking.screening.model_alias == "rank-cheap"
    assert all(source.weight == 1.0 for source in source_set.sources)
