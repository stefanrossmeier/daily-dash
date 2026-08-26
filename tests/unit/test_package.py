from daily_dash import cli


def test_cli_exists() -> None:
    assert callable(cli.main)


def test_parser_exists() -> None:
    parser = cli.build_parser()

    assert parser.prog == "daily-dash"
