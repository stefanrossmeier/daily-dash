#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required tool not found: $1" >&2
    exit 1
  fi
}

require git
require uv
require node
require npm
require docker

NODE_MAJOR="$(node -p 'Number(process.versions.node.split(".")[0])')"

if (( NODE_MAJOR <= 20 )); then
  echo "ERROR: Windmill CLI requires Node >20; found $(node --version)" >&2
  exit 1
fi

docker compose version >/dev/null

if [[ ! -x node_modules/.bin/wmill ]]; then
  echo "ERROR: Windmill CLI missing. Run: npm ci" >&2
  exit 1
fi

echo "git:      $(git --version)"
echo "uv:       $(uv --version)"
echo "node:     $(node --version)"
echo "npm:      $(npm --version)"
echo "docker:   $(docker --version)"
echo "compose:  $(docker compose version --short)"
echo "windmill: $(./scripts/wmill.sh --version)"

echo
echo "Tooling check passed."
