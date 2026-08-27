from datetime import UTC, datetime

from daily_dash.contracts import MarketGroup
from daily_dash.contracts.market import (
    MarketReportData,
    MarketSnapshotDocument,
    ProcessedMarketAsset,
    RawMarketAsset,
    RawMarketSnapshot,
)
from daily_dash.storage import JsonFileMarketSnapshotStore


def test_market_snapshot_is_written_as_json(tmp_path) -> None:
    collected_at = datetime(2026, 8, 27, 6, 15, tzinfo=UTC)

    raw = RawMarketSnapshot(
        run_id="abcdef12-3456-7890",
        source_set="markets",
        retrieved_at=collected_at,
        assets=[
            RawMarketAsset(
                asset_id="dax",
                name="DAX",
                symbol="^GDAXI",
                group=MarketGroup.INDICES,
                last=100.0,
                previous_close=99.0,
            )
        ],
    )

    report = MarketReportData(
        run_id=raw.run_id,
        profile="markets",
        generated_at=collected_at,
        assets=[
            ProcessedMarketAsset(
                asset_id="dax",
                name="DAX",
                symbol="^GDAXI",
                group=MarketGroup.INDICES,
                last=100.0,
                change_pct=1.010101,
            )
        ],
    )

    document = MarketSnapshotDocument(
        raw=raw,
        report=report,
    )

    path = JsonFileMarketSnapshotStore(tmp_path).save(document)

    assert path.name == "20260827T061500Z_abcdef12.json"
    assert path.parent == tmp_path / "markets" / "snapshots"

    restored = MarketSnapshotDocument.model_validate_json(path.read_text(encoding="utf-8"))

    assert restored == document
