# DailyDash API Surface

> Generated with `ai-craftkit` skill: `archdoc`  
> Source: `https://github.com/stefanrossmeier/daily-dash.git` at commit `e080781f788934b050123bffa686df5ae4faf125`  
> Prompt: `Inspect the repo, create the full documentation in the directory /docs/archdoc`

Last Reviewed Scope: full review
Doc Status: DRAFT
Last API Surface Update: 2026-08-30T00:00:00Z
Updated By: agent
Source Basis: code scan, workflow schemas, configuration, contract tests

## Scope And Evidence

This repository has integration-relevant interfaces even though it is not a general public web API: package/module CLIs, a local model gateway, Windmill script/flow inputs, artifact JSON schemas, and outbound third-party protocols.

| Label | Meaning |
|---|---|
| verified | Directly defined in code, workflow YAML, or tests. |
| uncertain | Plausible behavior not exercised in this review. |

## Interface Inventory

| Interface | Owner | Consumers |
|---|---|---|
| `daily-dash validate-config` | `daily_dash.cli` | Developers, CI, operators. |
| `python -m daily_dash.commands.<report>` | `commands/` | Windmill shell scripts and direct operators. |
| `POST /v1/chat`, `POST /v1/x-search` | Model gateway service | DailyDash model adapters. |
| `GET /health` | Model gateway service | Local stack health wrapper. |
| Windmill scripts/flows | `workflows/windmill/f/daily_dash` | Windmill scheduler/workers. |
| JSON run artifacts | `contracts/` and `storage/` | Delivery commands, private data repository, replay/debugging. |
| Telegram Bot API `sendMessage` | `delivery/telegram.py` | External delivery destination. |

## Package CLI

| Command | Inputs | Output / errors |
|---|---|---|
| `daily-dash validate-config [--config-dir PATH]` | Optional config root; defaults through `DAILY_DASH_CONFIG_DIR`, `DAILY_DASH_HOME`, then `config`. | Prints profile/source-set/schedule counts; exits 1 for `ConfigurationError`. |

The installed console script is declared in [pyproject.toml](../../pyproject.toml). It is the stable top-level CLI; individual report commands are invoked as Python modules by Windmill.

## Report Module CLI Contract

Every report module supports `run` and `deliver`; `run` writes an immutable artifact and emits one JSON summary to stdout, while `deliver` reads an existing artifact and emits JSON including `telegram_message_id` when successful.

| Module | Run inputs | Extra check command |
|---|---|---|
| `daily_dash.commands.news` | Required `--profile` in `news-top`, `news-alternative`, `news-german`; required `--data-repo`; optional `--config-dir`, `--gateway-url`, explicit timezone-aware `--window-start/--window-end`. | None. |
| `daily_dash.commands.news_smart` | Required `--data-repo`; optional config/gateway/explicit bounds. | None. |
| `daily_dash.commands.markets` | Optional fixed `--profile markets`; required `--data-repo`; optional config. | None. |
| `daily_dash.commands.markets_weekend` | Optional fixed `--profile markets-weekend`; required `--data-repo`; optional config. | None. |
| `daily_dash.commands.futures` | Optional fixed `--profile futures`; required `--data-repo`; optional config. | None. |
| `daily_dash.commands.yields` | Optional fixed `--profile yields`; required `--data-repo`; optional config. | None. |
| `daily_dash.commands.wsb` | Required `--data-repo`; optional config/gateway/explicit bounds. | `check-reddit [--config-dir PATH]`. |
| `daily_dash.commands.polymarket` | Required `--data-repo`; optional config/gateway. | `check-api [--config-dir PATH]`. |
| `daily_dash.commands.x_watchlist` | Required `--data-repo`; optional config/gateway/explicit bounds. | None. |

For all `deliver` commands, `--artifact PATH` is required and `--config-dir PATH` is optional. Delivery requires `DAILY_DASH_TELEGRAM_TOKEN` and `DAILY_DASH_TELEGRAM_CHAT_ID`; missing/invalid values end the command before network delivery.

## Run Summary Compatibility

The exact fields vary by report, but callers should treat `artifact_path` and `profile` as the stable common outputs. Model-backed summaries additionally include counts, cost, calls/attempts/retries, usage completeness, and effective retrieval window when applicable. Consumers should not parse human log output; Windmill scripts redirect the JSON summary into `result.json`.

## Model Gateway HTTP Contract

DailyDash sends JSON to a configurable base URL. Default resolution is explicit `gateway_url`, then `DAILY_DASH_MODEL_GATEWAY_URL`, then `http://127.0.0.1:18080`.

| Endpoint | Request fields | Response contract |
|---|---|---|
| `POST /v1/chat` | `alias`, `purpose`, `profile`, two-item `messages`, `response_schema_name`, `response_schema`. | `alias`, `provider`, `model`, optional `generation_id`, object `content`, usage counts/cost, latency, attempts, errors, usage flag, optional provider metadata. |
| `POST /v1/x-search` | `alias`, `purpose`, `profile`, `input`, `allowed_x_handles`, `from_date`, `to_date`, response-schema fields. | Same validated gateway response shape. |
| `GET /health` | No known request fields. | Used by `local-windmill.sh health`; response body is not asserted by inspected application code. |

`/v1/chat` is used for structured ranking/theme classification. `/v1/x-search` is a retrieval-specific interface and requires an alias configured to allow X search. Non-success HTTP responses become `RuntimeError` with response text; successful JSON is validated by `GatewayResponse` with forbidden unknown fields.

## Windmill Contracts

Flows use script paths under `f/daily_dash` and tag application steps with `dailydash`. Every production report flow has ordered run, persistence, then delivery modules; schedule files set `no_flow_overlap: true`.

| Script class | Core inputs |
|---|---|
| `run_news` | `profile` required. |
| `run_markets`, `run_futures`, `run_yields`, `run_news_smart`, `run_polymarket`, `run_x_watchlist` | Optional `data_repo`, defaulting to `/data/daily-dash-data`. |
| `run_wsb` | `data_repo` plus required Reddit OAuth client id, secret, and User-Agent. |
| `deliver_*` | Required artifact path, Telegram token, Telegram chat id. |
| `persist_data_repo` | Deploy key, repo path, relative data path, remote URL, branch, commit message. |

Windmill obtains Telegram, data-repo, and Reddit credentials through workspace variables rather than source configuration. The persistence script rejects an empty/absolute/traversal data path and fails closed on unexpected remote commits or a pre-staged data repository.

## Artifact JSON Contracts

Artifacts are strict Pydantic JSON documents. Schema identity is carried by `schema_version` and pipeline-specific discriminators. Important roots:

| Pipeline | Root document | Persisted path |
|---|---|---|
| News | `NewsRunDocument`, schema 1, `pipeline: news`. | `news/<profile suffix>/`. |
| Smart News | `SmartNewsRunDocument`, schema 1, `pipeline: news-smart`. | `news/smart/`. |
| Markets | `MarketSnapshotDocument`, schema 1, `pipeline: markets`. | `markets/snapshots/`. |
| Weekend Markets | `WeekendMarketSnapshotDocument`, schema 1, `pipeline: markets-weekend`. | `markets/weekend/snapshots/`. |
| Futures | `FuturesSnapshotDocument`, schema 1, `pipeline: futures`. | `futures/snapshots/`. |
| Yields | `YieldSnapshotDocument`, schema 1, `pipeline: yields`. | `yields/snapshots/`. |
| WSB | `WsbRunDocument`, schema 1, `pipeline: wsb`. | `wsb/snapshots/`. |
| Polymarket | `PolymarketRunDocument`, schema 2, `pipeline: polymarket`. | `polymarket/snapshots/`. |
| X Watchlist | `XWatchlistRunDocument`, schema 1, `pipeline: x-watchlist`. | `x-watchlist/snapshots/`. |

Filenames are `<UTC timestamp>_<first 8 run-id characters>.json`; writers raise `FileExistsError` rather than overwrite. `read()` validates the full typed model. Artifacts retain operational provenance such as source diagnostics, retrieval windows, and model/policy traces where relevant.

## Authentication And Trust Rules

- OpenRouter root credentials are mounted only into the model-gateway container as a secret file.
- Telegram token/chat id, data-repo deploy key, and Reddit OAuth settings are injected through Windmill/local secret-file provisioning.
- WSB requires approved Reddit OAuth credentials; its command performs a client-credentials exchange with Reddit.
- Futures is anonymous `tvDatafeed` access and does not use a TradingView credential.
- X Watchlist does not require an X credential in DailyDash; Grok X Search is accessed via the configured model gateway.
- Telegram delivery posts to `https://api.telegram.org/bot<TOKEN>/sendMessage`, supplies `chat_id`, `text`, and parse mode, and reports failure without raising from the transport adapter.

## Compatibility And Change Checks

Before changing an interface:

1. Preserve `schema_version` and pipeline literals for old artifacts, or add an explicit migration/version strategy.
2. Keep module `run` JSON output machine-readable because Windmill consumes it as `result.json`.
3. Keep delivery artifact-based; do not add a direct retrieval-to-Telegram path.
4. Update matching flow/schema YAML and contract tests when command arguments change.
5. Version prompt assets and align response schema names/Pydantic validation when model expectations change.
6. Check the `TELEGRAM_SAFE_MESSAGE_LIMIT` split behavior if presentation payload size changes.

## Contract Confidence

| Claim | Evidence | Status |
|---|---|---|
| CLI config validation and report module parsers define these inputs. | `cli.py` and each `commands/*.py`. | verified |
| Gateway request payloads and response shape are locally validated. | `llm/gateway.py` and model adapter schemas. | verified |
| Windmill run/persist/deliver ordering is contract-tested. | `tests/contract/test_*_windmill_flow.py`. | verified |
| Telegram endpoint availability and upstream API response semantics. | Not exercised during this review. | uncertain |
