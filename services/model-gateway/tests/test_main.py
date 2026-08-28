from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from daily_dash_model_gateway.main import ChatRequest, _post_openrouter, chat


class _SlowAsyncClient:
    def __init__(self, *, timeout: object) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> _SlowAsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    async def post(self, *args: object, **kwargs: object) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"ok": True})


class ModelGatewayDeadlineTests(unittest.TestCase):
    def test_openrouter_attempt_has_wall_clock_deadline(self) -> None:
        async def run() -> None:
            with patch(
                "daily_dash_model_gateway.main.httpx.AsyncClient",
                _SlowAsyncClient,
            ):
                with self.assertRaisesRegex(
                    httpx.ReadTimeout,
                    "wall-clock deadline",
                ):
                    await _post_openrouter(
                        headers={},
                        payload={},
                        timeout_seconds=0.01,
                    )

        asyncio.run(run())

    def test_gateway_retries_same_model_once_without_failover(self) -> None:
        async def run() -> None:
            success = httpx.Response(
                200,
                json={
                    "id": "generation-2",
                    "model": "openai/gpt-5.4-nano",
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "cost": 0.001,
                    },
                },
            )
            post = AsyncMock(
                side_effect=[
                    httpx.ReadTimeout("provider stalled"),
                    success,
                ]
            )
            with (
                patch(
                    "daily_dash_model_gateway.main._load_config",
                    return_value={
                        "aliases": {
                            "rank-cheap": {
                                "provider": "openrouter",
                                "model": "openai/gpt-5.4-nano",
                                "max_attempts": 2,
                                "timeout_seconds": 180,
                            }
                        }
                    },
                ),
                patch(
                    "daily_dash_model_gateway.main._load_api_key",
                    return_value="test-key",
                ),
                patch(
                    "daily_dash_model_gateway.main._post_openrouter",
                    post,
                ),
            ):
                response = await chat(
                    ChatRequest(
                        alias="rank-cheap",
                        purpose="test",
                        messages=[{"role": "user", "content": "hello"}],
                    )
                )

            self.assertEqual(response.model, "openai/gpt-5.4-nano")
            self.assertEqual(response.attempts, 2)
            self.assertFalse(response.usage_complete)
            self.assertEqual(len(response.attempt_errors), 1)
            self.assertIn("provider stalled", response.attempt_errors[0])
            self.assertEqual(post.await_count, 2)
            models = [call.kwargs["payload"]["model"] for call in post.await_args_list]
            self.assertEqual(models, ["openai/gpt-5.4-nano", "openai/gpt-5.4-nano"])

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
