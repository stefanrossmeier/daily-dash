#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

required=(
  DAILY_DASH_DATA_REPO_REMOTE_URL
  DAILY_DASH_DATA_REPO_DEPLOY_KEY
  DAILY_DASH_TELEGRAM_TOKEN
  DAILY_DASH_TELEGRAM_CHAT_ID
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: required environment variable is unset: $name" >&2
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
