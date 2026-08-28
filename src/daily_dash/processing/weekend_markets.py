from __future__ import annotations

from daily_dash.contracts import (
    RawWeekendMarketSnapshot,
    WeekendMarketQuote,
    WeekendMarketReportData,
)


def process_weekend_market_snapshot(
    snapshot: RawWeekendMarketSnapshot,
    *,
    profile_id: str,
) -> WeekendMarketReportData:
    issues = [
        f"{quote.name}: {quote.error}" for quote in snapshot.quotes if quote.error is not None
    ]
    quotes = [
        WeekendMarketQuote(
            quote_id=quote.quote_id,
            name=quote.name,
            price_decimals=quote.price_decimals,
            bid=quote.bid,
            ask=quote.ask,
            change_pct=quote.change_pct,
        )
        for quote in snapshot.quotes
    ]
    return WeekendMarketReportData(
        run_id=snapshot.run_id,
        profile=profile_id,
        generated_at=snapshot.retrieved_at,
        quotes=quotes,
        issues=issues,
    )
