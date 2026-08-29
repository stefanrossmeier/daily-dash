from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import HttpUrl

from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.news import NewsModelUsage, NewsRankingTrace, NewsSourceDiagnostic
from daily_dash.contracts.smart_news import SmartNewsModelTheme
from daily_dash.contracts.source import SourceItem
from daily_dash.pipelines import smart_news as pipeline_module
from daily_dash.pipelines.smart_news import run_smart_news_pipeline

ROOT = Path(__file__).resolve().parents[2]


def _article(now: datetime) -> SourceItem:
    return SourceItem(
        id="oil",
        source="FT World",
        source_kind=SourceKind.RSS,
        title="Oil falls as Middle East ceasefire hopes rise",
        text="Energy markets react as Iran ceasefire talks advance.",
        url=HttpUrl("https://example.test/oil"),
        published_at=now - timedelta(hours=1),
        retrieved_at=now,
    )


class _FakeAnalyzer:
    def __init__(self, client: object) -> None:
        self.client = client

    def analyze(self, articles: list[SourceItem], profile: object):
        return [
            SmartNewsModelTheme(
                title="Middle East ceasefire hopes push oil lower",
                summary="Oil prices fell as ceasefire talks advanced and energy risks eased.",
                headline_indices=[1],
            )
        ], NewsRankingTrace(
            prompt_id="news-smart",
            prompt_version="v1",
            prompt_profile="news-smart",
            system_sha256="a" * 64,
            profile_sha256="b" * 64,
            combined_sha256="c" * 64,
            model_alias="rank-cheap",
            provider="openrouter",
            resolved_model="openai/gpt-5.4-nano",
            usage=NewsModelUsage(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                cost_usd=0.001,
            ),
            latency_ms=100,
        )


def test_smart_news_pipeline_preserves_18_hour_rolling_window(monkeypatch, tmp_path) -> None:
    now = datetime(2026, 8, 28, 12, 20, tzinfo=UTC)
    article = _article(now)
    diagnostic = NewsSourceDiagnostic(
        source_id="ft-world",
        source_name="FT World",
        url="https://www.ft.com/world?format=rss",
        ok=True,
        item_count=1,
    )

    def fake_retrieve(*args: object, **kwargs: object):
        assert kwargs["lookback_hours"] == 18
        assert kwargs["max_items_per_source"] == 20
        return [article], [diagnostic]

    monkeypatch.setattr(pipeline_module, "retrieve_smart_source_set", fake_retrieve)
    monkeypatch.setattr(pipeline_module, "GatewaySmartNewsAnalyzer", _FakeAnalyzer)

    document, path = run_smart_news_pipeline(
        config_dir=ROOT / "config",
        data_repo=tmp_path,
        gateway_url="http://gateway.test",
        retrieved_at=now,
    )

    assert document.retrieval_window.source == "rolling"
    assert document.retrieval_window.lookback_hours == 18
    assert document.retrieval_window.window_start == now - timedelta(hours=18)
    assert document.retrieval_window.window_end == now
    assert document.article_count == 1
    assert document.theme_count == 1
    assert document.model_trace is not None
    assert document.model_trace.resolved_model == "openai/gpt-5.4-nano"
    assert path.parent == tmp_path / "news/smart"
