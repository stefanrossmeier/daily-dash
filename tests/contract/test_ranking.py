import pytest
from pydantic import ValidationError

from daily_dash.contracts import RankingDecision


def test_ranking_score_must_be_normalized() -> None:
    decision = RankingDecision(
        item_id="story-1",
        relevance=0.9,
        novelty=0.7,
        quality=0.8,
        score=0.84,
        selected=True,
        rationale="Highly relevant and recent.",
    )

    assert decision.score == 0.84


def test_ranking_score_above_one_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RankingDecision(
            item_id="story-1",
            relevance=0.9,
            novelty=0.7,
            quality=0.8,
            score=1.5,
            selected=True,
        )
