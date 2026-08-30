# Contributing to DailyDash

DailyDash welcomes focused bug fixes, source improvements, tests, documentation, and pipeline
changes that preserve the project's architectural and operational boundaries.

## Development setup

Requirements are documented in [`QUICKSTART.md`](QUICKSTART.md). For repository development:

```bash
npm ci
./scripts/check-tools.sh
uv sync --locked
```

The canonical pre-PR gate is:

```bash
./scripts/check.sh
```

It runs formatting/linting, strict mypy, pytest with branch coverage, model-gateway tests,
configuration validation, and a package build.

## Core invariants

Changes should preserve these rules unless a proposal explicitly changes the architecture and the
associated contract tests/documentation:

1. **Production flow is `run -> persist -> deliver`.** Do not bypass durable persistence before
   Telegram delivery.
2. **Windmill orchestrates; DailyDash owns business logic.** Flow definitions should remain thin.
3. **Retrieval, processing, LLM, storage, presentation, and delivery are separate layers.** See
   [`docs/16_ARCHITECTURE_BOUNDARIES.md`](docs/16_ARCHITECTURE_BOUNDARIES.md).
4. **Use deterministic logic when possible.** Do not add an LLM call when explicit processing is
   sufficient.
5. **All model access goes through the model gateway.** Application code must not read the root
   OpenRouter key directly.
6. **Stable prompts are versioned assets.** Put behavioral prompt content under `assets/prompts/`,
   not large inline Python strings.
7. **Substantive deterministic editorial policy can be versioned data.** Avoid burying large policy
   tables/term sets in Python when they should be auditable assets.
8. **Processing limits and presentation limits are different concerns.** Rendering configuration
   must not silently change the semantic result universe.
9. **Telegram is a reader surface, not a debug surface.** Internal scores, rationales, model traces,
   and dedupe diagnostics belong in persisted artifacts.
10. **No secrets or generated private data in the public repository.** Runtime credentials belong
    in the generated local secrets directory/Windmill secret storage; report artifacts belong in a
    separate private data sink.

Architecture directions are enforced by contract tests. If a new dependency direction is truly
required, document the reason rather than weakening tests casually.

## Making a change

Create a branch from current `main` and keep the scope narrow. Useful local checks while iterating:

```bash
./scripts/format.sh
git diff --check
uv run pytest -q <focused tests>
```

Before opening a pull request, run:

```bash
./scripts/check.sh
```

If the change modifies checked-in Windmill definitions or schedule generation, also run:

```bash
./scripts/sync-windmill-workspace.sh
```

Only synchronize a development/test workspace you intend to update; repository CI should remain
secret-free.

## Pipeline changes

For a new or materially changed report, cover the relevant layers:

- typed configuration/profile/source contracts;
- retrieval adapters and failure behavior;
- deterministic processing and deduplication;
- model response validation when applicable;
- prompt/policy asset loading and hashing when applicable;
- immutable persisted artifact contracts;
- presentation behavior, including empty states;
- Windmill `run -> persist -> deliver` contracts;
- schedules when applicable;
- architecture-boundary tests.

External sources should fail locally where possible: one unavailable feed/instrument should not
necessarily abort an otherwise useful report. Do not silently substitute a materially different
instrument/source without making the semantics explicit.

## Prompt and model changes

Treat prompt/model behavior as a versioned interface:

- create a new prompt version when stable instructions change materially;
- keep prior versions for traceability;
- update prompt hashes/contracts/tests;
- do not infer application behavior from numeric prompt versions;
- preserve model alias indirection instead of hard-coding provider model IDs in business logic;
- consider cost and retry behavior as part of the change.

## Configuration and schedules

`config/schedules.yaml` is the schedule source of truth. Generated Windmill schedule files should
match it exactly.

Profile ranking configuration defines the semantic result universe. Presentation configuration
controls rendering only.

## Commits and pull requests

Use Conventional Commits where practical, for example:

```text
feat(news): add ranked backfill for sparse reports
fix(futures): update TradingView protocol compatibility
refactor(secrets): consolidate local secret handling
test(architecture): enforce module boundaries
docs(deployment): clarify clean-machine bootstrap
```

Pull requests should explain:

- the problem and intended behavior;
- the architectural layers affected;
- external source/model implications;
- tests run;
- deployment/rebuild/workspace-sync implications;
- any user-visible Telegram changes.

The pull request template provides a checklist.

## Generated and local files

Do not commit local/generated state such as:

```text
.venv/
node_modules/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.coverage
.windmill-tmp/
.env
secrets/
*.zip
```

`node_modules/` only contains developer/operator tooling such as the pinned Windmill CLI; it is not
part of the application runtime.

## Security issues

Do not open a public issue containing credentials, private report data, or a security vulnerability
with meaningful exploit detail. Follow [`SECURITY.md`](SECURITY.md).

## Conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
