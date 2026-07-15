from datetime import datetime, timedelta, timezone

import pytest

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
    reminders.complete_firing(conn, one, now=NOW)
    reminders.complete_firing(conn, wk, now=NOW)
    active = reminders.list_reminders(conn, "1555")
    assert [r["id"] for r in active] == [wk]
    nxt = datetime.fromisoformat(active[0]["next_fire_at"])
    assert nxt == NOW + timedelta(days=7)


def test_complete_firing_catch_up_after_sleep():
    conn = connect(":memory:")
    rid = reminders.add_reminder(
        conn, "1555", "water plants", NOW - timedelta(days=5), recurrence="daily"
    )
    reminders.complete_firing(conn, rid, now=NOW)
    active = reminders.list_reminders(conn, "1555")
    assert [r["id"] for r in active] == [rid]
    nxt = datetime.fromisoformat(active[0]["next_fire_at"])
    assert nxt > NOW
    assert nxt - NOW <= timedelta(days=1)


def test_add_reminder_rejects_naive_datetime():
    conn = connect(":memory:")
    naive_dt = datetime(2026, 7, 14, 12, 0)  # no tzinfo
    with pytest.raises(ValueError, match="next_fire_at must be tz-aware"):
        reminders.add_reminder(conn, "1555", "test", naive_dt)


def test_due_reminders_rejects_naive_datetime():
    conn = connect(":memory:")
    naive_dt = datetime(2026, 7, 14, 12, 0)  # no tzinfo
    with pytest.raises(ValueError, match="now must be tz-aware"):
        reminders.due_reminders(conn, naive_dt)
