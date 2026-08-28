"""Topic → finished MP4, in one pipeline call.

    export COURSESMITH_API_KEY=cs_live_...
    python examples/01_create_video.py "How Recursion Unwinds"
"""

import sys

sys.path.insert(0, ".")
from coursesmith import CourseSmith

topic = sys.argv[1] if len(sys.argv) > 1 else "How Recursion Unwinds"

cs = CourseSmith()  # reads COURSESMITH_API_KEY / COURSESMITH_BASE_URL

print("credits:", cs.credits()["balance"])

# 1. One call creates (or reuses) a per-subject basket course + a lesson.
lesson = cs.create_standalone_lesson(topic, "programming")
lesson_id = lesson["subtopic_id"]
print("lesson:", lesson_id)

# 2. Script → narration (TTS) → final MP4, one job. Idempotency-Key is
#    added automatically, so a network retry never double-charges.
job = cs.create_video(
    lesson_id,
    generate={"lecture_style": "short", "tone": "conversational"},
    resolution="1080p",
)
print("pipeline job:", job["job_id"])

# 3. Poll to terminal (raises JobFailed on failure). Renders take 10–40 min.
done = cs.wait_for_job(job["job_id"], timeout=45 * 60)
print("video url:", done["video_url"])

# 4. Download.
path = cs.download_video(done["video_id"], f"{topic[:40].replace(' ', '_')}.mp4")
print("saved:", path)
