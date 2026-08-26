# Markets Pipeline

## Status

**Implemented and verified with live market data.**

The Markets pipeline is the first complete DailyDash vertical slice in the new architecture.

It replaces the behavior behind the legacy `run_markets.sh`, while deliberately not migrating legacy shell orchestration, Docker invocation, cron, locking, timeout, or file-based logging.

## Architecture

~~~text
config/profiles/markets.yaml
config/sources/markets.yaml
          │
          ▼
┌────────────────────────┐
│ Retrieval              │
│                        │
│ YahooFinanceRetriever  │
└────────────┬───────────┘
             │
             ▼
      RawMarketSnapshot
             │
             ▼
┌────────────────────────┐
│ Processing             │
│                        │
│ price/change handling  │
│ ATH calculations       │
│ degraded data handling │
└────────────┬───────────┘
             │
             ▼
       MarketReportData
             │
             ▼
┌────────────────────────┐
│ Presentation           │
│                        │
│ Markets renderer       │
└────────────┬───────────┘
             │
             ▼
        ReportArtifact
             │
        ┌────┴────┐
        ▼         ▼
     stdout    Telegram
~~~

The pipeline itself does not know how Telegram works, and Telegram delivery does not know how market data was retrieved or processed.

## Implementation boundaries

~~~text
src/daily_dash/retrieval/markets.py
    Yahoo Finance interaction

src/daily_dash/processing/markets.py
    market calculations and transformation

src/daily_dash/presentation/markets.py
    report rendering

src/daily_dash/pipelines/markets.py
    composition of the pipeline stages

src/daily_dash/delivery/telegram.py
    Telegram Bot API interaction
~~~

## Configuration

Market instruments and ATH proxy configuration are externalized into:

~~~text
config/profiles/markets.yaml
config/sources/markets.yaml
~~~

The market universe can therefore change without modifying retrieval, processing, or presentation code.

## Preserved legacy behavior

The first implementation preserves the useful behavior behind the old `run_markets.sh` market report:

- current market snapshot;
- percentage change relative to previous close;
- Yahoo Finance retrieval fallbacks;
- distance-to-all-time-high calculations;
- separate ATH proxy symbols where needed;
- partial/degraded reports when individual instruments fail;
- compact Telegram-friendly presentation.

The following legacy operational concerns are intentionally excluded:

- `run_markets.sh`;
- `flock`;
- host cron;
- Docker Compose invocation;
- shell-level timeout handling;
- shell/file log management.

These belong to orchestration, deployment, and observability rather than the application pipeline.

## Running

Run the complete repository quality gate:

~~~bash
./scripts/check.sh
~~~

Run Markets locally:

~~~bash
uv run daily-dash markets
~~~

Send the Markets report through Telegram:

~~~bash
uv run daily-dash markets --delivery telegram
~~~

## First verified live run

The first successful live-data execution of the new pipeline was performed on **August 26, 2026 at 23:38 local time**.

Command:

~~~bash
uv run daily-dash markets
~~~

Output:

~~~text
*Market Snapshot*  _(2026-08-26 23:38)_

Asset        Last       Δ% vs Close
----------   --------   -----------
DAX          26299.47   +0.25%
EuroStx50     6470.74   +0.16%
Stoxx600       656.41   -0.04%
MSCI World     126.68   +0.11%
MSCI EM         47.40   +0.55%
Nikkei       66170.00   -0.19%
HangSeng     25652.97   +0.56%
S&P500        7710.00   +0.26%
Nasdaq100    29432.50   +0.57%
Dow          53727.00   +0.09%
EURUSD         1.1658   -0.20%
DXY             99.14   +0.17%
VIX             15.21   🔴-1.55%
WTI             81.91   🟢+2.04%
Brent           86.56   🟢+1.62%
Gold          4647.80   🔴-1.13%
Silver          68.08   🔴-1.70%
BTC          78771.56   +0.31%
ETH           2498.23   🟢+2.28%

Distance to ATH

Asset        Dist
----------   -------
DAX           -0.58%
Stoxx600      -0.62%
MSCI World    -1.21%
MSCI EM       -5.67%
S&P500        -1.58%
Brent        -32.36%
Gold         -12.61%
Bitcoin      -36.86%
~~~

These values document one successful real-data execution. They are not fixtures or expected future market values.

Tests should verify calculations, contracts, fallback behavior, rendering rules, and error handling using deterministic test data.

## Security

No credentials belong in market configuration.

For local Telegram delivery the application expects:

~~~text
DAILY_DASH_TELEGRAM_TOKEN
DAILY_DASH_TELEGRAM_CHAT_ID
~~~

Local values may be stored in the Git-ignored `.env` file.

Production secrets will later be injected through the orchestration and secret-management layer.

## Architectural significance

Markets is the first reference implementation for the new DailyDash architecture:

~~~text
retrieve
   ↓
normalize / process
   ↓
present
   ↓
deliver
~~~

Subsequent pipelines should preserve the same separation where appropriate.
