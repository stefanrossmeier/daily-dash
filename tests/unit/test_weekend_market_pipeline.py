from datetime import UTC, datetime

import pytest

from daily_dash.config import WeekendMarketSourceSet, WeekendMarketsProfile
from daily_dash.contracts import RawWeekendMarketQuote, RawWeekendMarketSnapshot
from daily_dash.pipelines.weekend_markets import run_weekend_markets_pipeline
from daily_dash.presentation.weekend_markets import render_weekend_markets_report
from daily_dash.storage import JsonFileWeekendMarketSnapshotStore


class FakeRetriever:
    def retrieve(
        self,
        source_set: WeekendMarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawWeekendMarketSnapshot:
        return RawWeekendMarketSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            quotes=[
                RawWeekendMarketQuote(
                    quote_id="dax",
                    name="Germany 40",
                    url="https://example.test/dax",
                    price_decimals=1,
                    bid=100.0,
                    ask=101.0,
                    change_pct=1.25,
                )
            ],
        )


def test_weekend_markets_pipeline_persists_and_renders(tmp_path) -> None:
    profile = WeekendMarketsProfile.model_validate(
        {
            "profile_id": "markets-weekend",
            "pipeline": "markets-weekend",
            "source_set": "markets-weekend",
            "presentation": {"title": "Weekend Markets (IG)"},
        }
    )
    source_set = WeekendMarketSourceSet.model_validate(
        {
            "pipeline": "markets-weekend",
            "source_set_id": "markets-weekend",
            "provider": "ig-weekend",
            "quotes": [],
        }
    )
    now = datetime(2026, 8, 29, 8, 30, tzinfo=UTC)
    document, path = run_weekend_markets_pipeline(
        profile,
        source_set,
        FakeRetriever(),
        snapshot_store=JsonFileWeekendMarketSnapshotStore(tmp_path),
        run_id="run-1",
        now=now,
    )

    assert path.parent == tmp_path / "markets" / "weekend" / "snapshots"
    assert JsonFileWeekendMarketSnapshotStore.read(path) == document

    report = render_weekend_markets_report(document.report, profile)
    assert "Weekend Markets (IG)" in report.content
    assert "Germany 40" in report.content
    assert "Bid 100.0 · Ask 101.0 · 🟢+1.25%" in report.content


class EmptyRetriever:
    def retrieve(
        self,
        source_set: WeekendMarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawWeekendMarketSnapshot:
        return RawWeekendMarketSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            quotes=[],
        )


def test_weekend_markets_pipeline_fails_when_all_quotes_are_unavailable(tmp_path) -> None:
    profile = WeekendMarketsProfile.model_validate(
        {
            "profile_id": "markets-weekend",
            "pipeline": "markets-weekend",
            "source_set": "markets-weekend",
            "presentation": {"title": "Weekend Markets (IG)"},
        }
    )
    source_set = WeekendMarketSourceSet.model_validate(
        {
            "pipeline": "markets-weekend",
            "source_set_id": "markets-weekend",
            "provider": "ig-weekend",
            "quotes": [],
        }
    )

    with pytest.raises(RuntimeError, match="all weekend market quotes are unavailable"):
        run_weekend_markets_pipeline(
            profile,
            source_set,
            EmptyRetriever(),
            snapshot_store=JsonFileWeekendMarketSnapshotStore(tmp_path),
            run_id="run-empty",
            now=datetime(2026, 8, 29, 8, 30, tzinfo=UTC),
        )
