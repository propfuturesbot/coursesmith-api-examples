#!/usr/bin/env bash
# Everything AFTER the video: quiz + LMS exports, PPTX deck, PDF handout,
# captions, and an MP3 audio-only export.
#
#   export COURSESMITH_API_KEY=cs_live_...
#   ./examples/06_quiz_and_exports.sh <LESSON_ID> <SCRIPT_ID> <VIDEO_ID>
#
# (Get the ids from examples 01/02: the lesson you created, its script,
# and the finished video job's video_id.)

set -euo pipefail
API="${COURSESMITH_BASE_URL:-https://api.coursesmith.ai}"
LESSON="${1:?lesson id}"; SCRIPT="${2:?script id}"; VIDEO="${3:?video id}"
AUTH="Authorization: Bearer ${COURSESMITH_API_KEY:?set COURSESMITH_API_KEY}"

# ── Quiz ────────────────────────────────────────────────────────────────
QUIZ=$(curl -sf -X POST "$API/v1/lessons/$LESSON/quiz" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"config": {"easy": 3, "medium": 2, "hard": 0}}')
QUIZ_ID=$(echo "$QUIZ" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "quiz: $QUIZ_ID"

# All 12 formats: GET /v1/quiz-formats. Two shown here.
curl -sf "$API/v1/quizzes/$QUIZ_ID/export/scorm12" -H "$AUTH" -o quiz_scorm12.zip
curl -sf "$API/v1/quizzes/$QUIZ_ID/export/pdf"     -H "$AUTH" -o quiz.pdf
echo "exported: quiz_scorm12.zip quiz.pdf"

# ── Script-level exports ────────────────────────────────────────────────
curl -sf "$API/v1/scripts/$SCRIPT/deck.pptx"   -H "$AUTH" -o lesson_deck.pptx
curl -sf "$API/v1/scripts/$SCRIPT/handout.pdf" -H "$AUTH" -o lesson_handout.pdf
echo "exported: lesson_deck.pptx lesson_handout.pdf"

# ── Video-level extras ──────────────────────────────────────────────────
curl -sf "$API/v1/videos/$VIDEO/captions" -H "$AUTH" | python3 -m json.tool | head -20

# MP3 audio-only re-export of the finished video (async render job).
JOB=$(curl -sf -X POST "$API/v1/videos/$VIDEO/export" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"format": "mp3"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
echo "mp3 export job: $JOB   (poll GET /v1/jobs/$JOB, download video_url when done)"
