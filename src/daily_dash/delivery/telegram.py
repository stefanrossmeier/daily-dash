"""Telegram delivery is bounded to 105s per part (3 * 25s attempts + 2 * 15s
Retry-After waits), excluding local processing overhead; an artifact with N
parts is bounded to N * 105s. Other transient failures use jittered exponential
backoff with less than 10s total wait per part.
"""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from daily_dash.contracts import DeliveryResult, DeliveryStatus, ReportArtifact

TELEGRAM_SAFE_MESSAGE_LIMIT = 3800
_MAX_ATTEMPTS = 3
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRY_AFTER_SECONDS = 15.0
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_MAX_SECONDS = 10.0
_JITTER = random.Random()


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
    """Deliver artifacts through Telegram with bounded per-part retries."""

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

    @staticmethod
    def _description(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        if isinstance(payload, dict):
            description = payload.get("description")
            if isinstance(description, str):
                return description
        return None

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if not isinstance(retry_at, datetime):
                    return None
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                seconds = (retry_at - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return None
        return min(max(seconds, 0.0), _MAX_RETRY_AFTER_SECONDS)

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        delay: float = _BACKOFF_BASE_SECONDS * float(2 ** (attempt - 1))
        if delay > _BACKOFF_MAX_SECONDS:
            delay = _BACKOFF_MAX_SECONDS
        jitter: float = float(_JITTER.uniform(0.75, 1.25))
        return float(delay * jitter)

    @staticmethod
    def _failed(artifact: ReportArtifact, error: str) -> DeliveryResult:
        return DeliveryResult(
            run_id=artifact.run_id,
            destination="telegram",
            status=DeliveryStatus.FAILED,
            error=error,
        )

    def send(self, artifact: ReportArtifact) -> DeliveryResult:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        own_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        last_message_id: str | None = None

        try:
            for part in split_markdown_message(artifact.content):
                for attempt in range(1, _MAX_ATTEMPTS + 1):
                    try:
                        response = client.post(
                            url,
                            data={
                                "chat_id": self._chat_id,
                                "text": part,
                                "parse_mode": self._parse_mode,
                            },
                        )
                    except httpx.TransportError as exc:
                        if attempt < _MAX_ATTEMPTS:
                            time.sleep(self._backoff_seconds(attempt))
                            continue
                        return self._failed(
                            artifact,
                            f"Telegram transport failed after {attempt} attempts: {exc}",
                        )

                    description = self._description(response)
                    if response.status_code in _TRANSIENT_STATUS_CODES:
                        if attempt < _MAX_ATTEMPTS:
                            delay = (
                                self._retry_after_seconds(response)
                                if response.status_code == 429
                                else None
                            )
                            retry_delay = (
                                delay if delay is not None else self._backoff_seconds(attempt)
                            )
                            time.sleep(retry_delay)
                            continue
                        error = (
                            f"Telegram API returned HTTP {response.status_code} "
                            f"after {attempt} attempts"
                        )
                        if description:
                            error += f": {description}"
                        return self._failed(artifact, error)

                    if not response.is_success:
                        attempt_word = "attempt" if attempt == 1 else "attempts"
                        error = (
                            f"Telegram API returned HTTP {response.status_code} "
                            f"after {attempt} {attempt_word}"
                        )
                        if description:
                            error += f": {description}"
                        return self._failed(artifact, error)

                    try:
                        payload = response.json()
                    except ValueError as exc:
                        return self._failed(
                            artifact,
                            f"Telegram returned invalid JSON after {attempt} attempt(s): {exc}",
                        )
                    last_message_id = self._message_id(payload)
                    break
        finally:
            if own_client:
                client.close()

        return DeliveryResult(
            run_id=artifact.run_id,
            destination="telegram",
            status=DeliveryStatus.SUCCESS,
            external_id=last_message_id,
        )
