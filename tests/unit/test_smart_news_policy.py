from pathlib import Path

from daily_dash.config.loader import load_news_profile
from daily_dash.policies import load_smart_news_policy

ROOT = Path(__file__).resolve().parents[2]


def test_smart_news_profile_references_versioned_processing_policy() -> None:
    profile = load_news_profile(ROOT / "config/profiles/news-smart.yaml")
    assert profile.processing_policy is not None
    assert profile.processing_policy.id == "news-smart-macro"
    assert profile.processing_policy.version == "v1"


def test_smart_news_policy_is_external_and_hashed() -> None:
    asset = load_smart_news_policy("news-smart-macro", "v1", assets_dir=ROOT / "assets")
    assert "central bank" in asset.policy.macro_priority_terms
    assert "earnings" in asset.policy.narrow_corporate_terms
    assert asset.policy.scoring.macro_hit_weight == 3
    assert asset.policy.eligibility.minimum_score == 8
    assert len(asset.sha256) == 64
