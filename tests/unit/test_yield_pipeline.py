from datetime import UTC, date, datetime

import pytest

from daily_dash.config import YieldProfile, YieldSourceSet
from daily_dash.contracts import RawYieldSeries, RawYieldSnapshot, YieldObservation
from daily_dash.pipelines.yields import run_yield_pipeline
from daily_dash.storage import JsonFileYieldSnapshotStore


class FakeRetriever:
    def __init__(self, *, missing: str | None = None) -> None:
        self.missing = missing

    def retrieve(
        self,
        source_set: YieldSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawYieldSnapshot:
        required = ("us-2y", "us-10y", "de-10y", "eur-all-10y")
        series = []
        for series_id in required:
            if series_id == self.missing:
                series.append(
                    RawYieldSeries(
                        series_id=series_id,
                        name=series_id,
                        provider="test",
                        source_ref=f"test:{series_id}",
                        error="temporary provider failure",
                    )
                )
                continue
            series.append(
                RawYieldSeries(
                    series_id=series_id,
                    name=series_id,
                    provider="test",
                    source_ref=f"test:{series_id}",
                    observations=[YieldObservation(observed_on=date(2026, 8, 31), value_pct=3.0)],
                )
            )
        return RawYieldSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            series=series,
        )


def _profile() -> YieldProfile:
    return YieldProfile.model_validate(
        {
            "profile_id": "yields",
            "pipeline": "yields",
            "source_set": "yields",
            "presentation": {},
        }
    )


def _source_set() -> YieldSourceSet:
    return YieldSourceSet.model_validate(
        {"pipeline": "yields", "source_set_id": "yields", "series": []}
    )


def test_yield_pipeline_persists_immutable_artifact(tmp_path) -> None:
    document, path = run_yield_pipeline(
        _profile(),
        _source_set(),
        FakeRetriever(),
        snapshot_store=JsonFileYieldSnapshotStore(tmp_path),
        run_id="run-1",
        now=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
    )

    assert path.parent == tmp_path / "yields" / "snapshots"
    assert JsonFileYieldSnapshotStore.read(path) == document


def test_yield_pipeline_preserves_partial_provider_failure(tmp_path) -> None:
    document, _ = run_yield_pipeline(
        _profile(),
        _source_set(),
        FakeRetriever(missing="de-10y"),
        snapshot_store=JsonFileYieldSnapshotStore(tmp_path),
        run_id="run-2",
        now=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
    )

    spread = next(spread for spread in document.report.spreads if spread.spread_id == "us-de-10y")
    assert spread.value_pp is None
    assert "de-10y: temporary provider failure" in document.report.issues


class EmptyRetriever:
    def retrieve(
        self,
        source_set: YieldSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawYieldSnapshot:
        return RawYieldSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            series=[],
        )


def test_yield_pipeline_fails_when_all_series_are_unavailable(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="all Yield Report series are unavailable"):
        run_yield_pipeline(
            _profile(),
            _source_set(),
            EmptyRetriever(),
            snapshot_store=JsonFileYieldSnapshotStore(tmp_path),
            run_id="run-empty",
            now=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
        )
