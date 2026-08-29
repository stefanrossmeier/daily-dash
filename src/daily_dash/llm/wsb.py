from __future__ import annotations

import json

from daily_dash.config.models import WsbProfile
from daily_dash.contracts.news import NewsModelUsage, NewsRankingTrace
from daily_dash.contracts.wsb import WsbModelEvaluation, WsbPost
from daily_dash.llm.gateway import StructuredChatClient
from daily_dash.prompts import load_prompt_asset


def _slot(index: int) -> str:
    return f"W{index:03d}"


def _schema(slots: list[str]) -> dict[str, object]:
    score = {"type": "integer", "minimum": 0, "maximum": 100}
    evaluation = {
        "type": "object",
        "properties": {
            "relevance": score,
            "market_impact": score,
            "market_breadth": score,
            "positioning_signal": score,
            "signal_type": {
                "type": "string",
                "enum": [
                    "broad-market",
                    "market-moving-bet",
                    "both",
                    "narrow-or-irrelevant",
                ],
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "relevance",
            "market_impact",
            "market_breadth",
            "positioning_signal",
            "signal_type",
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


class GatewayWsbClassifier:
    def __init__(self, client: StructuredChatClient) -> None:
        self._client = client

    def classify_batch(
        self,
        posts: list[WsbPost],
        profile: WsbProfile,
    ) -> tuple[list[WsbModelEvaluation], NewsRankingTrace]:
        prompt = load_prompt_asset(
            profile.ranking.prompt.id,
            profile.ranking.prompt.version,
            profile.profile_id,
        )
        slots = [_slot(index) for index in range(1, len(posts) + 1)]
        payload = [
            {
                "slot": slot,
                "title": post.title,
                "text": post.text[: profile.retrieval.text_limit_chars],
            }
            for slot, post in zip(slots, posts, strict=True)
        ]
        user = (
            f"{prompt.profile_text}\n\n"
            "Evaluate every WSB thread exactly once. Reddit popularity metrics are "
            "intentionally withheld; classify only the semantic content.\n\n"
            f"Threads:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        response = self._client.chat_structured(
            alias=profile.ranking.model_alias,
            purpose="wsb-market-relevance-classification",
            profile=profile.profile_id,
            system=prompt.system,
            user=user,
            response_schema_name="daily_dash_wsb_ranking_v1",
            response_schema=_schema(slots),
        )
        raw = response.content.get("evaluations")
        if not isinstance(raw, dict):
            raise ValueError("WSB response evaluations must be an object")

        evaluations: list[WsbModelEvaluation] = []
        for slot, post in zip(slots, posts, strict=True):
            value = raw.get(slot)
            if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
                raise ValueError(f"missing WSB evaluation for slot {slot}")
            evaluation_data: dict[str, object] = dict(value)
            evaluation_data["id"] = post.id
            evaluations.append(WsbModelEvaluation.model_validate(evaluation_data))

        trace = NewsRankingTrace(
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            prompt_profile=prompt.profile,
            system_sha256=prompt.system_sha256,
            profile_sha256=prompt.profile_sha256,
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
