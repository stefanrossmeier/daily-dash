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
      CNBC quote JSON → observations parsing (percent-string conversion,
      `last_time` date extraction, weekend timestamp normalization to the
      previous business day, `previous_day_closing` dated the previous
      business day), missing/invalid fields → fail-softly error series with
      recorded issue. (P1)

## Stage: Developer (developer agent owns these)

- T003 Add `fr-2y` and `fr-10y` series to `config/sources/yields.yaml` with
      `provider: cnbc`, keys `FR2Y`/`FR10Y`; extend the yield-series provider
      literal in `src/daily_dash/config/models.py`; add the `cnbc` branch to
      `src/daily_dash/retrieval/yields.py` (plain-JSON quote API at
      `quote.cnbc.com/quote-html-webservice/restQuote`, no auth, httpx;
      business-day date normalization; fail-softly errors). Verify the
      endpoint with one live check. (P1)
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
      evidence, run speckit-converge; repeat the one live CNBC check.
      (P1)
- [ ] T009 Docs: assess cumulative diff; refresh archdoc only if
      interfaces/behavior changed (new provider branch is an interface
      change — record the assessment either way). (P2)

## Notes

- All tests offline; no network in CI-safe tests except the one-time CNBC
  endpoint verification during T003/T008.
- Data sources are already live-verified (plan.md): CNBC quote API is the
  sole verified source; Stooq and TradingView are rejected with recorded
  live evidence. Do not change the chosen source without architect rework.
- Do not modify other report profiles, Windmill flows, or artifact schemas.
