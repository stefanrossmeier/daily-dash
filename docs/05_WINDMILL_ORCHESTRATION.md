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

The operational Windmill Docker Compose deployment is intentionally not stored
inside this application repository.

An example local location is:

~~~text
~/repos/daily-dash-windmill-local
~~~

The eventual VPS deployment should likewise be managed separately from the
DailyDash application repository.

The public repository contains only the worker-image definition and workflow
definitions required to run DailyDash.

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

Examples:

~~~text
f/daily_dash/telegram_token
f/daily_dash/telegram_chat_id
~~~

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
daily-dash markets
    |
    +-- Yahoo Finance retrieval
    +-- market processing
    +-- JSON snapshot persistence
    +-- report rendering
    +-- Telegram delivery
~~~

The pipeline was verified with both stdout and Telegram delivery.

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

### Secrets

Telegram credentials are stored as Windmill secret variables:

~~~text
f/daily_dash/telegram_token
f/daily_dash/telegram_chat_id
~~~

Secrets are uploaded with `scripts/wmill-set-secret.sh`.

This helper uses a temporary ignored variable specification rather than placing
secret values directly on the Windmill CLI command line.

### Current limitations

At this milestone:

- snapshot creation is automatic;
- Telegram delivery is automatic;
- Git add/commit/push of collected data is still manual;
- the pipeline is manually triggered through Windmill;
- no production schedule exists yet.

The next milestone is a Windmill flow with explicit persistence verification
and automatic Git commit/push, followed by scheduling.

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
