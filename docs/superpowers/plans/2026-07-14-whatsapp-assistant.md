# WhatsApp Personal Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A multi-user WhatsApp to-do assistant (dedicated contact) with natural-language task management, categories, on-demand research, screenshot ingestion, and scheduled reminders.

**Architecture:** One FastAPI server receives Meta WhatsApp Cloud API webhooks, routes each allowlisted sender's message through a Gemini Flash tool-calling agent loop backed by per-user SQLite stores, and an APScheduler loop fires due reminders (template message outside the 24h window). A CLI harness drives the identical agent loop without WhatsApp.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, httpx, google-genai (Gemini), ddgs (DuckDuckGo), APScheduler, python-dateutil, SQLite (stdlib), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-14-whatsapp-assistant-design.md`
- $0/month Phase 1: Gemini free tier, Meta test number, no paid services.
- Every store query scoped by `user_phone` — no cross-user data access, ever.
- All stored datetimes are UTC ISO-8601 strings; user-facing times use the user's IANA timezone (default `America/Los_Angeles`).
- Research tool fires only when the user explicitly asks — enforced in the system prompt.
- LLM behind `LLMProvider`-shaped adapter (`chat(system, messages, tools) -> LLMResponse`); no Gemini types outside `assistant/llm.py`.
- Default Gemini model `gemini-2.5-flash`, overridable via `GEMINI_MODEL`.
- Env config only: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WEBHOOK_VERIFY_TOKEN`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `WHATSAPP_REMINDER_TEMPLATE`, `ADMIN_PHONE`, `DB_PATH`, `DEFAULT_TIMEZONE`.
- Package layout: flat `assistant/` package at repo root; tests in `tests/`; run `pytest` from repo root.
- Commit after every task (steps include the commands).

## File Structure

```
assistant/
├── __init__.py
├── config.py        # Settings dataclass + load_settings()
├── db.py            # sqlite connect() + schema
├── store/
│   ├── __init__.py
│   ├── users.py     # allowlist, admin, refusal tracking
│   ├── tasks.py     # task CRUD
│   ├── reminders.py # reminder CRUD + due/advance
│   └── history.py   # rolling chat history
├── research.py      # DuckDuckGo web search
├── tools.py         # tool schemas + dispatch()
├── llm.py           # ToolCall/LLMResponse + GeminiProvider
├── agent.py         # system prompt + tool-calling loop
├── whatsapp.py      # Cloud API client (send text/template, media)
├── webhook.py       # FastAPI app factory
├── scheduler.py     # reminder firing + APScheduler wiring
├── cli.py           # local chat harness (no WhatsApp)
└── serve.py         # production entrypoint
tests/               # one test file per module
requirements.txt, .env.example, .gitignore, Dockerfile, README.md
```

---

### Task 1: Scaffold + config

**Files:**
- Create: `.gitignore`, `requirements.txt`, `.env.example`, `assistant/__init__.py`, `assistant/config.py`, `assistant/store/__init__.py`, `tests/__init__.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.Settings` (frozen dataclass, fields listed below), `config.load_settings() -> Settings`.

- [ ] **Step 1: Create scaffold files**

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
.env
*.db
*.db-*
.pytest_cache/
```

`requirements.txt`:
```
fastapi
uvicorn
httpx
google-genai
ddgs
apscheduler
python-dateutil
python-dotenv
pytest
```

`.env.example`:
```
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WEBHOOK_VERIFY_TOKEN=pick-any-secret-string
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
WHATSAPP_REMINDER_TEMPLATE=task_reminder
ADMIN_PHONE=13100000000
DB_PATH=assistant.db
DEFAULT_TIMEZONE=America/Los_Angeles
```

`assistant/__init__.py`, `assistant/store/__init__.py`, `tests/__init__.py`: empty files.

- [ ] **Step 2: Create venv and install deps**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
Expected: installs succeed. Use `.venv/bin/pytest` / `.venv/bin/python` for all later commands.

- [ ] **Step 3: Write the failing test**

`tests/test_config.py`:
```python
from assistant.config import load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
    monkeypatch.setenv("ADMIN_PHONE", "15551234567")
    s = load_settings()
    assert s.whatsapp_token == "tok"
    assert s.admin_phone == "15551234567"


def test_load_settings_defaults(monkeypatch):
    for k in ("DB_PATH", "DEFAULT_TIMEZONE", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert s.db_path == "assistant.db"
    assert s.default_tz == "America/Los_Angeles"
    assert s.gemini_model == "gemini-2.5-flash"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError / ImportError on `assistant.config`)

- [ ] **Step 5: Write implementation**

`assistant/config.py`:
```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    whatsapp_token: str
    phone_number_id: str
    verify_token: str
    gemini_api_key: str
    gemini_model: str
    reminder_template: str
    admin_phone: str
    db_path: str
    default_tz: str


def load_settings() -> Settings:
    e = os.environ.get
    return Settings(
        whatsapp_token=e("WHATSAPP_TOKEN", ""),
        phone_number_id=e("WHATSAPP_PHONE_NUMBER_ID", ""),
        verify_token=e("WEBHOOK_VERIFY_TOKEN", ""),
        gemini_api_key=e("GEMINI_API_KEY", ""),
        gemini_model=e("GEMINI_MODEL", "gemini-2.5-flash"),
        reminder_template=e("WHATSAPP_REMINDER_TEMPLATE", "task_reminder"),
        admin_phone=e("ADMIN_PHONE", ""),
        db_path=e("DB_PATH", "assistant.db"),
        default_tz=e("DEFAULT_TIMEZONE", "America/Los_Angeles"),
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 2 PASS

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: project scaffold and env config"
```

---

### Task 2: Database schema

**Files:**
- Create: `assistant/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `db.connect(db_path: str) -> sqlite3.Connection` — Row factory, WAL, `check_same_thread=False`, schema created idempotently. Tables: `users(phone PK, name, is_admin, timezone, created_at)`, `tasks(id PK AI, user_phone, text, category, status, source, created_at, completed_at)`, `reminders(id PK AI, user_phone, text, next_fire_at, recurrence, active)`, `messages(id PK AI, user_phone, role, content, created_at)`, `processed(message_id PK)`, `refused(phone PK)`.

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
from assistant.db import connect


def test_connect_creates_schema():
    conn = connect(":memory:")
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert {"users", "tasks", "reminders", "messages", "processed", "refused"} <= names


def test_connect_is_idempotent(tmp_path):
    p = str(tmp_path / "t.db")
    connect(p).close()
    conn = connect(p)
    conn.execute("INSERT INTO processed (message_id) VALUES ('x')")
    assert conn.execute("SELECT COUNT(*) c FROM processed").fetchone()["c"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_db.py -v`
Expected: FAIL (no module `assistant.db`)

- [ ] **Step 3: Write implementation**

`assistant/db.py`:
```python
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  phone      TEXT PRIMARY KEY,
  name       TEXT NOT NULL DEFAULT '',
  is_admin   INTEGER NOT NULL DEFAULT 0,
  timezone   TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_phone   TEXT NOT NULL,
  text         TEXT NOT NULL,
  category     TEXT NOT NULL DEFAULT 'General',
  status       TEXT NOT NULL DEFAULT 'open',
  source       TEXT NOT NULL DEFAULT 'text',
  created_at   TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS reminders (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_phone   TEXT NOT NULL,
  text         TEXT NOT NULL,
  next_fire_at TEXT NOT NULL,
  recurrence   TEXT NOT NULL DEFAULT 'none',
  active       INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_phone TEXT NOT NULL,
  role       TEXT NOT NULL,
  content    TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processed (message_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS refused (phone TEXT PRIMARY KEY);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_db.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: sqlite schema and connection"
```

---

### Task 3: Users store (allowlist, admin, refusal)

**Files:**
- Create: `assistant/store/users.py`
- Test: `tests/test_users.py`

**Interfaces:**
- Consumes: `db.connect`.
- Produces: `add_user(conn, phone, name="", timezone_name="America/Los_Angeles", is_admin=False) -> None` (upsert), `get_user(conn, phone) -> sqlite3.Row | None`, `is_allowed(conn, phone) -> bool`, `remove_user(conn, phone) -> bool`, `list_users(conn) -> list[sqlite3.Row]`, `mark_refused(conn, phone) -> bool` (True only the first time a phone is refused).

- [ ] **Step 1: Write the failing test**

`tests/test_users.py`:
```python
from assistant.db import connect
from assistant.store import users


def test_add_get_allow_remove():
    conn = connect(":memory:")
    assert not users.is_allowed(conn, "15550001111")
    users.add_user(conn, "15550001111", name="Kian", is_admin=True)
    u = users.get_user(conn, "15550001111")
    assert u["name"] == "Kian" and u["is_admin"] == 1
    assert u["timezone"] == "America/Los_Angeles"
    assert users.is_allowed(conn, "15550001111")
    assert users.remove_user(conn, "15550001111")
    assert not users.is_allowed(conn, "15550001111")
    assert not users.remove_user(conn, "15550001111")


def test_mark_refused_once():
    conn = connect(":memory:")
    assert users.mark_refused(conn, "19998887777") is True
    assert users.mark_refused(conn, "19998887777") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_users.py -v`
Expected: FAIL (no module `assistant.store.users`)

- [ ] **Step 3: Write implementation**

`assistant/store/users.py`:
```python
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_user(conn, phone, name="", timezone_name="America/Los_Angeles", is_admin=False):
    conn.execute(
        "INSERT INTO users (phone, name, is_admin, timezone, created_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(phone) DO UPDATE SET name=excluded.name,"
        " is_admin=excluded.is_admin, timezone=excluded.timezone",
        (phone, name, int(is_admin), timezone_name, _now()),
    )
    conn.commit()


def get_user(conn, phone) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()


def is_allowed(conn, phone) -> bool:
    return get_user(conn, phone) is not None


def remove_user(conn, phone) -> bool:
    cur = conn.execute("DELETE FROM users WHERE phone = ?", (phone,))
    conn.commit()
    return cur.rowcount > 0


def list_users(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()


def mark_refused(conn, phone) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO refused (phone) VALUES (?)", (phone,)
    )
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_users.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: users store with allowlist and refusal tracking"
```

---

### Task 4: Tasks store

**Files:**
- Create: `assistant/store/tasks.py`
- Test: `tests/test_tasks.py`

**Interfaces:**
- Produces: `add_task(conn, phone, text, category="General", source="text") -> int`, `list_tasks(conn, phone, status="open") -> list[sqlite3.Row]`, `complete_task(conn, phone, task_id) -> bool`, `update_task(conn, phone, task_id, text=None, category=None) -> bool`. All scoped by phone; `complete_task`/`update_task` return False when the id doesn't belong to that phone.

- [ ] **Step 1: Write the failing test**

`tests/test_tasks.py`:
```python
from assistant.db import connect
from assistant.store import tasks


def test_add_list_complete():
    conn = connect(":memory:")
    tid = tasks.add_task(conn, "1555", "Apply to Jane Street", category="Applications")
    assert tasks.list_tasks(conn, "1555")[0]["text"] == "Apply to Jane Street"
    assert tasks.list_tasks(conn, "1666") == []          # isolation
    assert tasks.complete_task(conn, "1555", tid)
    assert tasks.list_tasks(conn, "1555") == []
    done = tasks.list_tasks(conn, "1555", status="done")
    assert done[0]["completed_at"] is not None


def test_scoping_and_update():
    conn = connect(":memory:")
    tid = tasks.add_task(conn, "1555", "laundry")
    assert not tasks.complete_task(conn, "1666", tid)     # not your task
    assert tasks.update_task(conn, "1555", tid, category="Errands")
    assert tasks.list_tasks(conn, "1555")[0]["category"] == "Errands"
    assert not tasks.update_task(conn, "1555", 999, text="x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tasks.py -v`
Expected: FAIL (no module `assistant.store.tasks`)

- [ ] **Step 3: Write implementation**

`assistant/store/tasks.py`:
```python
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_task(conn, phone, text, category="General", source="text") -> int:
    cur = conn.execute(
        "INSERT INTO tasks (user_phone, text, category, source, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (phone, text, category, source, _now()),
    )
    conn.commit()
    return cur.lastrowid


def list_tasks(conn, phone, status="open") -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tasks WHERE user_phone = ? AND status = ?"
        " ORDER BY category, id",
        (phone, status),
    ).fetchall()


def complete_task(conn, phone, task_id) -> bool:
    cur = conn.execute(
        "UPDATE tasks SET status='done', completed_at=?"
        " WHERE id=? AND user_phone=? AND status='open'",
        (_now(), task_id, phone),
    )
    conn.commit()
    return cur.rowcount > 0


def update_task(conn, phone, task_id, text=None, category=None) -> bool:
    sets, vals = [], []
    if text is not None:
        sets.append("text=?"); vals.append(text)
    if category is not None:
        sets.append("category=?"); vals.append(category)
    if not sets:
        return False
    cur = conn.execute(
        f"UPDATE tasks SET {', '.join(sets)} WHERE id=? AND user_phone=?",
        (*vals, task_id, phone),
    )
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tasks.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: tasks store with per-user scoping"
```

---

### Task 5: Reminders store

**Files:**
- Create: `assistant/store/reminders.py`
- Test: `tests/test_reminders.py`

**Interfaces:**
- Produces: `add_reminder(conn, phone, text, next_fire_at: datetime, recurrence="none") -> int` (datetime must be tz-aware; stored as UTC ISO), `list_reminders(conn, phone) -> list[sqlite3.Row]` (active only), `cancel_reminder(conn, phone, reminder_id) -> bool`, `due_reminders(conn, now: datetime) -> list[sqlite3.Row]` (active, `next_fire_at <= now`, all users), `complete_firing(conn, reminder_id) -> None` (recurrence `none` → deactivate; `daily`/`weekly`/`monthly` → advance `next_fire_at`).

- [ ] **Step 1: Write the failing test**

`tests/test_reminders.py`:
```python
from datetime import datetime, timedelta, timezone

from assistant.db import connect
from assistant.store import reminders

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def test_add_due_cancel():
    conn = connect(":memory:")
    rid = reminders.add_reminder(conn, "1555", "cancel Prime", NOW + timedelta(hours=1))
    assert reminders.due_reminders(conn, NOW) == []
    due = reminders.due_reminders(conn, NOW + timedelta(hours=2))
    assert [r["id"] for r in due] == [rid]
    assert reminders.cancel_reminder(conn, "1555", rid)
    assert reminders.due_reminders(conn, NOW + timedelta(hours=2)) == []
    assert not reminders.cancel_reminder(conn, "1666", rid)


def test_complete_firing_oneoff_and_weekly():
    conn = connect(":memory:")
    one = reminders.add_reminder(conn, "1555", "meeting", NOW)
    wk = reminders.add_reminder(conn, "1555", "laundry", NOW, recurrence="weekly")
    reminders.complete_firing(conn, one)
    reminders.complete_firing(conn, wk)
    active = reminders.list_reminders(conn, "1555")
    assert [r["id"] for r in active] == [wk]
    nxt = datetime.fromisoformat(active[0]["next_fire_at"])
    assert nxt == NOW + timedelta(days=7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reminders.py -v`
Expected: FAIL (no module `assistant.store.reminders`)

- [ ] **Step 3: Write implementation**

`assistant/store/reminders.py`:
```python
import sqlite3
from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta

_ADVANCE = {
    "daily": lambda d: d + timedelta(days=1),
    "weekly": lambda d: d + timedelta(days=7),
    "monthly": lambda d: d + relativedelta(months=1),
}


def add_reminder(conn, phone, text, next_fire_at: datetime, recurrence="none") -> int:
    cur = conn.execute(
        "INSERT INTO reminders (user_phone, text, next_fire_at, recurrence)"
        " VALUES (?, ?, ?, ?)",
        (phone, text, next_fire_at.astimezone(timezone.utc).isoformat(), recurrence),
    )
    conn.commit()
    return cur.lastrowid


def list_reminders(conn, phone) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reminders WHERE user_phone=? AND active=1 ORDER BY next_fire_at",
        (phone,),
    ).fetchall()


def cancel_reminder(conn, phone, reminder_id) -> bool:
    cur = conn.execute(
        "UPDATE reminders SET active=0 WHERE id=? AND user_phone=? AND active=1",
        (reminder_id, phone),
    )
    conn.commit()
    return cur.rowcount > 0


def due_reminders(conn, now: datetime) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reminders WHERE active=1 AND next_fire_at <= ?",
        (now.astimezone(timezone.utc).isoformat(),),
    ).fetchall()


def complete_firing(conn, reminder_id) -> None:
    row = conn.execute(
        "SELECT next_fire_at, recurrence FROM reminders WHERE id=?", (reminder_id,)
    ).fetchone()
    if row is None:
        return
    advance = _ADVANCE.get(row["recurrence"])
    if advance is None:
        conn.execute("UPDATE reminders SET active=0 WHERE id=?", (reminder_id,))
    else:
        nxt = advance(datetime.fromisoformat(row["next_fire_at"]))
        conn.execute(
            "UPDATE reminders SET next_fire_at=? WHERE id=?",
            (nxt.isoformat(), reminder_id),
        )
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reminders.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: reminders store with recurrence"
```

---

### Task 6: History store

**Files:**
- Create: `assistant/store/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Produces: `append(conn, phone, role, content) -> None`, `recent(conn, phone, limit=20) -> list[dict]` (oldest-first `{"role": str, "content": str}`), `last_user_message_at(conn, phone) -> datetime | None` (tz-aware UTC).

- [ ] **Step 1: Write the failing test**

`tests/test_history.py`:
```python
from datetime import datetime, timezone

from assistant.db import connect
from assistant.store import history


def test_append_recent_order_and_limit():
    conn = connect(":memory:")
    for i in range(25):
        history.append(conn, "1555", "user", f"m{i}")
    got = history.recent(conn, "1555", limit=20)
    assert len(got) == 20
    assert got[0] == {"role": "user", "content": "m5"}
    assert got[-1]["content"] == "m24"
    assert history.recent(conn, "1666") == []


def test_last_user_message_at():
    conn = connect(":memory:")
    assert history.last_user_message_at(conn, "1555") is None
    history.append(conn, "1555", "assistant", "hi")
    assert history.last_user_message_at(conn, "1555") is None
    history.append(conn, "1555", "user", "yo")
    ts = history.last_user_message_at(conn, "1555")
    assert ts.tzinfo is not None
    assert (datetime.now(timezone.utc) - ts).total_seconds() < 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_history.py -v`
Expected: FAIL (no module `assistant.store.history`)

- [ ] **Step 3: Write implementation**

`assistant/store/history.py`:
```python
from datetime import datetime, timezone


def append(conn, phone, role, content) -> None:
    conn.execute(
        "INSERT INTO messages (user_phone, role, content, created_at)"
        " VALUES (?, ?, ?, ?)",
        (phone, role, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def recent(conn, phone, limit=20) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE user_phone=?"
        " ORDER BY id DESC LIMIT ?",
        (phone, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def last_user_message_at(conn, phone):
    row = conn.execute(
        "SELECT created_at FROM messages WHERE user_phone=? AND role='user'"
        " ORDER BY id DESC LIMIT 1",
        (phone,),
    ).fetchone()
    return datetime.fromisoformat(row["created_at"]) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_history.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: rolling message history store"
```

---

### Task 7: Research (DuckDuckGo)

**Files:**
- Create: `assistant/research.py`
- Test: `tests/test_research.py`

**Interfaces:**
- Produces: `search_web(query: str, max_results: int = 5) -> list[dict]` with keys `title`, `url`, `snippet`. Raises nothing: returns `[]` on any search error.

- [ ] **Step 1: Write the failing test**

`tests/test_research.py`:
```python
from assistant import research


class FakeDDGS:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def text(self, query, max_results=5):
        return [{"title": "T", "href": "http://x", "body": "B"}]


class BrokenDDGS(FakeDDGS):
    def text(self, query, max_results=5):
        raise RuntimeError("rate limited")


def test_search_web_maps_fields(monkeypatch):
    monkeypatch.setattr(research, "DDGS", FakeDDGS)
    assert research.search_web("qs jobs") == [
        {"title": "T", "url": "http://x", "snippet": "B"}
    ]


def test_search_web_swallows_errors(monkeypatch):
    monkeypatch.setattr(research, "DDGS", BrokenDDGS)
    assert research.search_web("anything") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_research.py -v`
Expected: FAIL (no module `assistant.research`)

- [ ] **Step 3: Write implementation**

`assistant/research.py`:
```python
from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return [
                {"title": r["title"], "url": r["href"], "snippet": r["body"]}
                for r in ddgs.text(query, max_results=max_results)
            ]
    except Exception:
        return []
```
Note: if `from ddgs import DDGS` fails at install time, the package may still import as `from duckduckgo_search import DDGS` — use whichever import succeeds and keep the module attribute named `DDGS` so tests can monkeypatch it.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_research.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: duckduckgo research helper"
```

---

### Task 8: LLM adapter types (before tools, which import ToolCall)

**Files:**
- Create: `assistant/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `@dataclass ToolCall: name: str; args: dict`
  - `@dataclass LLMResponse: text: str | None; tool_calls: list[ToolCall]`
  - `class GeminiProvider: __init__(self, api_key: str, model: str)`, `chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse`
  - Neutral message dicts: `{"role": "user", "content": str, "image": (bytes, mime) | absent}`, `{"role": "assistant", "content": str}` or `{"role": "assistant", "tool_calls": [ToolCall,...]}`, `{"role": "tool", "name": str, "content": str}`.
  - Module-level pure function `_to_contents(messages) -> list` (Gemini `types.Content`) — unit-testable without network.

- [ ] **Step 1: Write the failing test**

`tests/test_llm.py`:
```python
from assistant.llm import ToolCall, _to_contents


def test_roles_map_to_gemini():
    msgs = [
        {"role": "user", "content": "add milk"},
        {"role": "assistant", "tool_calls": [ToolCall("add_tasks", {"items": []})]},
        {"role": "tool", "name": "add_tasks", "content": '{"ok": true}'},
        {"role": "assistant", "content": "Added!"},
    ]
    contents = _to_contents(msgs)
    assert [c.role for c in contents] == ["user", "model", "user", "model"]
    assert contents[1].parts[0].function_call.name == "add_tasks"
    assert contents[2].parts[0].function_response.name == "add_tasks"
    assert contents[3].parts[0].text == "Added!"


def test_image_message_becomes_two_parts():
    msgs = [{"role": "user", "content": "job posting", "image": (b"\x89PNG", "image/png")}]
    (c,) = _to_contents(msgs)
    assert len(c.parts) == 2
    assert c.parts[0].inline_data.mime_type == "image/png"
    assert c.parts[1].text == "job posting"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: FAIL (no module `assistant.llm`)

- [ ] **Step 3: Write implementation**

`assistant/llm.py`:
```python
from dataclasses import dataclass, field

from google import genai
from google.genai import types


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


def _to_contents(messages: list[dict]) -> list[types.Content]:
    contents = []
    for m in messages:
        if m["role"] == "tool":
            parts = [types.Part.from_function_response(
                name=m["name"], response={"result": m["content"]}
            )]
            contents.append(types.Content(role="user", parts=parts))
        elif m["role"] == "assistant":
            if m.get("tool_calls"):
                parts = [
                    types.Part.from_function_call(name=c.name, args=c.args)
                    for c in m["tool_calls"]
                ]
            else:
                parts = [types.Part.from_text(text=m["content"])]
            contents.append(types.Content(role="model", parts=parts))
        else:
            parts = []
            if m.get("image"):
                data, mime = m["image"]
                parts.append(types.Part.from_bytes(data=data, mime_type=mime))
            if m.get("content"):
                parts.append(types.Part.from_text(text=m["content"]))
            contents.append(types.Content(role="user", parts=parts))
    return contents


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def chat(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["parameters"],
                )
                for t in tools
            ])] if tools else None,
        )
        resp = self._client.models.generate_content(
            model=self._model, contents=_to_contents(messages), config=config
        )
        text_parts, calls = [], []
        for part in resp.candidates[0].content.parts:
            if part.function_call:
                calls.append(ToolCall(part.function_call.name, dict(part.function_call.args)))
            elif part.text:
                text_parts.append(part.text)
        return LLMResponse("\n".join(text_parts) or None, calls)
```
Note: if `types.Part.from_function_call` does not exist in the installed google-genai version, construct the part as `types.Part(function_call=types.FunctionCall(name=..., args=...))` — adjust to whatever the installed SDK exposes and re-run the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: llm adapter types and gemini provider"
```

---

### Task 9: Tool schemas + dispatch

**Files:**
- Create: `assistant/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: all four stores, `research.search_web`, `llm.ToolCall`, `config.Settings`.
- Produces: `TOOL_DEFS: list[dict]` (each `{"name", "description", "parameters"}` in JSON-schema form) and `dispatch(conn, settings, phone, call: ToolCall) -> dict`. Every result is a JSON-safe dict; errors come back as `{"error": "..."}` (never raise). Admin-only tools: `add_user`, `remove_user`, `list_users`. Reminder times arrive as local `"YYYY-MM-DD HH:MM"` in the caller's stored timezone and are converted to UTC.

- [ ] **Step 1: Write the failing test**

`tests/test_tools.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tools.py -v`
Expected: FAIL (no module `assistant.tools`)

- [ ] **Step 3: Write implementation**

`assistant/tools.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tools.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: tool schemas and dispatch with admin gating"
```

---

### Task 10: Agent loop

**Files:**
- Create: `assistant/agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `tools.TOOL_DEFS`, `tools.dispatch`, `store.history`, `store.tasks`, `store.reminders`, `store.users`, `llm.LLMResponse`.
- Produces: `handle_message(conn, settings, llm, phone, text=None, image: tuple[bytes, str] | None = None) -> str`. Appends user text (or `"[sent an image]"`) and the final assistant reply to history. Max 6 LLM turns; on LLM exception returns `"Hit a snag talking to my brain — try again in a minute 🙃"`; on turn exhaustion returns `"Sorry, I got stuck on that one — try rephrasing?"`.

- [ ] **Step 1: Write the failing test**

`tests/test_agent.py`:
```python
from assistant import agent
from assistant.config import Settings
from assistant.db import connect
from assistant.llm import LLMResponse, ToolCall
from assistant.store import history, tasks, users

SETTINGS = Settings("", "", "", "", "gemini-2.5-flash", "task_reminder",
                    "1555", ":memory:", "America/Los_Angeles")


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, system, messages, tools):
        self.calls.append((system, messages))
        return self.script.pop(0)


class BoomLLM:
    def chat(self, *a, **k):
        raise RuntimeError("quota")


def _conn():
    conn = connect(":memory:")
    users.add_user(conn, "1555", name="Kian", is_admin=True)
    return conn


def test_tool_call_then_reply():
    conn = _conn()
    llm = FakeLLM([
        LLMResponse(None, [ToolCall("add_tasks", {"items": [{"text": "buy milk"}]})]),
        LLMResponse("Added: buy milk ✅", []),
    ])
    reply = agent.handle_message(conn, SETTINGS, llm, "1555", text="add buy milk")
    assert reply == "Added: buy milk ✅"
    assert tasks.list_tasks(conn, "1555")[0]["text"] == "buy milk"
    assert history.recent(conn, "1555")[-1] == {"role": "assistant",
                                                "content": "Added: buy milk ✅"}
    system = llm.calls[0][0]
    assert "buy milk" not in system  # task added after prompt built is fine
    assert "Kian" in system


def test_open_tasks_appear_in_system_prompt():
    conn = _conn()
    tasks.add_task(conn, "1555", "finish PRA draft", category="Research")
    llm = FakeLLM([LLMResponse("You have 1 task", [])])
    agent.handle_message(conn, SETTINGS, llm, "1555", text="what's left?")
    assert "finish PRA draft" in llm.calls[0][0]


def test_image_gets_attached_and_logged():
    conn = _conn()
    llm = FakeLLM([LLMResponse("Got the screenshot 👍", [])])
    agent.handle_message(conn, SETTINGS, llm, "1555", image=(b"png", "image/png"))
    msgs = llm.calls[0][1]
    assert msgs[-1]["image"] == (b"png", "image/png")
    assert history.recent(conn, "1555")[0]["content"] == "[sent an image]"


def test_llm_error_message():
    conn = _conn()
    reply = agent.handle_message(conn, SETTINGS, BoomLLM(), "1555", text="hi")
    assert "snag" in reply
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent.py -v`
Expected: FAIL (no module `assistant.agent`)

- [ ] **Step 3: Write implementation**

`assistant/agent.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: tool-calling agent loop with per-user context"
```

---

### Task 11: WhatsApp Cloud API client

**Files:**
- Create: `assistant/whatsapp.py`
- Test: `tests/test_whatsapp.py`

**Interfaces:**
- Produces: `class WhatsAppClient: __init__(self, token, phone_number_id, base_url="https://graph.facebook.com/v23.0", http: httpx.Client | None = None)`, `send_text(to: str, body: str) -> None`, `send_template(to: str, name: str, params: list[str]) -> None`, `download_media(media_id: str) -> tuple[bytes, str]`. All raise `httpx.HTTPStatusError` on non-2xx.

- [ ] **Step 1: Write the failing test**

`tests/test_whatsapp.py`:
```python
import json

import httpx

from assistant.whatsapp import WhatsAppClient


def _client(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return WhatsAppClient("tok", "PNID", http=http)


def test_send_text():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["Authorization"]
        seen["json"] = json.loads(req.content)
        return httpx.Response(200, json={"messages": [{"id": "x"}]})

    _client(handler).send_text("1555", "hi")
    assert seen["url"].endswith("/PNID/messages")
    assert seen["auth"] == "Bearer tok"
    assert seen["json"]["type"] == "text"
    assert seen["json"]["text"]["body"] == "hi"


def test_send_template():
    seen = {}

    def handler(req):
        seen["json"] = json.loads(req.content)
        return httpx.Response(200, json={})

    _client(handler).send_template("1555", "task_reminder", ["cancel Prime"])
    t = seen["json"]["template"]
    assert t["name"] == "task_reminder"
    assert t["components"][0]["parameters"][0]["text"] == "cancel Prime"


def test_download_media_two_step():
    def handler(req):
        if "MEDIAID" in str(req.url):
            return httpx.Response(200, json={
                "url": "https://cdn.example/file", "mime_type": "image/png"})
        return httpx.Response(200, content=b"bytes!")

    data, mime = _client(handler).download_media("MEDIAID")
    assert (data, mime) == (b"bytes!", "image/png")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_whatsapp.py -v`
Expected: FAIL (no module `assistant.whatsapp`)

- [ ] **Step 3: Write implementation**

`assistant/whatsapp.py`:
```python
import httpx


class WhatsAppClient:
    def __init__(self, token, phone_number_id,
                 base_url="https://graph.facebook.com/v23.0",
                 http: httpx.Client | None = None):
        self._base = base_url
        self._pnid = phone_number_id
        self._http = http or httpx.Client(timeout=30)
        self._headers = {"Authorization": f"Bearer {token}"}

    def _post_message(self, payload: dict) -> None:
        payload = {"messaging_product": "whatsapp", **payload}
        r = self._http.post(f"{self._base}/{self._pnid}/messages",
                            json=payload, headers=self._headers)
        r.raise_for_status()

    def send_text(self, to: str, body: str) -> None:
        self._post_message({"to": to, "type": "text", "text": {"body": body}})

    def send_template(self, to: str, name: str, params: list[str]) -> None:
        self._post_message({
            "to": to, "type": "template",
            "template": {
                "name": name,
                "language": {"code": "en_US"},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in params],
                }],
            },
        })

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        meta = self._http.get(f"{self._base}/{media_id}", headers=self._headers)
        meta.raise_for_status()
        info = meta.json()
        blob = self._http.get(info["url"], headers=self._headers)
        blob.raise_for_status()
        return blob.content, info["mime_type"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_whatsapp.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: whatsapp cloud api client"
```

---

### Task 12: Webhook (FastAPI app)

**Files:**
- Create: `assistant/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `store.users`, `WhatsAppClient` (send_text, download_media).
- Produces: `create_app(settings, conn, wa, handler) -> FastAPI` where `handler(phone: str, text: str | None, image: tuple[bytes, str] | None) -> str` (the agent, injected so tests don't need an LLM).
  - `GET /webhook`: echoes `hub.challenge` when `hub.mode == "subscribe"` and `hub.verify_token` matches, else 403.
  - `POST /webhook`: always 200 `{"status": "ok"}`; per message: dedupe on `processed.message_id`; unknown senders get one-time polite refusal; text and image messages routed to `handler` in a FastAPI background task and reply sent via `wa.send_text`; other types get a capability note.
  - Refusal copy: `"Hi! I'm a private assistant and can't chat with new numbers. Ask my admin for access if you know them 🙂"`.
  - Unsupported-type copy: `"I can only handle text and images for now!"`.

- [ ] **Step 1: Write the failing test**

`tests/test_webhook.py`:
```python
from fastapi.testclient import TestClient

from assistant.config import Settings
from assistant.db import connect
from assistant.store import users
from assistant.webhook import create_app

SETTINGS = Settings("", "PNID", "sekrit", "", "gemini-2.5-flash",
                    "task_reminder", "1555", ":memory:", "America/Los_Angeles")


class FakeWA:
    def __init__(self):
        self.sent = []

    def send_text(self, to, body):
        self.sent.append((to, body))

    def download_media(self, media_id):
        return b"img", "image/jpeg"


def _payload(msg):
    return {"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}


def _text_msg(mid="wamid.1", frm="1555", body="hello"):
    return {"id": mid, "from": frm, "type": "text", "text": {"body": body}}


def _setup():
    conn = connect(":memory:")
    users.add_user(conn, "1555", name="Kian", is_admin=True)
    wa = FakeWA()
    handled = []

    def handler(phone, text, image):
        handled.append((phone, text, image))
        return "reply!"

    app = create_app(SETTINGS, conn, wa, handler)
    return TestClient(app), wa, handled


def test_verify_handshake():
    client, _, _ = _setup()
    r = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "sekrit",
        "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    r = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong",
        "hub.challenge": "42"})
    assert r.status_code == 403


def test_text_message_routed_and_replied():
    client, wa, handled = _setup()
    r = client.post("/webhook", json=_payload(_text_msg()))
    assert r.status_code == 200
    assert handled == [("1555", "hello", None)]
    assert wa.sent == [("1555", "reply!")]


def test_dedupe():
    client, wa, handled = _setup()
    client.post("/webhook", json=_payload(_text_msg(mid="wamid.same")))
    client.post("/webhook", json=_payload(_text_msg(mid="wamid.same")))
    assert len(handled) == 1


def test_unknown_sender_refused_once():
    client, wa, handled = _setup()
    client.post("/webhook", json=_payload(_text_msg(mid="a", frm="1999")))
    client.post("/webhook", json=_payload(_text_msg(mid="b", frm="1999")))
    assert handled == []
    assert len(wa.sent) == 1 and wa.sent[0][0] == "1999"


def test_image_message_downloads_media():
    client, wa, handled = _setup()
    msg = {"id": "wamid.img", "from": "1555", "type": "image",
           "image": {"id": "MEDIA1", "caption": "this job"}}
    client.post("/webhook", json=_payload(msg))
    assert handled == [("1555", "this job", (b"img", "image/jpeg"))]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_webhook.py -v`
Expected: FAIL (no module `assistant.webhook`)

- [ ] **Step 3: Write implementation**

`assistant/webhook.py`:
```python
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from assistant.store import users

REFUSAL = ("Hi! I'm a private assistant and can't chat with new numbers. "
           "Ask my admin for access if you know them 🙂")
UNSUPPORTED = "I can only handle text and images for now!"


def create_app(settings, conn, wa, handler) -> FastAPI:
    app = FastAPI()

    @app.get("/webhook")
    def verify(request: Request):
        q = request.query_params
        if (q.get("hub.mode") == "subscribe"
                and q.get("hub.verify_token") == settings.verify_token):
            return PlainTextResponse(q.get("hub.challenge", ""))
        return Response(status_code=403)

    def _process(phone, text, image):
        reply = handler(phone, text, image)
        wa.send_text(phone, reply)

    @app.post("/webhook")
    def receive(body: dict, background: BackgroundTasks):
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for msg in change.get("value", {}).get("messages", []):
                    _route(msg, background)
        return {"status": "ok"}

    def _route(msg, background):
        cur = conn.execute(
            "INSERT OR IGNORE INTO processed (message_id) VALUES (?)",
            (msg["id"],))
        conn.commit()
        if cur.rowcount == 0:
            return  # already seen (webhook retry)
        phone = msg["from"]
        if not users.is_allowed(conn, phone):
            if users.mark_refused(conn, phone):
                wa.send_text(phone, REFUSAL)
            return
        if msg["type"] == "text":
            background.add_task(_process, phone, msg["text"]["body"], None)
        elif msg["type"] == "image":
            image = wa.download_media(msg["image"]["id"])
            background.add_task(_process, phone,
                                msg["image"].get("caption"), image)
        else:
            wa.send_text(phone, UNSUPPORTED)

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_webhook.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: webhook app with verify, dedupe, allowlist"
```

---

### Task 13: Scheduler

**Files:**
- Create: `assistant/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `store.reminders`, `store.history`, `WhatsAppClient` (send_text, send_template), `Settings.reminder_template`.
- Produces: `check_and_fire(conn, settings, wa, now: datetime | None = None) -> None` (pure-ish, testable) and `start(conn, settings, wa) -> BackgroundScheduler` (30-second interval job, started). Firing rule: if the user's last inbound message is within 24h → `send_text(f"⏰ Reminder: {text}")`, else `send_template(phone, settings.reminder_template, [text])`. Send errors are swallowed; the reminder is still advanced/deactivated (no retry storms).

- [ ] **Step 1: Write the failing test**

`tests/test_scheduler.py`:
```python
from datetime import datetime, timedelta, timezone

from assistant.config import Settings
from assistant.db import connect
from assistant.scheduler import check_and_fire
from assistant.store import history, reminders

SETTINGS = Settings("", "", "", "", "gemini-2.5-flash", "task_reminder",
                    "1555", ":memory:", "America/Los_Angeles")
NOW = datetime.now(timezone.utc)


class FakeWA:
    def __init__(self, fail=False):
        self.texts, self.templates, self.fail = [], [], fail

    def send_text(self, to, body):
        if self.fail:
            raise RuntimeError("boom")
        self.texts.append((to, body))

    def send_template(self, to, name, params):
        self.templates.append((to, name, params))


def test_recent_user_gets_free_text():
    conn = connect(":memory:")
    history.append(conn, "1555", "user", "hey")
    reminders.add_reminder(conn, "1555", "call mom", NOW - timedelta(minutes=1))
    wa = FakeWA()
    check_and_fire(conn, SETTINGS, wa, now=NOW)
    assert wa.texts == [("1555", "⏰ Reminder: call mom")]
    assert wa.templates == []
    assert reminders.list_reminders(conn, "1555") == []  # one-off deactivated


def test_stale_user_gets_template():
    conn = connect(":memory:")
    reminders.add_reminder(conn, "1555", "laundry", NOW - timedelta(minutes=1),
                           recurrence="weekly")
    wa = FakeWA()
    check_and_fire(conn, SETTINGS, wa, now=NOW)
    assert wa.templates == [("1555", "task_reminder", ["laundry"])]
    nxt = reminders.list_reminders(conn, "1555")[0]
    assert datetime.fromisoformat(nxt["next_fire_at"]) > NOW  # advanced


def test_send_failure_still_advances():
    conn = connect(":memory:")
    history.append(conn, "1555", "user", "hey")
    reminders.add_reminder(conn, "1555", "x", NOW - timedelta(minutes=1))
    check_and_fire(conn, SETTINGS, FakeWA(fail=True), now=NOW)
    assert reminders.list_reminders(conn, "1555") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_scheduler.py -v`
Expected: FAIL (no module `assistant.scheduler`)

- [ ] **Step 3: Write implementation**

`assistant/scheduler.py`:
```python
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from assistant.store import history, reminders

log = logging.getLogger(__name__)


def check_and_fire(conn, settings, wa, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    for r in reminders.due_reminders(conn, now):
        phone, text = r["user_phone"], r["text"]
        last = history.last_user_message_at(conn, phone)
        try:
            if last and now - last < timedelta(hours=24):
                wa.send_text(phone, f"⏰ Reminder: {text}")
            else:
                wa.send_template(phone, settings.reminder_template, [text])
        except Exception:
            log.exception("failed to send reminder %s to %s", r["id"], phone)
        reminders.complete_firing(conn, r["id"])


def start(conn, settings, wa) -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(check_and_fire, "interval", seconds=30,
                  args=[conn, settings, wa])
    sched.start()
    return sched
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_scheduler.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: reminder scheduler with 24h-window template fallback"
```

---

### Task 14: CLI harness + serve entrypoint

**Files:**
- Create: `assistant/cli.py`, `assistant/serve.py`
- Test: manual smoke (below) — these are thin wiring around already-tested parts.

**Interfaces:**
- Consumes: everything above; `GeminiProvider`.
- Produces: `python -m assistant.cli` (chat loop; `img:<path> [caption]` sends an image; `quit` exits) and `python -m assistant.serve` (uvicorn on port 8000 + scheduler). Both load `.env` via python-dotenv and auto-provision the admin user from `ADMIN_PHONE`.

- [ ] **Step 1: Write cli.py**

`assistant/cli.py`:
```python
import mimetypes
import pathlib

from dotenv import load_dotenv

from assistant import agent, db
from assistant.config import load_settings
from assistant.llm import GeminiProvider
from assistant.store import users


def main():
    load_dotenv()
    settings = load_settings()
    conn = db.connect(settings.db_path)
    phone = settings.admin_phone or "10000000000"
    if not users.is_allowed(conn, phone):
        users.add_user(conn, phone, name="You", is_admin=True,
                       timezone_name=settings.default_tz)
    llm = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    print("Chat with your assistant (img:<path> [caption] to send an image, quit to exit)")
    while True:
        line = input("you> ").strip()
        if line in {"quit", "exit"}:
            break
        text, image = line, None
        if line.startswith("img:"):
            rest = line[4:].split(maxsplit=1)
            path = pathlib.Path(rest[0])
            text = rest[1] if len(rest) > 1 else None
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            image = (path.read_bytes(), mime)
        print("bot>", agent.handle_message(conn, settings, llm, phone,
                                           text=text, image=image))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write serve.py**

`assistant/serve.py`:
```python
import functools

import uvicorn
from dotenv import load_dotenv

from assistant import agent, db, scheduler
from assistant.config import load_settings
from assistant.llm import GeminiProvider
from assistant.store import users
from assistant.webhook import create_app
from assistant.whatsapp import WhatsAppClient


def main():
    load_dotenv()
    settings = load_settings()
    conn = db.connect(settings.db_path)
    if settings.admin_phone and not users.is_allowed(conn, settings.admin_phone):
        users.add_user(conn, settings.admin_phone, name="Admin", is_admin=True,
                       timezone_name=settings.default_tz)
    llm = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    wa = WhatsAppClient(settings.whatsapp_token, settings.phone_number_id)
    handler = functools.partial(agent.handle_message, conn, settings, llm)

    def handle(phone, text, image):
        return handler(phone, text=text, image=image)

    app = create_app(settings, conn, wa, handle)
    scheduler.start(conn, settings, wa)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Full test suite still green**

Run: `.venv/bin/pytest -q`
Expected: all tests pass, no errors.

- [ ] **Step 4: Live CLI smoke test (requires GEMINI_API_KEY in .env)**

```bash
cp .env.example .env   # fill in GEMINI_API_KEY at minimum
.venv/bin/python -m assistant.cli
```
Type: `add finish the AAAI abstract and buy detergent` → expect a reply confirming two tasks in sensible categories. Then `what's left?` → expect the organised list. Then `detergent done` → expect completion confirmed. Ctrl-C or `quit` to exit.
Expected: coherent replies; `assistant.db` contains the tasks.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: cli harness and serve entrypoint"
```

---

### Task 15: Dockerfile + README

**Files:**
- Create: `Dockerfile`, `README.md`

**Interfaces:**
- Consumes: `assistant.serve` entrypoint.

- [ ] **Step 1: Write Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/ assistant/
ENV DB_PATH=/data/assistant.db
VOLUME /data
EXPOSE 8000
CMD ["python", "-m", "assistant.serve"]
```

- [ ] **Step 2: Write README.md**

`README.md` must cover, concretely:
1. What it is (one paragraph) + architecture diagram (text).
2. Local dev: venv, `.env` from `.env.example`, `pytest`, `python -m assistant.cli`.
3. **Meta setup walkthrough:** create app at developers.facebook.com (type: Business) → add WhatsApp product → note the free **test number** and its `Phone number ID` → add up to 5 recipient numbers under *API Setup → To* → generate a temporary access token (later: permanent token via System User) → put token/ID in `.env`.
4. **Webhook wiring:** run `python -m assistant.serve`, then `cloudflared tunnel --url http://localhost:8000`, paste the tunnel URL + `WEBHOOK_VERIFY_TOKEN` into WhatsApp → Configuration → Webhook (subscribe to `messages` field).
5. **Reminder template:** in WhatsApp Manager → Message Templates, create utility template `task_reminder`, body `⏰ Reminder: {{1}}`, language en_US; wait for approval.
6. Phase 2: `docker build`, deploy to Railway/Fly, set env vars, point webhook at the public URL, mount `/data` volume.

- [ ] **Step 3: Verify docker build (if Docker installed; otherwise skip and note)**

Run: `docker build -t assistant . && docker run --rm assistant python -c "import assistant.serve"`
Expected: build succeeds, import exits 0.

- [ ] **Step 4: Full suite + commit**

```bash
.venv/bin/pytest -q && git add -A && git commit -m "feat: dockerfile and setup docs"
```

---

## Final Verification (whole plan)

- [ ] `.venv/bin/pytest -q` — everything green.
- [ ] CLI end-to-end (Task 14 Step 4 scenario) exercised, including an `img:` screenshot ingestion with a real screenshot file.
- [ ] Live WhatsApp round-trip: text the test number "add buy milk", get a reply; "buy milk done"; set a 2-minute reminder and receive it.
- [ ] Spec re-read: every requirement in `docs/superpowers/specs/2026-07-14-whatsapp-assistant-design.md` maps to shipped behavior.
