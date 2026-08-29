# Reproducing the local Windmill environment

This document is the clean-machine bootstrap procedure for the self-hosted Windmill
environment used by DailyDash.

The important design rule is that `daily-dash-windmill-local` is **generated runtime
state**, not a separately maintained source repository. Its reproducible source lives
in this public repository:

```text
deploy/local-windmill/
├── docker-compose.yml
├── docker-compose.override.yml
├── Caddyfile
├── .env.example
└── .gitignore
```

DailyDash-specific worker/model images are built from:

```text
deploy/example/windmill-worker.Dockerfile
deploy/example/model-gateway.Dockerfile
config/model-gateway.yaml
```

Windmill workspace definitions are versioned under:

```text
workflows/windmill/
```

Schedules are generated from the central registry:

```text
config/schedules.yaml
```

This means a reader can start from the public `daily-dash` repository and reconstruct
the complete local stack without access to the author's local Windmill directory.

## 1. Prerequisites

Install:

- Git;
- uv matching the repository requirement;
- Node.js >20 and npm;
- Docker with Docker Compose.

From the repository root:

```bash
npm ci
./scripts/check-tools.sh
./scripts/check.sh
```

The Windmill CLI is pinned by `package.json`/`package-lock.json`; do not independently
upgrade it for this setup.

## 2. Prepare the private data sink

Production-style DailyDash persistence writes immutable artifacts to a separate Git
checkout. Persistence is an output sink; application ranking/scheduling never reads
previous data artifacts as workflow state.

You can either clone your own private repository before bootstrap:

```bash
git clone git@github.com:YOUR_ACCOUNT/daily-dash-data.git ../daily-dash-data
```

or let the bootstrap script create an empty local Git repository. The latter is enough
for application/container development, but the full Windmill persistence step also
requires a reachable Git remote plus an SSH deploy key with write access.

Do not use the author's private data repository URL. The remote is configured as a
Windmill variable for each installation.

## 3. Materialize the local deployment directory

Run:

```bash
./scripts/bootstrap-local-windmill.sh \
  --target ../daily-dash-windmill-local \
  --data-repo ../daily-dash-data
```

The script:

1. copies the checked-in Compose/Caddy deployment source;
2. writes a local `.env` containing absolute host paths;
3. creates an ignored `secrets/` directory with 0600 one-value credential/config files;
4. initializes an empty `daily-dash-data` Git checkout when the target path does not
   already contain a repository;
5. records the DailyDash source revision used for the generated deployment.

If you intentionally refresh an existing generated folder after deployment-template
changes:

```bash
./scripts/bootstrap-local-windmill.sh \
  --target ../daily-dash-windmill-local \
  --data-repo ../daily-dash-data \
  --force
```

`--force` refreshes tracked infrastructure files but preserves an existing `.env` and
secret files. Add `--rewrite-env` only when host paths have changed.

## 4. Configure local secret files

The generated runtime keeps application credentials out of `.env`. `.env` contains
Compose/runtime paths only. Installation-specific credentials live as one-value files
under:

```text
../daily-dash-windmill-local/secrets/
├── openrouter_api_key
├── data_repo_deploy_key
├── telegram_token
├── telegram_chat_id
├── reddit_client_id
├── reddit_client_secret
└── reddit_user_agent
```

The bootstrap script creates the directory with mode `0700` and each placeholder file
with mode `0600`. Put one raw value in each file, with no shell assignment and no
quotes. Never commit this directory.

The model gateway reads `openrouter_api_key` directly as a read-only mounted file.
To use an existing OpenRouter key file instead, bootstrap with:

```bash
./scripts/bootstrap-local-windmill.sh \
  --target ../daily-dash-windmill-local \
  --data-repo ../daily-dash-data \
  --openrouter-key-file ~/.config/daily-dash/openrouter_api_key
```

The other files are local provisioning inputs. Helper scripts read them and upload the
corresponding values to Windmill without writing credentials into the repository or
root `.env`.

For WSB Reddit OAuth configuration, use the dedicated interactive helper instead of
editing the files manually:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local \
  ./scripts/configure-wsb-reddit.sh
```

## 5. Start Windmill

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local \
  ./scripts/local-windmill.sh up
```

The command builds the DailyDash worker and model gateway from the current public
checkout and starts the pinned Windmill stack.

Useful operations:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh status
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh health
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh logs
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh rebuild
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh down
```

`rebuild` explicitly rebuilds/recreates the DailyDash worker and model gateway after
application/config changes.

Open:

```text
http://localhost
```

A fresh Windmill instance starts with its bootstrap administrator. Use that only for
initial local setup; persistent/public deployments should replace it with an intended
administrator account.

## 6. Register/create the DailyDash workspace in the CLI

The checked-in `workflows/windmill/wmill.yaml` expects:

```text
local profile: daily-dash-local
workspace id:  daily-dash-workspace
base URL:      http://localhost
```

After completing the initial Windmill login, register the workspace:

```bash
./scripts/wmill.sh workspace add \
  daily-dash-local \
  daily-dash-workspace \
  http://localhost
```

If `daily-dash-workspace` does not yet exist, create it in the Windmill UI first or use
the CLI's workspace-creation option appropriate to the pinned CLI version.

Verify:

```bash
./scripts/wmill.sh workspace whoami
./scripts/wmill.sh workspace list
```

Authentication profiles/tokens are local machine state and are deliberately not
committed.

## 7. Configure installation-specific Windmill values

The checked-in flows contain no author-specific data-repository URL or credentials.
They resolve installation values from Windmill at runtime.

The canonical local secret inputs are the files from section 4. For the base
persistence/Telegram setup, populate:

```text
secrets/data_repo_deploy_key
secrets/telegram_token
secrets/telegram_chat_id
```

The data-repository remote and branch are not secrets. Supply the remote URL when
provisioning; the branch defaults to `main`:

```bash
export DAILY_DASH_DATA_REPO_REMOTE_URL='git@github.com:YOUR_ACCOUNT/daily-dash-data.git'
export DAILY_DASH_DATA_REPO_BRANCH='main'

DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local \
  ./scripts/configure-windmill-workspace.sh
```

`configure-windmill-workspace.sh` reads the secret files and creates/updates:

```text
f/daily_dash/data_repo_remote_url     non-secret
f/daily_dash/data_repo_branch         non-secret
f/daily_dash/data_repo_deploy_key     secret
f/daily_dash/telegram_token           secret
f/daily_dash/telegram_chat_id         secret
```

Environment variables with the same secret names are still accepted as explicit
overrides for CI/secret-manager injection, but local development should use the
`secrets/` files. Secret values are never written to `.env`.

WSB has separate Reddit credentials and does not require rerunning the base workspace
provisioning. Configure and upload them with:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local \
  ./scripts/configure-wsb-reddit.sh --windmill
```

This creates:

```text
f/daily_dash/reddit_client_id       secret
f/daily_dash/reddit_client_secret   secret
f/daily_dash/reddit_user_agent      non-secret
```

The persistence script currently uses GitHub's published SSH host key and therefore
expects a GitHub SSH remote for the production-style Git sink.

## 8. Synchronize flows and schedules

The public repository is the source of truth for workflow definitions. Before sync,
the helper regenerates News flows and schedule YAML and runs the contract checks.

```bash
./scripts/sync-windmill-workspace.sh
```

The underlying operation is a `wmill sync push` scoped by
`workflows/windmill/wmill.yaml`. It includes schedules but deliberately skips secrets,
variables, resources, users, groups and instance settings.

The sync scope is `f/**`; use a dedicated DailyDash workspace because sync semantics
can remove in-scope remote objects that do not exist locally.

## 9. Verify the reconstructed environment

Infrastructure health:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local \
  ./scripts/local-windmill.sh health
```

Repository checks:

```bash
./scripts/check.sh
```

Windmill identity:

```bash
./scripts/wmill.sh workspace whoami
```

At this point the reconstructed stack has:

```text
Windmill server + Postgres + Caddy
        |
        +--> dedicated worker tag=dailydash
        |       |
        |       +--> DailyDash application image
        |       +--> mounted private data checkout
        |
        +--> DailyDash model gateway
                |
                +--> OpenRouter key file (host secret)
```

The workspace contains the checked-in Markets/News flows and the generated schedules.

## 10. End-to-end acceptance

Before paid model calls or real Telegram publication:

```bash
./scripts/check.sh
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh health
```

Then run a flow through Windmill, for example:

```bash
cd workflows/windmill
../../scripts/wmill.sh flow run f/daily_dash/news_top
```

The News flow order is intentionally:

```text
run_news
→ persist_data_repo
→ deliver_news
```

so Telegram publication cannot occur before durable Git persistence.

## 11. What is reproducible and what remains installation-specific

Tracked/reproducible:

- Windmill/Caddy Compose source;
- pinned Windmill CLI and Windmill application image;
- DailyDash worker image definition;
- model-gateway image/configuration;
- workflows/scripts/flows;
- schedules and schedule generator;
- application/config/prompt assets.

Installation-specific and intentionally untracked:

- Windmill database volume;
- CLI authentication profile/token;
- absolute host checkout paths;
- OpenRouter key;
- Telegram credentials;
- private data repository URL/deploy key;
- generated DailyDash data.

That boundary is intentional: infrastructure and behavior are reproducible from Git,
while credentials and private output remain local/private.

## 12. VPS deployment

The same checked-in application, worker image, model gateway, workflow definitions and
schedule registry can be used on a Linux VPS. The differences are operational:

- choose persistent host paths (for example `/var/code/daily-dash` and
  `/var/code/daily-dash-data`);
- use Docker Engine/Compose rather than Docker Desktop;
- configure a real HTTPS endpoint instead of localhost;
- use token-based CLI authentication where browser login is inappropriate;
- replace bootstrap/default Windmill credentials;
- manage secrets with host/secret-management tooling;
- review database backup/upgrade procedures before production use.

Do not add host cron or another orchestration layer; Windmill remains the scheduler and
workflow orchestrator.

## Upstream references

- Windmill self-hosting: https://www.windmill.dev/docs/advanced/self_host
- Windmill CLI workspace management: https://www.windmill.dev/docs/advanced/cli/workspace-management
- Windmill CLI sync semantics: https://www.windmill.dev/docs/advanced/cli/sync

The local stack intentionally pins Windmill/Windmill Extra to `1.775.1`. Review
upstream release notes and database migration guidance before changing those versions.
