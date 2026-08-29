# Yield Report

The `yields` pipeline is a deterministic, no-LLM report built from official public statistical providers.

## Active sources

- US 3M / 2Y / 10Y: FRED (`DGS3MO`, `DGS2`, `DGS10`)
- Germany 2Y / 10Y: Deutsche Bundesbank daily Svensson term structure
- Euro-area AAA 3M / 2Y / 10Y: ECB daily yield-curve spot rates
- Euro-area all-ratings 10Y: ECB daily yield-curve spot rate

Stooq, Yahoo Finance, TradingView and lagged monthly-release sovereign datasets are intentionally not used by this pipeline.

## Financial-stress signal

The active report shows the ECB all-ratings 10Y minus ECB AAA 10Y spread as a current, official euro-area sovereign-risk proxy.

Cross-market and term spreads are always calculated from observations that share the same business date. Spread changes use the previous common observation date, avoiding comparisons between mismatched market dates.

Individual provider failures are preserved as visible data issues. The pipeline fails only when every configured yield series is unavailable.

## Deferred sovereign spreads

The following high-value stress indicators are intentionally deferred until DailyDash has a stable daily source with acceptable automated-use and redistribution terms:

- Italy 10Y minus Germany 10Y (BTP-Bund)
- France 10Y minus Germany 10Y (OAT-Bund)

When such a source is added, both spreads should use same-date observations and expose both the current spread and its change from the previous common business date.

## Runtime order

```text
run_yields
-> persist_data
-> deliver_yields
```

Telegram publication therefore happens only after the immutable JSON artifact has been committed and pushed by the persistence step.

## Schedule

Weekdays in `Europe/Berlin`:

- 10:03
- 18:03

These match the historical DailyDash cadence.
