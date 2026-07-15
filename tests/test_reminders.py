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
