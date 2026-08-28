import pytest
from pydantic import ValidationError

from daily_dash.config import NewsProfile


def test_news_profile_validates() -> None:
    profile = NewsProfile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "news-top",
            "pipeline": "news",
            "source_set": "news-top",
            "retrieval": {
                "lookback_hours": 24,
                "max_items_per_source": 50,
            },
            "keywords": {
                "include": ["ai"],
                "exclude": ["sports"],
            },
            "ranking": {
                "candidate_limit": 40,
                "top_k": 10,
                "llm_enabled": True,
                "model_alias": "rank-cheap",
                "min_score": 0.5,
            },
            "presentation": {
                "title": "Top News",
                "language": "en",
                "max_items": 10,
            },
        }
    )

    assert profile.profile_id == "news-top"
    assert profile.ranking.model_alias == "rank-cheap"


def test_news_profile_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        NewsProfile.model_validate(
            {
                "schema_version": 1,
                "profile_id": "news-top",
                "pipeline": "news",
                "source_set": "news-top",
                "retrieval": {},
                "keywords": {},
                "ranking": {},
                "presentation": {
                    "title": "Top News",
                },
                "unexpected": True,
            }
        )


def test_news_profile_rejects_top_k_above_candidate_limit() -> None:
    with pytest.raises(ValidationError):
        NewsProfile.model_validate(
            {
                "schema_version": 1,
                "profile_id": "news-top",
                "pipeline": "news",
                "source_set": "news-top",
                "retrieval": {},
                "keywords": {},
                "ranking": {
                    "candidate_limit": 10,
                    "top_k": 20,
                },
                "presentation": {
                    "title": "Top News",
                    "max_items": 10,
                },
            }
        )
