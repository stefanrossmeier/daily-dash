# Smart News pipeline

Smart News is the theme-oriented DailyDash briefing. It is intentionally separate
from Top, Alternative and German News: those workflows rank individual articles,
while Smart News asks one model call to cluster a broad recent news set into a small
number of macro and cross-market narratives.

## Preserved legacy behavior

The migration preserves the working content/model behavior from the original
`report_news_smart.py` implementation:

- one GPT-5.4-nano logical model call per non-empty run;
- up to 20 items per feed;
- up to 150 articles in the model input;
- at most 5 themes;
- a rolling 18-hour retrieval window;
- the original broad 21-feed Smart News source set;
- source labels, titles and short RSS summaries in the model input;
- the original deterministic macro/narrow-corporate theme filter;
- theme-only Telegram output; supporting headlines stay in the artifact;
- production slots at 07:15, 12:15 and 21:00 Europe/Berlin every day.

The model is reached through the existing `rank-cheap` model-gateway alias, which
resolves to `openai/gpt-5.4-nano`. Provider-level retries and usage/cost accounting
therefore use the same production gateway as the other model-backed News workflows.

## Prompt asset

The migrated prompt is not embedded in Python. It is a versioned asset:

```text
assets/prompts/news-smart/v1/
├── prompt.yaml
├── system.md
└── profiles/news-smart.md
```

`system.md` contains the original Smart News editor/theme instructions, including the
`{max_themes}` placeholder. `profiles/news-smart.md` contains the original final user
instruction appended after the numbered headline block. The artifact persists the
prompt id/version and SHA-256 provenance through its model trace.

## Runtime architecture

The application owns retrieval, input preparation, the model call, deterministic
post-processing, rendering and the immutable artifact contract. Windmill owns
orchestration, scheduling, durable Git persistence and Telegram delivery.

```text
RSS retrieval (18h rolling)
        ↓
exact-link dedupe + newest-first cap (150)
        ↓
GPT-5.4-nano Smart News theme clustering
        ↓
legacy deterministic macro-theme filter
        ↓
immutable artifact: daily-dash-data/news/smart/
        ↓
Git persistence
        ↓
Telegram theme brief
```

The Windmill flow is deliberately ordered:

```text
run_news_smart
→ persist_data
→ deliver_news_smart
```

Persistence failure therefore stops Telegram publication.

## Scheduling

`config/schedules.yaml` is the schedule source of truth. Smart News runs every day at:

```text
07:15
12:15
21:00
Europe/Berlin
```

Unlike the article-ranking News profiles, Smart News intentionally keeps the original
rolling 18-hour retrieval window because overlapping context is part of the theme
clustering behavior. The run artifact records the actual rolling interval and the
nearest configured scheduled slot. Explicit `--window-start` / `--window-end` values
are available for reproducible tests and replays.

## Persistence

Each run writes one immutable JSON artifact under:

```text
daily-dash-data/news/smart/
```

The artifact includes source diagnostics, all retrieved normalized source items, the
150-item-or-smaller model input set, raw structured model themes, final filtered
Smart News themes with original supporting headline URLs, the retrieval window and
model/prompt/usage provenance.
