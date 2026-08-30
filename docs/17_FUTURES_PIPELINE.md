# Futures Snapshot pipeline

The Futures Snapshot is a Windmill-native translation of the historical DailyDash
TradingView report. The market-data behavior is intentionally preserved rather than
redesigned: the same TradingView continuous-futures symbols are retrieved through
`tvDatafeed`, the same 1-hour/daily-bar fallback logic is used, and the same compact
Telegram table is rendered.

The pipeline is deterministic and makes **no LLM calls**:

```text
TradingView retrieval -> deterministic processing -> persisted snapshot -> presentation -> delivery
```

Windmill executes the production boundary as:

```text
run_futures -> persist_data -> deliver_futures
```

Telegram delivery cannot occur before the immutable JSON snapshot has been written and
committed by the persistence step.

## TradingView dependency and access

DailyDash pins the same library used by the historical implementation:

```text
tradingview-datafeed==2.1.1
```

The historical report did not require a TradingView account. It constructed
`TvDatafeed()` without credentials and used the library's anonymous/public TradingView
access. The Windmill translation preserves that behavior exactly: there are no
TradingView username/password settings, Windmill variables, or secrets.

`tvDatafeed` 2.1.1 still performs the history retrieval, but its quote-session setup
contains two calls that TradingView's current anonymous protocol rejects. DailyDash
wraps the library with a narrow compatibility subclass: the obsolete third
`force_permission` argument is removed from `quote_add_symbols`, and the obsolete
`quote_fast_symbols` message is suppressed. All other `tvDatafeed` messages and
`get_hist()` behavior are delegated unchanged. This compatibility is covered by a
regression test because it depends on a private upstream protocol.

No retrieved TradingView values are committed to the public application repository.
Generated snapshots are written through the separately configured DailyDash data-repo
persistence boundary.

## Contract universe

`config/sources/futures.yaml` is the source of truth for the exact legacy universe and
its display precision:

| Row | TradingView contract |
| --- | --- |
| S&P | `CME_MINI:ES1!` |
| Nasdaq | `CME_MINI:NQ1!` |
| Dow | `CBOT_MINI:YM1!` |
| Stoxx50 | `EUREX:FESX1!` |
| DAX | `EUREX:FDAX1!` |
| Stoxx600 | `EUREX:FXXP1!` |
| HSI | `HKEX:HSI1!` |
| Nikkei | `CME:NIY1!` |
| MSCI World | `ICEUS:MWL1!` |
| CSI500 | `CFFEX:IC1!` |
| EURUSD | `CME_MINI:E71!` |
| EURCHF | `CME:RF1!` |
| US 10Y | `CBOT_MINI:10Y1!` |
| Schatz | `EUREX:FGBS1!` |
| Gold | `COMEX:GC1!` |
| Silver | `COMEX:SI1!` |
| Brent | `NYMEX:BZ1!` |
| WTI | `NYMEX:CL1!` |
| Bitcoin | `CME:BTC1!` |
| Ethereum | `CME:ETH1!` |

The symbols ending in `1!` are TradingView continuous contracts. DailyDash records the
configured `EXCHANGE:SYMBOL` in each raw quote so persisted artifacts remain auditable.

## Retrieval semantics

For every configured row the retriever asks TradingView for:

```text
300 x 1-hour bars
30  x daily bars
```

Each history call has two attempts, matching the historical report.

The current value is selected as follows:

1. use the latest 1-hour close when that bar is at most three days old;
2. otherwise fall back to the latest daily close;
3. if neither history is available, keep the row unavailable and continue the report.

A failure in one symbol does not fail the whole snapshot. The error is stored with that
row and becomes a bounded `Data issues` section in the Telegram report, as in the old
implementation. If the `tvDatafeed` runtime itself cannot initialize, all rows degrade
to unavailable values so the run can still persist an auditable artifact.

## Percentage change

The report preserves the legacy definition:

```text
Δ% = (last / prior_daily_close - 1) * 100
```

When a current 1-hour bar and the newest daily bar refer to the same/newer Berlin
calendar date, DailyDash uses the second-newest daily close as the reference. When the
1-hour quote predates the most recent available daily date, the newest daily close is
the reference. If intraday data is stale and the latest daily close becomes `last`, the
previous daily close is used.

## Presentation

The Telegram output intentionally matches the old report shape:

```text
Futures Snapshot  (YYYY-MM-DD HH:MM Berlin)

Asset          Last       Δ%
...

TradingView 1h bars. Δ% vs prior daily close.
```

Unavailable values render as an em dash. At most eight row-level data issues are shown.
Internal provenance remains in the JSON artifact and is not added as extra table columns.

## Schedule

The historical weekday cadence is restored exactly in `config/schedules.yaml`:

```text
05:00
07:15
12:30
23:00
Europe/Berlin, Monday-Friday
```

Windmill schedule YAML is generated from that central registry. Do not edit production
schedule files manually.

## Local verification

After dependency/config changes rebuild the DailyDash worker, run the canonical project
gate, and synchronize the checked-in Windmill workspace:

```bash
./scripts/check.sh
./scripts/local-windmill.sh rebuild
./scripts/local-windmill.sh health
./scripts/sync-windmill-workspace.sh
```

For a direct non-delivery smoke run against the private data sink:

```bash
uv run python -m daily_dash.commands.futures run \
  --profile futures \
  --data-repo ../daily-dash-data
```

No TradingView account variables are required. The production acceptance test should
still be the Windmill flow because that exercises the required
`run -> persist -> deliver` ordering.
