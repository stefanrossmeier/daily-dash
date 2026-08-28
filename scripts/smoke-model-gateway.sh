#!/usr/bin/env bash
set -Eeuo pipefail

gateway_url="${DAILY_DASH_MODEL_GATEWAY_URL:-http://127.0.0.1:18080}"
alias="${1:-rank-cheap}"

payload="$(
  ALIAS="$alias" uv run python - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "alias": os.environ["ALIAS"],
            "purpose": "news-ranking-smoke-test",
            "run_id": "smoke-test",
            "profile": "news-top",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rank the supplied news candidates by importance for a "
                        "business, markets, technology and geopolitics briefing. "
                        "Return only the requested structured response."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "A: Central bank unexpectedly cuts rates by 75 basis points\n"
                        "B: Celebrity launches a new clothing collection\n"
                        "C: Major AI company announces a $40 billion acquisition\n"
                        "D: Large European economy enters recession"
                    ),
                },
            ],
            "response_schema_name": "ranking_smoke_test",
            "response_schema": {
                "type": "object",
                "properties": {
                    "ranking": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["A", "B", "C", "D"],
                        },
                        "minItems": 4,
                        "maxItems": 4,
                    }
                },
                "required": ["ranking"],
                "additionalProperties": False,
            },
        }
    )
)
PY
)"

curl \
  --fail-with-body \
  --silent \
  --show-error \
  "$gateway_url/v1/chat" \
  -H 'Content-Type: application/json' \
  --data "$payload"
