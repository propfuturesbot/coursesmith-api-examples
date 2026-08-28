# CourseSmith MCP Server

Lets AI agents (Claude, Cursor, Copilot, Windsurf…) drive the CourseSmith
public API through 17 tools: create lessons, ingest sources, generate
lectures, read/edit storyboards, render videos, and poll jobs.

## Requirements

```bash
pip install "mcp[cli]" httpx     # plain `pip install mcp httpx` also works
```

Python ≥ 3.10. The server file is `coursesmith_mcp.py` (single file — copy
it anywhere or reference it in this repo).

Environment:
- `COURSESMITH_API_KEY` — required. Create at coursesmith.ai → **Settings →
  API Keys** (paid tiers + admins).
- `COURSESMITH_BASE_URL` — optional. Defaults to
  `https://api.coursesmith.ai`; use `http://localhost:8091` (or
  `http://localhost:8090/api/public`) for local dev.

Sanity check from a terminal:

```bash
COURSESMITH_API_KEY=cs_live_... python coursesmith_mcp.py   # waits on stdio = healthy
```

## Connect your client

All clients speak the same stdio config; only the file location differs.
Use the ABSOLUTE path to `coursesmith_mcp.py` and a python that has `mcp`
installed (a venv's `bin/python` is safest).

### Claude Code (CLI / desktop / IDE)

One command:

```bash
claude mcp add coursesmith -e COURSESMITH_API_KEY=cs_live_... \
  -- python /abs/path/coursesmith-api-examples/mcp/coursesmith_mcp.py
```

Or per-project: the product repo ships `.mcp.json` at its root — anyone opening
repo in Claude Code gets the server automatically; just
`export COURSESMITH_API_KEY=cs_live_...` first.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "coursesmith": {
      "command": "python",
      "args": ["/abs/path/coursesmith-api-examples/mcp/coursesmith_mcp.py"],
      "env": { "COURSESMITH_API_KEY": "cs_live_..." }
    }
  }
}
```

Restart Claude Desktop; the tools appear under the 🔌 icon.

### Cursor

`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` in your project — same
JSON shape as Claude Desktop above. Enable it under **Cursor Settings → MCP**.

### VS Code (GitHub Copilot agent mode)

`.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "coursesmith": {
      "type": "stdio",
      "command": "python",
      "args": ["/abs/path/coursesmith-api-examples/mcp/coursesmith_mcp.py"],
      "env": { "COURSESMITH_API_KEY": "${input:coursesmith_key}" },
      "inputs": [{ "id": "coursesmith_key", "type": "promptString",
                   "description": "CourseSmith API key", "password": true }]
    }
  }
}
```

(VS Code ≥ 1.99 with Copilot; MCP is used in agent mode.)

### Windsurf

`~/.codeium/windsurf/mcp_config.json` — same `mcpServers` JSON shape as
Claude Desktop.

## The tools

`list_options` · `list_voices` · `get_credits` · `list_courses` ·
`get_course` · `create_course` · `create_lesson` · `ingest_source` ·
`process_source` · `commit_source` · `generate_lecture` · `get_storyboard` ·
`update_scene` (edit | rewrite | remap) · `add_scene` · `delete_scene` ·
`render_video` · `wait_for_job`

Typical agent flow: `create_lesson` → `generate_lecture` → `wait_for_job`
(re-call until terminal; each call polls ≤120 s) → `get_storyboard` →
`update_scene` → `render_video` → `wait_for_job` → the job's `video_url`.

Notes for agents: enums come from `list_options` (nothing is hardcoded);
charging tools send an idempotency key automatically, so a retried tool
call never double-charges; renders take 10–40 min — keep re-calling
`wait_for_job` rather than giving up.

Full REST reference: https://www.coursesmith.ai/developers
