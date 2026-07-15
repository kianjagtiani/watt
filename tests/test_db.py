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
