from __future__ import annotations

import json
import re

from daily_dash.config.models import PolymarketProfile
from daily_dash.contracts.news import NewsModelUsage, NewsRankingTrace
from daily_dash.contracts.polymarket import PolymarketEvent, PolymarketModelEvaluation
from daily_dash.llm.gateway import StructuredChatClient
from daily_dash.prompts import load_prompt_asset


def _slot(index: int) -> str:
    return f"P{index:03d}"


def _normalize_topic_key(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    if not normalized:
        raise ValueError("Polymarket topic_key must not be empty")
    return normalized[:120].rstrip("-")


def _schema(slots: list[str]) -> dict[str, object]:
    score = {"type": "integer", "minimum": 0, "maximum": 100}
    evaluation = {
        "type": "object",
        "properties": {
            "relevance": score,
            "market_impact": score,
            "market_breadth": score,
            "prediction_signal": score,
            "ranking_score": score,
            "topic_key": {"type": "string", "minLength": 3, "maxLength": 120},
            "theme": {
                "type": "string",
                "enum": [
                    "monetary-policy",
                    "macro-economy",
                    "geopolitics-security",
                    "energy-shipping",
                    "crypto-digital-assets",
                    "regulation-policy",
                    "equities-corporate",
                    "technology",
                    "other",
                ],
            },
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
            "prediction_signal",
            "ranking_score",
            "topic_key",
            "theme",
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


class GatewayPolymarketClassifier:
    def __init__(self, client: StructuredChatClient) -> None:
        self._client = client

    def classify_batch(
        self,
        events: list[PolymarketEvent],
        profile: PolymarketProfile,
    ) -> tuple[list[PolymarketModelEvaluation], NewsRankingTrace]:
        prompt = load_prompt_asset(
            profile.ranking.prompt.id,
            profile.ranking.prompt.version,
            profile.profile_id,
        )
        slots = [_slot(index) for index in range(1, len(events) + 1)]
        payload = [
            {
                "slot": slot,
                "event_title": event.title,
                "description": event.description[: profile.retrieval.description_limit_chars],
                "category": event.category,
                "tags": event.tags,
                "provider_event_slug": event.slug,
                "market_questions": [
                    market.question
                    for market in event.markets[: profile.retrieval.event_market_question_limit]
                ],
                "end_at": event.end_at.isoformat() if event.end_at else None,
            }
            for slot, event in zip(slots, events, strict=True)
        ]
        user = (
            f"{prompt.profile_text}\n\n"
            "Evaluate and rank every Polymarket EVENT exactly once. Child market questions are "
            "provided only to explain the event's possible outcomes. Prices, probabilities, "
            "volume, liquidity, comments, trade counts and price changes are intentionally "
            "withheld; rank only semantic financial-market intelligence value.\n\n"
            f"Events:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
        )
        response = self._client.chat_structured(
            alias=profile.ranking.model_alias,
            purpose="polymarket-event-ranking-classification",
            profile=profile.profile_id,
            system=prompt.system,
            user=user,
            response_schema_name="daily_dash_polymarket_event_ranking_v5",
            response_schema=_schema(slots),
        )
        raw = response.content.get("evaluations")
        if not isinstance(raw, dict):
            raise ValueError("Polymarket response evaluations must be an object")

        evaluations: list[PolymarketModelEvaluation] = []
        for slot, event in zip(slots, events, strict=True):
            value = raw.get(slot)
            if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
                raise ValueError(f"missing Polymarket evaluation for slot {slot}")
            evaluation_data: dict[str, object] = dict(value)
            evaluation_data["id"] = event.id
            evaluation_data["topic_key"] = _normalize_topic_key(evaluation_data.get("topic_key"))
            evaluations.append(PolymarketModelEvaluation.model_validate(evaluation_data))

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
