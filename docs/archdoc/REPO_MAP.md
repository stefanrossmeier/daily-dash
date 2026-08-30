# DailyDash Repository Map

> Generated with `ai-craftkit` skill: `archdoc`  
> Source: `https://github.com/stefanrossmeier/daily-dash.git` at commit `e080781f788934b050123bffa686df5ae4faf125`  
> Prompt: `Inspect the repo, create the full documentation in the directory /docs/archdoc`

Last Reviewed Scope: full review
Doc Status: DRAFT
Last Repo Map Update: 2026-08-30T00:00:00Z
Updated By: agent
Source Basis: README scan, code scan, tests scan, deployment files

## Overview

DailyDash is a self-hosted personal market-intelligence system. It retrieves market, news, yield, prediction-market, Reddit, and curated X data; applies deterministic processing plus focused LLM ranking/synthesis; persists immutable JSON artifacts to a separate Git repository; and delivers reports to Telegram. Windmill schedules and orchestrates the production flows.

## Start Here

1. [README.md](../../README.md) for product scope and the `run -> persist -> deliver` invariant.
2. [QUICKSTART.md](../../QUICKSTART.md) for the local stack and first flow run.
3. [src/daily_dash/commands](../../src/daily_dash/commands) for executable Python report commands.
4. [config](../../config) for profiles, source universes, model aliases, and schedule source of truth.
5. [workflows/windmill](../../workflows/windmill) for the deployed flow definitions.

## Top-Level Map

| Path | Role |
|---|---|
| [src/daily_dash](../../src/daily_dash) | Python application package: typed contracts, adapters, processing, pipelines, commands. |
| [config](../../config) | Versioned profiles, external source sets, schedules, and model aliases. |
| [assets](../../assets) | Versioned prompt and deterministic policy assets. |
| [workflows/windmill](../../workflows/windmill) | Windmill workspace-as-code, scripts, flows, and generated schedules. |
| [deploy](../../deploy) | Reproducible local Windmill Compose templates and image Dockerfiles. |
| [services/model-gateway](../../services/model-gateway) | Isolated HTTP gateway for provider/model access. |
| [scripts](../../scripts) | Validation, bootstrap, sync, live-check, and operator helpers. |
| [tests](../../tests) | Unit, contract, replay, ranking-evaluation, and fixture tests. |
| [docs](..) | Existing design/implementation records plus this generated `archdoc` set. |

## Important Files

| File | Why it matters |
|---|---|
| [pyproject.toml](../../pyproject.toml) | Python 3.12 package, dependencies, `daily-dash` CLI, Ruff, mypy, pytest configuration. |
| [package.json](../../package.json) | Pinned Windmill CLI is the only root Node dependency. |
| [config/schedules.yaml](../../config/schedules.yaml) | Canonical cadence and retrieval-window configuration for 11 report profiles. |
| [config/model-gateway.yaml](../../config/model-gateway.yaml) | Model alias to provider/model mapping and retry/timeout policy. |
| [src/daily_dash/cli.py](../../src/daily_dash/cli.py) | Public package CLI: configuration validation. |
| [src/daily_dash/config/validation.py](../../src/daily_dash/config/validation.py) | Cross-validates profile, source-set, and schedule relationships. |
| [src/daily_dash/llm/gateway.py](../../src/daily_dash/llm/gateway.py) | DailyDash client for model gateway `/v1/chat` and `/v1/x-search`. |
| [scripts/check.sh](../../scripts/check.sh) | Canonical full quality gate. |
| [scripts/sync-windmill-workspace.sh](../../scripts/sync-windmill-workspace.sh) | Regenerates derived workflows/schedules, checks contracts, and pushes workspace definitions. |
| [deploy/local-windmill/docker-compose.override.yml](../../deploy/local-windmill/docker-compose.override.yml) | DailyDash worker and model-gateway services added to Windmill. |

## Module Guide

| Module | Responsibility | Main neighbors |
|---|---|---|
| `contracts/` | Pydantic models defining internal and persisted documents. | All layers consume contracts. |
| `config/` | Typed YAML loading, path resolution, and cross-file validation. | Commands and pipelines. |
| `retrieval/` | External acquisition and normalization. | Pipelines; no processing/storage dependencies. |
| `llm/` | Prompt loading, gateway calls, response schemas, trace creation. | Pipelines; no retrieval/processing dependency. |
| `processing/` | Deterministic scoring, deduplication, eligibility, transformation. | Pipelines and contracts. |
| `pipelines/` | Compose retrieval, LLM, processing, and immutable artifact storage. | Commands call them. |
| `storage/` | Artifact filesystem/Git-sink persistence adapters. | Pipelines and command delivery. |
| `presentation/` | Pure Telegram Markdown/HTML rendering. | Command `deliver` paths. |
| `delivery/` | Telegram Bot API adapter. | Commands only. |
| `commands/` | `argparse` runtime entry points used by Windmill shell scripts. | Pipelines for `run`; storage/presentation/delivery for `deliver`. |

## Report Profiles

The validated configuration tree has 11 profile/source/schedule ids: `news-top`, `news-german`, `news-alternative`, `news-smart`, `markets`, `markets-weekend`, `futures`, `yields`, `wsb`, `polymarket`, and `x-watchlist`.

- News variants use RSS plus LLM ranking; Smart News uses a rolling window and LLM theme clustering followed by a versioned macro policy.
- Markets, futures, weekend markets, and yields are deterministic retrieval/processing reports.
- WSB, Polymarket, and X Watchlist use LLM-assisted relevance selection; X retrieval itself is model-gateway-backed Grok native X Search.

## Commands

| Command | Purpose |
|---|---|
| `uv run daily-dash validate-config` | Validate every checked-in profile, source set, and schedule relationship. |
| `./scripts/test.sh [pytest args]` | Run Python tests through `uv`. |
| `./scripts/check.sh` | Locked sync, formatting, lint, mypy, coverage tests, gateway tests, config validation, build. |
| `./scripts/format.sh` | Apply repository formatting. |
| `./scripts/bootstrap-local-windmill.sh` | Materialize private local runtime directory and data sink. |
| `./scripts/local-windmill.sh <action>` | Manage the local Compose stack: `up`, `down`, `rebuild`, `status`, `logs`, `health`, `config`. |
| `./scripts/sync-windmill-workspace.sh` | Regenerate and deploy versioned Windmill definitions. |

Detailed invocation contracts are in [API_SURFACE.md](API_SURFACE.md).

## Tests And Conventions

- `tests/unit/` covers local behavior; `tests/contract/` protects serialization, configuration, layer boundaries, and Windmill flow contracts.
- `tests/replay/` and `tests/ranking_eval/` support repeatable input and ranking evaluation.
- Pydantic models use `extra="forbid"`; preserve this strict contract behavior when adding fields.
- `config/schedules.yaml` is authoritative. Rendered `*.schedule.yaml` files are derived and are tested for exact equality.
- Prompt instructions belong in versioned `assets/prompts/<id>/<version>/`; substantial deterministic editorial policy belongs in `assets/policies/`.
- Public source, private runtime/secrets, and private data artifacts are separate locations.

## Glossary

| Term | Meaning |
|---|---|
| profile | One typed report configuration selecting pipeline, source set, limits, prompts, and presentation policy. |
| source set | External feed/instrument/account universe associated with one pipeline. |
| artifact | Immutable JSON document created by a pipeline before it is rendered/delivered. |
| model gateway | Local service that owns provider credentials and resolves logical model aliases. |
| Windmill flow | Ordered `run -> persist -> deliver` orchestration definition. |
| data repo | Separate private Git checkout mounted in workers at `/data/daily-dash-data`. |

## Agent Work Guide

1. Identify the owning layer and matching report profile.
2. Read the closest command, pipeline, and contract test before editing.
3. For user-visible behavior, trace `run`, artifact persistence, and `deliver` separately.
4. Preserve `run -> persist -> deliver`, model-gateway-only provider access, and layer import rules.
5. Run the narrowest relevant test first, then `./scripts/check.sh` before integration.
6. Regenerate and synchronize Windmill definitions only when their source changes.

## High-Risk Areas

| Area | Risk and first check |
|---|---|
| Windmill persistence | Concurrent Git writes and remote divergence can block delivery; inspect `persist_data_repo.sh` and workflow variable wiring. |
| Secrets | Gateway, Telegram, Reddit, and deploy-key credentials must remain outside Git/logs/artifacts; inspect `deploy/local-windmill` and workspace provisioning scripts. |
| External data adapters | RSS, TradingView/tvDatafeed, IG, Reddit, and public Polymarket APIs can change independently; begin with adapter-specific unit/contract tests. |
| Model contracts | Prompt/schema changes affect persisted traces and selection; inspect versioned prompt assets, gateway tests, and response Pydantic models. |
| Schedules | Incorrect time zones or generated schedule drift changes retrieval windows; validate configuration and run schedule contract tests. |

## README Reality Check

| Topic | README says | Repository shows | Status |
|---|---|---|---|
| Python runtime | Python 3.12 with `uv` | `pyproject.toml` requires `>=3.12`; `check.sh` uses `uv`. | verified |
| Quality gate | `./scripts/check.sh` | Script runs listed checks plus build cleanup. | verified |
| Windmill sync | Workspace definitions are generated/synchronized | Sync script regenerates News flows and schedules, runs selected contracts, then `wmill sync push`. | verified |
| Persistence before delivery | Every production flow persists first | Checked-in flow contracts assert run/persist/deliver ordering. | verified |

## Known Unknowns

- Production hosting target, backup/retention policy, and alerting configuration were not verified from the inspected source tree.
- Tests and local services were not executed during this documentation pass.
- The data-repository remote, branch, and all runtime secret values are installation-specific and intentionally not inspected.
