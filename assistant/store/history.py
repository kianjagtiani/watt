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
