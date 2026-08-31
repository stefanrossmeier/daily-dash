# ADR-0004: Route Model Work Through A Gateway And Versioned Assets

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
Source Basis: CAND-004, gateway configuration, architecture documentation, deployment configuration

## Context

Several reports use LLMs for narrow retrieval, ranking, or thematic work. These integrations need controlled provider access, structured output validation, traceable prompt behavior, and deterministic policy outside model output.

## Decision

Route model-provider access through the local model gateway using aliases in `config/model-gateway.yaml`. Keep stable prompts and substantive deterministic editorial policy as versioned assets. Record prompt/policy identity and hashes in traces, and retain deterministic processing as authority for selection and presentation policy.

## Evidence

| Claim | Evidence | Status |
|---|---|---|
| Gateway aliases define provider/model choice, retries, timeout, and capability flags. | `config/model-gateway.yaml` | verified |
| Prompt and policy assets are versioned and hashed into traces/artifacts. | `docs/16_ARCHITECTURE_BOUNDARIES.md`, `docs/archdoc/ARCHITECTURE.md` | verified |
| Gateway receives the provider key file and the worker receives its URL. | `deploy/local-windmill/docker-compose.override.yml` | verified |
| Model-backed reports do not call providers directly. | `README.md` | verified |

## Alternatives Considered

| Option | Why not selected |
|---|---|
| Direct provider calls from individual pipelines | Conflicts with centralized credential, alias, and trace boundaries. |
| Embed stable prompts and policy in Python | Conflicts with the versioned, inspectable asset model. |

## Consequences

- Provider and model changes are governed by aliases and recorded traces.
- Model-backed code must preserve structured validation and gateway-only access.
- Deterministic policy and presentation limits remain distinct from model results.
- Prompt/policy updates can affect artifact interpretation and evaluation.

## High-Risk Notes

Provider credentials and model responses cross a trust boundary. Keep credentials outside source, images, artifacts, and logs. Validate structured responses and preserve prompt/policy identity during behavioral investigations.

## Open Questions and Gaps

- Provider failover, long-term model retention, and alias-change compatibility policy were not found. (missing)

## Agent Work Guide

Read the matching prompt/policy asset, alias, and artifact contract before changing a model-backed report. Do not bypass the gateway or silently repurpose a versioned asset.
