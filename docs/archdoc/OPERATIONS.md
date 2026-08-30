# DailyDash Operations

> Generated with `ai-craftkit` skill: `archdoc`  
> Source: `https://github.com/stefanrossmeier/daily-dash.git` at commit `e080781f788934b050123bffa686df5ae4faf125`  
> Prompt: `Inspect the repo, create the full documentation in the directory /docs/archdoc`

Last Reviewed Scope: full review
Doc Status: DRAFT
Last Operations Update: 2026-08-30T00:00:00Z
Updated By: agent
Source Basis: README scan, scripts, Compose files, workflow definitions, code scan

## Runtime Overview

The supported local runtime is a Docker Compose deployment of Windmill, PostgreSQL, a dedicated DailyDash worker image, and a model-gateway image. Caddy exposes Windmill on port 80; the model gateway binds to `127.0.0.1:18080`. Windmill executes scheduled flows, routes DailyDash jobs by the `dailydash` worker tag, and supplies workspace variables/secrets.

The reports use the production sequence:

```text
scheduled/manual Windmill flow -> command run -> immutable private-data artifact -> Git persistence -> command deliver -> Telegram
```

## Prerequisites

Verified project guidance requires Git, `uv` compatible with the pinned version range, Python 3.12, Node.js greater than 20 with npm, Docker Compose, and `curl`. Install the pinned Windmill CLI with `npm ci`, then use `./scripts/check-tools.sh`.

## Local Bootstrap

From the repository root:

```bash
npm ci
./scripts/check-tools.sh
./scripts/check.sh

./scripts/bootstrap-local-windmill.sh \
  --target ../daily-dash-windmill-local \
  --data-repo ../daily-dash-data
```

Bootstrap copies tracked Compose/Caddy/example files into the private target; creates or initializes the separate data Git repository; initializes empty permission-restricted secret files; and writes a machine-specific `.env` with source/data paths and Compose settings. Do not place either runtime directory or data sink inside this public repository.

Configure a private data-repository remote/branch and Windmill credentials as described in [QUICKSTART.md](../../QUICKSTART.md), then run:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh up
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh health
./scripts/sync-windmill-workspace.sh
```

Windmill is opened at `http://localhost` after startup. The model gateway is intentionally local-only at `http://127.0.0.1:18080` from the host and `http://daily_dash_model_gateway:8080` from the DailyDash worker.

## Runtime Units

| Unit | Runtime role | Operational notes |
|---|---|---|
| PostgreSQL `db` | Windmill state. | Compose health check uses `pg_isready`; named `db_data` volume. |
| `windmill_server` | Windmill server. | Exposes internal ports 8000/2525; waits for database health. |
| `windmill_worker` | General worker pool. | Three replicas in Compose template; privileged configuration present. |
| `windmill_worker_dailydash` | DailyDash application jobs. | Built from repository; tagged `dailydash`; mounts private data repo. |
| `daily_dash_model_gateway` | Model provider boundary. | Reads `OPENROUTER_API_KEY_FILE`; publishes host localhost port 18080 only. |
| Caddy | Reverse proxy. | Publishes 80 and 25 in local template. |

## Configuration And Secrets

| Category | Location | Notes |
|---|---|---|
| Profiles/source universes/schedules | `config/`. | Committed, typed YAML; no secret values. |
| Model aliases | `config/model-gateway.yaml`. | Maps alias to provider/model, attempts, timeout, structured/X capability. |
| Runtime paths | Generated local `.env`. | Includes Compose database URL, images, source/data mount paths. |
| Local secret files | Generated `secrets/` directory. | One raw value per 0600 file; directory mode 0700. |
| Windmill secret variables | `f/daily_dash/*`. | Telegram, deploy-key, and Reddit secrets are injected into relevant steps. |

The canonical bootstrap provisions placeholders for `openrouter_api_key`, `data_repo_deploy_key`, `telegram_token`, `telegram_chat_id`, `reddit_client_id`, `reddit_client_secret`, and `reddit_user_agent`. Do not put values in source YAML, committed workflow definitions, images, output artifacts, or documentation.

## Scheduling And Triggering

`config/schedules.yaml` owns 11 enabled schedules in `Europe/Berlin`; generated Windmill files are checked in under `workflows/windmill/f/daily_dash`. All schedule definitions set `no_flow_overlap: true`.

- News Top runs at 00:00, 06:00, 12:00, and 18:00 daily; German and Alternative News have their own daily multi-slot cadences.
- Markets, futures, and yields run on weekdays; Weekend Markets runs Saturdays/Sundays.
- Smart News runs three times daily using its rolling 18-hour input window.
- WSB runs daily at 20:35, Polymarket daily at 20:45, and X Watchlist daily at 08:20 and 20:20.

Pipelines derive auditable windows from this registry. Explicit timezone-aware bounds are available on several module CLI run commands for replay/testing. Regenerate schedules with `scripts/render-windmill-schedules.py`; use `scripts/sync-windmill-workspace.sh` to generate, test, and push the workspace representation.

## Real Runtime Trace: Top News

```text
Windmill schedule f/daily_dash/news_top
-> run_news.sh
-> python -m daily_dash.commands.news run --profile news-top
-> run_news_pipeline
-> RSS retrieval and diagnostics
-> dedupe/candidate cap -> model gateway ranking -> deterministic selection/backfill
-> JsonNewsRunStore writes news/top/<timestamp>_<run>.json
-> persist_data_repo.sh stages, commits, and pushes news/top to private data repo
-> deliver_news.sh
-> python -m daily_dash.commands.news deliver --artifact <path>
-> render_news_report -> TelegramDelivery -> Telegram Bot API
```

The flow uses the artifact path returned by the run command. Failure before persistence must prevent delivery because the delivery module follows persistence in the flow definition.

## Health, Logs, And Debugging

| Goal | Command |
|---|---|
| Stack status | `DAILY_DASH_WINDMILL_DIR=... ./scripts/local-windmill.sh status` |
| HTTP and gateway health | `DAILY_DASH_WINDMILL_DIR=... ./scripts/local-windmill.sh health` |
| Recent service logs | `DAILY_DASH_WINDMILL_DIR=... ./scripts/local-windmill.sh logs` |
| Render effective Compose config | `DAILY_DASH_WINDMILL_DIR=... ./scripts/local-windmill.sh config` |
| Rebuild DailyDash images | `DAILY_DASH_WINDMILL_DIR=... ./scripts/local-windmill.sh rebuild` |
| Validate repository configuration | `uv run daily-dash validate-config` |
| Test a configured model alias | `./scripts/smoke-model-gateway.sh rank-cheap` |

For a manual production-style check, use `wmill.sh flow run f/daily_dash/news_top` from `workflows/windmill` after workspace setup. Verify an immutable artifact was committed/pushed before confirming Telegram delivery.

## Failure Modes And Recovery

| Symptom | Likely cause | First response |
|---|---|---|
| Worker fails before a run starts | Missing Python/config/assets/data-repo mount. | Inspect the corresponding `run_*.sh` preflight error and worker logs. |
| Model-backed flow fails | Gateway unhealthy, missing OpenRouter secret, alias/config error, or provider response failure. | Run local health and gateway smoke check; inspect model trace/error without exposing request secrets. |
| No usable report data | All enabled sources failed, or all required series/quotes were unavailable. | Inspect artifact/run logs and adapter diagnostics; upstream source behavior may have changed. |
| Persistence step refuses to run | Wrong branch, remote advanced, staged files, concurrent lock, invalid data path, or missing remote/key. | Synchronize the private data repo deliberately; clear only a confirmed stale lock; do not force merge/rebase collected data. |
| Telegram delivery fails | Missing Telegram secret, API/network failure, or malformed formatting. | Retain the already persisted artifact; repair credentials/format then rerun the artifact-based delivery step. |
| Windmill definitions drift | UI-only edits or unrendered schedules/flows. | Update source definitions, run sync script, and avoid treating UI state as source of truth. |
| Futures data is partial/unavailable | Unofficial anonymous TradingView protocol changes or stale bars. | Inspect adapter diagnostics; do not silently replace the instrument/source. |

## Persistence And Recovery Rules

Git persistence is intentionally fail-closed. The helper serializes writers with `.git/daily-dash-persist.lock`, deletes only locks older than 30 minutes, rejects nonmatching branch/staged changes/remote divergence, and pushes existing local commits on retry. A failed post-commit push can therefore be retried once the remote state is made compatible, without regenerating the artifact.

The data repository is both the operational artifact store and a simple history mechanism at current scale. Backup/retention and off-host restore procedures are not documented in the inspected repository.

## Verification Workflow

1. For a narrow code/config change, run the closest `tests/unit` or `tests/contract` case using `./scripts/test.sh`.
2. Validate the config tree after profile, source, model-alias, or schedule edits.
3. Run `./scripts/check.sh` before integration; it synchronizes the locked environment and runs formatting, linting, strict mypy, coverage tests, gateway tests, config validation, and package build.
4. For workflow/schedule changes, run `./scripts/sync-windmill-workspace.sh` only against the intended workspace.
5. Rebuild local DailyDash images after application/config/dependency changes that must be included in container images.

## Security Operations

Treat the private runtime directory, data repository, Windmill UI access, deploy key, provider key, and Telegram/Reddit secrets as sensitive. Use repository-scoped deploy keys, keep secret files permission-restricted, rotate exposed credentials, and inspect logs/artifacts before sharing. The Compose template notes that privileged workers and optional Docker-socket mounts have substantial host impact; do not enable the Docker socket for untrusted users.

## Known Unknowns

- Production host, TLS exposure, authentication hardening, alerting, and backup procedures are not fully defined by inspected repository files.
- No live health check, delivery, source request, or deployment was executed for this documentation pass.
- Windmill instance users/workspace memberships and actual secret provisioning state are intentionally outside version control and were not inspected.
