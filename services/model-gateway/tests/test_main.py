from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from daily_dash_model_gateway.main import (
    ChatRequest,
    XSearchRequest,
    _decode_json_object,
    _post_openrouter,
    chat,
    x_search,
)
from fastapi import HTTPException


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

    def test_gateway_retries_same_model_twice_without_failover(self) -> None:
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
                    httpx.ReadTimeout("provider stalled once"),
                    httpx.ReadTimeout("provider stalled twice"),
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
                                "max_attempts": 3,
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
            self.assertEqual(response.attempts, 3)
            self.assertFalse(response.usage_complete)
            self.assertEqual(len(response.attempt_errors), 2)
            self.assertIn("provider stalled once", response.attempt_errors[0])
            self.assertIn("provider stalled twice", response.attempt_errors[1])
            self.assertEqual(post.await_count, 3)
            models = [call.kwargs["payload"]["model"] for call in post.await_args_list]
            self.assertEqual(
                models,
                [
                    "openai/gpt-5.4-nano",
                    "openai/gpt-5.4-nano",
                    "openai/gpt-5.4-nano",
                ],
            )

        asyncio.run(run())

    def test_x_search_alias_injects_native_search_inside_gateway(self) -> None:
        async def run() -> None:
            success = httpx.Response(
                200,
                json={
                    "id": "generation-x",
                    "model": "x-ai/grok-4.3",
                    "output_text": '{"posts": []}',
                    "usage": {
                        "input_tokens": 20,
                        "output_tokens": 4,
                        "total_tokens": 24,
                        "cost": 0.006,
                    },
                    "openrouter_metadata": {
                        "requested": "x-ai/grok-4.3",
                        "strategy": "direct",
                        "region": "MUC",
                    },
                    "output": [
                        {
                            "id": "search-1",
                            "type": "web_search_call",
                            "status": "completed",
                            "action": {"type": "search", "query": "from:NickTimiraos"},
                        },
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": '{"posts": []}',
                                    "annotations": [
                                        {
                                            "type": "url_citation",
                                            "url": "https://x.com/i/status/123",
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            )
            post = AsyncMock(return_value=success)
            schema = {
                "type": "object",
                "required": ["posts"],
                "properties": {"posts": {"type": "array"}},
            }
            with (
                patch(
                    "daily_dash_model_gateway.main._load_config",
                    return_value={
                        "aliases": {
                            "x-retrieve": {
                                "provider": "openrouter",
                                "model": "x-ai/grok-4.3",
                                "max_attempts": 1,
                                "timeout_seconds": 180,
                                "allow_x_search": True,
                            }
                        }
                    },
                ),
                patch(
                    "daily_dash_model_gateway.main._load_api_key",
                    return_value="test-key",
                ),
                patch(
                    "daily_dash_model_gateway.main._post_openrouter_responses",
                    post,
                ),
            ):
                response = await x_search(
                    XSearchRequest(
                        alias="x-retrieve",
                        purpose="compatibility",
                        input="search X",
                        allowed_x_handles=["NickTimiraos"],
                        from_date="2026-08-28",
                        to_date="2026-08-29",
                        response_schema_name="x_schema",
                        response_schema=schema,
                    )
                )

            self.assertEqual(response.model, "x-ai/grok-4.3")
            self.assertEqual(response.content, {"posts": []})
            self.assertEqual(response.usage.cost_usd, 0.006)
            self.assertEqual(response.provider_metadata["x_search_call_count"], 1)
            self.assertEqual(response.provider_metadata["x_search_queries"], ["from:NickTimiraos"])
            self.assertEqual(
                response.provider_metadata["citation_urls"],
                ["https://x.com/i/status/123"],
            )
            self.assertNotIn("output", response.provider_metadata)

            payload = post.await_args.kwargs["payload"]
            self.assertEqual(payload["model"], "x-ai/grok-4.3")
            self.assertEqual(payload["plugins"], [{"id": "web", "engine": "native"}])
            self.assertEqual(
                payload["x_search_filter"],
                {
                    "allowed_x_handles": ["NickTimiraos"],
                    "from_date": "2026-08-28",
                    "to_date": "2026-08-29",
                },
            )
            self.assertEqual(payload["reasoning"], {"enabled": False})
            self.assertEqual(payload["provider"], {"require_parameters": True})
            self.assertEqual(
                payload["text"],
                {
                    "format": {
                        "type": "json_schema",
                        "name": "x_schema",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )

        asyncio.run(run())

    def test_decode_json_object_recovers_json_wrapped_in_prose(self) -> None:
        self.assertEqual(
            _decode_json_object('Result follows:\n```json\n{"posts": []}\n```'),
            {"posts": []},
        )

    def test_decode_json_object_reports_non_json_output(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "output_prefix"):
            _decode_json_object("No structured result was produced")

    def test_x_search_is_blocked_for_normal_ranking_alias(self) -> None:
        async def run() -> None:
            with patch(
                "daily_dash_model_gateway.main._load_config",
                return_value={
                    "aliases": {
                        "rank-cheap": {
                            "provider": "openrouter",
                            "model": "openai/gpt-5.4-nano",
                        }
                    }
                },
            ):
                with self.assertRaises(HTTPException) as caught:
                    await x_search(
                        XSearchRequest(
                            alias="rank-cheap",
                            purpose="compatibility",
                            input="search X",
                            allowed_x_handles=["NickTimiraos"],
                            from_date="2026-08-28",
                            to_date="2026-08-29",
                            response_schema={"type": "object"},
                        )
                    )

            self.assertEqual(caught.exception.status_code, 403)
            self.assertIn("not allowed to use X search", str(caught.exception.detail))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
