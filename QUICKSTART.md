# DailyDash Quickstart

This guide takes a clean checkout to a working local Windmill deployment. It uses explicit paths
so moving the source checkout cannot silently create a second runtime or data repository.

For deeper operational detail, see [`docs/09_LOCAL_WINDMILL_BOOTSTRAP.md`](docs/09_LOCAL_WINDMILL_BOOTSTRAP.md).

## 1. Prerequisites

Install:

- Git;
- `uv` compatible with the version required by `pyproject.toml`;
- Node.js >20 and npm;
- Docker with Docker Compose;
- `curl`.

Clone the repository:

```bash
git clone https://github.com/stefanrossmeier/daily-dash.git
cd daily-dash
```

Install the pinned Windmill CLI and verify the toolchain:

```bash
npm ci
./scripts/check-tools.sh
```

Run the repository quality gate:

```bash
./scripts/check.sh
```

## 2. Choose explicit local paths

The public source checkout, private runtime, and private data sink are separate concerns. Pick
paths appropriate to your machine; the following sibling layout is convenient:

```bash
export DAILY_DASH_SOURCE="$PWD"
export DAILY_DASH_WINDMILL_DIR="$(cd .. && pwd)/daily-dash-windmill-local"
export DAILY_DASH_DATA_REPO="$(cd .. && pwd)/daily-dash-data"
```

Do not put the runtime directory or data sink inside the public Git repository.

## 3. Prepare a private data sink

DailyDash persists generated artifacts before external delivery. For the full production-style
flow, create a private Git repository such as `YOUR_ACCOUNT/daily-dash-data`, add an SSH deploy key
with write permission, then clone it at the chosen path:

```bash
git clone git@github.com:YOUR_ACCOUNT/daily-dash-data.git "$DAILY_DASH_DATA_REPO"
```

For local-only development, bootstrap can create an empty local Git repository instead. The
Windmill Git-persistence step requires a reachable remote before it can push.

## 4. Materialize the local Windmill runtime

```bash
./scripts/bootstrap-local-windmill.sh \
  --target "$DAILY_DASH_WINDMILL_DIR" \
  --data-repo "$DAILY_DASH_DATA_REPO"
```

This creates a machine-specific runtime directory from the checked-in templates under
`deploy/local-windmill/`. Its `.env` contains non-secret Compose paths/settings only.

## 5. Populate local secret files

Canonical local secrets live together under:

```text
daily-dash-windmill-local/secrets/
├── openrouter_api_key
├── data_repo_deploy_key
├── telegram_token
├── telegram_chat_id
├── reddit_client_id
├── reddit_client_secret
└── reddit_user_agent
```

Each file contains one raw value with no shell assignment or quotes. The files are local runtime
state and must never be committed.

At minimum for model-backed Telegram reports, populate:

```text
openrouter_api_key
data_repo_deploy_key
telegram_token
telegram_chat_id
```

WSB additionally needs the Reddit values. Futures uses anonymous TradingView/tvDatafeed access and
requires no TradingView account. X Watchlist requires no X credentials; Grok native X Search is
accessed through the model gateway.

## 6. Start the stack

```bash
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" \
  ./scripts/local-windmill.sh up

DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" \
  ./scripts/local-windmill.sh health
```

Open `http://localhost` and complete the initial self-hosted Windmill bootstrap.

## 7. Configure the Windmill CLI workspace

The checked-in workspace expects the local CLI profile `daily-dash-local` and workspace id
`daily-dash-workspace`.

Create the workspace in Windmill if necessary, then register the CLI profile:

```bash
./scripts/wmill.sh workspace add \
  daily-dash-local \
  daily-dash-workspace \
  http://localhost

./scripts/wmill.sh workspace whoami
```

CLI authentication is local machine state and is not committed.

## 8. Provision installation-specific values and secrets

The private data-repository remote and branch are non-secret installation settings. Export them:

```bash
export DAILY_DASH_DATA_REPO_REMOTE_URL='git@github.com:YOUR_ACCOUNT/daily-dash-data.git'
export DAILY_DASH_DATA_REPO_BRANCH='main'
```

Provision the base values/secrets into Windmill from the canonical local secret files:

```bash
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" \
  ./scripts/configure-windmill-workspace.sh
```

For WSB, configure Reddit separately:

```bash
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" \
  ./scripts/configure-wsb-reddit.sh --windmill
```

## 9. Synchronize workflows and schedules

```bash
./scripts/sync-windmill-workspace.sh
```

This regenerates derived News flows/schedules, runs the relevant Windmill contract tests, and
pushes the checked-in workspace definitions. Do not maintain production-only flow edits in the
Windmill UI.

## 10. Smoke-test the model gateway

For a model-backed report:

```bash
./scripts/smoke-model-gateway.sh rank-cheap
```

A successful response includes the configured alias, resolved provider/model, structured content,
token usage, cost, latency, and attempt count.

## 11. Run a real flow

Run Top News through the same `run -> persist -> deliver` path used by schedules:

```bash
cd workflows/windmill
../../scripts/wmill.sh flow run f/daily_dash/news_top
```

Useful additional smoke tests:

```bash
../../scripts/wmill.sh flow run f/daily_dash/futures
../../scripts/wmill.sh flow run f/daily_dash/markets
../../scripts/wmill.sh flow run f/daily_dash/yields
```

For every production-style flow, verify that:

1. the run step completes;
2. an immutable JSON artifact is committed/pushed to the private data repository;
3. delivery runs only after persistence;
4. Telegram contains reader-facing content, not internal scores/rationales;
5. logs/artifacts contain no secrets.

## 12. Common lifecycle commands

Run these from the public `daily-dash` checkout:

```bash
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" ./scripts/local-windmill.sh status
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" ./scripts/local-windmill.sh health
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" ./scripts/local-windmill.sh logs
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" ./scripts/local-windmill.sh rebuild
DAILY_DASH_WINDMILL_DIR="$DAILY_DASH_WINDMILL_DIR" ./scripts/local-windmill.sh down
```

Use `rebuild` after application/config/dependency changes that must be copied into the DailyDash
worker/model-gateway images. Use `sync-windmill-workspace.sh` only when checked-in Windmill
workspace definitions or generated schedules/flows need synchronization.

## Next reading

- [`docs/09_LOCAL_WINDMILL_BOOTSTRAP.md`](docs/09_LOCAL_WINDMILL_BOOTSTRAP.md) — complete clean-machine setup
- [`docs/05_WINDMILL_ORCHESTRATION.md`](docs/05_WINDMILL_ORCHESTRATION.md) — orchestration model
- [`docs/16_ARCHITECTURE_BOUNDARIES.md`](docs/16_ARCHITECTURE_BOUNDARIES.md) — code-layer boundaries
- [`docs/15_DEPLOYMENT_CHECKLIST.md`](docs/15_DEPLOYMENT_CHECKLIST.md) — production-readiness checks
- [`docs/SCHEDULING.md`](docs/SCHEDULING.md) — schedules and retrieval windows
