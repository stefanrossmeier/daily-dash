#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_WINDMILL_DIR="$(cd "$ROOT/.." && pwd)/daily-dash-windmill-local"
WINDMILL_DIR="${DAILY_DASH_WINDMILL_DIR:-$DEFAULT_WINDMILL_DIR}"
PUSH_WINDMILL=0
SKIP_CHECK=0

usage() {
  cat <<USAGE
Usage: $0 [--windmill-dir PATH] [--windmill] [--no-check]

Configure approved Reddit Data API credentials for the WSB pipeline.
Credentials are stored as one-value files under WINDMILL_DIR/secrets, never in
DailyDash .env files.

  --windmill-dir PATH  Generated local Windmill runtime directory
                       (default: $WINDMILL_DIR)
  --windmill           Also upload the values to the configured Windmill workspace
  --no-check           Save/upload without making the OAuth validation request
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --windmill-dir)
      WINDMILL_DIR="$2"
      shift 2
      ;;
    --windmill)
      PUSH_WINDMILL=1
      shift
      ;;
    --no-check)
      SKIP_CHECK=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SECRET_DIR="$WINDMILL_DIR/secrets"
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

read_secret_file() {
  local name="$1"
  local path="$SECRET_DIR/$name"
  if [[ -f "$path" ]]; then
    cat "$path"
  fi
}

write_secret_file() {
  local name="$1"
  local value="$2"
  local path="$SECRET_DIR/$name"
  printf '%s' "$value" > "$path"
  chmod 600 "$path"
}

DAILY_DASH_REDDIT_CLIENT_ID="${DAILY_DASH_REDDIT_CLIENT_ID:-$(read_secret_file reddit_client_id)}"
DAILY_DASH_REDDIT_CLIENT_SECRET="${DAILY_DASH_REDDIT_CLIENT_SECRET:-$(read_secret_file reddit_client_secret)}"
DAILY_DASH_REDDIT_USER_AGENT="${DAILY_DASH_REDDIT_USER_AGENT:-$(read_secret_file reddit_user_agent)}"

if [[ -z "$DAILY_DASH_REDDIT_CLIENT_ID" ]]; then
  read -r -p "Reddit client ID: " DAILY_DASH_REDDIT_CLIENT_ID
fi
if [[ -z "$DAILY_DASH_REDDIT_CLIENT_SECRET" ]]; then
  read -r -s -p "Reddit client secret: " DAILY_DASH_REDDIT_CLIENT_SECRET
  echo
fi
if [[ -z "$DAILY_DASH_REDDIT_USER_AGENT" ]]; then
  read -r -p "Reddit username (without /u/): " reddit_username
  if [[ -z "$reddit_username" ]]; then
    echo "ERROR: Reddit username is required to build a transparent User-Agent" >&2
    exit 3
  fi
  DAILY_DASH_REDDIT_USER_AGENT="script:daily-dash:1.0 (by /u/$reddit_username)"
fi

for name in DAILY_DASH_REDDIT_CLIENT_ID DAILY_DASH_REDDIT_CLIENT_SECRET DAILY_DASH_REDDIT_USER_AGENT; do
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: required Reddit configuration is empty: $name" >&2
    exit 3
  fi
done

write_secret_file reddit_client_id "$DAILY_DASH_REDDIT_CLIENT_ID"
write_secret_file reddit_client_secret "$DAILY_DASH_REDDIT_CLIENT_SECRET"
write_secret_file reddit_user_agent "$DAILY_DASH_REDDIT_USER_AGENT"

export DAILY_DASH_REDDIT_CLIENT_ID DAILY_DASH_REDDIT_CLIENT_SECRET DAILY_DASH_REDDIT_USER_AGENT

echo "Saved Reddit configuration under $SECRET_DIR"
echo "User-Agent: $DAILY_DASH_REDDIT_USER_AGENT"

if [[ "$SKIP_CHECK" -eq 0 ]]; then
  uv run python -m daily_dash.commands.wsb check-reddit --config-dir "$ROOT/config"
fi

if [[ "$PUSH_WINDMILL" -eq 1 ]]; then
  "$ROOT/scripts/wmill-set-secret.sh" \
    DAILY_DASH_REDDIT_CLIENT_ID \
    f/daily_dash/reddit_client_id \
    'Approved Reddit Data API OAuth client id for WSB retrieval'
  "$ROOT/scripts/wmill-set-secret.sh" \
    DAILY_DASH_REDDIT_CLIENT_SECRET \
    f/daily_dash/reddit_client_secret \
    'Approved Reddit Data API OAuth client secret for WSB retrieval'
  "$ROOT/scripts/wmill-set-variable.sh" \
    DAILY_DASH_REDDIT_USER_AGENT \
    f/daily_dash/reddit_user_agent \
    'Transparent Reddit API User-Agent for WSB retrieval'
  echo "WSB Reddit configuration uploaded to Windmill."
fi
