import json
from datetime import datetime
from zoneinfo import ZoneInfo

from assistant import tools
from assistant.store import history, reminders, tasks, users

MAX_TURNS = 6
ERR_LLM = "Hit a snag talking to my brain — try again in a minute 🙃"
ERR_STUCK = "Sorry, I got stuck on that one — try rephrasing?"

SYSTEM_TEMPLATE = """You are a personal assistant that lives in WhatsApp. \
You manage {name}'s to-do list, reminders, and do light research.

Rules:
- Reply in short, friendly texting style. No markdown headers; hyphen lists are fine.
- Organise tasks into short categories (Applications, Errands, School, ...). \
When adding tasks, pick a sensible category.
- When the user says something is done (any phrasing), find the matching open \
task and complete it by id. If ambiguous, ask which one.
- Use the research tool ONLY when the user explicitly asks you to research or \
look something up. Never research proactively.
- If the user sends an image (e.g. a job posting screenshot), extract the \
actionable item(s), add them with source=screenshot, and confirm what you added.
- Reminder times: the user speaks in their local timezone ({tz}). \
Current local time: {now}.
- When telling the user about a reminder time, convert it from the UTC value \
shown below to their local timezone ({tz}).
- Only the admin may manage users.

{name}'s open tasks (id — [category] text):
{task_list}

Active reminders (id — text @ UTC time):
{reminder_list}
"""


def _build_system(conn, phone) -> str:
    user = users.get_user(conn, phone)
    tz = ZoneInfo(user["timezone"])
    open_tasks = tasks.list_tasks(conn, phone)
    task_list = "\n".join(
        f'#{t["id"]} — [{t["category"]}] {t["text"]}' for t in open_tasks
    ) or "(none)"
    rems = reminders.list_reminders(conn, phone)
    reminder_list = "\n".join(
        f'#{r["id"]} — {r["text"]} @ {r["next_fire_at"]} ({r["recurrence"]})'
        for r in rems
    ) or "(none)"
    return SYSTEM_TEMPLATE.format(
        name=user["name"] or "the user",
        tz=user["timezone"],
        now=datetime.now(tz).strftime("%A %Y-%m-%d %H:%M"),
        task_list=task_list,
        reminder_list=reminder_list,
    )


def handle_message(conn, settings, llm, phone, text=None, image=None) -> str:
    history.append(conn, phone, "user", text or "[sent an image]")
    system = _build_system(conn, phone)
    convo = history.recent(conn, phone)
    if image:
        convo[-1]["image"] = image

    reply = ERR_STUCK
    for _ in range(MAX_TURNS):
        try:
            resp = llm.chat(system, convo, tools.TOOL_DEFS)
        except Exception:
            reply = ERR_LLM
            break
        if not resp.tool_calls:
            reply = resp.text or "👍"
            break
        convo.append({"role": "assistant", "tool_calls": resp.tool_calls})
        for call in resp.tool_calls:
            result = tools.dispatch(conn, settings, phone, call)
            convo.append({"role": "tool", "name": call.name,
                          "content": json.dumps(result)})

    history.append(conn, phone, "assistant", reply)
    return reply
