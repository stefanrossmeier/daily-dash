from daily_dash import cli


def test_cli_exists() -> None:
    assert callable(cli.main)
