# Implementation Plan: France yields and Germany-France spreads

**Feature Branch**: `001-developer-t-004d1769`
**Kanban root**: `t_004d1769` · Board: Conrad developer workflow

## Technical Context

- Language: Python 3.12 package (`src/daily_dash`), Pydantic contracts,
  httpx retrieval, pytest. No new dependencies.
- Report under change: yields (deterministic retrieval/processing report).
- Artifact: `YieldSnapshotDocument` schema 1, pipeline `yields` — unchanged.

## Architecture Summary (existing)

`retrieval/yields.py` fetches configured series from FRED, Bundesbank, or ECB
and parses CSV into `YieldObservation` lists. `processing/yields.py` computes
levels (latest + previous observation, change in bp) and spreads via
`_aligned_pairs` (shared-date intersection of the two series, newest first;
spread = left − right on shared dates only). `presentation/yields.py` renders
a Telegram Markdown report with fixed group/spread lists. Commands, pipeline
wiring, storage, and Windmill flows are series-count agnostic.

## Proposed Changes

1. `config/sources/yields.yaml`: add series `fr-2y` ("France 2Y") and
   `fr-10y` ("France 10Y") with `provider: cnbc`, keys `FR2Y` / `FR10Y`.
   `observation_limit: 12` is reused (CNBC supplies at most two observations
   per quote: latest + previous day close).
2. `retrieval/yields.py`: add a `cnbc` provider branch using the existing
   `httpx` client against
   `https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=<key>&requestMethod=itv&noform=1&partnerId=2&fund=1&output=json`
   (plain JSON, no authentication). Parse `last` (e.g. `"5.0223%"`),
   `previous_day_closing`, and `last_time` into two `YieldObservation`s:
   latest dated by the business-day-normalized `last_time` date, previous
   dated the previous business day (documented normalization; CNBC's quote
   cache can carry weekend timestamps). Strip `%` before float conversion.
   Existing fail-softly error convention applies. No new dependency.
3. `processing/yields.py`: extend `level_specs` with
   `("fr-2y", "France 2Y")`, `("fr-10y", "France 10Y")`; add spreads
   `fr-de-2y` ("France 2Y − Germany 2Y", left `fr-2y`, right `de-2y`) and
   `fr-de-10y` ("France 10Y − Germany 10Y", left `fr-10y`, right `de-10y`)
   with `signal_kind="neutral"` — left minus right ⇒ France minus Germany,
   positive = French yields higher. Existing shared-date alignment in
   `_aligned_pairs` guarantees no cross-date subtraction; change uses the two
   most recent shared dates.
4. `presentation/yields.py`: append a `("France", ("fr-2y", "fr-10y"))` level
   group and extend the Cross-market spreads block with
   `fr-de-2y`, `fr-de-10y` after the existing US − Germany rows.

No contract, command, storage, pipeline, or Windmill changes.

## Data Source Decision (live-verified 2026-10-25)

All candidate sources were verified live before this plan:

- **ECB YC** (`data-api.ecb.europa.eu/service/data/YC`): enumerated all 2,165
  series keys — zero with `FR` ref area; only euro-area aggregate curves.
  Confirmed unusable for French government bond yields.
- **Bundesbank BBSIS**: full series listing is German-securities only; no
  French series.
- **FRED**: only monthly OECD French long-term / 3-month rates
  (`IRLTLT01FRM156N`, `IR3TIB01FRM156N`); no daily 2Y/10Y French yields.
- **Stooq** (owner-suggested): the two bond symbols exist and are correct —
  browser-verified `10yfry.B` "France 10-Year Government Bond Yield" close
  5.017 (2026-10-23, 5,358 daily rows since 2005) and `2yfry.B` "France
  2-Year Government Bond Yield" close 3.795 (8,427 rows). However,
  programmatic access is NOT viable for the cron pipeline, verified live
  three ways: (1) the quote CSV `/q/l/` endpoint returns HTTP 404 ("page
  does not exist"); (2) the history CSV `/q/d/l/` returns `Access denied`
  for anonymous clients even after solving the site's SHA-256
  proof-of-work challenge and holding the issued `auth` cookie; (3) the
  HTML pages are gated behind that PoW plus a Google Funding-Choices
  JavaScript consent flow — a plain-Python fetch after PoW returns only
  consent scripts, no quote data. Rejected as the pipeline source.
- **TradingView tvDatafeed** (`tradingview-datafeed==2.1.1`, already a
  production dependency): symbols `TVC:FR02Y` / `TVC:FR10Y` exist (symbol
  search API confirms "France 2/10 Year Government Bonds Yield"), but an
  anonymous `TvDatafeed().get_hist("TVC", ...)` call live-tested from this
  host times out on the WebSocket connection ("Connection timed out → no
  data") for both symbols. No TV credentials are configured in this
  repository, so the existing futures access path cannot be relied on.
  The TradingView scanner API does not cover these bond symbols
  (`totalCount: 0`). Rejected as primary.
- **CNBC quote API (chosen primary)**:
  `https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=<key>&requestMethod=itv&noform=1&partnerId=2&fund=1&output=json`
  works from plain HTTP with no authentication. Verified live for both
  symbols: `FR2Y` = "France 2 Year Bond", last `3.8038%`,
  `previous_day_closing` present, `last_time` timestamp; `FR10Y` =
  "France 10 Year Bond", last `5.0223%`, `previous_day_closing` `5.0214%`,
  `last_time` — values consistent with the Stooq closes verified above
  (CNBC quotes are intraday snapshot yields, a few bp from Stooq's 17:58
  close; internally consistent per source). Provides exactly the two
  observations the report needs (latest + previous close). Also listed on
  cnbc.com/france-government-bonds/ (FR1Y…FR30Y all exist).
- **Rejected second-tier candidates** (live-tested): MarketWatch bond pages
  (HTTP 401), Investing.com API (HTTP 403), WSJ market-data page
  (JavaScript-rendered, no server-side table), Yahoo Finance (no French
  government bond yield symbols exist), Banque de France Webstat (no OAT
  dataset), ECB (euro-area aggregates only).

**Fallback order**: CNBC quote API (with the retriever's existing
fail-softly retry/error convention) → `—` with recorded data issue (existing
convention). After live-testing all candidates above, no second
unauthenticated source passes verification, so the "backup source" is the
documented graceful-degradation path: France levels and the two spreads show
`—` and the data-issues list records the failure, exactly like existing
series outages; the rest of the report is unaffected. German data stays on
Bundesbank BBSIS; spread dates align via shared-date intersection (existing
policy, FR-004), with CNBC observation dates business-day-normalized as
specified in FR-001 so weekday data aligns with the German series.

## Test Plan

Focused unit tests (offline fixtures):
- retrieval: CNBC JSON parsing — `last`/`previous_day_closing` percent-string
  conversion, `last_time` date extraction, weekend timestamp normalization to
  the previous business day, missing/invalid fields → fail-softly error
  series.
- processing: France levels from fixture snapshot; fr−de spreads signed
  correctly; date alignment uses shared dates only (different-date case
  produces spread on the shared date / `—` when no overlap); missing French
  data → `—` levels/spreads and recorded issue.
- presentation: France group lines and Cross-market rows with exact expected
  formatting; pre-existing lines unchanged.
- config: `tests/contract/test_config_tree.py` covers the config tree
  (existing tests must still pass with the two new series; the yield-series
  provider literal gains `cnbc`).

## Verification

Run: `pytest tests/unit/test_yield_processing.py tests/unit/test_yield_presentation.py tests/contract/test_config_tree.py tests/contract/test_yields_windmill_flow.py` plus the full test suite. One live check of the
CNBC quote API for `FR2Y` and `FR10Y` before delivery (HTTP 200, both
symbols return `last`, `previous_day_closing`, `last_time`).

## Risk / Rollback

Additive config + one new retrieval branch + deterministic lists; rollback is
reverting the four files. No artifact schema change, no delivery change.
Third-party risk: CNBC is a quote-cache API without a stability guarantee and
no verified second unauthenticated source exists — hence fail-softly
behavior with `—` placeholders and recorded data issues keeps the report
functional if CNBC misses a day.
