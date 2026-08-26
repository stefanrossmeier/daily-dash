#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

uv run daily-dash validate-config
