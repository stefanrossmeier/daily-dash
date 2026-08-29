from __future__ import annotations

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from daily_dash.config.models import XWatchlistProfile, XWatchlistSourceSet
from daily_dash.contracts.news import NewsModelUsage
from daily_dash.contracts.x_watchlist import (
    XWatchlistModelTrace,
    XWatchlistPost,
    XWatchlistRetrievalDiagnostic,
)
from daily_dash.llm.gateway import ModelGatewayClient
from daily_dash.prompts import load_prompt_asset

_X_URL_RE = re.compile(r"^https?://(?:www\.)?x\.com/([^/]+)/status/(\d+)(?:[/?#].*)?$", re.I)
_STATUS_ID_RE = re.compile(r"/status/(\d+)(?:[/?#]|$)", re.I)


def _response_schema(max_items: int) -> dict[str, object]:
    post = {
        "type": "object",
        "properties": {
            "author_handle": {"type": "string"},
            "publication_time": {"type": ["string", "null"]},
            "post_text": {"type": "string"},
            "post_url": {"type": ["string", "null"]},
            "linked_urls": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "author_handle",
            "publication_time",
            "post_text",
            "post_url",
            "linked_urls",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "posts": {
                "type": "array",
                "maxItems": max_items,
                "items": post,
            }
        },
        "required": ["posts"],
        "additionalProperties": False,
    }


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _search_dates(window_start: datetime, window_end: datetime, timezone: str) -> tuple[date, date]:
    zone = ZoneInfo(timezone)
    local_start = window_start.astimezone(zone).date()
    local_end = window_end.astimezone(zone).date()
    # The gateway's X date filters are inclusive. Use only the local dates that
    # cover the exact scheduled interval; application code still enforces the
    # precise timestamp boundary deterministically.
    return local_start, local_end


def _provider_audit(metadata: dict[str, object]) -> tuple[list[str], list[str]]:
    queries_raw = metadata.get("x_search_queries")
    citations_raw = metadata.get("citation_urls")
    queries = [str(item) for item in queries_raw] if isinstance(queries_raw, list) else []
    citations = [str(item) for item in citations_raw] if isinstance(citations_raw, list) else []
    return queries, citations


def _citation_status_ids(citations: list[str]) -> set[str]:
    ids: set[str] = set()
    for url in citations:
        match = _STATUS_ID_RE.search(url)
        if match:
            ids.add(match.group(1))
    return ids


def retrieve_x_watchlist_posts(
    source_set: XWatchlistSourceSet,
    profile: XWatchlistProfile,
    *,
    window_start: datetime,
    window_end: datetime,
    gateway_url: str | None = None,
) -> tuple[list[XWatchlistPost], XWatchlistRetrievalDiagnostic, XWatchlistModelTrace]:
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("X Watchlist window bounds must be timezone-aware")
    if window_start >= window_end:
        raise ValueError("X Watchlist window start must be before end")

    prompt = load_prompt_asset(
        profile.retrieval.prompt.id,
        profile.retrieval.prompt.version,
        profile.profile_id,
    )
    from_date, to_date = _search_dates(window_start, window_end, profile.presentation.timezone)
    handles_text = ", ".join(f"@{handle}" for handle in source_set.handles)
    user = (
        f"{prompt.profile_text}\n\n"
        f"Allowed X handles: {handles_text}\n"
        f"Broad X search envelope: {from_date.isoformat()} through {to_date.isoformat()}.\n"
        "Search all allowed handles as needed and return the JSON object described above."
    )

    response = ModelGatewayClient(gateway_url, timeout_seconds=240.0).x_search_structured(
        alias=profile.retrieval.model_alias,
        purpose="x-watchlist-retrieval",
        profile=profile.profile_id,
        input_text=f"{prompt.system}\n\n{user}",
        allowed_x_handles=source_set.handles,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        response_schema_name="daily_dash_x_watchlist_retrieval_v3",
        response_schema=_response_schema(profile.retrieval.max_items),
    )

    raw_posts = response.content.get("posts")
    if not isinstance(raw_posts, list):
        raise ValueError("X Watchlist retrieval response posts must be an array")

    queries, citations = _provider_audit(response.provider_metadata)
    citation_ids = _citation_status_ids(citations)
    allowed = {handle.casefold(): handle for handle in source_set.handles}
    posts: list[XWatchlistPost] = []
    seen: set[str] = set()
    invalid_author = invalid_url = invalid_timestamp = outside = missing_citation = duplicates = 0

    for raw in raw_posts:
        if not isinstance(raw, dict):
            invalid_url += 1
            continue
        author_raw = raw.get("author_handle")
        author = str(author_raw or "").strip().lstrip("@")
        canonical_author = allowed.get(author.casefold())
        if canonical_author is None:
            invalid_author += 1
            continue

        url_raw = raw.get("post_url")
        url = str(url_raw or "").strip()
        match = _X_URL_RE.match(url)
        if match is None:
            invalid_url += 1
            continue
        url_author, status_id = match.groups()
        if url_author.casefold() != canonical_author.casefold():
            invalid_author += 1
            continue

        published = _parse_timestamp(raw.get("publication_time"))
        if published is None:
            invalid_timestamp += 1
            continue
        if not window_start <= published < window_end:
            outside += 1
            continue

        if profile.retrieval.require_citation_evidence and status_id not in citation_ids:
            missing_citation += 1
            continue
        if status_id in seen:
            duplicates += 1
            continue

        text = str(raw.get("post_text") or "").strip()
        if not text:
            invalid_url += 1
            continue
        linked_raw = raw.get("linked_urls")
        linked_urls = [str(item) for item in linked_raw] if isinstance(linked_raw, list) else []
        seen.add(status_id)
        posts.append(
            XWatchlistPost(
                id=status_id,
                author_handle=canonical_author,
                publication_time=published,
                post_text=text,
                post_url=f"https://x.com/{canonical_author}/status/{status_id}",
                linked_urls=linked_urls,
            )
        )

    posts.sort(key=lambda item: item.publication_time, reverse=True)
    diagnostic = XWatchlistRetrievalDiagnostic(
        ok=True,
        allowed_handles=source_set.handles,
        returned_count=len(raw_posts),
        validated_count=len(posts),
        rejected_invalid_author=invalid_author,
        rejected_invalid_url=invalid_url,
        rejected_invalid_timestamp=invalid_timestamp,
        rejected_outside_window=outside,
        rejected_missing_citation=missing_citation,
        duplicate_count=duplicates,
        search_call_count=len(queries),
        search_queries=queries,
        citation_count=len(citations),
    )
    trace = XWatchlistModelTrace(
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
        x_search_call_count=len(queries),
        x_search_queries=queries,
        citation_urls=citations,
    )
    return posts, diagnostic, trace
