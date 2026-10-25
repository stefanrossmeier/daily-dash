# Feature Specification: Rework verification — France yields + Germany-France spreads (root t_004d1769)

**Feature Branch**: `conrad/developer-t_876694f6`

**Created**: 2026-10-25

**Status**: Draft

**Input**: Verify spec conformance and full suite after test fixes for root t_004d1769 (France yields + Germany-France spreads in daily-dash Yield Report).

## Context

Root t_004d1769 implemented the France 2Y/10Y yields and France−Germany
spread feature (developer commit 9ff6054). Its test-stage rework identified
three defective tests; the fixes were applied in commit 226b348 on
`conrad/developer-t_004d1769`. This root exists solely to verify those test
fixes against the spec and the full suite. No new product behavior is
introduced by this root.

## User Scenarios & Testing

### User Story 1 — Test fixes conform to the feature spec (P1)

The three previously defective tests are corrected without weakening the
FR-004 date-alignment guarantee, without bypassing the France group required
by FR-002/FR-003, and without losing the FR-006 neutral-signal coverage.

**Independent Test**: Inspect commit 226b348 and run the full suite in the
t_004d1769 worktree.

**Acceptance Scenarios**:

1. **Given** the rework corrections for root t_004d1769, **When** commit
   226b348 is reviewed, **Then** each fix matches its prescribed correction
   and the corresponding FR (FR-002, FR-004, FR-006).
2. **Given** the t_004d1769 worktree at commit 226b348, **When** the full
   suite runs, **Then** all tests pass (no production code changed).

## Requirements *(mandatory)*

### Functional Requirements

- **VR-001**: Each test fix in commit 226b348 MUST match the rework
  corrections recorded on root t_004d1769 and remain consistent with
  FR-002/FR-004/FR-006 of `specs/001-developer-t-004d1769/spec.md`.
- **VR-002**: The full suite in the t_004d1769 worktree MUST pass with zero
  failures after the test fixes, with production code untouched
  (tests-only diff).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/` in the t_004d1769 worktree reports 244 passed,
  0 failed.
- **SC-002**: The fix commit's diff touches only `tests/unit/test_yield_*`
  files.

## Assumptions

- The feature work itself lives on `conrad/developer-t_004d1769`; this root
  owns no implementation code.
- The unrelated pre-existing `test_markets_pipeline` flake noted in the
  prior corrections is included in the suite result.

## Traceability

Kanban task: `t_3f5adcf3` (Conrad developer board). Workflow root: `t_876694f6`.
