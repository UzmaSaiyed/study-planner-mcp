# Study Planner MCP Server

An MCP (Model Context Protocol) server that lets an AI assistant such as Claude search, read and safely update a student's study tasks. Tasks are stored in a local SQLite database.

## What it exposes

| Type | Name | Purpose |
|---|---|---|
| Tool (read) | `search_tasks` | Search tasks by title, subject or notes (every word must match), with an optional status filter |
| Tool (read) | `get_task` | Full record for one task |
| Tool (read) | `list_due_soon` | Tasks that are overdue or due within N days (excludes Done) |
| Tool (write) | `add_task` | Add a task (needs confirmation) |
| Tool (write) | `mark_task_done` | Mark a task Done (needs confirmation) |
| Resource | `timetable://exams` | Exam timetable text from a local file |
| Prompt | `weekly_revision_plan` | Builds a day-by-day revision plan from due tasks and the timetable |

## Safety design

- **Read-only by default.** Changes only work when `READ_ONLY=false` is set.
- **Two-step writes.** The first call changes nothing and returns a preview and a short-lived code. The change happens only when the same call is repeated with that code. The code is single-use, expires after 2 minutes, and is tied to the exact arguments.
- **Input validation.** Statuses, dates, lengths and limits are checked. All SQL is parameterized.
- **Untrusted text.** Task notes are treated as data, not instructions, because free text can carry prompt injection.
- **Rate limiting.** At most 30 tool calls per minute by default.
- **Logging** goes to stderr, because stdout carries the protocol. Logs record tool names, task ids and search queries, but not task notes or titles.

## Project structure

```
server.py   MCP server: tools, resource, prompt and safety checks
db.py       SQLite helpers
seed.py     Fictional sample data
tests/      Integration tests that talk to the real server over stdio
```

## Setup (Windows PowerShell)

Requires Python 3.10 or newer. Tested with the MCP Python SDK 2.3.0 (pinned in `requirements.txt`). MCP Inspector needs Node.js.

```powershell
git clone https://github.com/UzmaSaiyed/study-planner-mcp.git
cd study-planner-mcp
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
```

`seed.py` adds 6 fictional sample tasks. Run it once, because running it again adds them again. Create `exam_timetable.txt` in the project folder, for example:

```
Exam timetable
Database Systems: 2026-11-20, 10:00, Room A12
Operating Systems: 2026-11-23, 10:00, Room B04
```

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `PLANNER_DB` | `planner.db` | Path to the SQLite database |
| `READ_ONLY` | `true` | Set to `false` to allow changes |
| `RATE_LIMIT_PER_MINUTE` | `30` | Maximum tool calls per minute |
| `EXAM_TIMETABLE_PATH` | `exam_timetable.txt` | Path to the timetable text file |

MCP Inspector and Claude Desktop do not pass your shell's environment variables to the server, so set these in the client's config, as shown below.

## Try it with MCP Inspector

```powershell
npx @modelcontextprotocol/inspector -e READ_ONLY=false python server.py
```

Leave out `-e READ_ONLY=false` to see read-only mode block writes.

## Connect to Claude Desktop

Add this inside the top level of `claude_desktop_config.json` (its location depends on how Claude Desktop was installed), using your own full paths with doubled backslashes:

```json
"mcpServers": {
  "study-planner": {
    "command": "C:\\path\\to\\study-planner-mcp\\.venv\\Scripts\\python.exe",
    "args": ["C:\\path\\to\\study-planner-mcp\\server.py"],
    "env": {
      "PLANNER_DB": "C:\\path\\to\\study-planner-mcp\\planner.db",
      "EXAM_TIMETABLE_PATH": "C:\\path\\to\\study-planner-mcp\\exam_timetable.txt",
      "READ_ONLY": "true"
    }
  }
}
```

Restart Claude Desktop fully after any change to the server or the config.

## Things to try in a client

- "What study tasks do I have due in the next 7 days?"
- "Find my database normalization task and show its notes."
- "Add a task: Revise ER diagrams for Database Systems, due 2026-11-20." (needs `READ_ONLY=false`)
- Run the **Weekly revision plan** prompt.

## Tests

```powershell
python -m pytest tests -q
```

The tests start the real server as a subprocess and talk to it over stdio. They cover every tool, bad inputs, SQL injection attempts, read-only mode, the confirmation flow, rate limiting, the resource and the prompt. They use a temporary database.

## Limitations

- The confirmation code is enforced by the server, but a server cannot prove that a human approved. The MCP client's own tool-approval prompt is the real human check, and the server adds defense in depth by rejecting replayed, expired or mismatched requests.
- Runs locally over stdio only. There is no authentication, and the rate limit is in memory and resets when the server restarts.
- Single user, SQLite. Tested on fictional data.
- In Claude Desktop, resources are attached by the user and the model could not open one by itself in my testing, so the revision plan prompt embeds the timetable text directly.
- Search requires every word of the query to appear in a task (case-insensitive, any order). There is no ranking, spelling correction or synonyms.

## License

MIT