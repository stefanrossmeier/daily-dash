from __future__ import annotations

import csv
import io
from datetime import date, datetime
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
