from datetime import UTC, datetime

from daily_dash.config import FuturesProfile, FuturesSourceSet
from daily_dash.contracts.futures import RawFuturesQuote, RawFuturesSnapshot
from daily_dash.pipelines.futures import run_futures_pipeline
from daily_dash.storage import JsonFileFuturesSnapshotStore


class FakeRetriever:
    def retrieve(
        self,
        source_set: FuturesSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawFuturesSnapshot:
        return RawFuturesSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            quotes=[
                RawFuturesQuote(
                    asset_id="sp500",
                    name="S&P",
                    instrument="ES",
                    last=5100,
                    previous_value=5000,
                    change_basis="previous_close",
                    source="TradingView",
                    source_ref="CME_MINI:ES1!",
                    data_type="tradingview_1h",
                ),
                RawFuturesQuote(
                    asset_id="brent",
                    name="Brent",
                    instrument="Brent",
                    source="TradingView",
                    source_ref="NYMEX:BZ1!",
                    error="no last price",
                ),
            ],
        )


def test_futures_pipeline_persists_partial_snapshot_instead_of_failing(tmp_path) -> None:
    profile = FuturesProfile.model_validate(
        {
            "profile_id": "futures",
            "pipeline": "futures",
            "source_set": "futures",
            "presentation": {},
        }
    )
    source_set = FuturesSourceSet.model_validate(
        {
            "pipeline": "futures",
            "source_set_id": "futures",
            "provider": "tradingview-datafeed",
            "assets": [
                {
                    "id": "sp500",
                    "name": "S&P",
                    "instrument": "E-mini S&P 500 continuous future",
                    "symbol": "ES1!",
                    "exchange": "CME_MINI",
                }
            ],
        }
    )
    document, path = run_futures_pipeline(
        profile,
        source_set,
        FakeRetriever(),
        snapshot_store=JsonFileFuturesSnapshotStore(tmp_path),
        run_id="run-1",
        now=datetime(2026, 8, 28, 21, 15, tzinfo=UTC),
    )
    assert path.parent == tmp_path / "futures" / "snapshots"
    assert document.report.quotes[1].status == "unavailable"
    assert JsonFileFuturesSnapshotStore.read(path) == document
