from daily_dash.retrieval.yields import _csv_observations, _fred_observations


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
