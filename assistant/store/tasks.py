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
