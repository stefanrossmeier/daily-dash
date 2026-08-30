# Windmill Orchestration

## Purpose

DailyDash uses Windmill as its orchestration layer.

Windmill owns:

- scheduling;
- workflow execution;
- retries;
- worker routing;
- orchestration logs;
- secret injection.

DailyDash owns:

- data retrieval;
- data processing;
- ranking;
- presentation;
- storage adapters;
- delivery adapters.

Business logic must not be duplicated in Windmill workflow definitions.

## Supported environments

The setup is designed to run both:

- locally on macOS using Docker Desktop;
- on a headless Linux VPS using Docker Engine and Docker Compose.

Application and workflow commands must not depend on macOS-specific tooling.

## Required tools

- Git
- uv
- Node.js >20
- npm
- Docker
- Docker Compose

Check the local toolchain with:

~~~bash
./scripts/check-tools.sh
~~~

## Windmill CLI

The Windmill CLI is installed locally in this repository rather than globally.

This avoids requiring root permissions and makes the setup reproducible on both
developer machines and headless VPS hosts.

Install:

~~~bash
npm ci
~~~

Run:

~~~bash
./scripts/wmill.sh --version
~~~

The CLI is intentionally pinned in package.json and package-lock.json.

It may report that a newer Windmill CLI exists. Do not upgrade the CLI
independently of the Windmill server version.

## Local Windmill deployment

The operational local Windmill deployment is reproducible from this repository.
The checked-in source of truth lives under:

~~~text
deploy/local-windmill/
~~~

A machine-specific runtime directory (for example `../daily-dash-windmill-local`)
is materialized with:

~~~bash
./scripts/bootstrap-local-windmill.sh \
  --target ../daily-dash-windmill-local \
  --data-repo ../daily-dash-data
~~~

The generated directory contains local absolute paths and secret-file references,
so it is runtime state rather than another source repository. Refresh it from the
checked-in deployment source instead of hand-maintaining divergent Compose files.

Lifecycle commands are wrapped by `scripts/local-windmill.sh`; workspace definitions
are synchronized with `scripts/sync-windmill-workspace.sh`.

See `docs/09_LOCAL_WINDMILL_BOOTSTRAP.md` for a complete clean-machine bootstrap.

## Workspace

Development workspace:

~~~text
daily-dash-workspace
~~~

Configure the CLI:

~~~bash
./scripts/wmill.sh workspace add   daily-dash-local   daily-dash-workspace   http://localhost
~~~

Verify:

~~~bash
./scripts/wmill.sh workspace whoami
./scripts/wmill.sh workspace list
~~~

## Bootstrap administrator

A fresh self-hosted Windmill instance initially uses the bootstrap account:

~~~text
admin@windmill.dev
~~~

This account is acceptable only during local/bootstrap setup.

Before exposing a persistent VPS instance, replace the bootstrap account with a
real superadmin account and verify that the new account can log in before
removing the bootstrap user.

Windmill instance users and workspace memberships are separate concepts.

Workspace administrators can manage users from:

~~~text
Workspace Settings -> Users & Invites
~~~

## Authentication on a headless VPS

Developer workstations may use interactive browser authentication.

Headless VPS and CI environments should use Windmill user tokens.

Tokens must never be committed to Git.

## Secrets

Runtime secrets belong in Windmill secret variables.

DailyDash runtime secrets include:

~~~text
f/daily_dash/telegram_token
f/daily_dash/telegram_chat_id
f/daily_dash/data_repo_deploy_key
~~~

Installation-specific non-secret variables include:

~~~text
f/daily_dash/data_repo_remote_url
f/daily_dash/data_repo_branch
~~~

Use `scripts/configure-windmill-workspace.sh` to install these values after the CLI
workspace has been configured. Futures uses anonymous TradingView/tvDatafeed access and
requires no TradingView secret or account variable.

Secrets must never appear in:

- application configuration;
- workflow source;
- Docker images;
- Git history;
- documentation examples.

## Worker model

DailyDash runs on a dedicated Windmill worker tagged:

~~~text
dailydash
~~~

The worker image contains the DailyDash application.

Conceptually:

~~~text
Windmill
    |
    | job tagged dailydash
    v
DailyDash worker
    |
    v
daily-dash CLI
    |
    +-- retrieval
    +-- processing
    +-- persistence
    +-- presentation
    +-- delivery
~~~

## VPS differences

The same application and workflow definitions are used locally and on the VPS.

Only operational details differ:

~~~text
Local macOS                     Headless VPS
----------------------------    -----------------------------
Docker Desktop                  Docker Engine
http://localhost                HTTPS reverse proxy / tunnel
browser CLI authentication      token authentication
developer filesystem paths      /srv/... filesystem paths
local Git credentials           repository deploy keys
~~~

No DailyDash pipeline should depend directly on these differences.

## Verified Markets milestone

The Markets pipeline has been verified end-to-end through the local
self-hosted Windmill instance.

Verified execution path:

~~~text
Windmill API
    |
    v
Windmill job queue
    |
    | tag=dailydash
    v
dedicated DailyDash worker
    |
    v
markets run command
    |
    +-- Yahoo Finance retrieval
    +-- market processing
    +-- JSON snapshot write
    |
    v
persist_data_repo
    |
    v
markets deliver command
    |
    +-- report rendering
    +-- Telegram delivery
~~~

The pipeline is structured so rendering and Telegram delivery occur only after the persisted run artifact exists.

Market snapshots are persisted in the private `daily-dash-data` repository.

The stable worker paths are:

~~~text
/opt/daily-dash
/opt/daily-dash/config
/data/daily-dash-data
~~~

Host-side paths are environment-specific.

Local development currently uses sibling checkouts.

The intended VPS layout is:

~~~text
/var/code/daily-dash
/var/code/daily-dash-data
~~~

The host data repository is mounted into the worker as:

~~~text
/var/code/daily-dash-data -> /data/daily-dash-data
~~~

### Workspace configuration

Telegram credentials and the private data-repository deploy key are Windmill secret
variables. The data remote URL and branch are non-secret Windmill variables. None are
hard-coded in the checked-in flows.

Configure all required values with:

~~~bash
./scripts/configure-windmill-workspace.sh
~~~

The helper uses temporary ignored variable specifications rather than committing
credentials or embedding installation-specific repository URLs in workflow source.

### Current state

Markets and News use checked-in Windmill flows. Production-style data persistence is
performed by a generic Git persistence step, and schedules are generated from
`config/schedules.yaml` and synchronized with the workspace definitions.

Installation-specific values such as Telegram credentials, the private data-repository
remote/deploy key and OpenRouter credentials are intentionally not synchronized from
Git. The clean-machine setup and variable/secret bootstrap are documented in
`docs/09_LOCAL_WINDMILL_BOOTSTRAP.md`.

## Automatic Git persistence

The Markets pipeline is now executed as a Windmill flow:

    Run Markets
        |
        v
    Persist generated data

The flow is versioned locally as:

    workflows/windmill/f/daily_dash/markets__flow/flow.yaml

The `markets__flow` naming convention is generated by and verified against the
pinned Windmill CLI version used by this repository.

The persistence step is generic and will also be reused by future News
pipelines.

The complete verified Markets path is:

    Windmill
        |
        v
    dedicated dailydash worker
        |
        v
    market retrieval
        |
        v
    processing
        |
        +----> Telegram
        |
        v
    JSON snapshot
        |
        v
    Git commit
        |
        v
    private daily-dash-data repository


## Futures Snapshot

Futures is a deterministic no-LLM translation of the historical TradingView/tvDatafeed
report. It uses the same durability boundary as the other production reports:

~~~text
run_futures
    -> persist_data
    -> deliver_futures
~~~

The flow is versioned at `workflows/windmill/f/daily_dash/futures__flow/flow.yaml`; its
weekday 05:00, 07:15, 12:30 and 23:00 Europe/Berlin schedules are generated from
`config/schedules.yaml`. The run step uses anonymous TradingView/tvDatafeed access and
receives no Telegram, OpenRouter, or TradingView credential. The exact legacy contract
universe, source references and row-level failures are persisted before the compact
Telegram report is rendered. See `docs/17_FUTURES_PIPELINE.md` for retrieval semantics.

## Weekend Markets

Weekend Markets is a separate no-LLM pipeline from the weekday Yahoo Finance snapshot.
It retrieves public no-login weekend quotes from IG for US crude, Germany 40, US Tech
100, gold, Wall Street and EUR/USD. The production flow follows the same durability
invariant as News and weekday Markets:

~~~text
run_markets_weekend
    -> persist_data
    -> deliver_markets_weekend
~~~

Snapshots are written under `markets/weekend/snapshots` in the private data sink. The
central schedule registry enables the flow only on Saturday and Sunday at 10:30 and
20:30 Europe/Berlin. No LLM or model gateway is involved.
