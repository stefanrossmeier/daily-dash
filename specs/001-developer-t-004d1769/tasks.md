# Tasks: France yields and Germany-France spreads

**Feature Branch**: `001-developer-t-004d1769` · Kanban root `t_004d1769`

## Stage: Test (test agent owns these first)

- [ ] T001 Write failing unit tests in `tests/unit/test_yield_processing.py`:
      France levels (fr-2y/fr-10y latest + change bp), fr−de spread sign and
      value on shared dates, shared-date alignment (no cross-date
      subtraction; `—` when no overlap), missing French series → `—` +
      issue recorded. (P1)
- [ ] T002 Write failing unit tests in `tests/unit/test_yield_presentation.py`:
      France Levels group lines and the two new Cross-market spread rows with
      exact formatting; assert all pre-existing lines unchanged. (P1)
- [ ] T002b Write failing unit tests for the France retrieval layer:
      TradingView bars → observations parsing, Stooq HTML-table fallback
      parsing (invalid closes skipped), fallback order (TradingView failure →
      Stooq used; both fail → error series with recorded issue). (P1)

## Stage: Developer (developer agent owns these)

- T003 Add `fr-2y` and `fr-10y` series to `config/sources/yields.yaml` with
      `provider: tradingview`, keys `FR02Y`/`FR10Y` (exchange `TVC`); extend
      the yield-series provider literal in `src/daily_dash/config/models.py`;
      add the `tradingview` branch to `src/daily_dash/retrieval/yields.py`
      reusing tvDatafeed, with Stooq daily-history HTML fallback
      (`10yfry.b`/`2yfry.b`). Verify the TVC symbols with one live check.
      (P1)
- [ ] T004 Extend `processing/yields.py`: add France levels to `level_specs`
      and `fr-de-2y`/`fr-de-10y` spreads (France − Germany, neutral signal).
      (P1)
- [ ] T005 Extend `presentation/yields.py`: France group in Levels and the
      two spread rows in Cross-market spreads. (P1)
- [ ] T006 Make T001/T002 tests pass; run the full test suite offline.
- [ ] T007 Commit; verify existing report content preserved (golden fixture
      rendering unchanged apart from new lines).

## Stage: Verification / Delivery

- [ ] T008 Independent verification: rerun suite, map acceptance criteria to
      evidence, run speckit-converge. (P1)
- [ ] T009 Docs: assess cumulative diff; refresh archdoc only if
      interfaces/behavior changed (config-only addition likely a no-op for
      archdoc; record the assessment). (P2)

## Notes

- All tests offline; no network in CI-safe tests except the one-time TVC
  symbol verification during T003.
- Data sources are already live-verified (plan.md); do not change the chosen
  fallback order without architect rework.
- Do not modify other report profiles, Windmill flows, or artifact schemas.
