"""Event reminders.

On AWS an Amazon EventBridge schedule (e.g. rate(1 hour)) invokes
`lambda_handler` below. Locally, the admin dashboard has a "Run reminders"
button that calls the same `run()` function through the API.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from . import config, notify
from .db import get_store

logger = logging.getLogger("eventhub")


def run(hours=24):
    store = get_store()
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=hours)
    checked = sent = 0
    for event in store.list_events():
        start = datetime.fromisoformat(event["start"])
        if not (now < start <= window_end):
            continue
        checked += 1
        for reg in store.registrations_for_event(event["id"]):
            if reg["status"] == "confirmed" and not reg.get("reminded"):
                notify.reminder(reg, event)
                store.update_registration(reg["id"], reminded=True)
                sent += 1
    result = {"checked_events": checked, "reminders_sent": sent, "window_hours": hours}
    logger.info(json.dumps({"event": "reminders_run", **result}))
    return result


def lambda_handler(event, context=None):
    """Entry point for the EventBridge scheduled rule."""
    return run(int(config.get("REMINDER_HOURS", "24")))
