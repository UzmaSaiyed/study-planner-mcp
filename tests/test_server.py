import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent


def make_client(tmp_path, read_only="true", rate_limit="30"):
    timetable = tmp_path / "timetable.txt"
    timetable.write_text("Database Systems: 2026-11-20", encoding="utf-8")
    env = dict(os.environ)
    env.update(
        PLANNER_DB=str(tmp_path / "test.db"),
        READ_ONLY=read_only,
        RATE_LIMIT_PER_MINUTE=rate_limit,
        EXAM_TIMETABLE_PATH=str(timetable),
    )
    subprocess.run([sys.executable, "seed.py"], cwd=ROOT, env=env, check=True, capture_output=True)
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], env=env, cwd=str(ROOT)
    )
    return Client(params)


def run(coro):
    return asyncio.run(coro)


def text_of(result):
    return "".join(getattr(block, "text", "") for block in result.content)


def count_rows(tmp_path, where="1=1"):
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return conn.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}").fetchone()[0]
    finally:
        conn.close()


def test_lists_five_tools_with_descriptions(tmp_path):
    async def go():
        async with make_client(tmp_path) as client:
            tools = (await client.list_tools()).tools
            assert {t.name for t in tools} == {
                "search_tasks", "get_task", "list_due_soon", "add_task", "mark_task_done",
            }
            assert all(t.description and len(t.description) > 40 for t in tools)
            by_name = {t.name: t for t in tools}
            assert by_name["search_tasks"].annotations.read_only_hint is True
            assert by_name["add_task"].annotations.read_only_hint is False
    run(go())


def test_read_tools_return_expected_data(tmp_path):
    async def go():
        async with make_client(tmp_path) as client:
            found = await client.call_tool("search_tasks", {"query": "viva"})
            assert len(found.structured_content["result"]) == 1

            detail = await client.call_tool("get_task", {"task_id": 1})
            assert "Revise normalization" in text_of(detail)

            due = await client.call_tool("list_due_soon", {"within_days": 7})
            assert "Finish regression notes" in text_of(due)
            assert "Practice SQL joins" not in text_of(due)
            assert "Prepare viva questions" not in text_of(due)

            missing = await client.call_tool("get_task", {"task_id": 999})
            assert missing.is_error
            assert "No task with id 999" in text_of(missing)
    run(go())


def test_bad_inputs_are_rejected_and_sql_injection_is_harmless(tmp_path):
    async def go():
        async with make_client(tmp_path) as client:
            assert (await client.call_tool("search_tasks", {"limit": 500})).is_error
            assert (await client.call_tool("search_tasks", {"status": "Finished"})).is_error
            assert (await client.call_tool("list_due_soon", {"within_days": 50})).is_error

            attack = await client.call_tool(
                "search_tasks", {"query": "'; DROP TABLE tasks;--"}
            )
            assert not attack.is_error
            assert attack.structured_content["result"] == []
    run(go())
    assert count_rows(tmp_path) == 6


def test_read_only_mode_is_the_default_and_blocks_changes(tmp_path):
    async def go():
        async with make_client(tmp_path) as client:
            result = await client.call_tool("add_task", {"title": "Test", "subject": "Test"})
            assert result.is_error
            assert "read-only" in text_of(result)
    run(go())
    assert count_rows(tmp_path) == 6


def test_write_needs_two_steps_and_the_code_works_once(tmp_path):
    async def go():
        async with make_client(tmp_path, read_only="false") as client:
            args = {"title": "Revise ER diagrams", "subject": "Database Systems"}

            first = await client.call_tool("add_task", args)
            assert first.structured_content["status"] == "confirmation_required"
            assert count_rows(tmp_path) == 6
            code = first.structured_content["confirm_code"]

            changed = await client.call_tool(
                "add_task", {**args, "title": "Something else", "confirm_code": code}
            )
            assert changed.is_error

            second = await client.call_tool("add_task", args)
            code = second.structured_content["confirm_code"]
            done = await client.call_tool("add_task", {**args, "confirm_code": code})
            assert done.structured_content["status"] == "done"

            reused = await client.call_tool("add_task", {**args, "confirm_code": code})
            assert reused.is_error
    run(go())
    assert count_rows(tmp_path, "title = 'Revise ER diagrams'") == 1


def test_mark_task_done_flow(tmp_path):
    async def go():
        async with make_client(tmp_path, read_only="false") as client:
            first = await client.call_tool("mark_task_done", {"task_id": 3})
            assert "Finish regression notes" in first.structured_content["preview"]
            code = first.structured_content["confirm_code"]

            done = await client.call_tool("mark_task_done", {"task_id": 3, "confirm_code": code})
            assert done.structured_content["status"] == "done"

            due = await client.call_tool("list_due_soon", {"within_days": 7})
            assert "Finish regression notes" not in text_of(due)

            already = await client.call_tool("mark_task_done", {"task_id": 4})
            assert already.is_error
    run(go())


def test_bad_date_is_rejected(tmp_path):
    async def go():
        async with make_client(tmp_path, read_only="false") as client:
            result = await client.call_tool(
                "add_task", {"title": "A", "subject": "B", "due_on": "2026-13-45"}
            )
            assert result.is_error
            assert "not a real date" in text_of(result)
    run(go())


def test_rate_limit_blocks_too_many_calls(tmp_path):
    async def go():
        async with make_client(tmp_path, rate_limit="3") as client:
            for _ in range(3):
                assert not (await client.call_tool("search_tasks", {})).is_error
            blocked = await client.call_tool("search_tasks", {})
            assert blocked.is_error
            assert "Too many requests" in text_of(blocked)
    run(go())


def test_resource_and_prompt(tmp_path):
    async def go():
        async with make_client(tmp_path) as client:
            resources = (await client.list_resources()).resources
            assert [str(r.uri) for r in resources] == ["timetable://exams"]
            content = await client.read_resource("timetable://exams")
            assert "Database Systems" in content.contents[0].text

            prompts = (await client.list_prompts()).prompts
            assert [p.name for p in prompts] == ["weekly_revision_plan"]
            prompt = await client.get_prompt("weekly_revision_plan", {"days": "5"})
            text = prompt.messages[0].content.text
            assert "within_days=5" in text
            assert "Database Systems: 2026-11-20" in text
    run(go())