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
