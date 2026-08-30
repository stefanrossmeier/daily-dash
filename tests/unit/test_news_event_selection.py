from daily_dash.contracts.news import (
    NewsRankingContent,
    NewsRankingEvaluation,
)
from daily_dash.processing.news import (
    backfill_distinct_events,
    normalize_event_key,
    select_distinct_events,
)


def _evaluation(
    item_id: str,
    event_key: str,
    rank_score: int,
) -> NewsRankingEvaluation:
    return NewsRankingEvaluation(
        id=item_id,
        event_key=event_key,
        rank_score=rank_score,
        tier=4,
        priority=rank_score,
        relevance=80,
        market_impact=80,
        surprise=70,
        quality=80,
        novelty=70,
        selected=True,
        rationale="Fixture.",
    )


def test_lower_ranked_duplicate_is_suppressed_and_next_event_promoted() -> None:
    ranking = NewsRankingContent(
        evaluations=[
            _evaluation("nvidia-a", "nvidia-quarterly-earnings", 98),
            _evaluation("nvidia-b", "nvidia-quarterly-earnings", 92),
            _evaluation("ecb", "ecb-rate-guidance", 88),
            _evaluation("oil", "hormuz-oil-flow-recovery", 80),
        ],
        ranking=["nvidia-a", "nvidia-b", "ecb", "oil"],
    )

    selected, suppressions = select_distinct_events(ranking, limit=3)

    assert selected == ["nvidia-a", "ecb", "oil"]
    assert len(suppressions) == 1
    assert suppressions[0].suppressed_id == "nvidia-b"
    assert suppressions[0].kept_id == "nvidia-a"
    assert suppressions[0].event_key == "nvidia-quarterly-earnings"


def test_same_company_different_events_are_not_collapsed() -> None:
    ranking = NewsRankingContent(
        evaluations=[
            _evaluation("earnings", "nvidia-quarterly-earnings", 95),
            _evaluation("deal", "nvidia-hugging-face-acquisition", 90),
        ],
        ranking=["earnings", "deal"],
    )

    selected, suppressions = select_distinct_events(ranking, limit=2)

    assert selected == ["earnings", "deal"]
    assert suppressions == []


def test_event_key_normalization_is_deterministic() -> None:
    assert (
        normalize_event_key("  Nvidia_Hugging Face Acquisition  ")
        == "nvidia-hugging-face-acquisition"
    )


def test_explicit_duplicate_relation_overrides_different_event_keys() -> None:
    from daily_dash.contracts.news import (
        NewsRankingContent,
        NewsRankingEvaluation,
    )
    from daily_dash.processing.news import (
        select_distinct_events,
    )

    common = {
        "tier": 4,
        "relevance": 80,
        "market_impact": 70,
        "surprise": 50,
        "quality": 80,
        "novelty": 60,
        "selected": True,
        "rationale": "Fixture.",
    }

    earnings = NewsRankingEvaluation(
        id="nvidia-earnings",
        event_key="nvidia-quarterly-earnings",
        duplicate_of_id=None,
        rank_score=90,
        priority=90,
        **common,
    )

    market_reaction = NewsRankingEvaluation(
        id="nvidia-market-reaction",
        event_key=("stocks-rise-after-nvidia-results"),
        duplicate_of_id="nvidia-earnings",
        rank_score=85,
        priority=85,
        **common,
    )

    futures_reaction = NewsRankingEvaluation(
        id="nvidia-futures",
        event_key=("futures-rise-on-nvidia-outlook"),
        duplicate_of_id="nvidia-earnings",
        rank_score=82,
        priority=82,
        **common,
    )

    fed = NewsRankingEvaluation(
        id="fed",
        event_key="fed-policy-guidance",
        duplicate_of_id=None,
        rank_score=80,
        priority=80,
        **common,
    )

    ranking = NewsRankingContent(
        evaluations=[
            earnings,
            market_reaction,
            futures_reaction,
            fed,
        ],
        ranking=[
            "nvidia-earnings",
            "nvidia-market-reaction",
            "nvidia-futures",
            "fed",
        ],
    )

    selected, suppressions = select_distinct_events(
        ranking,
        limit=2,
    )

    assert selected == [
        "nvidia-earnings",
        "fed",
    ]

    assert {item.suppressed_id for item in suppressions} == {
        "nvidia-market-reaction",
        "nvidia-futures",
    }

    assert all(item.kept_id == "nvidia-earnings" for item in suppressions)


def test_eligible_only_skips_candidates_rejected_by_top_policy() -> None:
    rejected = _evaluation("rejected", "narrow-company-event", 95).model_copy(
        update={"selection_eligible": False}
    )
    accepted = _evaluation("accepted", "broad-market-event", 80).model_copy(
        update={"selection_eligible": True}
    )
    ranking = NewsRankingContent(
        evaluations=[rejected, accepted],
        ranking=["rejected", "accepted"],
    )

    selected, suppressions = select_distinct_events(
        ranking,
        limit=2,
        eligible_only=True,
    )

    assert selected == ["accepted"]
    assert suppressions == []


def test_selected_only_skips_candidates_rejected_by_model() -> None:
    rejected = _evaluation("rejected", "weak-event", 95).model_copy(update={"selected": False})
    accepted = _evaluation("accepted", "strong-event", 80)
    ranking = NewsRankingContent(
        evaluations=[rejected, accepted],
        ranking=["rejected", "accepted"],
    )

    selected, suppressions = select_distinct_events(
        ranking,
        limit=2,
        selected_only=True,
    )

    assert selected == ["accepted"]
    assert suppressions == []


def test_backfill_uses_next_best_ranked_distinct_events_after_primary_selection() -> None:
    rejected_same_event = _evaluation("rejected-same", "shared-event", 99).model_copy(
        update={"selected": False}
    )
    selected_same_event = _evaluation("selected-same", "shared-event", 90)
    next_event = _evaluation("next-event", "next-event", 85).model_copy(update={"selected": False})
    third_event = _evaluation("third-event", "third-event", 80).model_copy(
        update={"selected": False}
    )
    ranking = NewsRankingContent(
        evaluations=[rejected_same_event, selected_same_event, next_event, third_event],
        ranking=["rejected-same", "selected-same", "next-event", "third-event"],
    )

    primary, _ = select_distinct_events(ranking, limit=4, selected_only=True)
    backfill, suppressions = backfill_distinct_events(
        ranking,
        selected_ids=primary,
        target_count=3,
    )

    assert primary == ["selected-same"]
    assert backfill == ["next-event", "third-event"]
    assert [(item.suppressed_id, item.kept_id) for item in suppressions] == [
        ("rejected-same", "selected-same")
    ]


def test_backfill_does_nothing_when_primary_selection_already_meets_target() -> None:
    ranking = NewsRankingContent(
        evaluations=[
            _evaluation("one", "event-one", 90),
            _evaluation("two", "event-two", 80),
        ],
        ranking=["one", "two"],
    )

    backfill, suppressions = backfill_distinct_events(
        ranking,
        selected_ids=["one", "two"],
        target_count=2,
    )

    assert backfill == []
    assert suppressions == []


def test_backfill_can_use_top_market_candidates_below_normal_eligibility_threshold() -> None:
    primary = _evaluation("primary", "primary-event", 90).model_copy(
        update={"selection_eligible": True}
    )
    fallback = _evaluation("fallback", "fallback-event", 85).model_copy(
        update={"selection_eligible": False}
    )
    ranking = NewsRankingContent(
        evaluations=[primary, fallback],
        ranking=["primary", "fallback"],
    )

    selected, _ = select_distinct_events(ranking, limit=2, eligible_only=True)
    backfill, _ = backfill_distinct_events(
        ranking,
        selected_ids=selected,
        target_count=2,
    )

    assert selected == ["primary"]
    assert backfill == ["fallback"]
