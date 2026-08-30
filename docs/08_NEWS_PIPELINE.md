# News Pipeline

## Status

News implements live RSS/Atom retrieval, deterministic hygiene, a shared
source-neutral candidate cap, one versioned rich LLM ranking call, deterministic
selection, and immutable JSON run artifacts.

Telegram delivery and Windmill scheduling are wired after live ranking behavior
has been inspected.

## Profiles and source configuration

The implementation is shared by:

- `news-top`
- `news-alternative`
- `news-german`

Each profile owns runtime policy in `config/profiles/<profile>.yaml` and
references a source set in `config/sources/<source-set>.yaml`.

Source membership therefore changes independently from retrieval, prompt,
model, ranking, presentation, and delivery code. The initial source sets are
deliberately conservative and migrated from the legacy DailyDash. They are a
starting point, not a completeness claim.

`weight` remains for source-config compatibility but News v1 does not use it
to determine semantic importance. Tags are descriptive metadata only.

## Pipeline

    configured source set
          |
          v
    RSS/Atom retrieval
          |
          v
    normalized SourceItem
          |
          v
    age filtering
          |
          v
    URL/title deduplication
          |
          v
    source-neutral candidate cap (max 150)
          |
          v
    one versioned rich ranking call
          |
          v
    model gateway (same-model retries only)
          |
          v
    structured ranking
          |
          v
    deterministic selection / event suppression
          |
          v
    immutable JSON output sink

## Keywords

Production News v1 performs no positive keyword ranking. Keyword arrays remain
empty so a legacy keyword baseline can later be implemented as an evaluation
mode against the LLM ranker.

The deterministic candidate cap performs no semantic keyword scoring.

## Source-neutral candidate cap

All three News profiles use the same `ranking.candidate_limit` of 150. After
URL/title deduplication, candidates are ordered deterministically by recency and
internal ID and capped only if the deduplicated pool exceeds that limit.

Publisher identity and source weights do not influence the cap. This is capacity
control, not an importance score. Under normal feed volume no truncation is
expected.

## Versioned prompts

The current prompt lives under:

    assets/prompts/news-ranking/v11/

Older versions remain checked in for reproducibility. Profiles reference the prompt by ID and version. Every run records prompt ID,
version, profile, and SHA-256 hashes for the system, profile, versioned task template, and combined
prompt text.

## Model gateway

News uses only the configured model alias, initially `rank-cheap`. Provider
model IDs and the OpenRouter credential remain behind the model gateway.

The ranker captures resolved model, provider, generation ID, token usage, exact
reported cost, latency, logical call count, provider attempt count and retries.

A normal News run performs exactly one logical model call. `rank-cheap` allows
one initial provider attempt plus at most two retries of the same model. There is
no application-level second full ranking/repair request.

## Ranking output

Prompt v9 evaluates every opaque candidate slot exactly once and returns:

- `rank_score`;
- `event_key` and `duplicate_of_slot`;
- tier and priority;
- relevance;
- market impact and market breadth;
- surprise;
- information quality;
- novelty;
- `selected`;
- one concise rationale.

The model does not reproduce internal candidate IDs or article URLs. DailyDash
resolves slots back to the original candidates, constructs a deterministic
ordering from the returned judgments and suppresses duplicate event coverage.
For Alternative and German, `selected=false` is ineligible for publication. Top
keeps its additional transparent broad-market eligibility policy. No profile is
forced to fill `presentation.max_items`.

## Storage

Persistence is a write-only output sink for the News run. Retrieval, schedule
resolution, candidate selection and ranking do not read prior persisted News
artifacts or use persistence as control state.

Run artifacts are written to the private data repository:

    news/top/<UTC timestamp>_<run-id>.json
    news/alternative/<UTC timestamp>_<run-id>.json
    news/german/<UTC timestamp>_<run-id>.json

Artifacts contain source diagnostics, normalized candidates, counts, complete
ranking output, selected IDs, prompt identity/hashes, model identity, usage,
cost, and latency.

## Failure behavior

Individual source failures degrade a run and are recorded in diagnostics. A run
fails if every enabled source fails or if no candidates remain.

Network health is intentionally not part of CI.

Check live source health with:

    ./scripts/check-news-sources.py --profile news-top
    ./scripts/check-news-sources.py --profile news-alternative
    ./scripts/check-news-sources.py --profile news-german

Add `--strict` when any source failure should result in a non-zero exit code.

## Testing

CI is deterministic and internet-independent. It tests:

- typed profile/source configuration;
- prompt references;
- RSS fixture parsing and age filtering;
- HTML cleanup;
- URL canonicalization;
- title/URL deduplication;
- source-neutral candidate capping;
- gateway ranker behavior with a fake structured client;
- prompt/model/cost trace capture;
- storage paths.

Real feed reachability and real OpenRouter ranking are separate integration
checks.

## Live ranking

With the model gateway reachable:

    ./scripts/run-live-news.py       --profile news-top       --data-repo ../daily-dash-data

Run the equivalent command for `news-alternative` and `news-german`.

## Windmill and delivery

The same application pipeline is used by Top, Alternative and German. Windmill
orchestrates run -> persistence -> Telegram. Persistence is a sink only; it is
not consulted to determine retrieval windows, ranking inputs or later run
behavior.

## Semantic output validation and retry ownership

Provider structured-output validation guarantees JSON structure but DailyDash
still validates local cross-item invariants such as slot coverage and duplicate
references.

The production rule is deliberately simple:

- DailyDash sends one complete rich-ranking request;
- the model gateway owns transient provider retries;
- `rank-cheap` permits one initial attempt plus at most two same-model retries;
- a response that reaches DailyDash but fails local semantic validation fails the
  run explicitly;
- DailyDash does not issue a second full ranking request to repair it.

The persisted model summary distinguishes `calls`, `attempts` and `retries`, so
a normal run is `1 / 1 / 0`, while a successful request after two gateway retries
is `1 / 3 / 2`. If a failed provider attempt prevents authoritative usage from
being known, `usage_complete` remains false rather than claiming exact cost.

## Ranking output contract v2

The initial `news-ranking/v1` experiment asked the model to return a complete
ordered array of internal candidate IDs.

Live testing showed that this is unnecessarily brittle for large candidate
batches: a model can return structurally valid JSON while duplicating one ID
inside a long permutation.

`news-ranking/v2` removes that responsibility from the model.

DailyDash assigns candidates temporary slots:

    C001
    C002
    ...
    C060

The structured-output schema contains one required property for every slot.

The model evaluates each fixed slot with:

- tier;
- priority;
- relevance;
- market impact;
- surprise;
- quality;
- novelty;
- selected;
- rationale.

The model does not reproduce internal candidate IDs and does not return an
ordered ID array.

DailyDash constructs the final ranking deterministically using:

1. tier, descending;
2. priority, descending;
3. market impact, descending;
4. surprise, descending;
5. relevance, descending;
6. novelty, descending;
7. quality, descending;
8. internal ID as a deterministic final tie-breaker.

This makes candidate coverage structural rather than dependent on the model
correctly reproducing a long opaque-ID permutation.

`v1` remains in the repository as a reproducible historical prompt asset.

If a model call must be retried, token usage, cost and latency are accumulated
across all attempts so the persisted run cost reflects the complete model
expense.

## Initial live validation

The first successful end-to-end `news-top` run using
`news-ranking/v2` processed:

- 89 retrieved articles;
- 80 articles after URL/title deduplication;
- 60 LLM ranking candidates;
- 12 final presentation items.

The run used the `rank-cheap` model alias, which resolved to
`openai/gpt-5.4-nano`.

Observed model metrics for this run:

- model cost: approximately $0.008;
- model latency: approximately 26 seconds.

The run demonstrated that the v2 slot-based output contract avoids the
candidate-ID permutation failures encountered during the v1 live experiment.

The first result also exposed areas for further evaluation rather than
immediate prompt changes:

- multiple independently written articles about the same underlying event can
  survive title/URL deduplication and occupy several final positions;
- some anecdotal stories may receive higher market-impact scores than expected;
- ranking stability must be measured across repeated runs and additional
  profiles.

These observations are intentionally retained as evaluation findings. Prompt
v2 remains unchanged until more live evidence is collected from Top,
Alternative and German News.

## LLM-owned ranking and original article links

`news-ranking/v3` makes the ranking responsibility explicit.

The model returns a `rank_score` for every candidate. This is the model's final
overall ordering judgment. DailyDash orders candidates primarily by this LLM
score. Other LLM-generated dimensions are used only as deterministic
 tie-breakers when scores are equal.

DailyDash does not use a hand-written semantic scoring formula to replace the
model's ranking decision.

The model is deliberately not given the article URL and does not return a URL.
The original URL stays attached to the normalized `SourceItem` retrieved from
the publisher feed.

After event-level duplicate suppression, presentation resolves every selected
ID back to that original `SourceItem` and renders its stored URL. Telegram links
therefore come from retrieval data, not model output.

This boundary is tested explicitly:

- model ranking input contains no article URL;
- the model output schema contains no URL;
- the Telegram renderer uses the original `SourceItem.url`;
- HTML escaping is applied to titles, source names and link attributes.

## Telegram delivery

News is rendered as Telegram HTML. Each selected headline is a clickable link
to the original publisher article and is followed by the publisher/source
name.

The shared `TelegramDelivery` supports a configurable parse mode. Its existing
default remains Markdown for Markets; News uses HTML.

The app-owned News command supports two separate operations:

    python -m daily_dash.commands.news run ...
    python -m daily_dash.commands.news deliver --artifact ...

This split is intentional. Windmill can persist the run artifact before sending
Telegram, so a delivered report has already been committed to the data
repository.

## Windmill ordering and Git persistence

The intended News flow is:

    run_news
       |
       v
    persist_data_repo
       |
       v
    deliver_news

`run_news` owns no orchestration logic. It calls the DailyDash application and
returns the immutable artifact path.

`persist_data_repo` is the existing generic Git persistence step and is reused
unchanged for News. The application itself does not contain Git credentials or
Git push logic.

`deliver_news` reads the already-persisted JSON run artifact, resolves the
selected original article URLs, renders Telegram HTML and sends it using the
existing Windmill Telegram secrets.

Keeping persistence before delivery ensures that a successful Telegram report
has a durable audit artifact in `daily-dash-data` first.

Each immutable News run artifact contains both sides of the output contract:

- `retrieved_items`: the complete normalized retrieval result for the resolved
  time window, before deterministic deduplication or the candidate cap;
- `candidates`: the deduplicated/capped items actually presented to ranking;
- `ranking`: the full model evaluation and ranking for those candidates;
- `selected_ids`: the ordered final selection used for presentation.

This makes `daily-dash-data` a complete write-only audit sink. Production News
execution never reads earlier persisted runs to determine retrieval windows,
ranking, selection, or delivery.

## Canonical event identity — ranking v4

The first live v3 run successfully demonstrated LLM-owned ranking through
`rank_score`, original article URL provenance, structured ranking output and
deterministic event suppression.

It also exposed an event-identity failure.

Two articles covering the same Salesforce earnings release received different
event keys because one article described the earnings and immediate stock
reaction while another described Wall Street's reaction to the same earnings.

The model correctly recognized the subject matter but encoded article framing
rather than the underlying catalyst into `event_key`.

`news-ranking/v4` therefore strengthens event identity without changing the
ranking architecture or structured-output contract.

The v4 rule is:

- event identity represents the underlying catalyst;
- earnings reports, share-price reactions and analyst reactions to the same
  earnings release normally share one event key;
- publisher-specific framing is excluded from event identity;
- genuinely separate developments involving the same company remain separate;
- event grouping must not influence `rank_score`.

The application still does not perform semantic ranking. The LLM owns
`rank_score`. DailyDash only selects the highest-ranked representative of each
model-assigned event.

Prompt v3 remains unchanged so that its live result remains reproducible.

## Explicit same-event relationships — ranking v5

Live v4 validation showed that canonical free-form event keys alone were not
reliable enough for duplicate suppression.

Several articles driven by the same Nvidia earnings catalyst received
different event keys because they described different downstream reactions,
including equity-index moves, futures moves and broader AI sentiment.

`news-ranking/v5` therefore introduces `duplicate_of_slot`.

The LLM now makes separate judgments for:

- `rank_score`: the final semantic ranking judgment;
- `event_key`: a human-readable event identity;
- `duplicate_of_slot`: an explicit same-underlying-catalyst relationship.

DailyDash converts `duplicate_of_slot` from temporary model slots to persisted
internal candidate IDs.

Duplicate groups are formed only from model-provided semantic signals:

- explicit `duplicate_of_slot` relationships;
- exact normalized `event_key` matches.

DailyDash does not independently determine semantic similarity.

Within a duplicate group, the first article in the LLM `rank_score` ordering
is retained. Lower-ranked members are suppressed and recorded in the run
artifact.

Original publisher URLs remain excluded from the model request and response.
Telegram presentation resolves URLs from the original persisted `SourceItem`.

The Telegram report is intentionally presentation-only: ranking scores, rationales,
and duplicate-suppression diagnostics remain in the immutable artifact and are not
shown to the reader. When a News profile selects no items, the report still sends a
short empty-state message explaining that no relevant new articles were found in the
report window. German News uses the equivalent German message.

### Initial live v5 validation

The first live `news-top` run using `news-ranking/v5` processed:

- 85 retrieved articles;
- 78 articles after deterministic URL/title deduplication;
- 60 LLM candidates;
- 5 LLM-identified same-event duplicates.

The model alias resolved to `openai/gpt-5.4-nano`.

Observed model metrics:

- cost: approximately $0.0127;
- latency: approximately 73 seconds.

Unlike v3 and v4, v5 successfully identified duplicate coverage even when
articles used different event-key wording.

This validates the separation of responsibilities:

- the LLM owns `rank_score`;
- the LLM identifies semantic same-event relationships;
- DailyDash deterministically applies those relationships;
- DailyDash retains the highest LLM-ranked representative;
- original article URLs remain outside the model contract.

The v5 ranking prompt is frozen pending broader evaluation across captured
Top, Alternative and German batches.
