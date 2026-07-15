from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from assistant import research
from assistant.llm import ToolCall
from assistant.store import reminders, tasks, users

_ITEM = {"type": "object", "properties": {
    "text": {"type": "string"},
    "category": {"type": "string", "description": "Short category like Applications, Errands, School"},
}, "required": ["text"]}

TOOL_DEFS = [
    {"name": "add_tasks",
     "description": "Add one or more to-do items for the user.",
     "parameters": {"type": "object", "properties": {
         "items": {"type": "array", "items": _ITEM},
         "source": {"type": "string", "enum": ["text", "screenshot"]},
     }, "required": ["items"]}},
    {"name": "complete_task",
     "description": "Mark a task done by its id (ids are shown in the task list).",
     "parameters": {"type": "object", "properties": {
         "task_id": {"type": "integer"}}, "required": ["task_id"]}},
    {"name": "update_task",
     "description": "Change a task's text and/or category.",
     "parameters": {"type": "object", "properties": {
         "task_id": {"type": "integer"}, "text": {"type": "string"},
         "category": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "list_tasks",
     "description": "List the user's tasks (status open or done).",
     "parameters": {"type": "object", "properties": {
         "status": {"type": "string", "enum": ["open", "done"]}}}},
    {"name": "set_reminder",
     "description": "Schedule a reminder. fire_at is local time 'YYYY-MM-DD HH:MM' in the user's timezone.",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string"}, "fire_at": {"type": "string"},
         "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"]},
     }, "required": ["text", "fire_at"]}},
    {"name": "cancel_reminder",
     "description": "Cancel a reminder by its id.",
     "parameters": {"type": "object", "properties": {
         "reminder_id": {"type": "integer"}}, "required": ["reminder_id"]}},
    {"name": "list_reminders",
     "description": "List the user's active reminders.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "research",
     "description": "Web-search a topic. Use ONLY when the user explicitly asks to research/look up something.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"}}, "required": ["query"]}},
    {"name": "add_user",
     "description": "ADMIN ONLY: allow a new phone number to use the assistant.",
     "parameters": {"type": "object", "properties": {
         "phone": {"type": "string"}, "name": {"type": "string"}}, "required": ["phone"]}},
    {"name": "remove_user",
     "description": "ADMIN ONLY: remove a phone number from the allowlist.",
     "parameters": {"type": "object", "properties": {
         "phone": {"type": "string"}}, "required": ["phone"]}},
    {"name": "list_users",
     "description": "ADMIN ONLY: list allowed users.",
     "parameters": {"type": "object", "properties": {}}},
]

_ADMIN_TOOLS = {"add_user", "remove_user", "list_users"}


def _row(t) -> dict:
    return {"id": t["id"], "text": t["text"], "category": t["category"]}


def dispatch(conn, settings, phone, call: ToolCall) -> dict:
    user = users.get_user(conn, phone)
    if user is None:
        return {"error": "unknown user"}
    if call.name in _ADMIN_TOOLS and not user["is_admin"]:
        return {"error": "only the admin can manage users"}
    a = call.args
    try:
        if call.name == "add_tasks":
            added = [
                _row_from_id(conn, phone, tasks.add_task(
                    conn, phone, i["text"], i.get("category", "General"),
                    a.get("source", "text")))
                for i in a["items"]
            ]
            return {"added": added}
        if call.name == "complete_task":
            ok = tasks.complete_task(conn, phone, int(a["task_id"]))
            return {"ok": True} if ok else {"error": "no open task with that id"}
        if call.name == "update_task":
            ok = tasks.update_task(conn, phone, int(a["task_id"]),
                                   a.get("text"), a.get("category"))
            return {"ok": True} if ok else {"error": "no task with that id"}
        if call.name == "list_tasks":
            return {"tasks": [_row(t) for t in
                              tasks.list_tasks(conn, phone, a.get("status", "open"))]}
        if call.name == "set_reminder":
            tz = ZoneInfo(user["timezone"])
            local = datetime.strptime(a["fire_at"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            rid = reminders.add_reminder(conn, phone, a["text"],
                                         local.astimezone(timezone.utc),
                                         a.get("recurrence", "none"))
            return {"ok": True, "reminder_id": rid}
        if call.name == "cancel_reminder":
            ok = reminders.cancel_reminder(conn, phone, int(a["reminder_id"]))
            return {"ok": True} if ok else {"error": "no active reminder with that id"}
        if call.name == "list_reminders":
            return {"reminders": [
                {"id": r["id"], "text": r["text"], "fire_at_utc": r["next_fire_at"],
                 "recurrence": r["recurrence"]}
                for r in reminders.list_reminders(conn, phone)]}
        if call.name == "research":
            return {"results": research.search_web(a["query"])}
        if call.name == "add_user":
            users.add_user(conn, a["phone"], a.get("name", ""),
                           timezone_name=settings.default_tz)
            return {"ok": True}
        if call.name == "remove_user":
            ok = users.remove_user(conn, a["phone"])
            return {"ok": True} if ok else {"error": "not a user"}
        if call.name == "list_users":
            return {"users": [{"phone": u["phone"], "name": u["name"]}
                              for u in users.list_users(conn)]}
        return {"error": f"unknown tool {call.name}"}
    except Exception as exc:
        return {"error": str(exc)}


def _row_from_id(conn, phone, task_id) -> dict:
    t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return _row(t)
