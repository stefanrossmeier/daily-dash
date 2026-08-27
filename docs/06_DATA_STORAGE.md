# Data Storage

## Current strategy

DailyDash runtime data is intentionally stored outside the public application
repository.

During the first implementation phase, collected data is stored in the private
Git repository:

~~~text
daily-dash-data
~~~

Git is not intended as the permanent production database.

It is useful at the current low data volume because it provides:

- easy inspection;
- readable JSON;
- version history;
- diffs;
- reproducible evaluation data;
- simple backups.

The application uses a storage abstraction so Git-backed filesystem storage can
later be replaced by PostgreSQL, object storage, or another persistence system.

## Repository separation

~~~text
daily-dash
    public
    code, configuration, workflows, documentation

daily-dash-data
    private
    collected runtime data

Windmill / VPS infrastructure
    operational configuration and secrets
~~~

Runtime data must never be written into the public `daily-dash` repository.

## Initial layout

The initial layout is intentionally flat:

~~~text
daily-dash-data/
└── markets/
    └── snapshots/
        ├── 20260827T061500Z_a1b2c3d4.json
        ├── 20260827T181500Z_e5f6a7b8.json
        └── ...
~~~

There are no year/month/day subdirectories at the current data volume.

Snapshot filenames begin with a UTC timestamp so lexical filename order is also
chronological order.

A short run identifier suffix avoids collisions.

## Snapshot policy

Market snapshots are immutable.

A pipeline run creates a new file rather than modifying an existing snapshot.

Each JSON document contains both:

- raw retrieved market data;
- processed market report data.

This allows the stored data to support debugging, comparison and later
re-processing.

## Local development

Example sibling repositories:

~~~text
public-ai-github/
├── daily-dash/
├── DailyDash/
└── daily-dash-data/
~~~

Run Markets with persistence using:

~~~bash
uv run daily-dash markets   --data-repo ../daily-dash-data
~~~

The path is runtime configuration and must not be hard-coded into DailyDash.

## VPS layout

A recommended VPS layout is:

~~~text
/var/code/daily-dash
/var/code/daily-dash-data
/srv/windmill
~~~

The Windmill DailyDash worker can mount:

~~~text
/var/code/daily-dash-data -> /data/daily-dash-data
~~~

The workflow then uses:

~~~text
/data/daily-dash-data
~~~

as the data repository path.

## Git access on the VPS

The VPS should not use a personal GitHub token.

For `daily-dash-data`, use a repository-specific GitHub deploy key with write
permission.

This limits the VPS credential to the private data repository.

## Future migration

Git-backed storage is an implementation of the storage interface, not part of
the processing contracts.

A later migration may replace it with:

- PostgreSQL;
- S3-compatible object storage;
- another database.

Retrieval, processing and presentation should not require changes when the
storage implementation changes.

## Automated Git persistence

Generated runtime data is automatically committed and pushed after a
successful pipeline run.

Git persistence is implemented as a reusable Windmill orchestration step and
is intentionally separate from pipeline business logic.

See:

    docs/07_GIT_DATA_PERSISTENCE.md
