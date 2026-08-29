from pathlib import Path

from daily_dash.config.loader import load_polymarket_profile
from daily_dash.contracts.polymarket import (
    PolymarketEvent,
    PolymarketEventMarket,
    PolymarketModelEvaluation,
)
from daily_dash.processing.polymarket import (
    polymarket_activity_scores,
    score_polymarket_evaluations,
    select_polymarket_hot_events,
    select_polymarket_signal_ids,
)

ROOT = Path(__file__).resolve().parents[2]


def _event(
    eid: str,
    *,
    volume: float = 100_000,
    trades: int = 0,
    comments: int = 0,
    h1: float = 0.0,
    d1: float = 0.0,
) -> PolymarketEvent:
    numeric = abs(hash(eid)) % 100_000 + 1
    return PolymarketEvent(
        id=eid,
        event_id=numeric,
        title=eid,
        url=f"https://polymarket.test/event/{eid}",
        slug=eid,
        tags=["finance"],
        volume_24h=volume,
        liquidity=10_000,
        comment_count=comments,
        recent_trades=trades,
        max_abs_one_hour_price_change=h1,
        max_abs_one_day_price_change=d1,
        markets=[
            PolymarketEventMarket(
                question=f"{eid}?",
                condition_id=f"0x{numeric:064x}",
                volume_24h=volume,
                top_outcome="Yes",
                top_probability=0.6,
            )
        ],
    )


def _eval(
    eid: str,
    *,
    ranking: int,
    topic: str | None = None,
    signal: str = "both",
    relevance: int = 90,
    impact: int = 80,
    breadth: int = 75,
    prediction: int = 85,
    theme: str = "macro-economy",
) -> PolymarketModelEvaluation:
    return PolymarketModelEvaluation(
        id=eid,
        relevance=relevance,
        market_impact=impact,
        market_breadth=breadth,
        prediction_signal=prediction,
        ranking_score=ranking,
        topic_key=topic or eid,
        theme=theme,
        signal_type=signal,
        rationale="test",
    )


def test_model_ranking_controls_signal_lane_not_activity() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    events = [
        _event("viral-macro", volume=9_000_000, trades=900, comments=500),
        _event("important", volume=50_000, trades=2),
    ]
    model = [
        _eval("viral-macro", ranking=65),
        _eval("important", ranking=92),
    ]

    scored = score_polymarket_evaluations(events, model, profile.ranking)

    assert select_polymarket_signal_ids(
        scored,
        limit=10,
        max_items_per_topic=1,
        max_items_per_theme=2,
    ) == ["important", "viral-macro"]


def test_semantic_topic_dedup_keeps_best_event_and_refills_distinct_topics() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    events = [
        _event("hormuz-aug"),
        _event("hormuz-dec"),
        _event("fed"),
        _event("clarity"),
    ]
    model = [
        _eval(
            "hormuz-aug",
            ranking=92,
            topic="strait-of-hormuz-traffic-normalization",
            theme="energy-shipping",
        ),
        _eval(
            "hormuz-dec",
            ranking=88,
            topic="strait-of-hormuz-traffic-normalization",
            theme="energy-shipping",
        ),
        _eval(
            "fed",
            ranking=90,
            topic="fed-september-2026-rate-decision",
            theme="monetary-policy",
        ),
        _eval(
            "clarity",
            ranking=82,
            topic="us-clarity-act",
            theme="regulation-policy",
        ),
    ]

    scored = score_polymarket_evaluations(events, model, profile.ranking)

    assert select_polymarket_signal_ids(
        scored,
        limit=3,
        max_items_per_topic=1,
        max_items_per_theme=2,
    ) == ["hormuz-aug", "fed", "clarity"]


def test_theme_cap_prevents_one_subject_from_monopolizing_signal_slots() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    events = [
        _event("fed-september"),
        _event("fed-december"),
        _event("fed-year"),
        _event("iran-deal"),
        _event("hormuz"),
    ]
    model = [
        _eval(
            "fed-september",
            ranking=98,
            topic="fed-september-rate-decision",
            theme="monetary-policy",
        ),
        _eval(
            "fed-december",
            ranking=93,
            topic="fed-december-rate-decision",
            theme="monetary-policy",
        ),
        _eval(
            "fed-year",
            ranking=92,
            topic="fed-rate-hike-2026",
            theme="monetary-policy",
        ),
        _eval(
            "iran-deal",
            ranking=91,
            topic="us-iran-nuclear-deal",
            theme="geopolitics-security",
        ),
        _eval(
            "hormuz",
            ranking=85,
            topic="strait-of-hormuz-normalization",
            theme="energy-shipping",
        ),
    ]

    scored = score_polymarket_evaluations(events, model, profile.ranking)

    assert select_polymarket_signal_ids(
        scored,
        limit=5,
        max_items_per_topic=1,
        max_items_per_theme=2,
    ) == ["fed-september", "fed-december", "iran-deal", "hormuz"]


def test_narrow_event_never_enters_financial_signal_lane() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    events = [_event("lol", volume=2_000_000, trades=500, comments=200)]
    model = [
        _eval(
            "lol",
            ranking=95,
            signal="narrow-or-irrelevant",
            relevance=10,
            impact=5,
            breadth=5,
            prediction=5,
        )
    ]

    scored = score_polymarket_evaluations(events, model, profile.ranking)

    assert scored[0].market_eligible is False
    assert (
        select_polymarket_signal_ids(
            scored,
            limit=7,
            max_items_per_topic=1,
            max_items_per_theme=2,
        )
        == []
    )


def test_hot_lane_is_global_deterministic_and_independent_of_financial_signal() -> None:
    profile = load_polymarket_profile(ROOT / "config/profiles/polymarket.yaml")
    events = [
        _event("lol", volume=2_000_000, trades=500, comments=200, h1=0.20),
        _event("liverpool", volume=1_800_000, trades=150, comments=100, h1=0.08),
        _event("fed", volume=1_500_000, trades=120, comments=80, d1=0.12),
        _event("quiet", volume=100_000, trades=2, comments=1),
    ]

    hot = select_polymarket_hot_events(events, profile.hot, limit=3)

    assert [item.event.id for item in hot] == ["lol", "liverpool", "fed"]
    assert all(item.activity_score > 0 for item in hot)


def test_hot_activity_score_rewards_current_activity_and_comments() -> None:
    events = [
        _event("active", volume=1_000_000, trades=300, comments=150, h1=0.10),
        _event("stale", volume=1_000_000, trades=0, comments=0),
    ]

    scores = polymarket_activity_scores(events)

    assert scores["active"] > scores["stale"]
