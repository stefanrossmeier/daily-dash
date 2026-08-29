# Grok Native X Search Compatibility Spike

This experiment tests whether DailyDash can replace browser-based X/Twitter acquisition with Grok's native X access through OpenRouter.

It is intentionally **not** a production pipeline. It does not create Windmill schedules, persist to `daily-dash-data`, or send Telegram messages.

## Security boundary

The experiment does **not** read `OPENROUTER_API_KEY`, the local OpenRouter secret file, or call OpenRouter directly.

The request path is:

```text
experiment
→ DailyDash model gateway
→ OpenRouter Responses API
→ Grok native X search
```

Only the model gateway owns the OpenRouter root credential. The application sends a constrained X-search contract containing the prompt, allowed handle, date range, and response schema. The gateway injects the provider-specific native-search configuration.

The dedicated gateway alias is:

```text
x-retrieve → x-ai/grok-4.3
```

Only aliases configured with `allow_x_search: true` may call the gateway's `/v1/x-search` endpoint. Normal ranking aliases cannot enable X search.

## Scope

The gateway currently translates the constrained request into OpenRouter's Responses API shape using:

- `x-ai/grok-4.3` through the `x-retrieve` alias;
- the `web` plugin with `engine: native`;
- top-level `x_search_filter.allowed_x_handles`;
- `from_date` and `to_date` filters;
- reasoning disabled;
- one account at a time.

The allowed experiment watchlist is:

```text
KobeissiLetter
AndreasSteno
markoinny
NickTimiraos
DeItaone
elerianm
```

`KimDotcom` is intentionally excluded from this experiment.

## Deterministic test first

Inspect the exact request that the application will send to the local model gateway without making a paid call:

```bash
uv run python -m daily_dash.experiments.grok_x_search --dry-run
```

An explicit account and date range can be supplied:

```bash
uv run python -m daily_dash.experiments.grok_x_search --handle NickTimiraos --from-date 2026-08-28 --to-date 2026-08-29 --dry-run
```

The dry-run payload intentionally does not contain an upstream model id, OpenRouter plugin configuration, or OpenRouter credential. Those are gateway concerns.

## Controlled live call

The local model gateway must be running with the current repository image/configuration. After changing the gateway, rebuild and health-check it using the normal local Windmill helper before the live request.

The runner executes the repository gate before making the paid request:

```bash
./scripts/run-grok-x-search-spike.sh --handle NickTimiraos --from-date 2026-08-28 --to-date 2026-08-29
```

The command prints the artifact path. By default the artifact is written below `/tmp` and is never delivered or persisted to the data repository.

## What the artifact captures

The artifact deliberately retains enough information to evaluate compatibility before production code is designed:

- gateway alias and resolved provider/model;
- sanitized gateway request;
- account and date filters;
- prompt id/version/profile and hashes;
- structured returned posts;
- token usage and reported cost;
- gateway attempts and latency;
- provider diagnostics returned by the gateway, including available X/web-search metadata.

The OpenRouter API key and authorization header never enter the experiment process or artifact.

## Acceptance questions

Inspect the live artifact before implementing a production X pipeline:

1. Did native X search actually run?
2. Are all returned posts authored by the requested handle?
3. Are trustworthy `x.com/.../status/...` URLs returned?
4. Are dates/timestamps usable enough to validate a scheduled reporting window?
5. Does the result include all or nearly all posts visible for the account in the requested period?
6. Are replies/reposts/quote posts distinguishable enough to enforce the desired policy?
7. Does OpenRouter expose reliable token, cost, routing, and search/plugin metadata through the gateway?
8. Is Grok 4.3 sufficient for the retrieval task?

Do not add Windmill scheduling, durable persistence, ranking, or Telegram delivery until these questions are answered from controlled live results.


## Outcome

The compatibility spike succeeded with Grok 4.3 through the secured model gateway. It demonstrated native X searches, structured post output, canonical X status citations, and exact OpenRouter usage/cost reporting. The production implementation is documented in `docs/14_X_WATCHLIST_PIPELINE.md`; the spike remains as a diagnostic tool rather than a scheduled pipeline.
