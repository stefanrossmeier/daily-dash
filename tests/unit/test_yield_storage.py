from datetime import UTC, datetime

import pytest

from daily_dash.contracts import RawYieldSnapshot, YieldReportData, YieldSnapshotDocument
from daily_dash.storage import JsonFileYieldSnapshotStore


def _document() -> YieldSnapshotDocument:
    now = datetime(2026, 8, 31, 16, 3, tzinfo=UTC)
    return YieldSnapshotDocument(
        raw=RawYieldSnapshot(
            run_id="12345678-run",
            source_set="yields",
            retrieved_at=now,
            series=[],
        ),
        report=YieldReportData(
            run_id="12345678-run",
            profile="yields",
            generated_at=now,
            levels=[],
            spreads=[],
        ),
    )


def test_yield_snapshot_store_roundtrip_and_immutability(tmp_path) -> None:
    store = JsonFileYieldSnapshotStore(tmp_path)
    document = _document()

    path = store.save(document)

    assert path == tmp_path / "yields/snapshots/20260831T160300Z_12345678.json"
    assert JsonFileYieldSnapshotStore.read(path) == document
    with pytest.raises(FileExistsError):
        store.save(document)
