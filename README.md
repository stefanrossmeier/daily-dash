# DailyDash

DailyDash is a reproducible, Windmill-orchestrated financial dashboard pipeline for
weekday market snapshots, public weekend market quotes, and ranked news briefings. The public repository contains the
application, model-gateway configuration, Windmill workflows/schedules, worker image,
and the source files needed to recreate the local self-hosted Windmill environment.

## Development

Requirements:

- Git
- uv
- Node.js >20
- npm
- Docker with Docker Compose

Install the pinned Windmill CLI and verify the repository:

```bash
npm ci
./scripts/check-tools.sh
./scripts/check.sh
```

## Recreate the local Windmill stack

The local deployment is generated from files tracked under
`deploy/local-windmill/`; the generated machine-specific directory is not a second
source of truth.

```bash
./scripts/bootstrap-local-windmill.sh \
  --target ../daily-dash-windmill-local \
  --data-repo ../daily-dash-data
```

Put an OpenRouter key in the generated `secrets/openrouter_api_key`, then start the
stack:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local \
  ./scripts/local-windmill.sh up
```

Open `http://localhost`, complete the initial Windmill login/workspace setup, add the
CLI workspace profile, configure DailyDash variables/secrets, and synchronize the
checked-in flows and schedules.

The complete clean-machine procedure, including the private data sink and Telegram
configuration, is documented in:

- [`docs/09_LOCAL_WINDMILL_BOOTSTRAP.md`](docs/09_LOCAL_WINDMILL_BOOTSTRAP.md)
- [`docs/05_WINDMILL_ORCHESTRATION.md`](docs/05_WINDMILL_ORCHESTRATION.md)
- [`docs/SCHEDULING.md`](docs/SCHEDULING.md)

## Repository boundaries

DailyDash deliberately keeps three concerns separate:

- this repository: application code, configuration, prompt assets and orchestration definitions;
- local/VPS Windmill deployment: generated from `deploy/local-windmill/` plus local secrets/paths;
- `daily-dash-data`: a separate private Git repository used only as an output sink.

No secret values or private data are required or stored in the public repository.


## Implemented workflows

- Weekday Markets: Yahoo Finance cross-asset snapshot, Monday-Friday.
- Weekend Markets: public IG weekend quotes, Saturday-Sunday, no LLM.
- News: Top, Alternative and German ranked briefings.
- Smart News: GPT-5.4-nano macro-theme clustering with a preserved 18-hour rolling context window.

All publishing workflows follow `generate artifact -> durable persistence -> external delivery`.
