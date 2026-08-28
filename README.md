# CourseSmith API Examples

Runnable examples for the [CourseSmith](https://www.coursesmith.ai) public
API — turn a topic, URL, document, or GitHub repo into a rendered, narrated
course video from your own code.

**Docs:** [Developer portal](https://www.coursesmith.ai/developers) ·
[API reference](https://www.coursesmith.ai/developers/reference) ·
[Swagger](https://api.coursesmith.ai/docs)

**Base URL:** `https://api.coursesmith.ai` (all endpoints under `/v1`)

Every example in this repo was run against production before being
committed.

## Setup

1. Create an API key at **coursesmith.ai → Settings → API Keys** (paid
   plans and admins).
2. ```bash
   cp .env.example .env        # put your cs_live_... key in it
   export $(grep -v '^#' .env | xargs)
   pip install httpx           # for the Python examples
   ```

Auth on every request: `Authorization: Bearer $COURSESMITH_API_KEY`.

## The 3-call quickstart — topic → MP4

```bash
# 1. A lesson to hang the video on
curl -X POST https://api.coursesmith.ai/v1/lessons/standalone \
  -H "Authorization: Bearer $COURSESMITH_API_KEY" -H "Content-Type: application/json" \
  -d '{"title": "How Recursion Unwinds", "subject_domain": "programming"}'
# -> {"course_id": "...", "topic_id": "...", "subtopic_id": "<LESSON_ID>"}

# 2. Generate script -> narrate -> render, one call
curl -X POST https://api.coursesmith.ai/v1/lessons/$LESSON_ID/videos \
  -H "Authorization: Bearer $COURSESMITH_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"generate": {"lecture_style": "short", "tone": "conversational"}, "resolution": "1080p"}'
# -> {"job_id": "pipe_..."}

# 3. Poll until succeeded (renders take 10–40 min), then download .video_url
curl https://api.coursesmith.ai/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer $COURSESMITH_API_KEY"
```

## Examples

| # | File | What it shows |
|---|------|---------------|
| 01 | [`examples/01_create_video.py`](examples/01_create_video.py) | Topic → finished MP4, downloaded (the quickstart, in Python with polling) |
| 02 | [`examples/02_edit_scenes.py`](examples/02_edit_scenes.py) | The edit loop: read the storyboard, set narration literally, LLM-restyle a scene ("chalkboard style"), swap a component, then render |
| 03 | [`examples/03_grounded_from_url.py`](examples/03_grounded_from_url.py) | URL → ingest → LLM split → commit **grounded** lessons → video that teaches from the article |
| 04 | [`examples/04_course_from_repo.sh`](examples/04_course_from_repo.sh) | GitHub repo → whole multi-topic course in one call |
| 05 | [`examples/05_webhooks/`](examples/05_webhooks/) | Register a webhook, receive `job.succeeded`/`job.failed`, verify the HMAC signature |
| 06 | [`examples/06_quiz_and_exports.sh`](examples/06_quiz_and_exports.sh) | Quiz + SCORM/PDF export, PPTX deck, captions, MP3 audio-only export |

Run any Python example from the repo root: `python examples/01_create_video.py`.
They all use the single-file SDK vendored here as
[`coursesmith.py`](coursesmith.py) (canonical copy ships in the product repo).

## Jobs, in one paragraph

Long operations return `202` with a job id (`pipe_` pipeline, `gen_`
generation, `vid_` render, `doc_` document ingest, `yt_` YouTube, `struct_`
structure). Poll `GET /v1/jobs/{id}` — status is always
`queued | processing | succeeded | failed | cancelled`, detail in `stage`,
results in `script_id` / `video_id` / `video_url`. Live updates:
`GET /v1/jobs/{id}/stream?api_key=...` (SSE) or register a webhook (ex. 05).
Charging POSTs accept an `Idempotency-Key` header: identical retries replay
the first response instead of charging twice.

## Errors

```json
{"error": {"code": "insufficient_credits", "message": "...", "request_id": "..."}}
```

Codes you should handle: `invalid_api_key` (401),
`insufficient_credits` / `tier_upgrade_required` (402), `not_found` (404),
`rate_limit_exceeded` (429 — wait `Retry-After`; generation is ~3/hour),
`validation_error` (422). Quote `request_id` to support for 5xx.

## Discover options — don't hardcode enums

```
GET /v1/generation-options    # models, lengths (reel…elaborate), tones, resolutions
GET /v1/lecture-formats?subject_domain=programming   # incl. motioncraft-lecture etc.
GET /v1/voices                # built-in + your cloned voices + premium
GET /v1/pricing  +  GET /v1/credits                  # know the cost first
```

## MCP (drive the API from Claude / Cursor / VS Code)

This repo ships the CourseSmith MCP server —
[`mcp/coursesmith_mcp.py`](mcp/coursesmith_mcp.py), 17 tools: create
lessons, generate lectures, edit storyboard scenes, render videos, poll
jobs. Setup for every client (Claude Code, Claude Desktop, Cursor,
VS Code Copilot, Windsurf) is in [`mcp/README.md`](mcp/README.md) and on
the [MCP guide](https://www.coursesmith.ai/developers/mcp). Claude Code:

```bash
pip install "mcp[cli]" httpx
claude mcp add coursesmith -e COURSESMITH_API_KEY=cs_live_... \
  -- python "$(pwd)/mcp/coursesmith_mcp.py"
```

Prefer skills over MCP? A ready-made Claude skill ships at
[`skills/coursesmith-video/SKILL.md`](skills/coursesmith-video/SKILL.md)
— drop the folder into `~/.claude/skills/`.

## License

MIT — use these examples freely in your own integrations.
