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
   `fr-10y` ("France 10Y") with `provider: tradingview`, keys `FR02Y` /
   `FR10Y` (exchange `TVC`). `observation_limit: 12` is reused.
2. `retrieval/yields.py`: add a `tradingview` provider branch reusing the
   installed tvDatafeed client (same dependency as
   `retrieval/futures/tradingview.py`), fetching daily bars and converting
   closes to `YieldObservation`; on failure/stale data fall back to the
   Stooq daily-history page for `10yfry.b` / `2yfry.b` (HTML table parse;
   close column). Existing fail-softly error convention applies to both.
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
- **Stooq**: CSV export endpoints `/q/d/l/` and `/q/l/` return the PoW
  challenge and `Access denied` from this host (curl and browser); the
  daily-history HTML page IS accessible and verified:
  `10yfry.b` (France 10Y) 5,358 daily rows, latest 23 Oct 2026 close 5.017;
  `2yfry.b` (France 2Y) 8,427 rows, latest close 3.795. Weekday-only.
- **TradingView (chosen primary)**: `TVC:FR02Y` / `TVC:FR10Y` symbol pages
  exist, and the public scanner API returns live values
  (`FR02Y` 3.7942, `FR10Y` 5.0188, update 23 Oct 2026) consistent with the
  Stooq closes. tvDatafeed is already a production dependency (futures
  pipeline) and supplies daily history depth.

**Fallback order**: TradingView `TVC:FR02Y`/`TVC:FR10Y` → Stooq daily-history
HTML page `2yfry.b`/`10yfry.b` → fail-softly `—` with recorded data issue
(existing convention). If both sources miss a day, France shows stale/`—`
per existing missing-and-stale-data conventions; spreads drop to the latest
shared date or `—`. German data stays on Bundesbank BBSIS; spread dates
align via shared-date intersection (existing policy, FR-004).

## Test Plan

Focused unit tests (offline fixtures):
- retrieval: TradingView daily bars → `YieldObservation` parsing; Stooq
  HTML-table fallback parsing (including invalid/skipped closes); fallback
  order (TradingView failure → Stooq data used; both fail → error series).
- processing: France levels from fixture snapshot; fr−de spreads signed
  correctly; date alignment uses shared dates only (different-date case
  produces spread on the shared date / `—` when no overlap); missing French
  data → `—` levels/spreads and recorded issue.
- presentation: France group lines and Cross-market rows with exact expected
  formatting; pre-existing lines unchanged.
- config: `tests/contract/test_config_tree.py` covers the config tree
  (existing tests must still pass with the two new series; the yield-series
  provider literal gains `tradingview`).

## Verification

Run: `pytest tests/unit/test_yield_processing.py tests/unit/test_yield_presentation.py tests/contract/test_config_tree.py tests/contract/test_yields_windmill_flow.py` plus the full test suite. Optional single live check of the
two TradingView symbols before delivery.

## Risk / Rollback

Additive config + one new retrieval branch + deterministic lists; rollback is
reverting the four files. No artifact schema change, no delivery change.
Third-party risk: Stooq may throttle or deny access (verified from this
host) and tvDatafeed is an unofficial client — hence the two-source fallback
order and fail-softly behavior.
