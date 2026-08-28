from __future__ import annotations

from typing import Any

import httpx

from daily_dash.contracts import DeliveryResult, DeliveryStatus, ReportArtifact

TELEGRAM_SAFE_MESSAGE_LIMIT = 3800


def split_markdown_message(text: str, limit: int = TELEGRAM_SAFE_MESSAGE_LIMIT) -> list[str]:
    """Split markdown on paragraph boundaries while keeping messages below Telegram's limit."""

    sections = text.split("\n\n")
    parts: list[str] = []
    current = ""

    for section in sections:
        candidate = section if not current else f"{current}\n\n{section}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            parts.append(current)
            current = ""

        if len(section) <= limit:
            current = section
            continue

        remainder = section
        while len(remainder) > limit:
            split_at = remainder.rfind("\n", 0, limit)
            if split_at <= 0:
                split_at = limit
            parts.append(remainder[:split_at].rstrip())
            remainder = remainder[split_at:].lstrip()
        current = remainder

    if current:
        parts.append(current)

    return parts or [text]


class TelegramDelivery:
    """Deliver rendered artifacts through the Telegram Bot API."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 25.0,
        parse_mode: str = "Markdown",
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._parse_mode = parse_mode

    @staticmethod
    def _message_id(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        message_id = result.get("message_id")
        if isinstance(message_id, int | str):
            return str(message_id)
        return None

    def send(self, artifact: ReportArtifact) -> DeliveryResult:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        own_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        last_message_id: str | None = None

        try:
            for part in split_markdown_message(artifact.content):
                response = client.post(
                    url,
                    data={
                        "chat_id": self._chat_id,
                        "text": part,
                        "parse_mode": self._parse_mode,
                    },
                )
                response.raise_for_status()
                last_message_id = self._message_id(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            return DeliveryResult(
                run_id=artifact.run_id,
                destination="telegram",
                status=DeliveryStatus.FAILED,
                error=str(exc),
            )
        finally:
            if own_client:
                client.close()

        return DeliveryResult(
            run_id=artifact.run_id,
            destination="telegram",
            status=DeliveryStatus.SUCCESS,
            external_id=last_message_id,
        )
