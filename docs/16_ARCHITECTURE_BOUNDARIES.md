# Architecture Boundaries

DailyDash separates external acquisition, deterministic/model processing, persistence, presentation, and delivery.

```text
retrieval -> processing / llm -> pipeline artifact -> persistence -> presentation -> delivery
```

Windmill owns orchestration and the `run -> persist -> deliver` sequence. Application pipelines never render Telegram output or deliver messages.

## Layer responsibilities

- `retrieval/`: external source access and source-specific normalization. It may not import processing, presentation, storage, pipelines, or delivery. X Watchlist is the deliberate exception that uses the model gateway because Grok X Search is the source adapter itself.
- `llm/`: model I/O, structured response schemas, and local validation of model responses. It may not depend on retrieval, processing, presentation, storage, pipelines, or delivery.
- `processing/`: deterministic domain logic only. It consumes contracts/config/policy assets and has no external I/O.
- `pipelines/`: orchestration of retrieval, LLM calls, processing, and immutable storage. It never renders or delivers reports.
- `presentation/`: pure rendering from persisted contracts plus presentation configuration. Display limits live here, not in retrieval or semantic processing.
- `commands/`: runtime adapters that invoke a pipeline or render/deliver an already-persisted artifact.

These dependency rules are enforced by `tests/contract/test_architecture_boundaries.py`.

## Versioned prompt assets

Stable semantic/model instructions do not live in Python. Active model prompts use:

```text
assets/prompts/<prompt-id>/<version>/
  prompt.yaml
  system.md
  task.md
  profiles/*.md
```

`system.md` and profile files contain editorial/model behavior. `task.md` contains the stable request protocol. Python supplies only runtime values such as candidate JSON, slot identifiers, date ranges, or account handles.

The prompt loader hashes the system, profile, and task assets into the model trace. Prompt manifests can also declare structured-response contract metadata instead of making Python infer behavior from numeric prompt versions.

## Versioned deterministic policy assets

Substantive deterministic editorial policy also lives outside source where appropriate. Smart News uses:

```text
assets/policies/news-smart-macro/v1/policy.yaml
```

The asset contains macro/narrow-corporate terms, scoring weights, and eligibility thresholds. The persisted Smart News artifact records the policy id, version, and SHA-256 hash.

## Presentation limits versus processing limits

Processing uses ranking limits (`ranking.top_k`) and lane-specific processing limits (`hot.max_items`). Presentation uses `presentation.max_*` only when rendering the persisted result. This keeps display policy from changing retrieval/model behavior.

## Markets command boundary

The old convenience path that retrieved, rendered, and optionally delivered Markets in one process was removed. Markets now follows the same production contract as every other report:

```text
run/persist -> load persisted artifact -> render/deliver
```
