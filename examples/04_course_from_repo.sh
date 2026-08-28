#!/usr/bin/env bash
# GitHub repo → whole multi-topic course, one call.
#
#   export COURSESMITH_API_KEY=cs_live_...
#   ./examples/04_course_from_repo.sh https://github.com/karpathy/micrograd
#
# The repo is cloned and analyzed server-side, and the call BLOCKS until
# the full Course → Topics → grounded Lessons tree exists (micrograd →
# ~7 topics / ~20 lessons). Use a small repo; give curl a long timeout.
# Each lesson can then be generated/rendered exactly like example 01/02.

set -euo pipefail
API="${COURSESMITH_BASE_URL:-https://api.coursesmith.ai}"
REPO="${1:-https://github.com/karpathy/micrograd}"
AUTH="Authorization: Bearer ${COURSESMITH_API_KEY:?set COURSESMITH_API_KEY}"

# 1. Build the course (synchronous 201; several minutes for real repos).
RESP=$(curl -sf --max-time 900 -X POST "$API/v1/courses/from-repo" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"type\": \"github\", \"repo_url\": \"$REPO\"}")
echo "$RESP" | python3 -m json.tool
COURSE=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['course_id'])")

# 2. The course GET returns the full tree: topics -> lessons.
curl -sf "$API/v1/courses/$COURSE" -H "$AUTH" \
  | python3 -c "
import json, sys
c = json.load(sys.stdin)
print()
print('COURSE:', c.get('title'))
for t in c.get('topics') or []:
    print(' ', t['title'])
    for s in t.get('subtopics') or []:
        print('    lesson', s['id'], '-', s['title'])
"
echo
echo "Render any lesson: POST /v1/lessons/{id}/videos (see example 01)."
