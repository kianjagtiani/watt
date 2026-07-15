from datetime import datetime, timezone

from assistant.config import Settings
from assistant.db import connect
from assistant.llm import ToolCall
from assistant import tools
from assistant.store import reminders, tasks, users

SETTINGS = Settings("", "", "", "", "gemini-2.5-flash", "task_reminder",
                    "1555", ":memory:", "America/Los_Angeles")


def _conn():
    conn = connect(":memory:")
    users.add_user(conn, "1555", name="Kian", is_admin=True)
    users.add_user(conn, "1666", name="Friend")
    return conn


def test_add_tasks_and_complete():
    conn = _conn()
    out = tools.dispatch(conn, SETTINGS, "1555", ToolCall("add_tasks", {
        "items": [{"text": "Apply to X", "category": "Applications"}],
        "source": "screenshot",
    }))
    assert out["added"][0]["text"] == "Apply to X"
    tid = out["added"][0]["id"]
    assert tasks.list_tasks(conn, "1555")[0]["source"] == "screenshot"
    out = tools.dispatch(conn, SETTINGS, "1555", ToolCall("complete_task", {"task_id": tid}))
    assert out == {"ok": True}
    out = tools.dispatch(conn, SETTINGS, "1555", ToolCall("complete_task", {"task_id": tid}))
    assert "error" in out


def test_set_reminder_converts_timezone():
    conn = _conn()
    out = tools.dispatch(conn, SETTINGS, "1555", ToolCall("set_reminder", {
        "text": "cancel Prime", "fire_at": "2026-07-28 09:00", "recurrence": "none",
    }))
    assert out["ok"]
    r = reminders.list_reminders(conn, "1555")[0]
    utc = datetime.fromisoformat(r["next_fire_at"]).astimezone(timezone.utc)
    assert utc == datetime(2026, 7, 28, 16, 0, tzinfo=timezone.utc)  # PDT = UTC-7


def test_admin_gate():
    conn = _conn()
    out = tools.dispatch(conn, SETTINGS, "1666", ToolCall("add_user", {"phone": "1777"}))
    assert "error" in out
    out = tools.dispatch(conn, SETTINGS, "1555",
                         ToolCall("add_user", {"phone": "1777", "name": "New"}))
    assert out["ok"] and users.is_allowed(conn, "1777")


def test_research_and_unknown_tool(monkeypatch):
    conn = _conn()
    monkeypatch.setattr(tools.research, "search_web",
                        lambda q, max_results=5: [{"title": "t", "url": "u", "snippet": "s"}])
    out = tools.dispatch(conn, SETTINGS, "1555", ToolCall("research", {"query": "q"}))
    assert out["results"][0]["title"] == "t"
    out = tools.dispatch(conn, SETTINGS, "1555", ToolCall("nope", {}))
    assert "error" in out
