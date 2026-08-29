#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_WINDMILL_DIR="$(cd "$ROOT/.." && pwd)/daily-dash-windmill-local"
WINDMILL_DIR="${DAILY_DASH_WINDMILL_DIR:-$DEFAULT_WINDMILL_DIR}"
SECRET_DIR="${DAILY_DASH_SECRETS_DIR:-$WINDMILL_DIR/secrets}"

load_secret_if_unset() {
  local env_name="$1"
  local file_name="$2"
  local path="$SECRET_DIR/$file_name"
  if [[ -z "${!env_name:-}" && -s "$path" ]]; then
    printf -v "$env_name" '%s' "$(cat "$path")"
    export "$env_name"
  fi
}

load_secret_if_unset DAILY_DASH_DATA_REPO_DEPLOY_KEY data_repo_deploy_key
load_secret_if_unset DAILY_DASH_TELEGRAM_TOKEN telegram_token
load_secret_if_unset DAILY_DASH_TELEGRAM_CHAT_ID telegram_chat_id

required=(
  DAILY_DASH_DATA_REPO_REMOTE_URL
  DAILY_DASH_DATA_REPO_DEPLOY_KEY
  DAILY_DASH_TELEGRAM_TOKEN
  DAILY_DASH_TELEGRAM_CHAT_ID
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: required configuration is unset: $name" >&2
    case "$name" in
      DAILY_DASH_DATA_REPO_DEPLOY_KEY)
        echo "Expected secret file: $SECRET_DIR/data_repo_deploy_key" >&2
        ;;
      DAILY_DASH_TELEGRAM_TOKEN)
        echo "Expected secret file: $SECRET_DIR/telegram_token" >&2
        ;;
      DAILY_DASH_TELEGRAM_CHAT_ID)
        echo "Expected secret file: $SECRET_DIR/telegram_chat_id" >&2
        ;;
      DAILY_DASH_DATA_REPO_REMOTE_URL)
        echo "Set DAILY_DASH_DATA_REPO_REMOTE_URL to the installation-specific Git SSH URL." >&2
        ;;
    esac
    exit 2
  fi
done

export DAILY_DASH_DATA_REPO_BRANCH="${DAILY_DASH_DATA_REPO_BRANCH:-main}"

"$ROOT/scripts/wmill-set-variable.sh" \
  DAILY_DASH_DATA_REPO_REMOTE_URL \
  f/daily_dash/data_repo_remote_url \
  'Git SSH URL of the private DailyDash data sink'

"$ROOT/scripts/wmill-set-variable.sh" \
  DAILY_DASH_DATA_REPO_BRANCH \
  f/daily_dash/data_repo_branch \
  'Branch used by DailyDash data persistence'

"$ROOT/scripts/wmill-set-secret.sh" \
  DAILY_DASH_DATA_REPO_DEPLOY_KEY \
  f/daily_dash/data_repo_deploy_key \
  'SSH deploy key for the private DailyDash data sink'

"$ROOT/scripts/wmill-set-secret.sh" \
  DAILY_DASH_TELEGRAM_TOKEN \
  f/daily_dash/telegram_token \
  'Telegram bot token'

"$ROOT/scripts/wmill-set-secret.sh" \
  DAILY_DASH_TELEGRAM_CHAT_ID \
  f/daily_dash/telegram_chat_id \
  'Telegram chat id'

echo
echo 'DailyDash Windmill variables and secrets configured.'
