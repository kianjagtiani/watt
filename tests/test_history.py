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
