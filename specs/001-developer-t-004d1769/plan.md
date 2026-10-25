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
   `fr-10y` ("France 10Y") with `provider: ecb`, dataset `YC`, French
   government (OAT) curve keys. `observation_limit: 12` is reused.
2. `processing/yields.py`: extend `level_specs` with
   `("fr-2y", "France 2Y")`, `("fr-10y", "France 10Y")`; add spreads
   `fr-de-2y` ("France 2Y − Germany 2Y", left `fr-2y`, right `de-2y`) and
   `fr-de-10y` ("France 10Y − Germany 10Y", left `fr-10y`, right `de-10y`)
   with `signal_kind="neutral"` — left minus right ⇒ France minus Germany,
   positive = French yields higher. Existing shared-date alignment in
   `_aligned_pairs` guarantees no cross-date subtraction; change uses the two
   most recent shared dates.
3. `presentation/yields.py`: append a `("France", ("fr-2y", "fr-10y"))` level
   group and extend the Cross-market spreads block with
   `"fr-de-2y", "fr-de-10y"` after the existing US − Germany rows.

No contract, retrieval, command, storage, pipeline, or Windmill changes.

## Data Source Decision

ECB data portal (`data-api.ecb.europa.eu`) yield-curve dataset `YC` publishes
government benchmark yield curves per euro-area country, including France
(`B.FR...SR_2Y` / `SR_10Y`), via the already-supported `ecb` provider path in
`retrieval/yields.py` (SDMX CSV, `lastNObservations`). This reuses existing
provider code and conventions; Bundesbank BBSIS also carries French series
but FRED does not offer daily French bond yields. Exact series keys are
config-only and verified once with a live check during implementation;
documented as an assumption in spec.md.

## Test Plan

Focused unit tests (offline fixtures):
- processing: France levels from fixture snapshot; fr−de spreads signed
  correctly; date alignment uses shared dates only (different-date case
  produces spread on the shared date / `—` when no overlap); missing French
  data → `—` levels/spreads and recorded issue.
- presentation: France group lines and Cross-market rows with exact expected
  formatting; pre-existing lines unchanged.
- config: `tests/contract/test_config_tree.py` covers the config tree
  (existing tests must still pass with the two new series).

## Verification

Run: `pytest tests/unit/test_yield_processing.py tests/unit/test_yield_presentation.py tests/contract/test_config_tree.py tests/contract/test_yields_windmill_flow.py` plus the full test suite. Optional single live check of the
two ECB series URLs before delivery.

## Risk / Rollback

Purely additive config + deterministic lists; rollback is reverting the three
files. No artifact schema change, no delivery change.
