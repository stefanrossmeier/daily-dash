from datetime import UTC, datetime

from daily_dash.config import MarketSourceSet, MarketsProfile
from daily_dash.contracts import MarketGroup, RawMarketAsset, RawMarketSnapshot


class FakeRetriever:
    def retrieve(
        self,
        source_set: MarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawMarketSnapshot:
        return RawMarketSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            assets=[
                RawMarketAsset(
                    asset_id="dax",
                    name="DAX",
                    symbol="^GDAXI",
                    group=MarketGroup.INDICES,
                    last=101.0,
                    previous_close=100.0,
                )
            ],
        )


def test_markets_pipeline_can_return_persisted_artifact_path(tmp_path) -> None:
    from daily_dash.pipelines.markets import run_markets_pipeline
    from daily_dash.storage import JsonFileMarketSnapshotStore

    profile = MarketsProfile.model_validate(
        {
            "profile_id": "markets",
            "pipeline": "markets",
            "source_set": "markets",
            "presentation": {},
        }
    )
    source_set = MarketSourceSet.model_validate(
        {
            "pipeline": "markets",
            "source_set_id": "markets",
            "provider": "yfinance",
            "assets": [],
        }
    )
    now = datetime(2026, 8, 26, 18, 0, tzinfo=UTC)

    document, output_path = run_markets_pipeline(
        profile,
        source_set,
        FakeRetriever(),
        run_id="run-1",
        now=now,
        snapshot_store=JsonFileMarketSnapshotStore(tmp_path),
    )

    assert document.raw.run_id == "run-1"
    assert document.report.profile == "markets"
    assert output_path.parent == tmp_path / "markets" / "snapshots"
    assert output_path.exists()
