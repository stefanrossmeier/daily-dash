# ADR-0002: Use Windmill Workspace-As-Code For Orchestration

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
Source Basis: CAND-002, configuration, workflow, and operations documentation

## Context

DailyDash schedules multiple report families, injects operational secrets, routes jobs to a dedicated worker, and keeps orchestration outside application pipelines.

## Decision

Use Windmill as the external orchestration runtime. Keep schedule definitions in `config/schedules.yaml`, materialize versioned workspace files under `workflows/windmill/`, and synchronize them with repository tooling. DailyDash commands and pipelines own report behavior; Windmill owns scheduling, job execution, retries, operational logs, and secret injection.

## Evidence

| Claim | Evidence | Status |
|---|---|---|
| Windmill owns scheduling/orchestration while pipelines own report behavior. | `README.md`, `docs/archdoc/ARCHITECTURE.md` | verified |
| Schedules are source-controlled and rendered into workspace files. | `config/schedules.yaml`, `docs/archdoc/OPERATIONS.md` | verified |
| A tagged DailyDash worker is defined in deployment configuration. | `deploy/local-windmill/docker-compose.override.yml` | verified |

## Alternatives Considered

| Option | Why not selected |
|---|---|
| Host cron directly invokes application commands | Moves orchestration and secret handling outside the runtime boundary. |
| UI-only Windmill definitions | Does not preserve a reproducible workspace representation. |

## Consequences

- Workflow and schedule updates require rendering and workspace synchronization.
- Runtime state, credentials, logs, and worker scaling remain outside the public checkout.
- Pipelines remain testable without a running Windmill instance.

## Open Questions and Gaps

- Production worker scaling, retry tuning, and deployment beyond local/VPS guidance were not verified by execution. (uncertain)

## Agent Work Guide

Inspect `config/schedules.yaml`, the matching workspace definition, and `docs/SCHEDULING.md` before changing a flow or schedule. Do not use UI-only edits as the source of truth.
