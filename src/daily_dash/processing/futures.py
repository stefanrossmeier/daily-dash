from __future__ import annotations

from daily_dash.config import FuturesProfile
from daily_dash.contracts.futures import (
    FuturesQuote,
    FuturesQuoteStatus,
    FuturesReportData,
    RawFuturesSnapshot,
)


def _change_pct(last: float | None, previous: float | None) -> float | None:
    if last is None or previous in {None, 0}:
        return None
    assert previous is not None
    return ((last / previous) - 1.0) * 100.0


def process_futures_snapshot(raw: RawFuturesSnapshot, profile: FuturesProfile) -> FuturesReportData:
    quotes: list[FuturesQuote] = []
    issues: list[str] = []

    for quote in raw.quotes:
        change_pct = _change_pct(quote.last, quote.previous_value)
        status: FuturesQuoteStatus
        if quote.last is None:
            status = "unavailable"
        elif change_pct is None or quote.error is not None:
            status = "partial"
        else:
            status = "ok"

        quotes.append(
            FuturesQuote(
                asset_id=quote.asset_id,
                name=quote.name,
                instrument=quote.instrument,
                price_decimals=quote.price_decimals,
                contract=quote.contract,
                last=quote.last,
                previous_value=quote.previous_value,
                change_pct=change_pct,
                change_basis=quote.change_basis,
                source=quote.source,
                source_ref=quote.source_ref,
                source_timestamp=quote.source_timestamp,
                data_type=quote.data_type,
                status=status,
            )
        )
        if quote.error:
            source = f" ({quote.source_ref})" if quote.source_ref else ""
            issues.append(f"{quote.name}{source}: {quote.error}")

    return FuturesReportData(
        run_id=raw.run_id,
        profile=profile.profile_id,
        generated_at=raw.retrieved_at,
        quotes=quotes,
        issues=issues,
    )
