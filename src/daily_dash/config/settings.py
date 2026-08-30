from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramSettings(BaseSettings):
    """Telegram credentials loaded only at the delivery boundary."""

    model_config = SettingsConfigDict(
        env_prefix="DAILY_DASH_",
        extra="ignore",
    )

    telegram_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
