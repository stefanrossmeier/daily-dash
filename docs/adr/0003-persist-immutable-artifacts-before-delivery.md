# ADR-0003: Persist Immutable Artifacts Before Delivery

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
Source Basis: CAND-003, persistence and operations documentation

## Context

Report data must remain inspectable and deliverable after execution attempts, while the public source repository must exclude generated personal data and runtime secrets.

## Decision

Create immutable JSON artifacts in a separate private Git data repository and enforce `run -> persist -> deliver`. Delivery reads a persisted artifact rather than an in-memory pipeline result. Keep storage behind pipeline-specific interfaces so a future database or object-store migration does not require changing retrieval, model processing, or presentation behavior.

## Evidence

| Claim | Evidence | Status |
|---|---|---|
| Public source, private runtime state, and generated-data sink are separate. | `README.md` | verified |
| Persistence validates paths, rejects unsafe state, serializes writers, and supports retry after failed push. | `docs/07_GIT_DATA_PERSISTENCE.md` | verified |
| Operations use an artifact-based run, persist, then deliver flow. | `docs/archdoc/OPERATIONS.md` | verified |
| Storage protocols permit later backend replacement. | `docs/archdoc/ARCHITECTURE.md` | verified |

## Alternatives Considered

| Option | Why not selected |
|---|---|
| Deliver directly from a pipeline result | Removes the durable recovery and audit boundary. |
| Start with a database or object store | Current implementation favors readable Git history at present scale. |

## Consequences

- Failed delivery can be retried from an already persisted artifact.
- Persistence failures prevent delivery and require deliberate resolution of repository divergence.
- Git is an intentionally replaceable backend, not a permanent database commitment.
- A migration must preserve artifact immutability and persistence-before-delivery.

## High-Risk Notes

Persistence failure can suppress delivery, while forced synchronization can damage audit history. Inspect the private data repository branch, staged state, remote divergence, and logs first. Do not automatically merge or rebase collected data.

## Open Questions and Gaps

- Backup, retention, off-host restore, and a migration trigger are not documented. (missing)

## Agent Work Guide

Read `docs/07_GIT_DATA_PERSISTENCE.md` and the relevant flow before changing storage or delivery. Preserve artifact immutability and `run -> persist -> deliver`; a backend migration needs documented recovery behavior.
