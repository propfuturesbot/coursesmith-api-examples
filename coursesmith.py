"""
CourseSmith Python SDK — a thin typed client for the public developer API.

    pip install httpx

    from coursesmith import CourseSmith

    cs = CourseSmith(api_key="cs_live_...")            # or COURSESMITH_API_KEY
    lesson = cs.create_standalone_lesson("Intro to B-Trees", "programming")
    job = cs.create_video(lesson["subtopic_id"],
                          generate={"lecture_format_id": "explainer",
                                    "lecture_style": "short"})
    done = cs.wait_for_job(job["job_id"], timeout=3600)
    print(done["video_url"])

Every method raises CourseSmithError on non-2xx, carrying the API's stable
error `code` (insufficient_credits, rate_limit_exceeded, ...). Long
operations return a job dict — pass its `job_id` to wait_for_job().
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = "https://api.coursesmith.ai"
_TERMINAL = {"succeeded", "failed", "cancelled"}


class CourseSmithError(Exception):
    def __init__(self, status_code: int, code: str, message: str,
                 request_id: Optional[str] = None, body: Any = None):
        super().__init__(f"[{status_code} {code}] {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.body = body


class JobFailed(CourseSmithError):
    """wait_for_job saw a failed/cancelled terminal state."""


class CourseSmith:
    def __init__(self, api_key: Optional[str] = None,
                 base_url: Optional[str] = None, timeout: float = 120.0):
        self.api_key = api_key or os.environ.get("COURSESMITH_API_KEY", "")
        if not self.api_key.startswith("cs_"):
            raise ValueError(
                "Provide an API key (cs_live_...) via api_key= or "
                "COURSESMITH_API_KEY. Create one in the dashboard under "
                "Settings → API Keys."
            )
        self.base_url = (base_url or os.environ.get("COURSESMITH_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )

    # ── plumbing ────────────────────────────────────────────────────────────

    def _req(self, method: str, path: str, *, idempotent: bool = False,
             **kwargs) -> Any:
        headers = kwargs.pop("headers", {}) or {}
        if idempotent:
            headers.setdefault("Idempotency-Key", uuid.uuid4().hex)
        resp = self._client.request(method, path, headers=headers, **kwargs)
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
            except Exception:  # noqa: BLE001
                err = {}
            raise CourseSmithError(
                resp.status_code,
                err.get("code", "error"),
                err.get("message", resp.text[:500]),
                err.get("request_id"),
                err or resp.text,
            )
        ctype = resp.headers.get("content-type", "")
        return resp.json() if "json" in ctype else resp.content

    # ── account & options ───────────────────────────────────────────────────

    def me(self) -> dict: return self._req("GET", "/v1/me")
    def credits(self) -> dict: return self._req("GET", "/v1/credits")
    def pricing(self) -> dict: return self._req("GET", "/v1/pricing")
    def generation_options(self) -> dict:
        return self._req("GET", "/v1/generation-options")
    def lecture_formats(self, subject_domain: Optional[str] = None) -> dict:
        return self._req("GET", "/v1/lecture-formats",
                         params={"subject_domain": subject_domain} if subject_domain else None)
    def subjects(self) -> list: return self._req("GET", "/v1/subjects")
    def suggest_subject(self, title: str, description: Optional[str] = None) -> dict:
        return self._req("POST", "/v1/subjects/suggest",
                         json={"title": title, "description": description})
    def voices(self) -> dict: return self._req("GET", "/v1/voices")
    def branding_assets(self, asset_type: Optional[str] = None) -> dict:
        return self._req("GET", "/v1/branding-assets",
                         params={"asset_type": asset_type} if asset_type else None)

    # ── courses / lessons ───────────────────────────────────────────────────

    def create_course(self, title: str, **fields) -> dict:
        return self._req("POST", "/v1/courses", json={"title": title, **fields})
    def list_courses(self, **params) -> dict:
        return self._req("GET", "/v1/courses", params=params or None)
    def get_course(self, course_id: str) -> dict:
        return self._req("GET", f"/v1/courses/{course_id}")
    def create_topic(self, course_id: str, title: str, **fields) -> dict:
        return self._req("POST", f"/v1/courses/{course_id}/topics",
                         json={"title": title, **fields})
    def create_lesson(self, topic_id: str, title: str, **fields) -> dict:
        return self._req("POST", f"/v1/topics/{topic_id}/lessons",
                         json={"title": title, **fields})
    def create_standalone_lesson(self, title: str, subject_domain: str,
                                 subject_label: Optional[str] = None) -> dict:
        """One call → {course_id, topic_id, subtopic_id}; use subtopic_id
        as the lesson_id everywhere else."""
        return self._req("POST", "/v1/lessons/standalone", json={
            "title": title, "subject_domain": subject_domain,
            "subject_label": subject_label,
        })
    def generate_course_structure(self, course_id: str, *, difficulty_level: str,
                                  subject_domain: str, course_length: str = "standard",
                                  **fields) -> dict:
        return self._req("POST", f"/v1/courses/{course_id}/structure", json={
            "difficulty_level": difficulty_level,
            "subject_domain": subject_domain,
            "course_length": course_length, **fields,
        })

    # ── sources (grounded path) ─────────────────────────────────────────────

    def ingest_url(self, url: str) -> dict:
        return self._req("POST", "/v1/sources", json={"type": "url", "url": url})
    def ingest_text(self, markdown: str) -> dict:
        return self._req("POST", "/v1/sources",
                         json={"type": "text", "markdown": markdown})
    def ingest_youtube(self, urls: list[str]) -> dict:
        return self._req("POST", "/v1/sources",
                         json={"type": "youtube", "urls": urls})
    def ingest_github(self, repo_url: str) -> dict:
        return self._req("POST", "/v1/sources",
                         json={"type": "github", "repo_url": repo_url})
    def process_source(self, source_id: str, force: bool = False) -> dict:
        """Blocking 30–90 s: LLM split into concepts + proposed lectures."""
        return self._req("POST", f"/v1/sources/{source_id}/process",
                         params={"force": force})
    def get_source(self, source_id: str) -> dict:
        return self._req("GET", f"/v1/sources/{source_id}")
    def commit_source(self, source_id: str, lectures: list[dict],
                      destination: dict, topics: Optional[list[dict]] = None) -> dict:
        """→ {course_id, topic_id, subtopic_ids}; grounded lesson ids."""
        body: dict[str, Any] = {"lectures": lectures, "destination": destination}
        if topics:
            body["topics"] = topics
        return self._req("POST", f"/v1/sources/{source_id}/commit", json=body)
    def course_from_repo(self, repo_url: str) -> dict:
        return self._req("POST", "/v1/courses/from-repo",
                         json={"type": "github", "repo_url": repo_url})
    def course_from_document(self, file_path: str, **form) -> dict:
        with open(file_path, "rb") as f:
            return self._req("POST", "/v1/courses/from-document",
                             files={"file": (os.path.basename(file_path), f)},
                             data=form or None)

    # ── generation & the edit loop ──────────────────────────────────────────

    def generate(self, lesson_id: str, **options) -> dict:
        """Start script generation (all formats/toggles). Returns a job."""
        return self._req("POST", f"/v1/lessons/{lesson_id}/generate",
                         json=options, idempotent=True)
    def plan(self, lesson_id: str, **options) -> dict:
        return self._req("POST", f"/v1/lessons/{lesson_id}/plan", json=options)
    def generate_from_plan(self, lesson_id: str, approved_plan: list[dict],
                           **options) -> dict:
        return self._req("POST", f"/v1/lessons/{lesson_id}/generate-from-plan",
                         json={**options, "approved_plan": approved_plan},
                         idempotent=True)
    def list_scripts(self, lesson_id: str) -> list:
        return self._req("GET", f"/v1/lessons/{lesson_id}/scripts")
    def get_script(self, script_id: str) -> dict:
        return self._req("GET", f"/v1/scripts/{script_id}")
    def update_script(self, script_id: str, **fields) -> dict:
        """GET → modify → this. Narration authority is handled server-side."""
        return self._req("PUT", f"/v1/scripts/{script_id}", json=fields)
    def patch_scene(self, script_id: str, scene_id: str, **fields) -> dict:
        return self._req("PATCH", f"/v1/scripts/{script_id}/scenes/{scene_id}",
                         json=fields)
    def rewrite_scene(self, script_id: str, scene_id: str,
                      instruction: Optional[str] = None) -> dict:
        return self._req("POST",
                         f"/v1/scripts/{script_id}/scenes/{scene_id}/rewrite",
                         json={"instruction": instruction})
    def remap_scene(self, script_id: str, scene_id: str, component_id: str,
                    instruction: Optional[str] = None) -> dict:
        return self._req("POST",
                         f"/v1/scripts/{script_id}/scenes/{scene_id}/remap",
                         json={"component_id": component_id,
                               "instruction": instruction})
    def add_scene(self, script_id: str, section_id: str, description: str,
                  **fields) -> dict:
        return self._req("POST", f"/v1/scripts/{script_id}/scenes",
                         json={"section_id": section_id,
                               "description": description, **fields})
    def delete_scene(self, script_id: str, scene_id: str) -> dict:
        return self._req("DELETE", f"/v1/scripts/{script_id}/scenes/{scene_id}")

    # ── videos ──────────────────────────────────────────────────────────────

    def create_video(self, lesson_id: str, *, generate: Optional[dict] = None,
                     script_id: Optional[str] = None,
                     voice_id: Optional[str] = None,
                     resolution: str = "1080p") -> dict:
        """The whole pipeline: (optional generate) → TTS → MP4. Job-based."""
        return self._req("POST", f"/v1/lessons/{lesson_id}/videos", json={
            "generate": generate, "script_id": script_id,
            "voice_id": voice_id, "resolution": resolution,
        }, idempotent=True)
    def list_videos(self, **params) -> dict:
        return self._req("GET", "/v1/videos", params=params or None)
    def get_video(self, video_id: str) -> dict:
        return self._req("GET", f"/v1/videos/{video_id}")
    def download_video(self, video_id: str, path: str) -> str:
        job = self.get_video(video_id)
        if not job.get("video_url"):
            raise CourseSmithError(409, "conflict",
                                   f"Video not ready (status {job.get('status')})")
        with httpx.stream("GET", job["video_url"], timeout=600) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        return path
    def export_video(self, video_id: str, format: str = "mp3",
                     resolution: str = "1080p") -> dict:
        return self._req("POST", f"/v1/videos/{video_id}/export",
                         json={"format": format, "resolution": resolution})
    def video_captions(self, video_id: str) -> dict:
        return self._req("GET", f"/v1/videos/{video_id}/captions")

    # ── quizzes & exports ───────────────────────────────────────────────────

    def create_quiz(self, lesson_id: str, **fields) -> dict:
        return self._req("POST", f"/v1/lessons/{lesson_id}/quiz", json=fields)
    def export_quiz(self, quiz_id: str, format_id: str) -> bytes:
        return self._req("GET", f"/v1/quizzes/{quiz_id}/export/{format_id}")
    def export_deck(self, script_id: str, theme: str = "aurora") -> bytes:
        return self._req("GET", f"/v1/scripts/{script_id}/deck.pptx",
                         params={"theme": theme})

    # ── jobs & webhooks ─────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> dict:
        return self._req("GET", f"/v1/jobs/{job_id}")
    def cancel_job(self, job_id: str) -> dict:
        return self._req("POST", f"/v1/jobs/{job_id}/cancel")

    def wait_for_job(self, job_id: str, timeout: float = 3600,
                     poll_interval: float = 6.0) -> dict:
        """Poll until terminal. Returns the succeeded job; raises JobFailed
        on failed/cancelled, TimeoutError past `timeout` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(job_id)
            status = job.get("status")
            if status == "succeeded":
                return job
            if status in _TERMINAL:
                raise JobFailed(200, f"job_{status}",
                                job.get("error") or f"job {status}", body=job)
            if time.monotonic() > deadline:
                raise TimeoutError(f"job {job_id} still {status} after {timeout}s")
            time.sleep(poll_interval)

    def create_webhook(self, url: str, events: Optional[list[str]] = None,
                       job_types: Optional[list[str]] = None) -> dict:
        body: dict[str, Any] = {"url": url}
        if events:
            body["events"] = events
        if job_types:
            body["job_types"] = job_types
        return self._req("POST", "/v1/webhooks", json=body)
    def list_webhooks(self) -> list:
        return self._req("GET", "/v1/webhooks")
    def delete_webhook(self, webhook_id: str) -> dict:
        return self._req("DELETE", f"/v1/webhooks/{webhook_id}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CourseSmith":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
