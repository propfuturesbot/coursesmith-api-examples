#!/usr/bin/env bash
# Register a webhook endpoint and fire a signed test event at it.
#
#   export COURSESMITH_API_KEY=cs_live_...
#   ./examples/05_webhooks/register.sh https://your-host.example.com/hooks
#
# For local testing, expose receiver.py with a tunnel first, e.g.:
#   cloudflared tunnel --url http://localhost:8787

set -euo pipefail
API="${COURSESMITH_BASE_URL:-https://api.coursesmith.ai}"
URL="${1:?usage: register.sh <https-endpoint-url>}"
AUTH="Authorization: Bearer ${COURSESMITH_API_KEY:?set COURSESMITH_API_KEY}"

# 1. Create. THE SECRET IS RETURNED ONLY ONCE — store it now.
RESP=$(curl -sf -X POST "$API/v1/webhooks" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"url\": \"$URL\", \"events\": [\"job.succeeded\", \"job.failed\"]}")
echo "$RESP" | python3 -m json.tool
WHK=$(echo "$RESP"   | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
SECRET=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['secret'])")

echo
echo "export COURSESMITH_WEBHOOK_SECRET=$SECRET   # <- receiver.py needs this"
echo

# 2. Fire a signed test event (type carries job.succeeded, job_type 'test').
curl -sf -X POST "$API/v1/webhooks/$WHK/test" -H "$AUTH" | python3 -m json.tool

# From here on, every pipeline/generation/render job you start delivers
# job.succeeded / job.failed to $URL — failures retry after 1m, 5m, 30m,
# and an endpoint failing 20 times in a row is auto-disabled.
