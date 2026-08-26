from __future__ import annotations

from daily_dash.contracts.market import (
    MarketReportData,
    ProcessedMarketAsset,
    RawMarketAsset,
    RawMarketSnapshot,
)


def _percentage_change(last: float | None, previous: float | None) -> float | None:
    if last is None or previous in (None, 0.0):
        return None
    return ((last / previous) - 1.0) * 100.0


def _ath_distance(last: float | None, high: float | None) -> float | None:
    if last is None or high is None or high <= 0:
        return None
    return ((last / high) - 1.0) * 100.0


def _process_asset(asset: RawMarketAsset) -> ProcessedMarketAsset:
    return ProcessedMarketAsset(
        asset_id=asset.asset_id,
        name=asset.name,
        symbol=asset.symbol,
        group=asset.group,
        price_decimals=asset.price_decimals,
        last=asset.last,
        change_pct=_percentage_change(asset.last, asset.previous_close),
        ath_label=asset.ath_label,
        ath_symbol=asset.ath_symbol,
        ath_distance_pct=_ath_distance(asset.ath_last, asset.ath_high),
    )


def process_market_snapshot(
    snapshot: RawMarketSnapshot,
    *,
    profile_id: str,
) -> MarketReportData:
    issues = [
        f"{asset.name} ({asset.symbol}): {asset.error}"
        for asset in snapshot.assets
        if asset.error is not None
    ]

    return MarketReportData(
        run_id=snapshot.run_id,
        profile=profile_id,
        generated_at=snapshot.retrieved_at,
        assets=[_process_asset(asset) for asset in snapshot.assets],
        issues=issues,
    )
