from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Protocol

import httpx

from daily_dash.config import YieldSeriesConfig, YieldSourceSet
from daily_dash.contracts import RawYieldSeries, RawYieldSnapshot, YieldObservation

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
BUNDESBANK_BASE = "https://api.statistiken.bundesbank.de/rest/data"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"


class YieldRetriever(Protocol):
    def retrieve(
        self,
        source_set: YieldSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawYieldSnapshot:
        """Retrieve every configured yield series."""


def _parse_date(value: str) -> date | None:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> float | None:
    text = value.strip().replace("\u00a0", "")
    if not text or text in {".", "-", "..", "NA", "N/A"}:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


CNBC_BASE = (
    "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
)
# Akamai on quote.cnbc.com rejects the default httpx user agent (403); a
# browser-like agent plus the cnbc.com referer are required (verified live).
CNBC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.cnbc.com/",
    "Accept": "application/json",
}


def _previous_business_day(day: date) -> date:
    candidate = day - timedelta(days=1)
    while candidate.weekday() >= 5:  # Saturday=5, Sunday=6
        candidate -= timedelta(days=1)
    return candidate


def _cnbc_timestamp_date(value: str) -> date | None:
    text = value.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _cnbc_observations(payload: dict, *, limit: int) -> list[YieldObservation]:
    quotes = payload.get("FormattedQuoteResult", {}).get("FormattedQuote") or []
    if not quotes:
        return []
    quote = quotes[0]

    observed_on = _cnbc_timestamp_date(str(quote.get("last_time") or ""))
    if observed_on is None:
        return []
    # CNBC's quote cache can carry weekend/intraday timestamps; a weekend
    # stamp is normalized back to the most recent business day so it can
    # align with the official daily series (specs/001-developer-t-004d1769).
    if observed_on.weekday() >= 5:  # Saturday=5, Sunday=6
        observed_on = _previous_business_day(observed_on)

    latest_text = str(quote.get("last") or "").strip().rstrip("%").strip()
    latest_value = _parse_float(latest_text) if latest_text else None
    if latest_value is None:
        return []
    observations = [YieldObservation(observed_on=observed_on, value_pct=latest_value)]

    previous_text = str(quote.get("previous_day_closing") or "").strip().rstrip("%").strip()
    previous_value = _parse_float(previous_text) if previous_text else None
    if previous_value is not None:
        observations.append(
            YieldObservation(
                observed_on=_previous_business_day(observed_on),
                value_pct=previous_value,
            )
        )
    return observations[:limit]


def _sniff_rows(text: str) -> list[dict[str, str]]:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [
        {str(key): str(value or "") for key, value in row.items() if key is not None}
        for row in reader
    ]


def _csv_observations(text: str, *, limit: int) -> list[YieldObservation]:
    rows = _sniff_rows(text)
    if not rows:
        return []
    reader_fieldnames = list(rows[0])
    fields = {field.casefold(): field for field in reader_fieldnames}
    date_field = next(
        (fields[name] for name in ("time_period", "date", "datum", "data") if name in fields),
        None,
    )
    value_field = next(
        (fields[name] for name in ("obs_value", "value", "wert", "valore") if name in fields),
        None,
    )
    if date_field is None or value_field is None:
        return []

    observations: list[YieldObservation] = []
    for row in rows:
        observed_on = _parse_date(row.get(date_field, ""))
        value = _parse_float(row.get(value_field, ""))
        if observed_on is None or value is None:
            continue
        observations.append(YieldObservation(observed_on=observed_on, value_pct=value))

    observations.sort(key=lambda item: item.observed_on, reverse=True)
    return observations[:limit]


def _fred_observations(text: str, *, limit: int) -> list[YieldObservation]:
    rows = list(csv.reader(io.StringIO(text)))
    observations: list[YieldObservation] = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        observed_on = _parse_date(row[0])
        value = _parse_float(row[1])
        if observed_on is None or value is None:
            continue
        observations.append(YieldObservation(observed_on=observed_on, value_pct=value))
    observations.sort(key=lambda item: item.observed_on, reverse=True)
    return observations[:limit]


class OfficialYieldRetriever:
    """Retrieve yields from official central-bank/statistical-provider endpoints."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    def _retrieve_series(self, config: YieldSeriesConfig, limit: int) -> RawYieldSeries:
        source_ref = (
            f"{config.provider}:{config.dataset or ''}:{config.key or config.dataset or ''}"
        )
        try:
            with httpx.Client(timeout=self._timeout_seconds, follow_redirects=True) as client:
                if config.provider == "fred":
                    response = client.get(FRED_BASE, params={"id": config.key})
                    response.raise_for_status()
                    observations = _fred_observations(response.text, limit=limit)
                elif config.provider == "bundesbank":
                    response = client.get(
                        f"{BUNDESBANK_BASE}/{config.dataset}/{config.key}",
                        params={
                            "format": "sdmx_csv",
                            "detail": "dataonly",
                            "lastNObservations": str(limit),
                        },
                        headers={"Accept": "text/csv"},
                    )
                    response.raise_for_status()
                    observations = _csv_observations(response.text, limit=limit)
                elif config.provider == "ecb":
                    response = client.get(
                        f"{ECB_BASE}/{config.dataset}/{config.key}",
                        params={
                            "format": "csvdata",
                            "detail": "dataonly",
                            "lastNObservations": str(limit),
                        },
                        headers={"Accept": "text/csv"},
                    )
                    response.raise_for_status()
                    observations = _csv_observations(response.text, limit=limit)
                elif config.provider == "cnbc":
                    response = client.get(
                        CNBC_BASE,
                        params={
                            "symbols": config.key,
                            "requestMethod": "itv",
                            "noform": "1",
                            "partnerId": "2",
                            "fund": "1",
                            "output": "json",
                        },
                        headers=CNBC_HEADERS,
                    )
                    response.raise_for_status()
                    observations = _cnbc_observations(response.json(), limit=limit)
                else:  # pragma: no cover - enforced by Pydantic
                    raise ValueError(f"unsupported yield provider: {config.provider}")

            if not observations:
                raise ValueError("no matching observations returned")
            return RawYieldSeries(
                series_id=config.id,
                name=config.name,
                provider=config.provider,
                source_ref=source_ref,
                observations=observations,
            )
        except Exception as exc:
            return RawYieldSeries(
                series_id=config.id,
                name=config.name,
                provider=config.provider,
                source_ref=source_ref,
                error=f"{type(exc).__name__}: {exc}",
            )

    def retrieve(
        self,
        source_set: YieldSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawYieldSnapshot:
        series = [
            self._retrieve_series(config, source_set.observation_limit)
            for config in source_set.series
            if config.enabled
        ]
        return RawYieldSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            series=series,
        )
