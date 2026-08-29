#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_WINDMILL_DIR="$(cd "$ROOT/.." && pwd)/daily-dash-windmill-local"
WINDMILL_DIR="${DAILY_DASH_WINDMILL_DIR:-$DEFAULT_WINDMILL_DIR}"
SECRET_DIR="$WINDMILL_DIR/secrets"
DATA_REPO="${DAILY_DASH_WSB_TEST_DATA_REPO:-/tmp/daily-dash-wsb-test}"
GATEWAY_URL="${DAILY_DASH_MODEL_GATEWAY_URL:-http://127.0.0.1:18080}"

read_required() {
  local name="$1"
  local path="$SECRET_DIR/$name"
  if [[ ! -s "$path" ]]; then
    echo "ERROR: required WSB configuration file is missing or empty: $path" >&2
    echo "Run: DAILY_DASH_WINDMILL_DIR=\"$WINDMILL_DIR\" ./scripts/configure-wsb-reddit.sh" >&2
    exit 2
  fi
  cat "$path"
}

export DAILY_DASH_REDDIT_CLIENT_ID="${DAILY_DASH_REDDIT_CLIENT_ID:-$(read_required reddit_client_id)}"
export DAILY_DASH_REDDIT_CLIENT_SECRET="${DAILY_DASH_REDDIT_CLIENT_SECRET:-$(read_required reddit_client_secret)}"
export DAILY_DASH_REDDIT_USER_AGENT="${DAILY_DASH_REDDIT_USER_AGENT:-$(read_required reddit_user_agent)}"

"$ROOT/scripts/check.sh"
uv run python -m daily_dash.commands.wsb check-reddit --config-dir "$ROOT/config"
curl --fail --silent --show-error "$GATEWAY_URL/health" >/dev/null

echo "Reddit OAuth: ok"
echo "Model gateway: ok ($GATEWAY_URL)"
echo "Test artifact root: $DATA_REPO"

rm -rf "$DATA_REPO"
uv run python -m daily_dash.commands.wsb run \
  --config-dir "$ROOT/config" \
  --data-repo "$DATA_REPO" \
  --gateway-url "$GATEWAY_URL" \
  "$@"
