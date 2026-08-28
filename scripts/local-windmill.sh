#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_DIR="$(cd "$ROOT/.." && pwd)/daily-dash-windmill-local"
DEPLOY_DIR="${DAILY_DASH_WINDMILL_DIR:-$DEFAULT_DIR}"

usage() {
  cat <<USAGE
Usage: $0 <up|down|rebuild|status|logs|health|config>

Set DAILY_DASH_WINDMILL_DIR to use a deployment directory other than:
  $DEFAULT_DIR
USAGE
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "$DEPLOY_DIR/docker-compose.yml" || ! -f "$DEPLOY_DIR/.env" ]]; then
  echo "ERROR: local Windmill deployment is not bootstrapped: $DEPLOY_DIR" >&2
  echo "Run ./scripts/bootstrap-local-windmill.sh first." >&2
  exit 3
fi

command -v docker >/dev/null 2>&1 || {
  echo "ERROR: docker is required" >&2
  exit 4
}

dc() {
  (
    cd "$DEPLOY_DIR"
    docker compose "$@"
  )
}

case "$1" in
  up)
    dc up -d --build
    ;;
  down)
    dc down
    ;;
  rebuild)
    dc build --no-cache windmill_worker_dailydash daily_dash_model_gateway
    dc up -d --no-deps --force-recreate windmill_worker_dailydash daily_dash_model_gateway
    ;;
  status)
    dc ps
    ;;
  logs)
    dc logs --tail=200 windmill_server windmill_worker_dailydash daily_dash_model_gateway
    ;;
  config)
    dc config
    ;;
  health)
    dc ps windmill_server windmill_worker_dailydash daily_dash_model_gateway
    printf '\nWindmill HTTP:\n'
    curl --fail --silent --show-error http://localhost/ >/dev/null
    echo 'ok'
    printf '\nDailyDash model gateway:\n'
    curl --fail --silent --show-error http://127.0.0.1:18080/health
    echo
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
