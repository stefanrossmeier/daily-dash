# DailyDash documentation

The root [`README.md`](../README.md) is the public project overview and [`QUICKSTART.md`](../QUICKSTART.md)
is the shortest path from clone to a working local deployment. This directory contains the deeper
design, pipeline, orchestration, and operational documentation.

## Start here

| Document | What it covers |
| --- | --- |
| [`VPS_DEPLOYMENT.md`](VPS_DEPLOYMENT.md) | zero-to-running single-VPS deployment under `/var/code`, HTTPS, secrets, backups, updates |
| [`09_LOCAL_WINDMILL_BOOTSTRAP.md`](09_LOCAL_WINDMILL_BOOTSTRAP.md) | clean-machine self-hosted Windmill setup, local secrets, data sink, workspace provisioning |
| [`16_ARCHITECTURE_BOUNDARIES.md`](16_ARCHITECTURE_BOUNDARIES.md) | dependency directions and layer responsibilities |
| [`05_WINDMILL_ORCHESTRATION.md`](05_WINDMILL_ORCHESTRATION.md) | orchestration model, workspace, workers, secrets, local/VPS differences |
| [`SCHEDULING.md`](SCHEDULING.md) | schedule registry and retrieval-window semantics |
| [`15_DEPLOYMENT_CHECKLIST.md`](15_DEPLOYMENT_CHECKLIST.md) | repository/runtime gate and end-to-end smoke tests |
| [`06_DATA_STORAGE.md`](06_DATA_STORAGE.md) | private artifact storage and repository separation |
| [`07_GIT_DATA_PERSISTENCE.md`](07_GIT_DATA_PERSISTENCE.md) | automated Git persistence mechanics |

## Pipeline documentation

| Document | Pipeline / topic |
| --- | --- |
| [`04_MARKETS_PIPELINE.md`](04_MARKETS_PIPELINE.md) | Markets |
| [`17_FUTURES_PIPELINE.md`](17_FUTURES_PIPELINE.md) | Futures Snapshot |
| [`10_YIELDS_PIPELINE.md`](10_YIELDS_PIPELINE.md) | Yields |
| [`08_NEWS_PIPELINE.md`](08_NEWS_PIPELINE.md) | Top / German / Alternative News |
| [`11_SMART_NEWS_PIPELINE.md`](11_SMART_NEWS_PIPELINE.md) | Smart News |
| [`11_WSB_PIPELINE.md`](11_WSB_PIPELINE.md) | WallStreetBets |
| [`12_POLYMARKET_PIPELINE.md`](12_POLYMARKET_PIPELINE.md) | Polymarket |
| [`14_X_WATCHLIST_PIPELINE.md`](14_X_WATCHLIST_PIPELINE.md) | X Watchlist |
| [`13_X_GROK_SEARCH_SPIKE.md`](13_X_GROK_SEARCH_SPIKE.md) | Grok/X Search investigation that led to the current X retrieval adapter |

Weekend Markets is documented alongside the Markets/orchestration/configuration implementation;
its source/profile/schedule are under `config/` and its Windmill flow is under
`workflows/windmill/`.

## Project history and design planning

The numbered early documents are retained because they show how the current architecture was
derived:

- [`01_ANALYSIS.md`](01_ANALYSIS.md)
- [`02_PIPELINE_ORCHESTRATION_PLAN.md`](02_PIPELINE_ORCHESTRATION_PLAN.md)
- [`03_IMPLEMENTATION_PLAN.md`](03_IMPLEMENTATION_PLAN.md)

They are historical/design context rather than the primary setup instructions. When they differ
from current configuration or current pipeline documentation, the current code/config contracts
are authoritative.

## Public project documents

- [`../README.md`](../README.md) — overview
- [`../QUICKSTART.md`](../QUICKSTART.md) — setup
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution workflow
- [`../SECURITY.md`](../SECURITY.md) — vulnerability reporting and security boundaries
- [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) — community expectations
- [`../LICENSE`](../LICENSE) — Apache License 2.0
