# Tasks: Rework verification — France yields + Germany-France spreads (root t_004d1769)

**Spec**: `specs/001-developer-t-876694f6/spec.md`
**Plan**: `specs/001-developer-t-876694f6/plan.md`

## Phase 1: Verification (architect, this root)

- [x] T001 (P1) Review commit 226b348 on `conrad/developer-t_004d1769`;
      confirm each of the three test fixes matches the recorded rework
      corrections and FR-002/FR-004/FR-006 (VR-001). — DONE
- [x] T002 (P1) Run the full suite in the t_004d1769 worktree
      (`.venv/bin/python -m pytest tests/`); expect 244 passed, 0 failed,
      tests-only diff (VR-002, SC-001, SC-002). — DONE

## Phase 2: Downstream (parent root t_004d1769)

- Delivery/verify/docs stages of root t_004d1769 proceed on its own cards;
  no new implementation tasks under this root.
