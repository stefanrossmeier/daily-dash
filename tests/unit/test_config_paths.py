from pathlib import Path

from pytest import MonkeyPatch

from daily_dash.config import default_config_dir


def test_config_dir_defaults_to_relative_config(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("DAILY_DASH_CONFIG_DIR", raising=False)
    monkeypatch.delenv("DAILY_DASH_HOME", raising=False)

    assert default_config_dir() == Path("config")


def test_config_dir_uses_daily_dash_home(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("DAILY_DASH_CONFIG_DIR", raising=False)
    monkeypatch.setenv("DAILY_DASH_HOME", "/opt/daily-dash")

    assert default_config_dir() == Path("/opt/daily-dash/config")


def test_explicit_config_dir_takes_precedence(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_DASH_HOME", "/opt/daily-dash")
    monkeypatch.setenv(
        "DAILY_DASH_CONFIG_DIR",
        "/etc/daily-dash/config",
    )

    assert default_config_dir() == Path("/etc/daily-dash/config")
