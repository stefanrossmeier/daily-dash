# DailyDash Modernization — Step-by-Step Implementation Plan

This plan deliberately builds a new system **beside** the legacy DailyDash repository. The legacy project remains runnable until each selected workflow is proven equivalent or better.

## Target repositories and state

```text
GitHub public
└── dailydash-next
    code + configs + Windmill flow definitions + docs + safe fixtures

Git private
├── vps-infra
│   host configuration, deployment stacks, backups, reverse proxy, secret bootstrap
└── dailydash-evals-data          # optional
    curated/labelled ranking evaluation cases only

Private runtime services
├── Windmill PostgreSQL database
├── DailyDash PostgreSQL database/schema
└── private S3-compatible object bucket
```

There is **no production data directory inside `dailydash-next`**.

---

# Phase 0 — Freeze and baseline the legacy system

## Step 0.1: Do not refactor the old repository

Tag the current legacy state, for example:

```bash
git tag legacy-before-workflow-rewrite-2026-08-25
git push origin legacy-before-workflow-rewrite-2026-08-25
```

Keep it available as behavioral reference only.

## Step 0.2: Capture representative outputs

Manually save a small set of **sanitized** examples for:

- Top News,
- Alternative News,
- German News,
- Smart News,
- WSB,
- Polymarket,
- current X report.

Do not copy production secrets/session files. Do not commit automatically collected production history into the new public repo.

## Step 0.3: Define success criteria

Before writing the new rankers, label examples of what you actually wanted to see.

For WSB and Polymarket especially, collect candidate pools and label:

- must show,
- useful,
- marginal,
- noise.

This becomes ranking ground truth instead of relying on visual impressions.

**Deliverable:** initial `dailydash-evals-data` private repository.

---

# Phase 1 — Create the new public application repository

## Step 1.1: Initialize

```bash
mkdir dailydash-next
cd dailydash-next
git init
uv init --python 3.12
uv add pydantic pydantic-settings httpx pyyaml tenacity structlog
uv add --dev pytest pytest-cov ruff mypy respx
```

Add provider libraries only when a retriever needs them. Avoid copying the legacy `requirements.txt` wholesale.

## Step 1.2: Create the package layout

```bash
mkdir -p \
  src/dailydash/{contracts,config,retrieval,processing,llm,presentation,storage,pipelines} \
  config/profiles config/sources \
  workflows/windmill \
  tests/{unit,contract,replay,ranking_eval,fixtures} \
  deploy/example docs
```

## Step 1.3: Add repository safety defaults

`.gitignore` must include at least:

```gitignore
.env
.env.*
!.env.example
.data/
data/
artifacts/
*.db
*.sqlite*
secrets/
credentials/
```

Add a CI check that fails if common secret patterns or files are committed. Use a secret scanner such as Gitleaks in GitHub Actions.

## Step 1.4: Add configuration model

Use Pydantic settings for non-secret application settings and YAML profiles for business configuration.

Do **not** add a Python helper that silently loads a repo-local `.env` in production. Local development may use `.env`, but production secrets come from the orchestrator/gateway environment.

**Exit criterion:** `uv run pytest` works in the empty skeleton.

---

# Phase 2 — Implement contracts and storage before pipelines

## Step 2.1: Create contracts

Implement:

- `SourceItem`
- `CandidateBatch`
- `RankingDecision`
- `RankedBatch`
- `ReportArtifact`
- `RunManifest`
- `DeliveryResult`
- `CostSummary`

Version schemas explicitly, for example `schema_version: 1`.

## Step 2.2: Object storage abstraction

Create:

```python
class ObjectStore(Protocol):
    def put_json(self, key: str, value: Any) -> ObjectRef: ...
    def get_json(self, ref: ObjectRef) -> Any: ...
```

Implement two backends:

1. `LocalObjectStore` for tests/development.
2. `S3ObjectStore` for VPS production.

Object naming convention:

```text
raw/<pipeline>/<profile>/<yyyy>/<mm>/<dd>/<run_id>/...
normalized/<pipeline>/<profile>/<yyyy>/<mm>/<dd>/<run_id>.json
ranked/<pipeline>/<profile>/<yyyy>/<mm>/<dd>/<run_id>.json
reports/<pipeline>/<profile>/<yyyy>/<mm>/<dd>/<run_id>.json
manifests/<yyyy>/<mm>/<dd>/<run_id>.json
```

## Step 2.3: Metadata store

Start with PostgreSQL and a small schema:

```text
runs
items
run_items
rankings
deliveries
```

Do not put full raw provider payloads into Postgres.

## Step 2.4: Retention

Initial retention suggestion:

- raw payloads: 30–90 days,
- normalized/ranked artifacts: 180 days,
- report artifacts/run manifests: long-term,
- LLM raw responses: 30 days unless promoted to an evaluation case.

Use bucket lifecycle rules rather than a custom cron cleanup job.

**Exit criterion:** a local test can write/read a run without using the Git checkout for data.

---

# Phase 3 — Build the generic RSS/news pipeline

This is the first real vertical slice and should prove the architecture.

## Step 3.1: Rewrite `news_feed_utils.py` as a retriever

Implement `retrieval/rss.py` with:

- async HTTP via `httpx`,
- bounded concurrency,
- timeout/retry,
- user agent,
- Atom/RSS parsing,
- timestamp parsing,
- per-source result/error metadata.

The function returns source items. It does not score or format anything.

## Step 3.2: Migrate source configuration

Create:

```text
config/sources/news-top.yaml
config/sources/news-alternative.yaml
config/sources/news-german.yaml
```

Start from the existing source lists, then verify each feed independently before enabling it.

## Step 3.3: Implement normalization/dedupe

Normalize:

- title whitespace/entities,
- canonical URL where possible,
- UTC timestamps,
- source ID,
- language/profile metadata.

Deduplicate using a tiered strategy:

1. provider/stable ID,
2. canonical URL,
3. normalized title hash,
4. optional near-duplicate title similarity.

## Step 3.4: Port keyword logic as features

Do not throw away the current keyword work.

Move it into `processing/features.py` as features such as:

```text
central_bank_hits
macro_hits
market_move_hits
commodity_hits
risk_hits
equity_hits
percentage_move_present
source_weight
```

Use these to reduce candidate volume and as model context. They no longer directly define final rank.

## Step 3.5: Implement generic news pipeline

API:

```python
run_news(profile_id: str, *, publish: bool = False) -> ReportArtifact
```

The same function must successfully execute all three profiles.

**Exit criterion:** Top/Alternative/German produce valid JSON/Markdown locally with no LLM and no Telegram.

---

# Phase 4 — Introduce the cheap ranking layer

## Step 4.1: Add model client boundary

```python
class ModelClient(Protocol):
    def structured(self, alias: str, schema: type[T], messages: list[Message]) -> T: ...
```

No pipeline imports `openai`, `anthropic`, xAI, or OpenRouter-specific clients directly.

## Step 4.2: Start with direct OpenRouter adapter

For fastest progress, initially implement `OpenRouterModelClient` using its OpenAI-compatible API.

Required telemetry:

- logical alias,
- requested model,
- resolved model/provider if returned,
- prompt/input tokens,
- output tokens,
- search/tool usage,
- cost if returned or calculable,
- latency.

## Step 4.3: Implement news ranker schema/prompt

Send compact records, not entire articles. Example candidate:

```json
{
  "id": "n17",
  "source": "ECB Press",
  "published_minutes_ago": 42,
  "title": "...",
  "summary": "...max ~300 chars...",
  "features": {
    "central_bank_hits": 2,
    "macro_hits": 1
  }
}
```

Rank with 0–4 dimensions and a short reason.

## Step 4.4: Benchmark models

Baseline:

- OpenRouter `openai/gpt-4.1-nano`

Challenger:

- OpenRouter `google/gemini-3.1-flash-lite`

Run both on the private labelled sets. Pick by ranking metrics first and cost second.

A model swap must be a config change, not a code change.

## Step 4.5: Add deterministic fallback

If model call fails after retry:

- rank by the pre-rank features,
- mark `degraded=true`,
- include failure metadata,
- still allow report generation.

**Exit criterion:** all three news profiles outperform or at least match the legacy selection on the labelled cases while staying inside the target cost.

---

# Phase 5 — Build Smart News as synthesis over artifacts

## Step 5.1: Remove retrieval from Smart News

Input is a list of report/ranked-batch references from recent Top/Alternative/German runs.

## Step 5.2: Merge and cross-dedupe

Preserve source provenance and item IDs.

## Step 5.3: Port the useful macro editorial prompt

Retain the current preference for:

- geopolitical developments,
- energy,
- inflation/rates,
- growth,
- fiscal policy,
- currencies/bonds,
- broad risk sentiment,
- meaningful regulation.

Remove the legacy post-hoc keyword theme filter after the new synthesis behavior is benchmarked; if it still adds value, keep it as validation rather than as a second competing ranker.

## Step 5.4: Validate provenance

Every output theme must reference supporting item IDs. Reject references that are not in the input set.

**Exit criterion:** Smart News can be replayed from stored ranked artifacts with Internet access disabled.

---

# Phase 6 — Rebuild WSB with semantic ranking

## Step 6.1: Extract Reddit retriever

Port OAuth/token/listing logic from `report_wsb.py` into `retrieval/reddit_wsb.py`.

Return normalized `SourceItem`s with metrics.

## Step 6.2: Keep activity features, remove activity-as-final-rank

Keep:

- comments,
- score,
- age,
- listing source,
- ticker extraction.

Replace final `select_top()` with the generic candidate + LLM rank pipeline.

## Step 6.3: Create WSB labelled dataset

This is mandatory because “good WSB content” is subjective and the current algorithm is known to be wrong.

Aim initially for 100–300 labelled posts collected across several days.

## Step 6.4: Evaluate

Target metrics should include:

- top-10 noise rate,
- Precision@10 for `must show/useful`,
- NDCG@10.

Only after the ranker is acceptable add Telegram rendering.

**Exit criterion:** materially lower meme/noise rate than the current heat-score ranking.

---

# Phase 7 — Rebuild Polymarket with semantic ranking

## Step 7.1: Extract API adapter

Port only the provider fetching/parsing logic.

## Step 7.2: Normalize activity

Avoid direct raw-volume domination. Use logarithmic/scaled activity features.

## Step 7.3: Build labelled market set

Label markets based on whether they are worth showing in a macro/market dashboard.

## Step 7.4: Apply tiny LLM ranker

The LLM receives:

- question,
- category/tags,
- probability,
- 24h volume,
- recent trade activity,
- event/end date where available.

It never receives an instruction to forecast outcomes.

**Exit criterion:** top results are consistently macro/market-relevant rather than merely liquid.

---

# Phase 8 — Replace X scraping with Grok social search

## Step 8.1: Delete the legacy assumptions

Do not copy:

- `x_scrape.py`,
- X usernames/passwords,
- browser cookies,
- session import,
- Playwright profile mounts,
- Chromium/Firefox dependencies.

## Step 8.2: OpenRouter/X-search spike

Write one integration test/script that requests a structured social pulse using a Grok 4+ model through OpenRouter with native search.

Verify from the live response:

1. whether X results are included,
2. citations/source URLs are usable,
3. handle/date constraints supported by the current API behave correctly,
4. number of server-side searches is reported,
5. actual cost is acceptable.

Do not build the rest of the pipeline until this is proven.

## Step 8.3: Implement `GrokSocialRetriever`

Return ordinary `SourceItem`/social findings with provenance. Nothing downstream knows that Grok performed retrieval.

## Step 8.4: Schedule conservatively

Start with one run per day. Move to two only if the second run adds useful new information.

**Exit criterion:** useful X/social summary with no X account or browser state on the VPS.

---

# Phase 9 — Add presentation

## Step 9.1: Telegram presenter

Port the useful safe message-splitting behavior from `telegram_utils.py`, but make it consume `ReportArtifact`.

## Step 9.2: Markdown presenter

Every pipeline should render to Markdown locally. This becomes the easiest way to inspect replay/evaluation outputs.

## Step 9.3: Delivery idempotency

Store a delivery key such as:

```text
<run_id>:telegram:<chat_id>:<template_version>
```

A retry of Telegram publishing must not re-run retrieval/ranking.

---

# Phase 10 — Introduce Windmill

Do this **after one pipeline works locally**. Otherwise orchestrator debugging and application debugging become mixed.

## Step 10.1: Deploy Windmill from the private `vps-infra` repo

The private infra repository owns:

- Compose files,
- pinned image versions,
- internal networks,
- reverse proxy/TLS,
- Postgres backup jobs,
- VPS firewall,
- OS/container update procedure,
- infrastructure secret bootstrap.

DailyDash public repo owns no host cron.

## Step 10.2: Secure admin access

Preferred:

- Windmill UI reachable only over Tailscale/WireGuard, or
- strong reverse-proxy authentication + TLS if public access is required.

Change all default credentials before exposure.

## Step 10.3: Configure workers

For DailyDash, use normal Python/TypeScript workers and avoid Docker-socket access unless a future step genuinely requires container execution.

Enable the process isolation options supported by the deployment.

## Step 10.4: Create Windmill resources/secrets

Secrets/resources:

- DailyDash PostgreSQL,
- object-store endpoint/bucket/credentials,
- Telegram bot token/chat ID,
- Reddit client ID/secret,
- model-gateway endpoint + scoped virtual key.

No single workflow receives all of them.

## Step 10.5: Deploy the news flow

Translate the already-working local pipeline stages into a flow. Add:

- retries,
- timeouts,
- source fan-out,
- error branch,
- final metrics step.

## Step 10.6: Add schedules inside Windmill

Once verified, remove the corresponding legacy cron entry. Repeat per migrated pipeline.

**Exit criterion:** `crontab -l` on the VPS contains no DailyDash business schedule.

---

# Phase 11 — Add the model gateway

## Step 11.1: Deploy LiteLLM internally

Deploy it from `vps-infra`, not from the public application stack.

Network:

```text
DailyDash/Windmill worker -> LiteLLM -> OpenRouter -> model providers
```

LiteLLM is not Internet-exposed.

## Step 11.2: Create model aliases

Map logical aliases to upstream models. Keep upstream OpenRouter model names out of pipeline YAML where possible.

## Step 11.3: Create scoped virtual keys/budgets

Separate ranker, synthesis and social search.

## Step 11.4: Repoint `ModelClient`

Only the base URL/API key changes. Pipeline code remains identical.

## Step 11.5: Add spend alerting

Store a daily/monthly spend summary. Alert if a workflow exceeds its normal envelope by a large factor.

**Exit criterion:** the OpenRouter root key is available only to the gateway.

---

# Phase 12 — VPS/data security hardening

## Secrets

- no secrets in public Git,
- no secrets in private Git plaintext,
- use Windmill encrypted secrets for application jobs,
- use SOPS/age or a dedicated secret manager for infrastructure bootstrap files,
- rotate old X/browser credentials because they are no longer needed,
- use separate credentials for application DB and orchestrator DB.

## Containers/processes

- run non-root where supported,
- read-only filesystem for stateless components,
- `cap_drop: [ALL]` where compatible,
- resource limits,
- no privileged containers,
- no host filesystem mounts except required data/config,
- no Docker socket in application jobs,
- internal-only DB/gateway networks.

## Data

- private bucket,
- encryption at rest from storage provider,
- short-lived/scoped object-store credentials where practical,
- lifecycle retention,
- backup the metadata DB,
- do not back up transient raw data forever unless wanted.

## LLM boundary

- ranking/synthesis models have no application tools,
- strict JSON schemas,
- source text is explicitly untrusted content,
- truncate maximum source text lengths,
- no secrets inserted into prompts,
- persist prompt/model version for audit.

## Admin plane

- firewall deny-by-default inbound,
- SSH key-only,
- Tailscale/WireGuard preferred for Windmill/LiteLLM administration,
- reverse proxy only for intentionally public services,
- automated security updates handled by `vps-infra`, not DailyDash.

---

# Phase 13 — CI/CD

## Public application CI

On pull request:

```text
ruff
mypy
pytest unit
pytest contract
secret scan
config/schema validation
ranking eval smoke set
```

On main:

- build/publish application package/image if used,
- deploy/sync Windmill scripts/flows to staging or production through an explicit deployment job,
- never upload production data to GitHub Actions artifacts by default.

Pin dependencies with `uv.lock`.

## Infra CI

Private `vps-infra` validates Compose/config/SOPS files and performs controlled deployment separately.

This means changing a DailyDash prompt does not accidentally modify firewall/host cron, and changing the VPS does not require modifying application code.

---

# Phase 14 — Observability and cost

Add a run summary similar to:

```json
{
  "run_id": "...",
  "pipeline": "news",
  "profile": "news-top",
  "retrieved": 183,
  "normalized": 177,
  "deduped": 121,
  "candidates": 42,
  "selected": 10,
  "source_errors": 2,
  "model_alias": "rank-cheap",
  "model": "...",
  "input_tokens": 6832,
  "output_tokens": 911,
  "search_calls": 0,
  "estimated_cost_usd": 0.0011,
  "duration_seconds": 7.8,
  "delivery": "ok"
}
```

Later add OpenTelemetry traces with `run_id` correlation if desired.

---

# Phase 15 — Decommission legacy components incrementally

Migrate one job at a time.

Recommended order:

1. Top News
2. Alternative News
3. German News
4. Smart News
5. WSB
6. Polymarket
7. Social Pulse / Grok X replacement

For each:

1. run old and new in parallel for several days,
2. compare outputs/evaluation metrics,
3. enable new Telegram publishing,
4. disable old cron,
5. retain old code until stable,
6. eventually archive legacy repo.

Do not migrate the other finance jobs merely for completeness.

---

# Concrete first milestone

The first milestone should be intentionally small:

> **One generic news flow, three profiles, persistent external artifacts, tiny-model ranking, Markdown + Telegram output, and a visible Windmill DAG.**

This single milestone proves almost every architectural idea:

- retrieval/processing/presentation separation,
- data outside Git,
- configuration-driven reuse,
- LLM gateway abstraction,
- cheap semantic ranking,
- workflow orchestration,
- secrets,
- replayability,
- publication.

Only after this is clean should WSB, Polymarket, Smart News and Grok social search be added.

---

# Definition of done for v1

A public v1 is ready when all of the following are true:

- [ ] public repository contains no collected production data,
- [ ] no X browser/session scraping exists,
- [ ] Top/Alternative/German share one news implementation,
- [ ] all four principal layers are separate modules,
- [ ] WSB and Polymarket use evaluated tiny-LLM ranking,
- [ ] Social Pulse uses Grok/OpenRouter search at <=2 scheduled runs/day,
- [ ] model calls use logical aliases and have spend telemetry,
- [ ] model-gateway/root-provider secrets are isolated,
- [ ] all application schedules are in Windmill, not host cron,
- [ ] host operations live in a separate private infra repo,
- [ ] runtime data is in Postgres/object storage, not Git,
- [ ] curated ranking data is private and reproducible,
- [ ] every pipeline can be replayed from stored artifacts,
- [ ] Telegram is only a presentation adapter,
- [ ] CI runs tests, static checks and secret scanning,
- [ ] README contains an architecture diagram and cost/security discussion.
