# Deployment checklist

This checklist is the final repository-side gate before deploying DailyDash to a
persistent Windmill host. It complements the detailed bootstrap procedure in
`docs/09_LOCAL_WINDMILL_BOOTSTRAP.md`.

## 1. Repository gate

Run from the repository root:

```bash
npm ci
./scripts/check-tools.sh
./scripts/format.sh
git diff --check
./scripts/check.sh
```

`./scripts/check.sh` is the canonical code gate. It synchronizes the locked Python
environment, verifies formatting/Ruff/mypy, runs the complete pytest suite with branch
coverage, runs the model-gateway tests, validates configuration, and builds the Python
package. Review the coverage report for meaningful gaps; deployment-critical contracts,
presentation, persistence ordering and gateway boundaries should be covered by tests
rather than relying only on the aggregate percentage.

## 2. Local/runtime secrets

The public repository must not contain secret values. Verify that the deployment has:

```text
OpenRouter API key        -> model gateway only
Telegram bot token/chat   -> delivery steps only
data-repo deploy key/URL  -> persistence step only
Reddit OAuth values       -> WSB run step only
```

X Watchlist requires no X login, cookies or browser state. Grok accesses X through the
model gateway.

Futures requires no TradingView account secret; it preserves the legacy anonymous
`TvDatafeed()` access path.

## 3. Rebuild and health-check the runtime

For the standard adjacent local deployment directory:

```bash
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh rebuild
DAILY_DASH_WINDMILL_DIR=../daily-dash-windmill-local ./scripts/local-windmill.sh health
```

## 4. Synchronize checked-in Windmill state

```bash
./scripts/sync-windmill-workspace.sh
```

This regenerates derived News flows and schedule files, runs the Windmill flow/schedule
contract tests, and pushes the checked-in workspace definitions. Do not make production-
only flow edits in the Windmill UI.

## 5. Verify schedule registry

`config/schedules.yaml` is authoritative. Confirm the intended `Europe/Berlin` slots in
`docs/SCHEDULING.md`, especially:

```text
Futures      05:00, 07:15, 12:30, 23:00 Monday-Friday
WSB          20:35 daily
Polymarket   20:45 daily
X Watchlist  08:20 and 20:20 daily
```

News/Markets/Yields schedules are also generated from the same registry.

## 6. End-to-end smoke tests

Use Windmill so the production ordering is exercised:

```text
run -> persist -> deliver
```

At minimum, manually run representative flows after the deployment is synchronized:

```bash
cd workflows/windmill
../../scripts/wmill.sh flow run f/daily_dash/news_top
../../scripts/wmill.sh flow run f/daily_dash/futures
../../scripts/wmill.sh flow run f/daily_dash/wsb
../../scripts/wmill.sh flow run f/daily_dash/polymarket
../../scripts/wmill.sh flow run f/daily_dash/x_watchlist
```

Also verify Markets/Yields and one of German/Alternative News if those sources are
reachable from the target host. Futures is also a useful TradingView WebSocket/network
smoke test because it exercises the exact production anonymous tvDatafeed path.

For every smoke test, confirm:

- a compact immutable JSON artifact is persisted to `daily-dash-data` before delivery;
- Telegram contains reader-facing report content, not model scores/rationales/internal
  selection diagnostics;
- empty reports send a clear empty-state message instead of a blank Telegram message;
- model traces record resolved model, tokens, exact cost, latency and attempts;
- no Telegram, Reddit or data-repository secret appears in the artifact/logs.

## 7. Final Git state

Before deploying a revision, ensure the public source revision is reproducible and clean:

```bash
git status --short
git log -1 --oneline
```

Deploy the committed revision, not an uncommitted local working tree.
