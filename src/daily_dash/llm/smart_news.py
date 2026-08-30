from __future__ import annotations

import html
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from daily_dash.config.models import NewsProfile
from daily_dash.contracts.news import NewsModelUsage, NewsRankingTrace
from daily_dash.contracts.smart_news import SmartNewsModelTheme
from daily_dash.contracts.source import SourceItem
from daily_dash.llm.gateway import StructuredChatClient
from daily_dash.prompts import load_prompt_asset

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean_input_text(value: object, max_len: int | None = None) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if max_len and len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def build_theme_input(articles: list[SourceItem]) -> str:
    lines: list[str] = []
    for index, article in enumerate(articles, start=1):
        source = _clean_input_text(article.source, max_len=80)
        title = _clean_input_text(article.title, max_len=220)
        summary = _clean_input_text(article.text, max_len=320)
        lines.append(f"{index}) [{source}] {title}")
        if summary and summary.casefold() != title.casefold():
            lines.append(f"   Summary: {summary}")
    return "\n".join(lines)


class _SmartNewsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    themes: list[SmartNewsModelTheme]


def _response_schema(*, max_themes: int, max_article_index: int) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "themes": {
                "type": "array",
                "maxItems": max_themes,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "headline_indices": {
                            "type": "array",
                            "maxItems": 6,
                            "items": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": max_article_index,
                            },
                        },
                    },
                    "required": ["title", "summary", "headline_indices"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["themes"],
        "additionalProperties": False,
    }


class GatewaySmartNewsAnalyzer:
    """Run the legacy Smart News theme-clustering prompt through the model gateway."""

    def __init__(self, client: StructuredChatClient) -> None:
        self._client = client

    def analyze(
        self,
        articles: list[SourceItem],
        profile: NewsProfile,
    ) -> tuple[list[SmartNewsModelTheme], NewsRankingTrace]:
        if not articles:
            raise ValueError("Smart News analysis requires at least one article")

        max_themes = profile.ranking.top_k
        prompt = load_prompt_asset(
            profile.ranking.prompt.id,
            profile.ranking.prompt.version,
            profile.profile_id,
        )

        system = prompt.render_system(max_themes=max_themes)
        headlines_block = build_theme_input(articles)
        user = prompt.render_task(
            headlines_block=headlines_block,
            profile_text=prompt.profile_text,
        )

        response = self._client.chat_structured(
            alias=profile.ranking.model_alias,
            purpose="news-smart-theme-clustering",
            profile=profile.profile_id,
            system=system,
            user=user,
            response_schema_name="daily_dash_news_smart_v1",
            response_schema=_response_schema(
                max_themes=max_themes,
                max_article_index=len(articles),
            ),
        )

        try:
            parsed = _SmartNewsResponse.model_validate(response.content)
        except ValidationError as exc:
            raise RuntimeError(f"Smart News response failed local validation: {exc}") from exc

        trace = NewsRankingTrace(
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

        return parsed.themes, trace
