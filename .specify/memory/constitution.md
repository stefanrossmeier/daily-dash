# DailyDash Constitution

## Core Principles

### I. Layered Pipeline Boundaries (NON-NEGOTIABLE)
Every report pipeline is `retrieval -> processing -> storage/presentation -> delivery`.
Layers depend only inward; `retrieval` must not import processing/storage, and
`presentation` stays pure (no I/O). Enforced by
`tests/contract/test_architecture_boundaries.py`.

### II. Typed Contracts and Versioned Artifacts
All persisted documents are strict Pydantic models with `schema_version` and a
pipeline discriminator; artifacts are immutable and writers raise
`FileExistsError` rather than overwrite. Historical artifact meaning is never
silently repurposed; changes introduce versions.

### III. Configuration as Code
Profiles, source universes, schedules, and model aliases live in typed YAML
under `config/`. New report inputs require a config entry plus config-tree
contract coverage, never hardcoded source lists.

### IV. Test-First for Deterministic Logic
Retrieval parsing, processing calculations, and presentation rendering get
focused unit tests; flow wiring (run -> persist -> deliver ordering) gets
contract tests. Tests run offline (fixtures, no network).

### V. Fail Softly Per Source, Fail Closed Overall
One unavailable external record becomes a recorded issue; the pipeline fails
only when all required sources are unavailable. Missing values render as `—`
placeholders, never as fabricated numbers.

### VI. Simplicity
Standard-library-plus-`httpx`/`pydantic` stack, no new dependencies for
routine report extensions. Reuse existing providers before adding new ones.

## Additional Constraints

- Windmill flow order is `run -> persist -> deliver`; schedules are
  regenerated from `config/schedules.yaml`, never hand-edited in
  `workflows/windmill`.
- Untrusted external data (feeds, APIs, model output) is validated at
  boundaries by Pydantic contracts; secrets never enter source YAML or
  artifacts.
- Presentation payload changes must respect `TELEGRAM_SAFE_MESSAGE_LIMIT`
  splitting.

## Development Workflow

- Deterministic logic ships with focused unit tests (test-first for new
  behavior); flow wiring gets contract tests; all tests must pass offline
  before review.
- Human review is required before any merge; agents never approve or merge
  their own changes.
- Architectural documentation under `docs/archdoc/` is refreshed only when
  architecture, interfaces, dependencies, or documented facts change.

## Governance

This constitution governs all Spec Kit features in this repository. Amendments
require a reviewed PR updating this file with rationale. Where a principle
conflicts with convenience, the principle wins.

**Version**: 1.0.0 | **Ratified**: 2026-10-25 | **Last Amended**: 2026-10-25