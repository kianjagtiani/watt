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
