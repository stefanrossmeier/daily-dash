import pytest

from daily_dash.retrieval.yields import _csv_observations, _fred_observations

from daily_dash.retrieval.yields import _cnbc_observations


def test_fred_csv_parser_skips_missing_values_and_returns_latest_first() -> None:
    observations = _fred_observations(
        "DATE,DGS10\n2026-08-27,4.21\n2026-08-28,.\n2026-08-29,4.25\n",
        limit=2,
    )

    assert [item.observed_on.isoformat() for item in observations] == [
        "2026-08-29",
        "2026-08-27",
    ]
    assert [item.value_pct for item in observations] == [4.25, 4.21]


def test_sdmx_csv_parser_reads_comma_delimited_data() -> None:
    observations = _csv_observations(
        "KEY,TIME_PERIOD,OBS_VALUE\nfoo,2026-08-28,2.42\nfoo,2026-08-29,2.45\n",
        limit=5,
    )

    assert observations[0].observed_on.isoformat() == "2026-08-29"
    assert observations[0].value_pct == 2.45


def test_sdmx_csv_parser_reads_semicolon_delimited_decimal_comma_data() -> None:
    observations = _csv_observations(
        "KEY;TIME_PERIOD;OBS_VALUE\nfoo;2026-08-28;2,42\nfoo;2026-08-29;2,45\n",
        limit=5,
    )

    assert [item.observed_on.isoformat() for item in observations] == [
        "2026-08-29",
        "2026-08-28",
    ]
    assert [item.value_pct for item in observations] == [2.45, 2.42]


# --- T002b: CNBC quote JSON parsing for France yields (FR-001) ---

requires_cnbc_parser = pytest.mark.skipif(
    _cnbc_observations is None,
    reason="CNBC parser (_cnbc_observations) not implemented yet (T003)",
)


def _cnbc_payload(last: str, prev: str, last_time: str) -> dict:
    return {
        "FormattedQuoteResult": {
            "FormattedQuote": [
                {
                    "symbol": "FR10Y",
                    "name": "France 10 Year Bond",
                    "last": last,
                    "previous_day_closing": prev,
                    "last_time": last_time,
                }
            ]
        }
    }


@requires_cnbc_parser
def test_cnbc_parser_produces_latest_and_previous_observations() -> None:
    observations = _cnbc_observations(
        _cnbc_payload("5.0223%", "5.0214%", "2026-10-23T11:08:07.000+0200"), limit=12
    )

    assert [item.observed_on.isoformat() for item in observations] == [
        "2026-10-23",
        "2026-10-22",
    ]
    assert [item.value_pct for item in observations] == [5.0223, 5.0214]


@requires_cnbc_parser
def test_cnbc_parser_normalizes_weekend_last_time_to_previous_business_day() -> None:
    # 2026-10-24 is a Saturday: the latest observation must land on
    # Friday 2026-10-23, and the previous observation on Thursday 2026-10-22.
    observations = _cnbc_observations(
        _cnbc_payload("5.0223%", "5.0214%", "2026-10-24T11:08:07.000+0200"), limit=12
    )

    assert [item.observed_on.isoformat() for item in observations] == [
        "2026-10-23",
        "2026-10-22",
    ]


@requires_cnbc_parser
def test_cnbc_parser_strips_percent_signs_and_handles_plain_floats() -> None:
    observations = _cnbc_observations(
        _cnbc_payload("3.8038", "3.795", "2026-10-23T17:58:00.000+0200"), limit=12
    )

    assert [item.value_pct for item in observations] == [3.8038, 3.795]


@requires_cnbc_parser
def test_cnbc_parser_skips_missing_or_invalid_fields() -> None:
    observations = _cnbc_observations(
        _cnbc_payload("", "5.0214%", "2026-10-23T11:08:07.000+0200"), limit=12
    )
    assert observations == []

    observations = _cnbc_observations(
        _cnbc_payload("5.0223%", "", "2026-10-23T11:08:07.000+0200"), limit=12
    )
    assert [item.observed_on.isoformat() for item in observations] == ["2026-10-23"]


@requires_cnbc_parser
def test_cnbc_parser_empty_quote_list() -> None:
    assert _cnbc_observations({"FormattedQuoteResult": {"FormattedQuote": []}}, limit=12) == []
