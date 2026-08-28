#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$ROOT/deploy/local-windmill"
DEFAULT_TARGET="$(cd "$ROOT/.." && pwd)/daily-dash-windmill-local"
DEFAULT_DATA_REPO="$(cd "$ROOT/.." && pwd)/daily-dash-data"

usage() {
  cat <<USAGE
Usage: $0 [options]

Materialize a reproducible local Windmill deployment from the files tracked in
this daily-dash repository.

Options:
  --target PATH              Generated Windmill directory
                             (default: $DEFAULT_TARGET)
  --data-repo PATH           Separate DailyDash data Git checkout
                             (default: $DEFAULT_DATA_REPO)
  --openrouter-key-file PATH Existing file containing the OpenRouter API key.
                             If omitted, TARGET/secrets/openrouter_api_key is
                             created as an empty 0600 file.
  --force                    Refresh tracked infrastructure files in an existing
                             target. Existing .env and secrets are preserved.
  --rewrite-env              Rewrite TARGET/.env using the supplied/current paths.
  -h, --help                 Show this help.
USAGE
}

canonical_path() {
  local path="$1"
  local parent
  parent="$(dirname "$path")"
  mkdir -p "$parent"
  parent="$(cd "$parent" && pwd)"
  printf '%s/%s\n' "$parent" "$(basename "$path")"
}

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required tool not found: $1" >&2
    exit 10
  }
}

TARGET="$DEFAULT_TARGET"
DATA_REPO="$DEFAULT_DATA_REPO"
OPENROUTER_KEY_FILE=""
FORCE=false
REWRITE_ENV=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"
      shift 2
      ;;
    --data-repo)
      DATA_REPO="$2"
      shift 2
      ;;
    --openrouter-key-file)
      OPENROUTER_KEY_FILE="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --rewrite-env)
      REWRITE_ENV=true
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

require git

TARGET="$(canonical_path "$TARGET")"
DATA_REPO="$(canonical_path "$DATA_REPO")"

if [[ -e "$TARGET" && ! -d "$TARGET" ]]; then
  echo "ERROR: target exists and is not a directory: $TARGET" >&2
  exit 3
fi

if [[ -d "$TARGET" && -n "$(find "$TARGET" -mindepth 1 -maxdepth 1 -print -quit)" && "$FORCE" != true ]]; then
  echo "ERROR: target is not empty: $TARGET" >&2
  echo "Re-run with --force to refresh the tracked infrastructure files." >&2
  exit 4
fi

mkdir -p "$TARGET"

for file in docker-compose.yml docker-compose.override.yml Caddyfile .env.example .gitignore README.md; do
  cp "$TEMPLATE_DIR/$file" "$TARGET/$file"
done

if [[ -e "$DATA_REPO" && ! -d "$DATA_REPO" ]]; then
  echo "ERROR: data repo path exists and is not a directory: $DATA_REPO" >&2
  exit 5
fi

if [[ ! -d "$DATA_REPO" ]]; then
  mkdir -p "$DATA_REPO"
fi

if [[ ! -d "$DATA_REPO/.git" ]]; then
  if [[ -n "$(find "$DATA_REPO" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ERROR: data repo exists but is not a Git repository: $DATA_REPO" >&2
    echo "Use an empty directory or an existing daily-dash-data clone." >&2
    exit 6
  fi

  git -C "$DATA_REPO" init -q -b main
  printf '%s\n' '# DailyDash local data sink' > "$DATA_REPO/README.md"
  git -C "$DATA_REPO" add README.md
  git -C "$DATA_REPO" \
    -c user.name='DailyDash Bootstrap' \
    -c user.email='daily-dash-bootstrap@users.noreply.github.com' \
    commit -qm 'chore: initialize local data sink'
fi

if [[ -n "$OPENROUTER_KEY_FILE" ]]; then
  OPENROUTER_KEY_FILE="$(canonical_path "$OPENROUTER_KEY_FILE")"
  if [[ ! -f "$OPENROUTER_KEY_FILE" ]]; then
    echo "ERROR: OpenRouter key file not found: $OPENROUTER_KEY_FILE" >&2
    exit 7
  fi
else
  mkdir -p "$TARGET/secrets"
  chmod 700 "$TARGET/secrets"
  OPENROUTER_KEY_FILE="$TARGET/secrets/openrouter_api_key"
  if [[ ! -e "$OPENROUTER_KEY_FILE" ]]; then
    : > "$OPENROUTER_KEY_FILE"
  fi
  chmod 600 "$OPENROUTER_KEY_FILE"
fi

ENV_FILE="$TARGET/.env"
if [[ ! -e "$ENV_FILE" || "$REWRITE_ENV" == true ]]; then
  cat > "$ENV_FILE" <<ENV
DATABASE_URL=postgres://postgres:changeme@db/windmill?sslmode=disable
WM_IMAGE=ghcr.io/windmill-labs/windmill:1.775.1
DAILY_DASH_SOURCE=$ROOT
DAILY_DASH_DATA_SOURCE=$DATA_REPO
DAILY_DASH_OPENROUTER_KEY_FILE=$OPENROUTER_KEY_FILE
ENV
  chmod 600 "$ENV_FILE"
else
  echo "Preserving existing $ENV_FILE"
fi

if git -C "$ROOT" rev-parse HEAD >/dev/null 2>&1; then
  git -C "$ROOT" rev-parse HEAD > "$TARGET/daily-dash-source-revision.txt"
fi

cat <<SUMMARY

Local Windmill deployment materialized.

  deployment:      $TARGET
  daily-dash:      $ROOT
  data sink:       $DATA_REPO
  OpenRouter file: $OPENROUTER_KEY_FILE

Next:
  1. Put your OpenRouter key in the key file (one line, no quotes).
  2. Run: DAILY_DASH_WINDMILL_DIR="$TARGET" ./scripts/local-windmill.sh up
  3. Open http://localhost and complete the Windmill bootstrap login/workspace setup.
  4. Run ./scripts/configure-windmill-workspace.sh after exporting the required values.
  5. Run ./scripts/sync-windmill-workspace.sh

See docs/09_LOCAL_WINDMILL_BOOTSTRAP.md for the complete procedure.
SUMMARY
