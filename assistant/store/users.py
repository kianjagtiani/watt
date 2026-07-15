import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_user(conn, phone, name="", timezone_name="America/Los_Angeles", is_admin=False):
    conn.execute(
        "INSERT INTO users (phone, name, is_admin, timezone, created_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(phone) DO UPDATE SET"
        " name=CASE WHEN excluded.name='' THEN users.name ELSE excluded.name END,"
        " is_admin=MAX(users.is_admin, excluded.is_admin),"
        " timezone=excluded.timezone",
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
