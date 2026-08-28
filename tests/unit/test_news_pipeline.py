from daily_dash.contracts.news import NewsModelUsage, NewsRankingTrace
from daily_dash.pipelines.news import _model_summary


def _trace(*, cost: float, attempts: int = 1, usage_complete: bool = True) -> NewsRankingTrace:
    return NewsRankingTrace(
        prompt_id="fixture",
        prompt_version="v1",
        prompt_profile="news-top",
        system_sha256="a" * 64,
        profile_sha256="b" * 64,
        combined_sha256="c" * 64,
        model_alias="rank-cheap",
        provider="openrouter",
        resolved_model="openai/gpt-5.4-nano",
        usage=NewsModelUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=cost,
        ),
        latency_ms=100,
        attempts=attempts,
        usage_complete=usage_complete,
    )


def test_model_summary_aggregates_all_two_stage_calls() -> None:
    summary = _model_summary(
        [
            _trace(cost=0.001),
            _trace(cost=0.002, attempts=2, usage_complete=False),
            _trace(cost=0.003),
        ]
    )

    assert summary.usage.input_tokens == 30
    assert summary.usage.output_tokens == 15
    assert summary.usage.total_tokens == 45
    assert summary.usage.cost_usd == 0.006
    assert summary.latency_ms == 300
    assert summary.calls == 3
    assert summary.attempts == 4
    assert summary.usage_complete is False
