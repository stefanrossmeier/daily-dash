#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_REPO="${DAILY_DASH_POLYMARKET_TEST_DATA_REPO:-/tmp/daily-dash-polymarket-test}"
GATEWAY_URL="${DAILY_DASH_MODEL_GATEWAY_URL:-http://127.0.0.1:18080}"

"$ROOT/scripts/check.sh"
uv run python -m daily_dash.commands.polymarket check-api --config-dir "$ROOT/config"
curl --fail --silent --show-error "$GATEWAY_URL/health" >/dev/null

echo "Polymarket public APIs: ok"
echo "Model gateway: ok ($GATEWAY_URL)"
echo "Test artifact root: $DATA_REPO"

rm -rf "$DATA_REPO"
uv run python -m daily_dash.commands.polymarket run \
  --config-dir "$ROOT/config" \
  --data-repo "$DATA_REPO" \
  --gateway-url "$GATEWAY_URL"

ARTIFACT="$(find "$DATA_REPO/polymarket/snapshots" -type f -name '*.json' | sort | tail -1)"
if [[ -n "$ARTIFACT" ]]; then
  BYTES="$(wc -c < "$ARTIFACT" | tr -d ' ')"
  echo "Polymarket artifact: $ARTIFACT ($BYTES bytes)"
fi
