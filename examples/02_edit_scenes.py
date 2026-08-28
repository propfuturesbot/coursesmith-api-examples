"""The edit loop: generate a script, edit scenes three different ways,
then render the edited version.

    python examples/02_edit_scenes.py <LESSON_ID>

(Use example 01 or the quickstart to get a lesson id first. If the lesson
already has a script, the generation step re-attaches instead of paying
again.)
"""

import sys

sys.path.insert(0, ".")
from coursesmith import CourseSmith

lesson_id = sys.argv[1]
cs = CourseSmith()

# 1. Generate the script first (skip if one exists — cheapest tier shown).
scripts = cs.list_scripts(lesson_id)
if not scripts:
    gen = cs.generate(lesson_id, lecture_style="short", tone="conversational")
    cs.wait_for_job(gen["job_id"], timeout=30 * 60)
    scripts = cs.list_scripts(lesson_id)
script_id = scripts[0]["id"]

# 2. Read the storyboard: scenes live in sections[].subphases[].
script = cs.get_script(script_id)
scenes = [sub for sec in script["sections"] for sub in (sec.get("subphases") or [])]
for s in scenes:
    comp = (s.get("remotion_component") or {}).get("component_id")
    print(f"scene {s['id']}  [{comp}]  {s['title']}")

first, second = scenes[0], scenes[min(1, len(scenes) - 1)]

# 3a. Literal edit — set the narration text exactly. The server clears the
#     stale derived narration carriers, so the MP4 always speaks this text.
cs.patch_scene(script_id, first["id"],
               narration="Welcome! In the next minute you'll see exactly "
                         "how the call stack unwinds.",
               title="A one-minute promise")

# 3b. LLM restyle — free-text instruction (this is how you get e.g. a
#     chalkboard look on a scene).
cs.rewrite_scene(script_id, second["id"],
                 instruction="Restyle as a CHALKBOARD: dark board, white "
                             "chalk strokes, handwritten labels. Keep the "
                             "same teaching content.")

# 3c. Component swap — let the LLM repopulate props for a new visual.
#     (Component ids come from generation output or the component catalog.)
# cs.remap_scene(script_id, second["id"], component_id="KeyTakeaways")

# 4. Render the EDITED script: pipeline without `generate` uses the
#    lesson's newest script.
job = cs.create_video(lesson_id, resolution="1080p")
done = cs.wait_for_job(job["job_id"], timeout=45 * 60)
print("edited video:", done["video_url"])
