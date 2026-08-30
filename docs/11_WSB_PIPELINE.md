# WallStreetBets market-relevance pipeline

DailyDash treats r/wallstreetbets primarily as an alternative market-signal source, with a deliberately narrow exception for exceptionally hot WSB topics.

## Product goal

Publish a thread when it satisfies at least one of three lanes:

1. **Broad-market signal** — the topic/event/thesis can plausibly affect indices, sectors, rates, volatility, liquidity, commodities, currencies, or the macro environment.
2. **Market-moving bet** — concentrated/crowded retail positioning has a plausible transmission path to a significant security, sector, volatility regime, or the wider market.
3. **Exceptionally hot WSB topic** — a rare thread with extreme age-adjusted activity and substantial absolute engagement may be surfaced even when it is semantically narrow. This is an explicit product exception, capped separately and never quota-filled.

Ordinary single-name speculation, memes, screenshots and portfolio updates do not qualify merely because they are popular. The extreme-activity lane exists for genuinely exceptional WSB phenomena, not the daily top post.

## Ranking architecture

```text
Reddit hot/rising/new/top-day/top-week
        ↓
paginate `new` across the configured schedule window
        ↓
URL deduplication + housekeeping-thread removal
        ↓
diversified candidate cap (heat / comments / recency)
        ↓
GPT-5.4-nano semantic classification in small batches
        ↓
semantic score = broad-market path OR positioning path
        ↓
85% semantic score + 15% bounded Reddit activity tie-breaker
        ↓
semantic eligibility floors      extreme-activity absolute floor
        ↓                              ↓
market-signal lane              max 1 extreme-only thread
        └──────────────┬───────────────┘
                       ↓
                0..10 selected threads
```

The model receives title + post text only. Reddit score/comment counts are deliberately withheld from the model so popularity cannot influence semantic classification. Engagement is added deterministically only after classification. It remains a bounded 15% tie-breaker for the market-signal lane. Separately, the explicit extreme-activity lane can admit at most one otherwise narrow thread when it clears configured absolute activity thresholds.

Current extreme-only thresholds are intentionally strict:

```text
heat >= 75
AND (score >= 2500 OR comments >= 300)
max extreme-only items = 1
```

Because these are absolute floors rather than a percentile/rank, no hot-topic item is produced when nothing is genuinely exceptional. A thread that is both market-relevant and extremely hot counts as a market-signal item and does not consume the extreme-only allowance.

The ranking prompt is a versioned asset at `assets/prompts/wsb-ranking/v2/`.

## Telegram presentation

The persisted artifact keeps semantic scores, eligibility flags and rationales for
auditability. Telegram does not expose those DailyDash-internal fields. The delivered
report contains only each selected Reddit thread title/link plus Reddit-native comment
and upvote counts. If nothing qualifies, the report sends a plain empty-state message
rather than exposing threshold or classifier terminology.

## Reddit Data API prerequisite

WSB retrieval is **OAuth-only**. DailyDash does not treat public JSON scraping or an RSS fallback as a production data source.

The `new` listing is cursor-paginated with Reddit's `after`/`count` listing protocol until the oldest fetched post reaches the configured window start, the listing is exhausted, or `retrieval.max_new_pages` is reached (currently 10 pages). This is important for fixed-window replay and for longer or unusually busy daily windows. `hot`, `rising`, `top_day`, and `top_week` remain one-page supplementary views; the paginated `new` listing provides chronological recall while the candidate cap keeps LLM cost bounded. The artifact records pages fetched per listing plus `window_complete`; if the configured page cap is reached before the window start, the retrieval diagnostic is marked incomplete rather than silently claiming full recall.

Reddit's current Responsible Builder Policy requires explicit approval before accessing Reddit data through the API. Reddit also describes its Data API as legacy for many external use cases and directs developers toward the Developer Platform where possible. If the DailyDash use case is not supported by the Developer Platform, request access from Reddit and do not try to bypass the approval requirement.

Official references:

- https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy
- https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki
- https://old.reddit.com/wiki/api

The runtime requires three values:

```text
DAILY_DASH_REDDIT_CLIENT_ID
DAILY_DASH_REDDIT_CLIENT_SECRET
DAILY_DASH_REDDIT_USER_AGENT
```

Use a unique, transparent User-Agent. A suitable shape is:

```text
script:daily-dash:1.0 (by /u/<reddit-username>)
```

Do not commit the client secret.

## Configure local access


The canonical local layout is:

```text
daily-dash-windmill-local/secrets/
├── openrouter_api_key
├── reddit_client_id
├── reddit_client_secret
└── reddit_user_agent
```

For the author's usual checkout layout, set the runtime directory explicitly:

```bash
export DAILY_DASH_WINDMILL_DIR=~/repos/daily-dash-windmill-local
```

From the repository root:

```bash
./scripts/configure-wsb-reddit.sh
```

The script:

1. reuses values already exported or stored in the local Windmill `secrets/` directory;
2. prompts for missing values, hiding the client-secret input;
3. writes one value per 0600 file (`reddit_client_id`, `reddit_client_secret`, `reddit_user_agent`);
4. requests an OAuth token and reads one WSB listing as a credential/access check;
5. does **not** call the model gateway.

To save values without making the validation request:

```bash
./scripts/configure-wsb-reddit.sh --no-check
```

The DailyDash root `.env` is not used for these credentials.

## Configure Windmill

If Markets/Yields/News persistence and Telegram delivery already work, do **not** rerun the base `configure-windmill-workspace.sh`; its data-repository and Telegram values are already present in Windmill. WSB only adds the three Reddit values below.

After local OAuth validation succeeds, upload the same values to the configured Windmill workspace:

```bash
./scripts/configure-wsb-reddit.sh --windmill
```

The script creates/updates:

```text
secret   f/daily_dash/reddit_client_id
secret   f/daily_dash/reddit_client_secret
variable f/daily_dash/reddit_user_agent
```

The WSB flow injects those values only into `run_wsb`; they are not stored in the checked-in flow definition or Docker Compose environment.

After changing the checked-in Windmill definitions, synchronize the workspace in the normal way:

```bash
./scripts/sync-windmill-workspace.sh
```

## Controlled local live test

Use the wrapper instead of invoking the Python module directly because the wrapper loads the one-value files from the local Windmill `secrets/` directory and verifies prerequisites first:

```bash
./scripts/run-wsb-live-test.sh \
  --window-start 2026-08-28T08:00:00+02:00 \
  --window-end 2026-08-29T08:00:00+02:00
```

Before the paid classifier call, the wrapper performs:

```text
./scripts/check.sh
Reddit OAuth access check
model-gateway /health check
```

The test artifact is written to `/tmp/daily-dash-wsb-test` by default. Override it with `DAILY_DASH_WSB_TEST_DATA_REPO` if needed.

The local gateway defaults to `http://127.0.0.1:18080`; override it through `DAILY_DASH_MODEL_GATEWAY_URL`.

## Failure interpretation

### Missing Reddit configuration

```text
missing Reddit OAuth configuration
```

Run `DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/configure-wsb-reddit.sh` after obtaining approved API access.

### Reddit OAuth 401/403

Credentials are invalid, access is not approved for the app/use case, or Reddit has revoked/restricted the client. Do not fall back to scraping; resolve the API-access problem.

### Model gateway unavailable

Reddit retrieval can be healthy while the classifier gateway is down. Rebuild/start the local DailyDash Windmill stack and verify `http://127.0.0.1:18080/health`.

## Scheduling

Production schedule:

```text
Every day (Monday-Sunday) 20:35 Europe/Berlin
```

The old 20:30 slot was moved five minutes later to avoid the existing 20:30 workload. WSB now runs every day, including weekends. Retrieval is anchored to the current local daily cycle with a 60-minute overlap. A scheduled Saturday 20:35 run covers Friday 19:35 through Saturday 20:35 in Europe/Berlin. A manual run before the daily slot uses the same Friday 19:35 start but ends at the current time, so ad-hoc validation includes activity since the previous production slot instead of replaying Thursday→Friday. A manual run after 20:35 remains capped at the daily 20:35 cutoff. The overlap protects against scheduler jitter and late-arriving posts without creating a multi-day weekend gap.

## Persistence and delivery

```text
run_wsb → persist_data → deliver_wsb
```

Artifacts are written under `wsb/snapshots/` in the private data repository. Telegram delivery is downstream of durable persistence.
