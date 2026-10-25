# Plan: Rework verification — France yields + Germany-France spreads (root t_004d1769)

**Feature Branch**: `conrad/developer-t_876694f6`
**Spec**: `specs/001-developer-t-876694f6/spec.md`
**Source Revision**: base 2050fba7728a5b2d570e3b3b0c235f7aea40f169 (planning performed at commit f88b4c4, 2026-10-25)

## Technical Context

- Repository `stefanrossmeier/daily-dash`; this root performs verification
  only, no product code changes. Feature work under verification lives on
  `conrad/developer-t_004d1769` (commits 9ff6054, 226b348).
- The feature under review is specified in
  `specs/001-developer-t-004d1769/spec.md` (FR-001..FR-007): CNBC quote API
  retriever for FR2Y/FR10Y, France levels group, France−Germany spreads,
  FR-004 shared-date alignment, additive-only changes, neutral signals,
  focused unit tests.

## Constitution Check

- Verify-only root; no new runtime components, no new external data sources,
  no schema changes. Additive test-only fixes on the parent root. Gate: PASS.

## Architecture Summary

- No architecture change. The only reviewed artifact is the test diff in
  commit 226b348 (`tests/unit/test_yield_processing.py`,
  `tests/unit/test_yield_processing.py` presentation module) against the
  existing yield processing/presentation modules and
  `config/sources/yields.yaml`.

## Data Sources

- No new data sources introduced by this root. The feature's sources were
  live-verified by the architect on root t_004d1769 (CNBC quote API chosen;
  Stooq/TradingView/ECB/Bundesbank/FRED ruled out with evidence).

## Decisions

- D1: Fix (1) supplies a synthetic fr-2y 08-27 observation so the +5 bp
  change comes from two shared dates — preserves FR-004's no-cross-date
  rule.
- D2: Fix (2) populates France level rows and fr-de spread placeholders in
  the fixture rather than weakening `render_yield_report`.
- D3: Fix (3) asserts the neutral marker per France spread row instead of a
  whole-block count, keeping FR-006 coverage discriminating.

## Verification Approach

- Read commit 226b348 diff; map each fix to the recorded corrections.
- Run the full suite in the t_004d1769 worktree (`pytest tests/`).
