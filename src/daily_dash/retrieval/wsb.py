from __future__ import annotations

import hashlib
import html
import os
import re
from datetime import datetime

import httpx

from daily_dash.config.models import WsbSourceSet
from daily_dash.contracts.wsb import WsbPost, WsbRetrievalDiagnostic

_TIMEOUT_SECONDS = 20.0
_HOUSEKEEPING_RE = re.compile(
    r"(daily\s+discussion|what\s+are\s+your\s+moves|moves\s+tomorrow|"
    r"weekend\s+discussion|paper\s+trading|positions\s+or\s+ban|"
    r"mod\s+announcement|rules\s+update|ban\s+bet|unban)",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


class WsbRedditConfigurationError(RuntimeError):
    """Raised when approved Reddit Data API credentials are unavailable."""


def _post_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def _clean_title(value: str) -> str:
    return html.unescape(value or "").replace("[", "(").replace("]", ")").strip()


def _clean_text(value: str) -> str:
    plain = _TAG_RE.sub(" ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", plain).strip()


def _age_hours(created_at: datetime, retrieved_at: datetime) -> float:
    return max(0.25, (retrieved_at - created_at).total_seconds() / 3600.0)


def _heat(num_comments: int, score: int, created_at: datetime, retrieved_at: datetime) -> float:
    age_h = _age_hours(created_at, retrieved_at)
    return max(0.0, (num_comments / age_h) + (max(score, 0) / age_h) * 0.12)


def _listing_path(
    subreddit: str,
    listing: str,
    limit: int,
    *,
    after: str | None = None,
    count: int = 0,
) -> str:
    base = f"/r/{subreddit}"
    if listing == "top_day":
        path = f"{base}/top?t=day&limit={limit}&raw_json=1"
    elif listing == "top_week":
        path = f"{base}/top?t=week&limit={limit}&raw_json=1"
    else:
        path = f"{base}/{listing}?limit={limit}&raw_json=1"
    if after:
        path = f"{path}&after={after}&count={count}"
    return path


def _merge_post(pool: dict[str, WsbPost], post: WsbPost, source: str) -> None:
    previous = pool.get(post.url)
    if previous is None:
        post.listing_sources = [source]
        pool[post.url] = post
        return

    sources = list(dict.fromkeys([*previous.listing_sources, source]))
    if post.heat > previous.heat:
        post.listing_sources = sources
        pool[post.url] = post
    else:
        previous.listing_sources = sources


def _parse_listing(
    data: dict[str, object],
    *,
    source: str,
    window_start: datetime,
    window_end: datetime,
    retrieved_at: datetime,
    pool: dict[str, WsbPost],
) -> datetime | None:
    listing_data = data.get("data")
    if not isinstance(listing_data, dict):
        return None
    children = listing_data.get("children")
    if not isinstance(children, list):
        return None

    oldest_created_at: datetime | None = None
    for child in children:
        if not isinstance(child, dict):
            continue
        raw = child.get("data")
        if not isinstance(raw, dict):
            continue
        try:
            created_at = datetime.fromtimestamp(
                float(raw.get("created_utc") or 0.0), tz=window_start.tzinfo
            )
        except (TypeError, ValueError, OSError):
            continue
        if oldest_created_at is None or created_at < oldest_created_at:
            oldest_created_at = created_at
        if not window_start <= created_at < window_end:
            continue

        title = _clean_title(str(raw.get("title") or ""))
        if not title or _HOUSEKEEPING_RE.search(title):
            continue
        if raw.get("stickied") or raw.get("pinned") or raw.get("distinguished"):
            continue

        permalink = str(raw.get("permalink") or "")
        if not permalink:
            continue
        url = f"https://www.reddit.com{permalink}"
        num_comments = int(raw.get("num_comments") or 0)
        score = int(raw.get("score") or 0)
        text = _clean_text(str(raw.get("selftext") or ""))
        author_raw = raw.get("author")
        author = str(author_raw) if author_raw else None
        post = WsbPost(
            id=_post_id(url),
            title=title,
            text=text,
            url=url,
            author=author,
            created_at=created_at,
            num_comments=max(num_comments, 0),
            score=score,
            heat=_heat(num_comments, score, created_at, retrieved_at),
        )
        _merge_post(pool, post, source)

    return oldest_created_at


def _listing_item_count(data: dict[str, object]) -> int:
    listing_data = data.get("data")
    if not isinstance(listing_data, dict):
        return 0
    children = listing_data.get("children")
    return len(children) if isinstance(children, list) else 0


def _listing_after(data: dict[str, object]) -> str | None:
    listing_data = data.get("data")
    if not isinstance(listing_data, dict):
        return None
    raw_after = listing_data.get("after")
    if not raw_after:
        return None
    return str(raw_after)


def _reddit_settings() -> tuple[str, str, str]:
    client_id = os.getenv("DAILY_DASH_REDDIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("DAILY_DASH_REDDIT_CLIENT_SECRET", "").strip()
    user_agent = os.getenv("DAILY_DASH_REDDIT_USER_AGENT", "").strip()
    missing = [
        name
        for name, value in (
            ("DAILY_DASH_REDDIT_CLIENT_ID", client_id),
            ("DAILY_DASH_REDDIT_CLIENT_SECRET", client_secret),
            ("DAILY_DASH_REDDIT_USER_AGENT", user_agent),
        )
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        raise WsbRedditConfigurationError(
            f"missing Reddit OAuth configuration: {joined}. "
            "Run ./scripts/configure-wsb-reddit.sh after obtaining approved Reddit Data API access."
        )
    return client_id, client_secret, user_agent


def _oauth_token(
    client: httpx.Client,
    *,
    client_id: str,
    client_secret: str,
    user_agent: str,
) -> str:
    response = client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={"User-Agent": user_agent},
    )
    response.raise_for_status()
    raw = response.json()
    token = raw.get("access_token") if isinstance(raw, dict) else None
    if not token:
        raise RuntimeError("Reddit OAuth response did not contain an access token")
    return str(token)


def check_wsb_reddit_access(source_set: WsbSourceSet) -> int:
    """Validate approved OAuth credentials without invoking the model gateway."""

    client_id, client_secret, user_agent = _reddit_settings()
    with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=True) as client:
        token = _oauth_token(
            client,
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        path = _listing_path(source_set.subreddit, "hot", 1)
        response = client.get(
            f"https://oauth.reddit.com{path}",
            headers={"User-Agent": user_agent, "Authorization": f"bearer {token}"},
        )
        response.raise_for_status()
        raw = response.json()
    if not isinstance(raw, dict):
        raise RuntimeError("Reddit listing response was not a JSON object")
    listing_data = raw.get("data")
    if not isinstance(listing_data, dict) or not isinstance(listing_data.get("children"), list):
        raise RuntimeError("Reddit listing response did not contain listing children")
    return len(listing_data["children"])


def retrieve_wsb_posts(
    source_set: WsbSourceSet,
    *,
    listing_limit: int,
    max_new_pages: int,
    window_start: datetime,
    window_end: datetime,
    retrieved_at: datetime,
) -> tuple[list[WsbPost], list[WsbRetrievalDiagnostic]]:
    """Retrieve WSB through approved Reddit OAuth access only."""

    try:
        client_id, client_secret, user_agent = _reddit_settings()
    except WsbRedditConfigurationError as exc:
        return [], [WsbRetrievalDiagnostic(mode="oauth", ok=False, item_count=0, error=str(exc))]

    pool: dict[str, WsbPost] = {}
    listing_pages: dict[str, int] = {}
    window_complete = True
    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=True) as client:
            token = _oauth_token(
                client,
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            for listing in source_set.listings:
                after: str | None = None
                seen_count = 0
                page_limit = max_new_pages if listing == "new" else 1
                listing_pages[listing] = 0
                for page_index in range(page_limit):
                    path = _listing_path(
                        source_set.subreddit,
                        listing,
                        listing_limit,
                        after=after,
                        count=seen_count,
                    )
                    response = client.get(
                        f"https://oauth.reddit.com{path}",
                        headers={
                            "User-Agent": user_agent,
                            "Authorization": f"bearer {token}",
                        },
                    )
                    response.raise_for_status()
                    listing_pages[listing] += 1
                    raw = response.json()
                    if not isinstance(raw, dict):
                        break
                    oldest_created_at = _parse_listing(
                        raw,
                        source=listing,
                        window_start=window_start,
                        window_end=window_end,
                        retrieved_at=retrieved_at,
                        pool=pool,
                    )
                    if listing != "new":
                        break
                    if oldest_created_at is not None and oldest_created_at <= window_start:
                        break
                    seen_count += _listing_item_count(raw)
                    after = _listing_after(raw)
                    if not after:
                        break
                    if page_index + 1 >= page_limit:
                        window_complete = False
    except Exception as exc:
        return [], [
            WsbRetrievalDiagnostic(
                mode="oauth",
                ok=False,
                item_count=0,
                error=f"{type(exc).__name__}: {exc}",
            )
        ]

    rows = sorted(
        pool.values(),
        key=lambda post: (post.heat, post.num_comments, post.score, post.created_at),
        reverse=True,
    )
    diagnostic_error = None
    if not window_complete:
        diagnostic_error = (
            "new listing reached max_new_pages before the configured window start; "
            "chronological recall may be incomplete"
        )
    return rows, [
        WsbRetrievalDiagnostic(
            mode="oauth",
            ok=bool(rows) and window_complete,
            item_count=len(rows),
            listing_pages=listing_pages,
            window_complete=window_complete,
            error=diagnostic_error,
        )
    ]
