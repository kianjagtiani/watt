import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from assistant.store import history, reminders

log = logging.getLogger(__name__)


def check_and_fire(conn, settings, wa, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    for r in reminders.due_reminders(conn, now):
        phone, text = r["user_phone"], r["text"]
        last = history.last_user_message_at(conn, phone)
        try:
            if last and now - last < timedelta(hours=24):
                wa.send_text(phone, f"⏰ Reminder: {text}")
            else:
                wa.send_template(phone, settings.reminder_template, [text])
        except Exception:
            log.exception("failed to send reminder %s to %s", r["id"], phone)
        reminders.complete_firing(conn, r["id"])


def start(conn, settings, wa) -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(check_and_fire, "interval", seconds=30,
                  args=[conn, settings, wa])
    sched.start()
    return sched
