"""EventHub API: one Lambda-style entry point (`lambda_handler`) with a tiny router.

It speaks the API Gateway *Lambda proxy* event format, so the same function is:
  * called directly by tests,
  * wrapped by local_server.py for local development,
  * deployed unchanged to AWS Lambda behind API Gateway.

Authentication
  AUTH_MODE=local    Bearer JWT issued by /auth/login (see auth.py)
  AUTH_MODE=cognito  API Gateway's Cognito authorizer verifies the token and
                     passes the claims in event.requestContext.authorizer.claims
"""
import base64
import json
import logging
import re
import secrets
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from . import auth, config, notify, reminders
from .db import get_store

logger = logging.getLogger("eventhub")
logger.setLevel(logging.INFO)

CATEGORIES = [
    "Technology", "Music", "Business", "Sports",
    "Arts", "Food", "Education", "Community",
]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat(timespec="seconds")


def parse_dt(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(400, "Dates must be ISO 8601, e.g. 2026-12-01T18:30:00Z")
    parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)  # always UTC, so ISO strings sort correctly


def _json_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    raise TypeError(f"Cannot serialise {type(obj)}")


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def response(status, body=None):
    headers = {"Content-Type": "application/json", **CORS_HEADERS}
    payload = "" if body is None else json.dumps(body, default=_json_default)
    return {"statusCode": status, "headers": headers, "body": payload}


def _groups(claims):
    raw = claims.get("cognito:groups") or []
    if isinstance(raw, str):
        raw = [g for g in re.split(r"[\s,\[\]]+", raw) if g]
    return list(raw)


def current_user(event):
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    # REST API / payload v1 puts claims at authorizer.claims; HTTP API (v2) at authorizer.jwt.claims
    claims = authorizer.get("claims") or (authorizer.get("jwt") or {}).get("claims") or {}
    if not claims and config.auth_mode() == "local":
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        header = headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            claims = auth.decode_token(header[7:].strip()) or {}
    if not claims.get("sub"):
        return None
    email = claims.get("email", "")
    return {
        "id": claims["sub"],
        "email": email,
        "name": claims.get("name") or claims.get("cognito:username") or email.split("@")[0],
        "role": "admin" if "admin" in _groups(claims) else "participant",
    }


class Ctx:
    """Everything a route handler needs, parsed lazily."""

    def __init__(self, event, params):
        self.event = event
        self.params = params
        self.query = event.get("queryStringParameters") or {}
        self._body = None
        self._user = False

    @property
    def body(self):
        if self._body is None:
            raw = self.event.get("body")
            if raw and self.event.get("isBase64Encoded"):
                raw = base64.b64decode(raw).decode()
            try:
                self._body = json.loads(raw) if raw else {}
            except ValueError:
                raise ApiError(400, "Request body must be valid JSON")
            if not isinstance(self._body, dict):
                raise ApiError(400, "JSON body must be an object")
        return self._body

    @property
    def user(self):
        if self._user is False:
            self._user = current_user(self.event)
        return self._user

    def require_user(self):
        if not self.user:
            raise ApiError(401, "Please sign in to continue")
        return self.user

    def require_admin(self):
        user = self.require_user()
        if user["role"] != "admin":
            raise ApiError(403, "Only organisers can do this")
        return user


ROUTES = []


def route(method, pattern):
    regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$")

    def decorator(fn):
        ROUTES.append((method, regex, fn))
        return fn

    return decorator


def event_view(event):
    view = dict(event)
    registered = event.get("registered", 0)
    view["registered"] = registered
    view["seats_left"] = max(0, event["capacity"] - registered)
    view["sold_out"] = view["seats_left"] == 0
    return view


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def clean_event_fields(body, partial=False):
    out = {}
    if not partial:
        for key in ("title", "category", "venue", "start", "capacity"):
            if body.get(key) in (None, ""):
                raise ApiError(400, f"'{key}' is required")

    if "title" in body:
        title = str(body["title"]).strip()
        if not 3 <= len(title) <= 120:
            raise ApiError(400, "Title must be 3 to 120 characters")
        out["title"] = title
    if "description" in body:
        out["description"] = str(body["description"] or "").strip()[:2000]
    elif not partial:
        out["description"] = ""
    if "category" in body:
        if body["category"] not in CATEGORIES:
            raise ApiError(400, "Category must be one of: " + ", ".join(CATEGORIES))
        out["category"] = body["category"]
    for key in ("venue", "city", "organizer", "image"):
        if key in body:
            out[key] = str(body[key] or "").strip()[:300]
    if "start" in body:
        out["start"] = parse_dt(body["start"]).isoformat(timespec="seconds")
    if "end" in body:
        out["end"] = parse_dt(body["end"]).isoformat(timespec="seconds") if body["end"] else ""
    if "price" in body or not partial:
        try:
            price = float(body.get("price") or 0)
        except (TypeError, ValueError):
            raise ApiError(400, "Price must be a number")
        if price < 0:
            raise ApiError(400, "Price cannot be negative")
        out["price"] = int(price) if price == int(price) else round(price, 2)
    if "capacity" in body:
        try:
            capacity = int(body["capacity"])
        except (TypeError, ValueError):
            raise ApiError(400, "Capacity must be a whole number")
        if not 1 <= capacity <= 100000:
            raise ApiError(400, "Capacity must be between 1 and 100000")
        out["capacity"] = capacity
    if out.get("start") and out.get("end") and out["end"] <= out["start"]:
        raise ApiError(400, "The end time must be after the start time")
    return out


# --------------------------------------------------------------------------- #
# Routes: system and auth
# --------------------------------------------------------------------------- #
@route("GET", "/health")
def health(ctx):
    return 200, {
        "status": "ok",
        "storage": config.storage_mode(),
        "auth": config.auth_mode(),
        "notifications": config.notify_mode(),
        "time": now_iso(),
    }


@route("POST", "/auth/signup")
def signup(ctx):
    if config.auth_mode() != "local":
        raise ApiError(404, "Sign-up is handled by Amazon Cognito in this mode")
    body = ctx.body
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    if not 2 <= len(name) <= 60:
        raise ApiError(400, "Enter your name (2 to 60 characters)")
    if not EMAIL_RE.match(email):
        raise ApiError(400, "Enter a valid email address")
    if len(password) < 8:
        raise ApiError(400, "Password must be at least 8 characters")
    user = {
        "id": "usr_" + uuid.uuid4().hex[:12],
        "email": email,
        "name": name,
        "role": "participant",
        "password_hash": auth.hash_password(password),
        "created_at": now_iso(),
    }
    try:
        get_store().create_user(user)
    except ValueError:
        raise ApiError(409, "An account with this email already exists")
    return 201, {"token": auth.create_token(user), "user": public_user(user)}


@route("POST", "/auth/login")
def login(ctx):
    if config.auth_mode() != "local":
        raise ApiError(404, "Sign-in is handled by Amazon Cognito in this mode")
    email = str(ctx.body.get("email", "")).strip().lower()
    password = str(ctx.body.get("password", ""))
    user = get_store().get_user_by_email(email)
    if not user or not auth.verify_password(password, user["password_hash"]):
        raise ApiError(401, "Email or password is incorrect")
    return 200, {"token": auth.create_token(user), "user": public_user(user)}


@route("GET", "/auth/me")
def me(ctx):
    return 200, {"user": ctx.require_user()}


def public_user(user):
    return {k: user[k] for k in ("id", "email", "name", "role")}


# --------------------------------------------------------------------------- #
# Routes: events
# --------------------------------------------------------------------------- #
@route("GET", "/events")
def list_events(ctx):
    q = (ctx.query.get("q") or "").strip().lower()
    category = ctx.query.get("category") or ""
    scope = ctx.query.get("scope") or "upcoming"
    if scope in ("past", "all"):
        ctx.require_admin() if scope == "all" else None
    cutoff = now().isoformat(timespec="seconds")

    events = get_store().list_events()
    if category:
        events = [e for e in events if e["category"] == category]
    if q:
        events = [
            e for e in events
            if q in " ".join(
                str(e.get(k, "")) for k in ("title", "description", "venue", "city", "category")
            ).lower()
        ]
    if scope == "upcoming":
        events = [e for e in events if e["start"] >= cutoff]
    elif scope == "past":
        events = [e for e in events if e["start"] < cutoff]
    events.sort(key=lambda e: e["start"], reverse=(scope == "past"))
    return 200, {"events": [event_view(e) for e in events], "count": len(events)}


@route("GET", "/events/{id}")
def get_event(ctx):
    store = get_store()
    event = store.get_event(ctx.params["id"])
    if not event:
        raise ApiError(404, "Event not found")
    body = {"event": event_view(event), "my_registration": None}
    if ctx.user:
        for reg in store.registrations_for_user(ctx.user["id"]):
            if reg["event_id"] == event["id"] and reg["status"] == "confirmed":
                body["my_registration"] = reg
    return 200, body


@route("POST", "/events")
def create_event(ctx):
    user = ctx.require_admin()
    fields = clean_event_fields(ctx.body)
    if fields["start"] <= now_iso():
        raise ApiError(400, "The start time must be in the future")
    event = {
        "id": "evt_" + secrets.token_hex(5),
        "city": "",
        "organizer": user["name"],
        "image": "",
        "end": "",
        **fields,
        "registered": 0,
        "created_by": user["id"],
        "created_at": now_iso(),
    }
    get_store().put_event(event)
    return 201, {"event": event_view(event)}


@route("PUT", "/events/{id}")
def update_event(ctx):
    ctx.require_admin()
    store = get_store()
    event = store.get_event(ctx.params["id"])
    if not event:
        raise ApiError(404, "Event not found")
    fields = clean_event_fields(ctx.body, partial=True)
    if "capacity" in fields and fields["capacity"] < event.get("registered", 0):
        raise ApiError(
            400, f"{event.get('registered', 0)} people are already registered; "
            "capacity cannot go below that"
        )
    event.update(fields)
    if event.get("end") and event["end"] <= event["start"]:
        raise ApiError(400, "The end time must be after the start time")
    event["updated_at"] = now_iso()
    store.put_event(event)
    return 200, {"event": event_view(event)}


@route("DELETE", "/events/{id}")
def delete_event(ctx):
    ctx.require_admin()
    store = get_store()
    event = store.get_event(ctx.params["id"])
    if not event:
        raise ApiError(404, "Event not found")
    notified = 0
    for reg in store.registrations_for_event(event["id"]):
        if reg["status"] == "confirmed":
            store.update_registration(reg["id"], status="cancelled", cancelled_at=now_iso())
            notify.event_cancelled(reg, event)
            notified += 1
    store.delete_event(event["id"])
    return 200, {"deleted": event["id"], "participants_notified": notified}


# --------------------------------------------------------------------------- #
# Routes: registrations
# --------------------------------------------------------------------------- #
@route("POST", "/events/{id}/register")
def register(ctx):
    user = ctx.require_user()
    store = get_store()
    event = store.get_event(ctx.params["id"])
    if not event:
        raise ApiError(404, "Event not found")
    if event["start"] <= now_iso():
        raise ApiError(400, "This event has already started")
    for reg in store.registrations_for_user(user["id"]):
        if reg["event_id"] == event["id"] and reg["status"] == "confirmed":
            raise ApiError(409, "You are already registered for this event")
    if not store.reserve_seat(event["id"]):
        raise ApiError(409, "Sorry, this event is sold out")

    registration = {
        "id": "reg_" + secrets.token_hex(6),
        "event_id": event["id"],
        "user_id": user["id"],
        "user_email": user["email"],
        "user_name": user["name"],
        "ticket_code": "EH-" + secrets.token_hex(3).upper(),
        "status": "confirmed",
        "reminded": False,
        "created_at": now_iso(),
    }
    try:
        store.put_registration(registration)
    except Exception:
        store.release_seat(event["id"])
        raise
    notify.registration_confirmed(registration, event)
    return 201, {
        "registration": registration,
        "event": event_view(store.get_event(event["id"])),
    }


@route("DELETE", "/registrations/{id}")
def cancel_registration(ctx):
    user = ctx.require_user()
    store = get_store()
    reg = store.get_registration(ctx.params["id"])
    if not reg:
        raise ApiError(404, "Registration not found")
    if reg["user_id"] != user["id"] and user["role"] != "admin":
        raise ApiError(403, "This is not your registration")
    if reg["status"] != "confirmed":
        raise ApiError(409, "This registration is already cancelled")
    reg = store.update_registration(reg["id"], status="cancelled", cancelled_at=now_iso())
    store.release_seat(reg["event_id"])
    event = store.get_event(reg["event_id"])
    if event:
        notify.registration_cancelled(reg, event)
    return 200, {"registration": reg}


@route("GET", "/registrations/me")
def my_registrations(ctx):
    user = ctx.require_user()
    store = get_store()
    regs = sorted(store.registrations_for_user(user["id"]), key=lambda r: r["created_at"], reverse=True)
    items = []
    for reg in regs:
        event = store.get_event(reg["event_id"])
        items.append({**reg, "event": event_view(event) if event else None})
    return 200, {"registrations": items}


@route("GET", "/events/{id}/registrations")
def event_registrations(ctx):
    ctx.require_admin()
    store = get_store()
    event = store.get_event(ctx.params["id"])
    if not event:
        raise ApiError(404, "Event not found")
    regs = sorted(store.registrations_for_event(event["id"]), key=lambda r: r["created_at"], reverse=True)
    return 200, {"event": event_view(event), "registrations": regs}


# --------------------------------------------------------------------------- #
# Routes: admin
# --------------------------------------------------------------------------- #
@route("GET", "/admin/stats")
def stats(ctx):
    ctx.require_admin()
    store = get_store()
    events = store.list_events()
    confirmed = [r for r in store.all_registrations() if r["status"] == "confirmed"]
    cutoff = now_iso()
    upcoming = [e for e in events if e["start"] >= cutoff]
    price = {e["id"]: e.get("price", 0) for e in events}
    per_event = Counter(r["event_id"] for r in confirmed)
    by_category = []
    for category in CATEGORIES:
        in_cat = [e for e in events if e["category"] == category]
        by_category.append({
            "category": category,
            "events": len(in_cat),
            "registrations": sum(per_event[e["id"]] for e in in_cat),
        })
    top = sorted(events, key=lambda e: per_event[e["id"]], reverse=True)[:5]
    seats = sum(e["capacity"] for e in upcoming)
    filled = sum(e.get("registered", 0) for e in upcoming)
    today = now().date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    per_day = Counter(r["created_at"][:10] for r in confirmed)
    return 200, {
        "total_events": len(events),
        "upcoming_events": len(upcoming),
        "total_registrations": len(confirmed),
        "revenue": sum(price.get(r["event_id"], 0) for r in confirmed),
        "fill_rate": round(100 * filled / seats) if seats else 0,
        "by_category": by_category,
        "top_events": [
            {"id": e["id"], "title": e["title"], "registrations": per_event[e["id"]],
             "capacity": e["capacity"]}
            for e in top
        ],
        "registrations_by_day": [
            {"date": d.isoformat(), "count": per_day[d.isoformat()]} for d in days
        ],
    }


@route("POST", "/admin/reminders/run")
def run_reminders(ctx):
    ctx.require_admin()
    hours = int(ctx.body.get("hours") or config.get("REMINDER_HOURS", "24"))
    return 200, reminders.run(hours)


@route("GET", "/admin/notifications")
def notifications(ctx):
    ctx.require_admin()
    return 200, {"notifications": notify.recent(50), "mode": config.notify_mode()}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def lambda_handler(event, context=None):
    started = time.time()
    http = (event.get("requestContext") or {}).get("http") or {}  # HTTP API payload v2
    method = (event.get("httpMethod") or http.get("method") or "GET").upper()
    path = event.get("path") or event.get("rawPath") or "/"
    if path.startswith("/api/"):
        path = path[4:]
    path = path.rstrip("/") or "/"
    status = 500
    try:
        if method == "OPTIONS":
            status, result = 204, response(204)
            return result
        path_matched = False
        for route_method, regex, fn in ROUTES:
            match = regex.match(path)
            if not match:
                continue
            path_matched = True
            if route_method != method:
                continue
            status, body = fn(Ctx(event, match.groupdict()))
            return response(status, body)
        if path_matched:
            raise ApiError(405, "Method not allowed")
        raise ApiError(404, f"No route for {method} {path}")
    except ApiError as error:
        status = error.status
        return response(error.status, {"error": error.message})
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error")
        status = 500
        return response(500, {"error": "Something went wrong on our side. Please try again."})
    finally:
        logger.info(json.dumps({
            "event": "request", "method": method, "path": path, "status": status,
            "ms": round((time.time() - started) * 1000, 1),
        }))
