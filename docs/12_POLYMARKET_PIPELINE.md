# Polymarket market-signals and hot-topics pipeline

DailyDash treats Polymarket as two related but independent products:

1. **Market Signals** — financially material prediction-market events ranked semantically by the LLM.
2. **Hot on Polymarket** — globally active events surfaced deterministically without an LLM, even when they are sports, entertainment or otherwise financially irrelevant.

This split keeps the financial ranking useful while still answering the separate question “what is unusually active on Polymarket right now?”

## Why the pipeline is event-level

The first migration ranked individual contracts. That created two problems in controlled live runs:

- one event such as a September FOMC decision could consume several candidates through +25, -25, +50 and no-change child contracts;
- 80 contract candidates produced roughly 50k model tokens and artifacts around 240-270 KB because every candidate description and evaluation was persisted.

The current design retrieves and ranks **Polymarket events**, not every child contract. One event may contain several child market questions, but it is one LLM candidate. Child questions are provided only to explain the event's outcome space.

## Public data sources

No Polymarket authentication is required.

```text
Gamma Events API: https://gamma-api.polymarket.com/events
Data Trades API:  https://data-api.polymarket.com/trades
```

The Gamma events endpoint supports tag filtering and returns nested markets, event-level 24-hour volume, liquidity, tags and comment counts. The Data API supports filtering trades by Polymarket event IDs.

API locations are configuration under `config/sources/polymarket.yaml` rather than inline code.

## Retrieval architecture

```text
                    Polymarket Gamma events
                             │
             ┌───────────────┴────────────────┐
             │                                │
     semantic tag queries             global volume query
 finance / crypto / politics /       top 100 active events
 geopolitics / economy / tech                 │
             │                                │
 round-robin event recall                     │
 max 30 unique events                 top 30 activity pool
             │                                │
             │                     event-scoped recent trades
             │                                │
             ▼                                ▼
       GPT-5.4-nano                    deterministic hotness
       event ranking                    no LLM call
             │                                │
       Market Signals                   Hot on Polymarket
```

The expensive semantic lane is capped at **30 events** rather than 80 individual contracts. Retrieval is diversified across configured relevant tags so the candidate pool is not simply the 30 highest-volume contracts on the whole platform.

The global hot lane considers the 30 highest-volume events from a 100-event global retrieval. Recent trades are requested only for those event IDs, in batches of 10 events with explicit 120-minute `start` / `end` bounds and 1,000-row pages. This replaces the old unfiltered 10,000-trade scan and avoids one oversized 30-event request.

## LLM ranking

The model receives only semantic event information:

```text
event title
event description
category
tags
provider event slug
up to 6 child market questions
resolution horizon
```

It deliberately does **not** receive:

```text
probabilities
outcome prices
24h volume
liquidity
comment count
recent trade count
1h / 1d price movement
```

The versioned prompt is:

```text
assets/prompts/polymarket-ranking/v6/
├── prompt.yaml
├── system.md
└── profiles/
    └── polymarket.md
```

The classifier returns:

```text
relevance            0..100
market_impact        0..100
market_breadth       0..100
prediction_signal    0..100
ranking_score        0..100
topic_key
theme
signal_type
rationale
```

`ranking_score` is the primary ordering signal for Market Signals. Platform activity does not contribute a percentage to this score.

`topic_key` remains useful even after moving to provider events because Polymarket can expose separate events that are still the same underlying economic thesis. Deadline-only variants such as Hormuz traffic normalization by August versus December should share one topic key; only the highest-ranked representative is published.

`theme` is a controlled broad report subject such as `monetary-policy`, `geopolitics-security`, or `energy-shipping`. Final selection allows at most **two signals per theme**, preventing six high-scoring Fed-path events from monopolizing a seven-item report while preserving LLM ranking order within each theme.

## Market-signal eligibility

The application applies explicit floors around the LLM result. A candidate must not be `narrow-or-irrelevant`, must clear the configured ranking/relevance/impact floors, and must have either sufficient breadth or prediction-signal value.

The report is not quota-filled. Fewer than seven signals is valid when fewer events deserve publication. Topic deduplication is applied first, followed by the configured maximum of two selected signals per broad theme.

## Global hotness lane

The hot section is intentionally independent of financial relevance and uses no LLM.

Activity score:

```text
40% normalized 24h volume
25% normalized recent trades
15% normalized cumulative comment count
12% normalized maximum absolute 1h child-market move
 8% normalized maximum absolute 1d child-market move
```

Comment count is a minority input because the public field is cumulative rather than a 24-hour comment count.

An event must have at least `$500,000` of 24-hour volume and satisfy at least one of:

```text
recent trades >= 100
comments >= 50
max |1h move| >= 5 percentage points
max |1d move| >= 10 percentage points
```

Up to three hot events are displayed. They can be sports or entertainment: the section explicitly means “Hot on Polymarket”, not “financial signal”.

## Telegram presentation

Telegram keeps the two product lanes but does not expose DailyDash ranking internals.
Market Signals show the event link plus Polymarket-native probability and 24-hour
volume when available. Hot events show the event link plus native activity context
(volume, recent trades, comments and one-hour price move). LLM selection scores,
impact/breadth/prediction scores, rationales and the deterministic `activity_score`
remain in the artifact only. Empty sections use plain user-facing messages.

## Compact immutable artifact

The production artifact is schema version 2 and is deliberately compact. It persists:

```text
schedule/window metadata
retrieval diagnostics
selected Market Signals with compact event metadata + full selected rationale
selected Hot events with compact activity metadata
compact score audit for at most 30 semantic candidates
model traces / token usage / cost
```

It does **not** persist full descriptions or child-market payloads for rejected candidates. A regression test requires a representative 30-candidate artifact to remain below **50 KB**.

This keeps the private `daily-dash-data` repository useful as an operational history instead of accumulating hundreds of kilobytes of redundant provider text per day.

## Scheduling

Production schedule:

```text
Every day (Monday-Sunday) 20:45 Europe/Berlin
```

The run artifact records the same current daily-cycle metadata used by WSB, including the previous daily slot, today's slot and the configured overlap. Polymarket's provider metrics remain live snapshot metrics rather than reconstructed historical values.

## Controlled live test

The public API validation is free and does not invoke the model:

```bash
uv run python -m daily_dash.commands.polymarket check-api \
  --config-dir config
```

For a controlled ranking test:

```bash
./scripts/run-polymarket-live-test.sh
```

The wrapper runs the repository gate, validates the public APIs, checks the local model gateway and writes only under:

```text
/tmp/daily-dash-polymarket-test/polymarket/snapshots/
```

No Telegram delivery or private-repository push occurs during the controlled local run.

## Windmill architecture

```text
run_polymarket
→ persist_data_repo
→ deliver_polymarket
```

Artifacts are written under:

```text
polymarket/snapshots/
```

The generic data-repository persistence step pushes the immutable compact artifact before Telegram can run. Polymarket needs no new secret or credential in Windmill; it reuses the existing model gateway, data-repository deploy key and Telegram configuration.
