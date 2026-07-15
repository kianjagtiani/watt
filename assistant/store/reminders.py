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
