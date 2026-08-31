# ADR-0001: Enforce Layered Pipeline Boundaries

> Generated with `ai-craftkit` skill: `adrgen`  
> Source: `https://github.com/stefanrossmeier/daily-dash.git` at commit `e080781f788934b050123bffa686df5ae4faf125`  
> Prompt: `Inspect the repo, write the ADRs directly in /docs/adr`

Decision Status: PROPOSED
Decision Date: 2026-08-31
Last Reviewed Scope: repo discovery
Doc Status: NEEDS REVIEW
Last ADR Update: 2026-08-31T00:00:00Z
Updated By: agent
Source Mode: discover
Source Basis: CAND-001, architecture documentation, contract test

## Context

DailyDash report families share a path from external data acquisition to durable artifacts and Telegram reports. The current architecture assigns ownership to retrieval, LLM adapters, deterministic processing, pipelines, storage, presentation, delivery, and command adapters.

## Decision

Maintain the documented one-way layer boundaries. Retrieval normalizes external data; LLM modules perform structured model I/O; processing remains deterministic and free of external I/O; pipelines compose artifacts; presentation renders persisted contracts; delivery transports rendered output; commands remain runtime adapters. Enforce these boundaries with import-based contract tests.

## Evidence

| Claim | Evidence | Status |
|---|---|---|
| Layer responsibilities and exclusions are documented. | `docs/16_ARCHITECTURE_BOUNDARIES.md` | verified |
| Forbidden cross-layer imports and presentation-policy isolation are tested. | `tests/contract/test_architecture_boundaries.py` | verified |
| The layer model applies across report families. | `docs/archdoc/ARCHITECTURE.md` | verified |

## Alternatives Considered

| Option | Why not selected |
|---|---|
| Report-specific commands that retrieve, render, and deliver together | Conflicts with reusable artifact and presentation boundaries. |
| Review-only dependency conventions | Does not provide executable regression protection. |

## Consequences

- New report capabilities belong in the owning layer and are composed by a pipeline.
- Presentation configuration cannot alter pipeline semantic processing.
- Cross-layer imports can fail the contract suite before integration.

## Open Questions and Gaps

- Original rationale for the exact layer decomposition was not found; current implementation is verified. (missing)

## Agent Work Guide

Read `docs/16_ARCHITECTURE_BOUNDARIES.md` and run the architecture contract test before changing these boundaries. Preserve dependency direction unless an explicit ADR revises it.
