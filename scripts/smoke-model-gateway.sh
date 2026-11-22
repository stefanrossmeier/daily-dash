#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
uv run python - "${1:-rank-cheap}" <<'PYCODE'
import json
import sys
from daily_dash.llm.gateway import ModelGatewayClient
result = ModelGatewayClient().chat_structured(
    alias=sys.argv[1], purpose="inference-smoke", profile="news-top",
    system="Return a JSON object with ok set to true.", user="Synthetic gateway smoke.",
    response_schema_name="smoke", response_schema={"type":"object",
        "properties":{"ok":{"type":"boolean"}},"required":["ok"],"additionalProperties":False})
print(json.dumps(result.model_dump(mode="json")))
PYCODE
