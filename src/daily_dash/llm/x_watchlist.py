from __future__ import annotations

import json

from daily_dash.config.models import XWatchlistProfile
from daily_dash.contracts.news import NewsModelUsage
from daily_dash.contracts.x_watchlist import (
    XWatchlistModelEvaluation,
    XWatchlistModelTrace,
    XWatchlistPost,
)
from daily_dash.llm.gateway import StructuredChatClient
from daily_dash.prompts import load_prompt_asset


def _slot(index: int) -> str:
    return f"X{index:03d}"


def _schema(slots: list[str]) -> dict[str, object]:
    score = {"type": "integer", "minimum": 0, "maximum": 100}
    evaluation = {
        "type": "object",
        "properties": {
            "relevance": score,
            "market_impact": score,
            "market_breadth": score,
            "information_value": score,
            "category": {
                "type": "string",
                "enum": [
                    "macro",
                    "monetary-policy",
                    "rates",
                    "fx",
                    "equities",
                    "commodities",
                    "credit",
                    "crypto",
                    "geopolitics",
                    "market-structure",
                    "company-specific",
                    "other",
                ],
            },
            "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
            "topic_key": {"type": "string"},
            "rationale": {"type": "string"},
        },
        "required": [
            "relevance",
            "market_impact",
            "market_breadth",
            "information_value",
            "category",
            "urgency",
            "topic_key",
            "rationale",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "evaluations": {
                "type": "object",
                "properties": {slot: evaluation for slot in slots},
                "required": slots,
                "additionalProperties": False,
            }
        },
        "required": ["evaluations"],
        "additionalProperties": False,
    }


class GatewayXWatchlistClassifier:
    def __init__(self, client: StructuredChatClient) -> None:
        self._client = client

    def classify_batch(
        self,
        posts: list[XWatchlistPost],
        profile: XWatchlistProfile,
    ) -> tuple[list[XWatchlistModelEvaluation], XWatchlistModelTrace]:
        prompt = load_prompt_asset(
            profile.ranking.prompt.id,
            profile.ranking.prompt.version,
            profile.profile_id,
        )
        slots = [_slot(index) for index in range(1, len(posts) + 1)]
        payload = [
            {
                "slot": slot,
                "author_handle": post.author_handle,
                "publication_time": post.publication_time.isoformat(),
                "post_text": post.post_text,
            }
            for slot, post in zip(slots, posts, strict=True)
        ]
        user = prompt.render_task(
            profile_text=prompt.profile_text,
            posts_json=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        response = self._client.chat_structured(
            alias=profile.ranking.model_alias,
            purpose="x-watchlist-market-ranking",
            profile=profile.profile_id,
            system=prompt.system,
            user=user,
            response_schema_name="daily_dash_x_watchlist_ranking_v1",
            response_schema=_schema(slots),
        )
        raw = response.content.get("evaluations")
        if not isinstance(raw, dict):
            raise ValueError("X Watchlist ranking response evaluations must be an object")

        evaluations: list[XWatchlistModelEvaluation] = []
        for slot, post in zip(slots, posts, strict=True):
            value = raw.get(slot)
            if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
                raise ValueError(f"missing X Watchlist evaluation for slot {slot}")
            data: dict[str, object] = dict(value)
            data["id"] = post.id
            evaluations.append(XWatchlistModelEvaluation.model_validate(data))

        trace = XWatchlistModelTrace(
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            prompt_profile=prompt.profile,
            system_sha256=prompt.system_sha256,
            profile_sha256=prompt.profile_sha256,
            task_sha256=prompt.task_sha256,
            combined_sha256=prompt.combined_sha256,
            model_alias=response.alias,
            provider=response.provider,
            resolved_model=response.model,
            generation_id=response.generation_id,
            usage=NewsModelUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
                cost_usd=response.usage.cost_usd,
            ),
            latency_ms=response.latency_ms,
            attempts=response.attempts,
            attempt_errors=response.attempt_errors,
            usage_complete=response.usage_complete,
        )
        return evaluations, trace
