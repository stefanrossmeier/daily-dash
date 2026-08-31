# Architecture Decision Records

> Generated with `ai-craftkit` skill: `adrgen`  
> Source: `https://github.com/stefanrossmeier/daily-dash.git` at commit `e080781f788934b050123bffa686df5ae4faf125`  
> Prompt: `Inspect the repo, write the ADRs directly in /docs/adr`

Last ADR Index Update: 2026-08-31T00:00:00Z
Updated By: agent

## Purpose

This directory records repository-wide architecture decisions and their supporting evidence.

## Status Legend

- `PROPOSED`: draft awaiting explicit human confirmation.
- `ACCEPTED`: confirmed decision.
- `NEEDS REVIEW`: rationale or current applicability needs review.

## ADRs

| ID | Title | Status | Date | Notes |
|---|---|---|---|---|
| ADR-0001 | [Enforce layered pipeline boundaries](0001-enforce-layered-pipeline-boundaries.md) | PROPOSED | 2026-08-31 | Source candidate CAND-001. |
| ADR-0002 | [Use Windmill workspace-as-code for orchestration](0002-use-windmill-workspace-as-code-for-orchestration.md) | PROPOSED | 2026-08-31 | Source candidate CAND-002. |
| ADR-0003 | [Persist immutable artifacts before delivery](0003-persist-immutable-artifacts-before-delivery.md) | PROPOSED | 2026-08-31 | Source candidate CAND-003. |
| ADR-0004 | [Route model work through a gateway and versioned assets](0004-route-model-work-through-a-gateway-and-versioned-assets.md) | PROPOSED | 2026-08-31 | Source candidate CAND-004. |

## Candidate Documents

| File | Notes |
|---|---|
| [ADR_CANDIDATES.md](ADR_CANDIDATES.md) | Discovery evidence and generation history. |

## Agent Guidance

Before changing architecture-sensitive code, read the related ADR and its evidence. Preserve a recorded decision unless work explicitly revisits it; document implementation conflicts rather than inventing rationale.
