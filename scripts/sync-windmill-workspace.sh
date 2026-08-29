#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="${DAILY_DASH_WINDMILL_WORKSPACE:-daily-dash-local}"

cd "$ROOT"

uv run python scripts/generate-news-windmill-flows.py >/dev/null
uv run python scripts/render-windmill-schedules.py >/dev/null

uv run pytest -q \
  tests/contract/test_news_windmill_flows.py \
  tests/contract/test_x_watchlist_windmill_flow.py \
  tests/contract/test_windmill_schedules.py

cd "$ROOT/workflows/windmill"
"$ROOT/scripts/wmill.sh" sync push --workspace "$WORKSPACE" --yes

echo
echo "Windmill definitions synchronized to workspace: $WORKSPACE"
