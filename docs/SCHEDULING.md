# Scheduling and retrieval windows

`config/schedules.yaml` is the source of truth for DailyDash production schedules.
It is intentionally separate from pipeline implementation and ranking configuration.
Changing an article-ranking News pipeline's schedule changes its next retrieval windows
without changing Python code. Smart News is the deliberate exception described below:
it keeps a rolling 18-hour context window while Windmill owns its execution schedule.

Each schedule defines its own timezone, eligible days of week and local run slots.
Article-ranking News schedules additionally define a backward grace period. A scheduled News run at
slot `T` resolves the previous eligible slot `P` from the same schedule and retrieves
the half-open interval:

```text
[P - grace, T)
```

The default grace is one hour. This creates deliberate overlap at schedule boundaries
so late RSS publication timestamps are less likely to be missed. Duplicate URL/title
handling and semantic duplicate handling remain responsible for overlap inside a run.

The current registry contains independent schedules for Top, German, Alternative and Smart
News, the weekday Markets snapshot, and the separate Weekend Markets pipeline. Smart News
runs every day at 07:15, 12:15 and 21:00 Europe/Berlin. Unlike the article-ranking News
profiles, it deliberately preserves its legacy rolling 18-hour retrieval window because
overlapping context is part of the theme-clustering product behavior. Weekend Markets runs
only on Saturday and Sunday at 10:30 and 20:30 Europe/Berlin.

For deterministic tests and manual replays, News accepts explicit ISO-8601
`--window-start` and `--window-end` values. Both must be supplied and include timezone
offsets. Explicit windows bypass schedule resolution and are persisted in the run
artifact as such.

Windmill `*.schedule.yaml` files are generated from the same registry:

```bash
uv run python scripts/render-windmill-schedules.py
```

The checked-in generated files are covered by contract tests, and
`workflows/windmill/wmill.yaml` enables schedule synchronization. The generated
schedules set `no_flow_overlap: true`.

Initial schedule values are configuration, not code. They should be reviewed before
production enablement and can be changed independently per pipeline.
