"""URL → grounded lessons → video that teaches from the article.

    python examples/03_grounded_from_url.py https://en.wikipedia.org/wiki/B-tree

Flow: ingest the URL (synchronous — text is extracted immediately), let
the LLM propose a lecture split, commit the split (the lessons stay
GROUNDED in the source text), then pipeline one lesson to a video.
"""

import sys

sys.path.insert(0, ".")
from coursesmith import CourseSmith

url = sys.argv[1] if len(sys.argv) > 1 else "https://en.wikipedia.org/wiki/B-tree"
cs = CourseSmith()

# 1. Ingest — returns source_id + word_count right away for URLs.
#    (YouTube and github types return a job instead; poll those.)
src = cs.ingest_url(url)
source_id = src["source_id"]
print(f"ingested {src['word_count']} words -> source {source_id}")

# 2. LLM split into concepts + proposed lectures. Blocking 30–90 s;
#    charged once — the proposal is cached on the source, so re-running
#    (without force=True) is free.
proposal = cs.process_source(source_id)
lectures = proposal["proposed_lectures"]
for i, lec in enumerate(lectures):
    print(f"[{i}] {lec['title']} — {lec['summary']}")

# 3. Commit the split — creates a course whose lessons carry the source
#    text as grounding: generation teaches FROM the document, not from
#    general knowledge.
committed = cs.commit_source(
    source_id,
    lectures=lectures[:3],                      # keep it cheap: first 3
    destination={"mode": "new_course", "title": "B-Trees, from the source"},
)
lesson_ids = committed["subtopic_ids"]
print("course:", committed["course_id"], "grounded lessons:", lesson_ids)

# 4. Video for the first grounded lesson.
job = cs.create_video(lesson_ids[0],
                      generate={"lecture_style": "short"},
                      resolution="1080p")
done = cs.wait_for_job(job["job_id"], timeout=45 * 60)
print("video:", done["video_url"])
