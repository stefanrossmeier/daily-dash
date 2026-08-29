from datetime import UTC, datetime, timedelta
from pathlib import Path

from daily_dash.config.loader import load_wsb_profile
from daily_dash.contracts.wsb import WsbModelEvaluation, WsbPost
from daily_dash.processing.wsb import (
    score_wsb_evaluations,
    select_wsb_candidates,
    select_wsb_ids,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 28, 18, 35, tzinfo=UTC)


def _post(
    post_id: str,
    *,
    heat: float,
    comments: int = 0,
    score: int | None = None,
    age_minutes: int = 60,
) -> WsbPost:
    return WsbPost(
        id=post_id,
        title=f"Thread {post_id}",
        url=f"https://reddit.test/{post_id}",
        created_at=NOW - timedelta(minutes=age_minutes),
        num_comments=comments,
        score=comments * 2 if score is None else score,
        heat=heat,
    )


def _model(
    post_id: str,
    *,
    relevance: int,
    impact: int,
    breadth: int,
    positioning: int,
    signal_type: str,
) -> WsbModelEvaluation:
    return WsbModelEvaluation(
        id=post_id,
        relevance=relevance,
        market_impact=impact,
        market_breadth=breadth,
        positioning_signal=positioning,
        signal_type=signal_type,
        rationale="test transmission",
    )


def test_ordinary_popularity_cannot_rescue_semantically_irrelevant_thread() -> None:
    profile = load_wsb_profile(ROOT / "config/profiles/wsb.yaml")
    posts = [
        _post("meme", heat=60.0, comments=250, score=2400),
        _post("macro", heat=1.0),
    ]
    model = [
        _model(
            "meme",
            relevance=20,
            impact=15,
            breadth=10,
            positioning=20,
            signal_type="narrow-or-irrelevant",
        ),
        _model(
            "macro",
            relevance=90,
            impact=85,
            breadth=90,
            positioning=20,
            signal_type="broad-market",
        ),
    ]

    scored = score_wsb_evaluations(posts, model, profile.ranking)

    by_id = {item.id: item for item in scored}
    assert by_id["meme"].activity_score == 1.0
    assert by_id["meme"].market_eligible is False
    assert by_id["meme"].extreme_activity_eligible is False
    assert by_id["meme"].eligible is False
    assert by_id["macro"].market_eligible is True
    assert by_id["macro"].eligible is True
    assert select_wsb_ids(
        scored,
        limit=10,
        extreme_activity_max_items=profile.ranking.extreme_activity_max_items,
    ) == ["macro"]


def test_extremely_hot_narrow_thread_can_qualify_as_bounded_exception() -> None:
    profile = load_wsb_profile(ROOT / "config/profiles/wsb.yaml")
    posts = [
        _post("viral", heat=120.0, comments=450, score=5000),
        _post("macro", heat=5.0, comments=20, score=100),
    ]
    model = [
        _model(
            "viral",
            relevance=15,
            impact=10,
            breadth=5,
            positioning=10,
            signal_type="narrow-or-irrelevant",
        ),
        _model(
            "macro",
            relevance=90,
            impact=85,
            breadth=90,
            positioning=20,
            signal_type="broad-market",
        ),
    ]

    scored = score_wsb_evaluations(posts, model, profile.ranking)
    by_id = {item.id: item for item in scored}

    assert by_id["viral"].market_eligible is False
    assert by_id["viral"].extreme_activity_eligible is True
    assert by_id["viral"].eligible is True
    assert select_wsb_ids(
        scored,
        limit=10,
        extreme_activity_max_items=profile.ranking.extreme_activity_max_items,
    ) == ["macro", "viral"]


def test_extreme_activity_lane_is_not_filled_when_nothing_clears_absolute_floor() -> None:
    profile = load_wsb_profile(ROOT / "config/profiles/wsb.yaml")
    posts = [_post("popular", heat=74.9, comments=299, score=2499)]
    model = [
        _model(
            "popular",
            relevance=10,
            impact=10,
            breadth=5,
            positioning=10,
            signal_type="narrow-or-irrelevant",
        )
    ]

    scored = score_wsb_evaluations(posts, model, profile.ranking)

    assert scored[0].extreme_activity_eligible is False
    assert (
        select_wsb_ids(
            scored,
            limit=10,
            extreme_activity_max_items=profile.ranking.extreme_activity_max_items,
        )
        == []
    )


def test_extreme_activity_lane_is_capped() -> None:
    profile = load_wsb_profile(ROOT / "config/profiles/wsb.yaml")
    posts = [
        _post("viral-1", heat=140.0, comments=600, score=6000),
        _post("viral-2", heat=120.0, comments=500, score=5000),
        _post("macro", heat=1.0),
    ]
    model = [
        _model(
            "viral-1",
            relevance=15,
            impact=10,
            breadth=5,
            positioning=10,
            signal_type="narrow-or-irrelevant",
        ),
        _model(
            "viral-2",
            relevance=15,
            impact=10,
            breadth=5,
            positioning=10,
            signal_type="narrow-or-irrelevant",
        ),
        _model(
            "macro",
            relevance=90,
            impact=85,
            breadth=90,
            positioning=20,
            signal_type="broad-market",
        ),
    ]

    scored = score_wsb_evaluations(posts, model, profile.ranking)
    selected = select_wsb_ids(
        scored,
        limit=10,
        extreme_activity_max_items=profile.ranking.extreme_activity_max_items,
    )

    assert selected[0] == "macro"
    assert len([post_id for post_id in selected if post_id.startswith("viral-")]) == 1


def test_market_moving_bet_can_qualify_without_broad_market_breadth() -> None:
    profile = load_wsb_profile(ROOT / "config/profiles/wsb.yaml")
    posts = [_post("squeeze", heat=12.0)]
    model = [
        _model(
            "squeeze",
            relevance=88,
            impact=78,
            breadth=30,
            positioning=92,
            signal_type="market-moving-bet",
        )
    ]

    scored = score_wsb_evaluations(posts, model, profile.ranking)

    assert scored[0].market_eligible is True
    assert scored[0].eligible is True
    assert scored[0].semantic_score >= profile.ranking.min_semantic_score


def test_candidate_cap_is_not_only_heat_sorted() -> None:
    posts = [
        _post("hot-1", heat=100.0, comments=50, age_minutes=300),
        _post("hot-2", heat=90.0, comments=40, age_minutes=250),
        _post("new-quiet", heat=0.1, comments=0, age_minutes=1),
    ]

    candidates = select_wsb_candidates(posts, limit=3)

    assert {post.id for post in candidates} == {"hot-1", "hot-2", "new-quiet"}
