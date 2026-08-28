---
name: coursesmith-video
description: Create narrated course videos through the CourseSmith public API — turn a topic, URL, document, or GitHub repo into a rendered MP4, edit storyboard scenes, generate quizzes, and export decks. Use when the user asks to make a course video, lecture video, explainer MP4, or to automate CourseSmith from Claude.
---

# CourseSmith Video Creation

Drive the CourseSmith public API to produce finished, narrated course videos.
Base URL: `https://api.coursesmith.ai` (override with `$COURSESMITH_BASE_URL`
for local dev: `http://localhost:8091` or `http://localhost:8090/api/public`).

## Auth — before anything else

Every call needs `Authorization: Bearer $COURSESMITH_API_KEY` (a `cs_live_…`
key). If the env var is unset, STOP and ask the user to create a key at
**coursesmith.ai → Settings → API Keys** (paid tiers + admins only) and
export it. Never print a full key back to the user; never send it anywhere
except the CourseSmith base URL.

## The core flow — topic → MP4 in 3 calls

```bash
# 1. A lesson to hang the video on (standalone = no course setup needed)
curl -X POST $BASE/v1/lessons/standalone \
  -H "Authorization: Bearer $COURSESMITH_API_KEY" -H "Content-Type: application/json" \
  -d '{"title": "<video topic>", "subject_domain": "<see /v1/subjects; or POST /v1/subjects/suggest>"}'
# → {course_id, topic_id, subtopic_id}; subtopic_id is the lesson_id below

# 2. One call: generate script → narrate (TTS) → render MP4
curl -X POST $BASE/v1/lessons/$LESSON_ID/videos \
  -H "Authorization: Bearer $COURSESMITH_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"generate": {"lecture_style": "short", "tone": "conversational"}, "resolution": "1080p"}'
# → {"job_id": "pipe_…"}

# 3. Poll until terminal (renders take 10–40 min; poll every 15–30 s)
curl $BASE/v1/jobs/$JOB_ID -H "Authorization: Bearer $COURSESMITH_API_KEY"
# succeeded → download the MP4 at .video_url
```

Statuses are always `queued | processing | succeeded | failed | cancelled`
(details in `stage`). NEVER re-POST a charging call without its original
`Idempotency-Key` — identical retries replay free; re-posting fresh charges
again.

## Discover options — don't guess enums

- `GET /v1/generation-options` — models, lengths (`reel`…`elaborate`),
  tones, pacing, resolutions (4K = pro/studio).
- `GET /v1/lecture-formats?subject_domain=X` — formats valid for the
  subject (e.g. `motioncraft-lecture` = every scene a bespoke Remotion
  animation; whiteboard, sketch, cinematic…). Pass as `lecture_format_id`.
- `GET /v1/voices` — built-in, the user's cloned voices, premium. Pass a
  `voice_id` in `generate` or the pipeline body.
- `GET /v1/credits` + `GET /v1/pricing` — check affordability BEFORE
  generating; a reel generation + render ≈ 40–90 credits, MotionCraft ≈ 60+.

## Ground the video in real material (better than a bare topic)

```
POST /v1/sources {"type": "url"|"text"|"github"|"youtube", ...}   # ingest
POST /v1/sources/{id}/process                                     # LLM split (blocking 30–90 s)
POST /v1/sources/{id}/commit {"lectures":[...], "destination":{"type":"new_course","course_title":"…"}}
# → subtopic_ids are GROUNDED lesson ids — generate against those
```
One-shots: `POST /v1/courses/from-repo` (GitHub → whole course) and
`POST /v1/courses/from-document` (multipart file → course, poll the `doc_` job).

## Edit before rendering (the review loop)

1. Generate the script first: `POST /v1/lessons/{id}/generate` → poll `gen_` job.
2. Read it: `GET /v1/lessons/{id}/scripts` → `GET /v1/scripts/{script_id}` —
   scenes live in `sections[].subphases[]` (`content` = narration).
3. Edit:
   - Literal text/title: `PATCH /v1/scripts/{id}/scenes/{scene_id}`
     `{"narration": "...", "title": "..."}` — stale narration carriers are
     cleared server-side, so the MP4 always speaks the new text.
   - LLM restyle/rewrite: `POST …/scenes/{scene_id}/rewrite`
     `{"instruction": "e.g. restyle as a chalkboard; add an analogy"}`.
   - Swap visual component: `POST …/scenes/{scene_id}/remap`.
   - Add / delete / reorder: `POST /v1/scripts/{id}/scenes`,
     `DELETE …/scenes/{scene_id}`, `POST …/sections/{sec}/reorder`.
4. Render the edited script: `POST /v1/lessons/{id}/videos` **without**
   `generate` (renders the newest script).

## After the video

- `POST /v1/videos/{id}/export {"format": "mp3"}` — audio-only version.
- `GET /v1/videos/{id}/captions` — transcript.
- `POST /v1/lessons/{id}/quiz` → `GET /v1/quizzes/{id}/export/scorm12` (or
  pdf, gift, qti21…) — LMS-ready quiz.
- `GET /v1/scripts/{id}/deck.pptx` — the lecture as slides.

## Errors & guardrails

Every failure returns `{"error": {"code", "message", "request_id"}}`. React
by code: `insufficient_credits`/`tier_upgrade_required` (402) → tell the
user, don't retry; `rate_limit_exceeded` (429) → wait `Retry-After` seconds
(generation is capped ~3/hour); `plan_not_supported` → skip the plan gate
and call generate directly; 5xx → report the `request_id` to the user for
support. Long jobs: keep polling — never assume failure from slowness alone
(MotionCraft generation can run 15+ min). Full reference:
https://www.coursesmith.ai/developers
