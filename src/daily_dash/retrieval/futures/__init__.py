from __future__ import annotations

from datetime import datetime
from typing import Protocol

from daily_dash.config import FuturesSourceSet
from daily_dash.contracts.futures import RawFuturesSnapshot
from daily_dash.retrieval.futures.tradingview import TradingViewFuturesRetriever


class FuturesRetriever(Protocol):
    def retrieve(
        self,
        source_set: FuturesSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawFuturesSnapshot: ...


__all__ = ["FuturesRetriever", "TradingViewFuturesRetriever"]
