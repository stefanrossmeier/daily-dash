# X Watchlist Pipeline

## Purpose

The X Watchlist is a twice-daily market/macro digest built from a fixed curated source set:

- `KobeissiLetter`
- `AndreasSteno`
- `markoinny`
- `NickTimiraos`
- `DeItaone`
- `elerianm`

There is no browser automation, X login, cookie state, Playwright profile, or direct X credential. Grok accesses X through OpenRouter, and only the DailyDash model gateway owns the OpenRouter root credential.

## Production flow

```text
Windmill schedule
  -> run_x_watchlist
       -> one Grok-native X retrieval request for all six allowed handles
       -> validate author/status URL/citation/timestamp
       -> exact scheduled-window filtering
       -> bounded semantic ranking through rank-cheap
       -> immutable JSON artifact
  -> persist_data_repo
  -> deliver_x_watchlist
```

Persistence completes before Telegram delivery.

## Retrieval

The source set is checked in at `config/sources/x-watchlist.yaml`. The production retrieval prompt is versioned at `assets/prompts/x-watchlist-retrieval/v3/`.

The application sends all six handles in one gateway request. The gateway resolves alias `x-retrieve` to the configured Grok model and injects native X search plus the handle/date restrictions. Application code cannot access the OpenRouter root key.

The X API/search date filter is deliberately treated as a coarse retrieval envelope. Only the local calendar dates that cover the exact scheduled interval are sent upstream; the retrieval prompt asks Grok to start with those bounded searches rather than first repeating unbounded account searches. The application parses every returned timestamp and accepts only posts in the exact half-open scheduled interval:

```text
[previous scheduled slot, current scheduled slot)
```

Returned posts are also rejected when:

- the author is outside the configured watchlist;
- the status URL is not a canonical `x.com/<handle>/status/<id>` URL;
- the URL handle disagrees with the returned author;
- the timestamp cannot be parsed;
- citation evidence does not contain the same X status ID;
- the status ID is duplicated.

Retrieval does not use likes, repost counts, views, follower counts, or other engagement data.

## Ranking

Ranking is separate from Grok retrieval. The current profile uses the existing `rank-cheap` gateway alias and the versioned `x-watchlist-ranking/v3` prompt.

Every candidate receives four 0-100 semantic judgments:

- relevance;
- market impact;
- market breadth;
- information value.

It also receives category, urgency, `topic_key`, and a short rationale. A deliberately relaxed deterministic semantic score and minimum thresholds decide eligibility. The production thresholds favor recall because the delivered report is a reading list: potentially useful distinct topics should survive even when their immediate market impact is modest. Topic caps prevent the report from being filled by near-duplicate posts about one underlying development. The production cap is one published post per underlying event/topic. There is no quota: the report is `0..N` up to the configured maximum.

Ranking fields remain in the persisted artifact for auditability, but Telegram deliberately does not expose scores, categories, urgency, or rationales. The delivered report contains the selected account/timestamp, original X post text, and source link only. Selected post text is not clipped by the presenter; Telegram-safe delivery splitting handles message-size limits.

## Artifact and model accounting

Artifacts are written under:

```text
x-watchlist/snapshots/
```

They contain the validated candidate posts, evaluations, selected IDs, retrieval diagnostics, prompt hashes, resolved models, tokens, exact OpenRouter cost, latency, attempts, X-search query count, search queries, and X citation URLs.

The model gateway deliberately strips opaque provider reasoning/encrypted blobs before returning metadata to application code. Search-query/citation evidence is retained; giant raw provider payloads are not.

## Schedule

`config/schedules.yaml` is authoritative:

```text
08:20 Europe/Berlin
20:20 Europe/Berlin
```

every day. Windmill schedule files are generated from that registry.

## Local acceptance

After applying a change:

```bash
./scripts/format.sh
git diff --check
./scripts/check.sh
./scripts/local-windmill.sh rebuild
./scripts/local-windmill.sh health
./scripts/sync-windmill-workspace.sh
```

Then exercise the real persistence and Telegram path through Windmill:

```bash
cd workflows/windmill
../../scripts/wmill.sh flow run f/daily_dash/x_watchlist
```

This executes the same production ordering used by the schedules:

```text
run -> persist -> deliver
```

For deterministic replays without Windmill, the application command accepts explicit timezone-aware `--window-start` and `--window-end` values, but that path only writes an artifact and does not publish it.
