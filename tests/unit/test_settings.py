from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_dash.config.settings import TelegramSettings


def test_telegram_settings_do_not_load_repository_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "DAILY_DASH_TELEGRAM_TOKEN=dotenv-token\nDAILY_DASH_TELEGRAM_CHAT_ID=-123456\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DAILY_DASH_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("DAILY_DASH_TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValidationError):
        TelegramSettings()


def test_telegram_settings_accept_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAILY_DASH_TELEGRAM_TOKEN", "environment-token")
    monkeypatch.setenv("DAILY_DASH_TELEGRAM_CHAT_ID", "-123456")

    settings = TelegramSettings()

    assert settings.telegram_token == "environment-token"
    assert settings.telegram_chat_id == "-123456"
