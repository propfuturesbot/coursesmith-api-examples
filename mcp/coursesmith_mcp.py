"""
CourseSmith MCP server — lets agents (Claude, etc.) drive the public API.

Run (stdio transport):

    pip install "mcp[cli]" httpx
    export COURSESMITH_API_KEY=cs_live_...
    export COURSESMITH_BASE_URL=http://localhost:8000/api/public   # or prod
    python mcp-server/coursesmith_mcp.py

Claude Desktop / Claude Code config:

    {"mcpServers": {"coursesmith": {
        "command": "python",
        "args": ["/abs/path/mcp-server/coursesmith_mcp.py"],
        "env": {"COURSESMITH_API_KEY": "cs_live_..."}}}}

Every tool returns the API's JSON verbatim. Long operations return a job id
— call wait_for_job (bounded poll) until status is terminal. Enums are
discoverable via list_options; nothing is hardcoded.
"""

import json
import os
import time
import uuid
from typing import Any, Optional

import httpx

try:  # mcp >= 2.0 renamed FastMCP to MCPServer (same decorator API)
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

BASE_URL = (os.environ.get("COURSESMITH_BASE_URL")
            or "https://api.coursesmith.ai").rstrip("/")
API_KEY = os.environ.get("COURSESMITH_API_KEY", "")

mcp = FastMCP("coursesmith")


def _cap(payload: Any, limit: int = 30000) -> str:
    """Serialize with a size cap that NEVER emits broken JSON — a raw
    string slice cut mid-token (the original approach) made large
    storyboards unparseable for the calling agent."""
    s = json.dumps(payload, default=str)
    if len(s) <= limit:
        return s
    return json.dumps({"truncated": True, "total_chars": len(s),
                       "preview": s[:limit]})


def _req(method: str, path: str, *, idempotent: bool = False, **kwargs) -> Any:
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if idempotent:
        headers["Idempotency-Key"] = uuid.uuid4().hex
    with httpx.Client(base_url=BASE_URL, timeout=150) as client:
        resp = client.request(method, path, headers=headers, **kwargs)
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"raw": resp.text[:2000]}
    if resp.status_code >= 400:
        return {"error": body.get("error", body), "status_code": resp.status_code}
    return body


@mcp.tool()
def list_options(subject_domain: Optional[str] = None) -> str:
    """All generation options: models, lengths, tones, formats (filtered by
    subject when given), languages. Call before generate_lecture."""
    return json.dumps({
        "generation_options": _req("GET", "/v1/generation-options"),
        "lecture_formats": _req("GET", "/v1/lecture-formats",
                                params={"subject_domain": subject_domain}
                                if subject_domain else None),
        "languages": _req("GET", "/v1/languages"),
    }, default=str)


@mcp.tool()
def list_voices(language: Optional[str] = None) -> str:
    """Available narration voices: built-in, the user's clones, premium."""
    return _cap(_req("GET", "/v1/voices"), 20000)


@mcp.tool()
def get_credits() -> str:
    """Credit balance, tier limits, and the price of each operation."""
    return json.dumps({"credits": _req("GET", "/v1/credits"),
                       "pricing": _req("GET", "/v1/pricing")}, default=str)


@mcp.tool()
def list_courses(page: int = 1) -> str:
    """The user's courses (paginated)."""
    return json.dumps(_req("GET", "/v1/courses", params={"page": page}),
                      default=str)


@mcp.tool()
def get_course(course_id: str) -> str:
    """Full course tree: topics → lessons → script summaries."""
    return json.dumps(_req("GET", f"/v1/courses/{course_id}"), default=str)


@mcp.tool()
def create_course(title: str, description: Optional[str] = None,
                  subject_domain: Optional[str] = None) -> str:
    """Create an empty course (add topics/lessons after)."""
    return json.dumps(_req("POST", "/v1/courses", json={
        "title": title, "description": description,
        "subject_domain": subject_domain}), default=str)


@mcp.tool()
def create_lesson(title: str, subject_domain: str = "general",
                  topic_id: Optional[str] = None) -> str:
    """Create a lesson. With topic_id it goes into that topic; without, a
    standalone lesson is created (returns subtopic_id = the lesson id)."""
    if topic_id:
        return json.dumps(_req("POST", f"/v1/topics/{topic_id}/lessons",
                               json={"title": title}), default=str)
    return json.dumps(_req("POST", "/v1/lessons/standalone", json={
        "title": title, "subject_domain": subject_domain}), default=str)


@mcp.tool()
def ingest_source(type: str, url: Optional[str] = None,
                  markdown: Optional[str] = None,
                  repo_url: Optional[str] = None) -> str:
    """Ingest teaching material: type=url|text|github (youtube via the REST
    API). Returns source_id (github also returns proposed lectures)."""
    return _cap(_req("POST", "/v1/sources", json={
        "type": type, "url": url, "markdown": markdown,
        "repo_url": repo_url}), 30000)


@mcp.tool()
def process_source(source_id: str) -> str:
    """LLM-split an ingested source into concepts + proposed lectures
    (blocking 30-90s; charged once, restores are free)."""
    return _cap(_req("POST", f"/v1/sources/{source_id}/process"), 30000)


@mcp.tool()
def commit_source(source_id: str, lectures_json: str,
                  destination_json: str) -> str:
    """Create GROUNDED lessons from processed proposals. lectures_json =
    JSON array from process_source (edit freely); destination_json e.g.
    {"type": "new_course", "course_title": "..."}. Returns lesson ids."""
    return json.dumps(_req("POST", f"/v1/sources/{source_id}/commit", json={
        "lectures": json.loads(lectures_json),
        "destination": json.loads(destination_json)}), default=str)


@mcp.tool()
def generate_lecture(lesson_id: str, lecture_format_id: Optional[str] = None,
                     length: str = "short", tone: str = "conversational",
                     prompt: Optional[str] = None,
                     voice_id: Optional[str] = None,
                     language: Optional[str] = None) -> str:
    """Generate the lecture script + storyboard for a lesson. Returns a
    job id — poll with wait_for_job. Rate-limited (default 3/hour)."""
    body = {"lecture_style": length, "tone": tone}
    if lecture_format_id:
        body["lecture_format_id"] = lecture_format_id
    if prompt:
        body["prompt"] = prompt
    if voice_id:
        body["voice_id"] = voice_id
    if language:
        body["language"] = language
    return json.dumps(_req("POST", f"/v1/lessons/{lesson_id}/generate",
                           json=body, idempotent=True), default=str)


@mcp.tool()
def get_storyboard(lesson_id: str) -> str:
    """The lesson's newest script as a compact storyboard: every scene's
    id, title, narration and component (bulky render props elided — edit
    them via the REST API if needed)."""
    scripts = _req("GET", f"/v1/lessons/{lesson_id}/scripts")
    if isinstance(scripts, dict) and scripts.get("error"):
        return json.dumps(scripts)
    if not scripts:
        return json.dumps({"error": "lesson has no script yet"})
    full = _req("GET", f"/v1/scripts/{scripts[0]['id']}")
    if isinstance(full, dict) and full.get("error"):
        return json.dumps(full)
    compact = {
        "script_id": full.get("id"),
        "lesson_id": lesson_id,
        "sections": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "scenes": [
                    {
                        "id": sub.get("id"),
                        "title": sub.get("title"),
                        "narration": sub.get("content"),
                        "component_id": (sub.get("remotion_component") or {}).get("component_id"),
                    }
                    for sub in (s.get("subphases") or [])
                ],
            }
            for s in (full.get("sections") or [])
        ],
    }
    return _cap(compact, 60000)


@mcp.tool()
def update_scene(script_id: str, scene_id: str, mode: str = "edit",
                 narration: Optional[str] = None, title: Optional[str] = None,
                 instruction: Optional[str] = None,
                 component_id: Optional[str] = None) -> str:
    """Edit one scene. mode=edit sets narration/title literally (stale
    narration carriers are cleared server-side); mode=rewrite asks the LLM
    (instruction); mode=remap switches the visual component."""
    if mode == "rewrite":
        return json.dumps(_req(
            "POST", f"/v1/scripts/{script_id}/scenes/{scene_id}/rewrite",
            json={"instruction": instruction}), default=str)
    if mode == "remap":
        return json.dumps(_req(
            "POST", f"/v1/scripts/{script_id}/scenes/{scene_id}/remap",
            json={"component_id": component_id, "instruction": instruction}),
            default=str)
    return json.dumps(_req(
        "PATCH", f"/v1/scripts/{script_id}/scenes/{scene_id}",
        json={"narration": narration, "title": title,
              "component_id": component_id}), default=str)


@mcp.tool()
def add_scene(script_id: str, section_id: str, description: str,
              position: Optional[int] = None) -> str:
    """Generate + insert a new scene into a section from a description."""
    return json.dumps(_req("POST", f"/v1/scripts/{script_id}/scenes", json={
        "section_id": section_id, "description": description,
        "position": position}), default=str)


@mcp.tool()
def delete_scene(script_id: str, scene_id: str) -> str:
    """Remove one scene from the storyboard."""
    return json.dumps(_req(
        "DELETE", f"/v1/scripts/{script_id}/scenes/{scene_id}"), default=str)


@mcp.tool()
def render_video(lesson_id: str, resolution: str = "1080p",
                 voice_id: Optional[str] = None,
                 generate_first: bool = False,
                 length: str = "short") -> str:
    """Script → narration audio → final MP4, one job. generate_first=True
    also generates a fresh script. Poll the returned job with wait_for_job
    (renders take 10-40 min)."""
    body: dict[str, Any] = {"resolution": resolution, "voice_id": voice_id}
    if generate_first:
        body["generate"] = {"lecture_style": length}
    return json.dumps(_req("POST", f"/v1/lessons/{lesson_id}/videos",
                           json=body, idempotent=True), default=str)


@mcp.tool()
def wait_for_job(job_id: str, timeout_seconds: int = 120) -> str:
    """Poll a job until terminal or timeout (≤120 s per call — re-call for
    long renders). Returns the latest job state either way."""
    timeout_seconds = min(max(timeout_seconds, 5), 120)
    deadline = time.monotonic() + timeout_seconds
    job: Any = {}
    while time.monotonic() < deadline:
        job = _req("GET", f"/v1/jobs/{job_id}")
        if isinstance(job, dict) and (
            job.get("status") in ("succeeded", "failed", "cancelled")
            or job.get("error")
        ):
            break
        time.sleep(5)
    return json.dumps(job, default=str)


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("Set COURSESMITH_API_KEY (create one in Settings → API Keys)")
    mcp.run()
