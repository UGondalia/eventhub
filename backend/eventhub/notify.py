"""Notifications.

NOTIFY_MODE=local  Appends each message to data/outbox.jsonl (visible in the
                   admin "Notifications" tab), so you can see exactly what
                   would have been emailed.
NOTIFY_MODE=sns    Publishes to an Amazon SNS topic (SNS_TOPIC_ARN). The
                   recipient address travels as a message attribute so that
                   per-subscriber filter policies can route it.

A failing notification must never break a registration, so errors are logged
and swallowed.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from . import config

IST = timezone(timedelta(hours=5, minutes=30))


def _when(iso):
    """2026-11-26T09:30:00+00:00 -> 'Thu, 26 Nov 2026, 03:00 PM IST'."""
    try:
        return datetime.fromisoformat(iso).astimezone(IST).strftime("%a, %d %b %Y, %I:%M %p IST")
    except (TypeError, ValueError):
        return iso

logger = logging.getLogger("eventhub")


def _publish(kind, to_email, subject, message):
    record = {
        "id": uuid.uuid4().hex[:10],
        "kind": kind,
        "to": to_email,
        "subject": subject,
        "message": message,
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        if config.notify_mode() == "sns":
            import boto3

            boto3.client(
                "sns", region_name=config.get("AWS_REGION", "us-east-1")
            ).publish(
                TopicArn=config.get("SNS_TOPIC_ARN"),
                Subject=subject[:99],
                Message=message,
                MessageAttributes={
                    "email": {"DataType": "String", "StringValue": to_email or "unknown"},
                    "kind": {"DataType": "String", "StringValue": kind},
                },
            )
        else:
            with open(config.outbox_file(), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        logger.info(json.dumps({"event": "notification", "kind": kind, "to": to_email}))
    except Exception as error:  # noqa: BLE001
        logger.error(json.dumps({"event": "notification_failed", "error": str(error)}))
    return record


def recent(limit=50):
    """Newest-first list of locally 'sent' notifications (local mode only)."""
    if config.notify_mode() == "sns":
        return []
    try:
        with open(config.outbox_file(), encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
    except FileNotFoundError:
        return []
    return list(reversed(rows))[:limit]


def registration_confirmed(reg, event):
    return _publish(
        "registration",
        reg["user_email"],
        f"You're in! {event['title']}",
        f"Hi {reg['user_name']},\n\nYour registration for \"{event['title']}\" is confirmed.\n"
        f"When: {_when(event['start'])}\nWhere: {event['venue']}, {event.get('city', '')}\n"
        f"Ticket code: {reg['ticket_code']}\n\nSee you there!\n- EventHub",
    )


def registration_cancelled(reg, event):
    return _publish(
        "cancellation",
        reg["user_email"],
        f"Registration cancelled: {event['title']}",
        f"Hi {reg['user_name']},\n\nYour registration (ticket {reg['ticket_code']}) for "
        f"\"{event['title']}\" has been cancelled.\n- EventHub",
    )


def event_cancelled(reg, event):
    return _publish(
        "event_cancelled",
        reg["user_email"],
        f"Event cancelled: {event['title']}",
        f"Hi {reg['user_name']},\n\nWe're sorry, \"{event['title']}\" has been cancelled "
        f"by the organiser.\n- EventHub",
    )


def reminder(reg, event):
    return _publish(
        "reminder",
        reg["user_email"],
        f"Reminder: {event['title']} is coming up",
        f"Hi {reg['user_name']},\n\nJust a reminder that \"{event['title']}\" starts at "
        f"{_when(event['start'])} at {event['venue']}.\nTicket code: {reg['ticket_code']}\n- EventHub",
    )
