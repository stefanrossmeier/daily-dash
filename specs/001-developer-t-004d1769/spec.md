# Feature Specification: France government bond yields and Germany-France spreads in the Yield Report

**Feature Branch**: `001-developer-t-004d1769`

**Created**: 2026-10-25

**Status**: Draft

**Input**: User description: "Extend the Yield Report with French government bond yields and Germany-France spreads: add France 2Y and France 10Y to Levels (yield, change from previous observation in basis points, observation date, existing formatting); add 'France 2Y - Germany 2Y' and 'France 10Y - Germany 10Y' to Cross-market spreads, France minus Germany (positive = French yields higher); spread levels in percentage points, changes in basis points, observation dates; follow existing conventions for data sources, precision, indicators, missing/stale data; prefer existing providers; align observation dates when calculating spreads and never silently subtract yields from different dates; preserve all existing report content and behavior; add focused tests."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - France yields in Levels (Priority: P1)

A reader of the daily Yield Report sees, inside the existing Levels section, a
new "France" group listing France 2Y and France 10Y, each with the latest
yield, the change from the previous observation in basis points, and the
observation date, formatted exactly like the existing US/Germany/Euro groups.

**Why this priority**: Without retrieved French yields, no France spread can
exist; this is the data foundation and independently shows French levels.

**Independent Test**: Given a raw snapshot fixture with French observations,
processing produces `fr-2y`/`fr-10y` levels, and the rendered report contains
the France group lines with correct formats.

**Acceptance Scenarios**:

1. **Given** a raw snapshot with two French observations, **When** the yield
   pipeline processes it, **Then** the Levels section contains France 2Y and
   France 10Y lines with yield `X.XX%`, change `±N bp`, and ISO date.
2. **Given** a French series with no observations (source error), **When**
   processed, **Then** the France level lines show `—` placeholders and the
   issue is recorded in the data-issues list.

---

### User Story 2 - Germany-France spreads in Cross-market spreads (Priority: P1)

The Cross-market spreads section gains "France 2Y − Germany 2Y" and
"France 10Y − Germany 10Y": France minus Germany, so positive means French
yields are higher. Levels in percentage points, changes in basis points,
observation date — matching the existing cross-market rows (US − Germany).

**Why this priority**: This is the headline deliverable requested by the user.

**Independent Test**: Given fixtures with French and German observations,
processing produces date-aligned spreads with correct signed values and the
rendered Cross-market block contains the two new rows.

**Acceptance Scenarios**:

1. **Given** French 2Y at 3.20% and German 2Y at 2.10% on the same date,
   **When** processed, **Then** the "France 2Y − Germany 2Y" spread is
   `+1.10 pp` and positive indicates higher French yields.
2. **Given** French and German observations on non-matching dates,
   **When** processed, **Then** only observations on shared dates are used
   and the reported date is the shared (French latest matched) date; no
   spread is computed from different dates.

---

### User Story 3 - Existing report unchanged (Priority: P2)

All existing content — US/Germany/Euro AAA/all-ratings levels, the nine
existing spreads, curve regime, and data-issues behavior — renders exactly as
before; the change is purely additive.

**Why this priority**: Preserves reader trust and existing behavior.

**Independent Test**: Rendering a pre-change fixture produces identical
content for every pre-existing line.

**Acceptance Scenarios**:

1. **Given** an existing full-coverage fixture, **When** rendered, **Then**
   every pre-existing line is unchanged and only France lines are appended.

### Edge Cases

- French series returns an error or is empty → level shows `—`, spread shows
  `—`, a data issue is recorded; the report still delivers.
- French and German latest observations fall on different dates → spread uses
  the latest shared date only; if no shared date exists, spread is `—` with
  no date (existing alignment policy).
- French observation dates differ in cadence from German → shared-date
  alignment handles it; no extrapolation or interpolation.
- Spread change computed from the two most recent shared dates; if only one
  shared date exists, change is `—`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The yields source set MUST add France 2Y and France 10Y series
  using an existing provider that publishes French government bond yields
  (the ECB yield-curve dataset already used for Euro AAA series; series keys
  are configuration in `config/sources/yields.yaml`).
- **FR-002**: The Levels section MUST include a France group with France 2Y
  and France 10Y using the existing level format (yield `%.2f%`, change
  `±N bp`, ISO observation date) and existing missing-data `—` convention.
- **FR-003**: The Cross-market spreads section MUST include
  "France 2Y − Germany 2Y" and "France 10Y − Germany 10Y", computed as
  France minus Germany, in percentage points, with change in basis points and
  the aligned observation date.
- **FR-004**: Spread calculations MUST align observations by date and MUST
  never subtract yields from different observation dates; they reuse the
  existing shared-date alignment policy.
- **FR-005**: All existing report content and behavior MUST be preserved
  (additive-only change); artifact `schema_version` stays 1 and pipeline
  stays `yields`.
- **FR-006**: New spreads carry the `neutral` signal indicator (no France
  spread threshold policy exists yet), consistent with existing
  signal-neutral spreads such as the Euro rating spread.
- **FR-007**: New series/spreads MUST have focused unit tests covering
  retrieval parsing of French series data, level computation, date-aligned
  spread computation, and presentation formatting.

### Key Entities *(include if feature involves data)*

- **YieldLevel** (existing): one series' latest value, change, date — reused
  for France 2Y/10Y with new series ids `fr-2y`, `fr-10y`.
- **YieldSpread** (existing): date-aligned spread between two series — reused
  for `fr-de-2y`, `fr-de-10y` with left = France, right = Germany.
- **YieldSourceSet config** (existing): gains two series entries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A rendered Yield Report from a full-coverage fixture contains
  the France Levels group and both Germany-France spread rows with correct
  values, signs, and dates.
- **SC-002**: Every focused new test passes offline and all pre-existing
  yields tests still pass.
- **SC-003**: With a French source failure, the report still renders with `—`
  placeholders and a recorded issue (fail-softly behavior preserved).

## Assumptions

- The ECB yield-curve dataset (`provider: ecb`, dataset `YC`) publishes
  daily French government bond (OAT) yields under French-country keys; exact
  keys are verified during implementation and live-checked once.
- France spread thresholds for color indicators are out of scope; `neutral`
  is used.
- Windmill flow wiring needs no change: the yields flow is source-set driven.
- No new dependencies.

## Traceability

Kanban task: `t_004d1769` (Conrad developer board).