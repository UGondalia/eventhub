"""API tests. Run from the backend folder:  python -m unittest discover -s tests -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eventhub import db  # noqa: E402
from eventhub.handlers import lambda_handler  # noqa: E402
from eventhub.seed import ADMIN, DEMO, seed  # noqa: E402


def call(method, path, body=None, token=None, query=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    event = {
        "httpMethod": method, "path": path, "headers": headers,
        "queryStringParameters": query, "body": json.dumps(body) if body is not None else None,
    }
    result = lambda_handler(event, None)
    return result["statusCode"], (json.loads(result["body"]) if result["body"] else None)


def future(days=3):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Seed once, then copy the file for every test (keeps the suite fast).
        cls.template_dir = tempfile.mkdtemp()
        os.environ.update(STORAGE="local", AUTH_MODE="local", NOTIFY_MODE="local",
                          DATA_FILE=os.path.join(cls.template_dir, "db.json"),
                          OUTBOX_FILE=os.path.join(cls.template_dir, "outbox.jsonl"))
        db._CACHE.clear()
        seed()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copy(os.path.join(self.template_dir, "db.json"), os.path.join(self.tmp, "db.json"))
        os.environ["DATA_FILE"] = os.path.join(self.tmp, "db.json")
        os.environ["OUTBOX_FILE"] = os.path.join(self.tmp, "outbox.jsonl")
        db._CACHE.clear()
        _, res = call("POST", "/auth/login", {"email": ADMIN["email"], "password": ADMIN["password"]})
        self.admin = res["token"]
        _, res = call("POST", "/auth/login", {"email": DEMO["email"], "password": DEMO["password"]})
        self.user = res["token"]

    def new_event(self, **overrides):
        body = {"title": "Test Event", "category": "Technology", "venue": "Hall A", "city": "Surat",
                "start": future(), "capacity": 2, "price": 100, **overrides}
        status, res = call("POST", "/events", body, self.admin)
        self.assertEqual(status, 201, res)
        return res["event"]

    # ---- auth
    def test_health(self):
        self.assertEqual(call("GET", "/health")[0], 200)

    def test_signup_login_me(self):
        status, res = call("POST", "/auth/signup", {"name": "Test User", "email": "t@x.com", "password": "password1"})
        self.assertEqual(status, 201)
        self.assertEqual(call("POST", "/auth/signup", {"name": "Test User", "email": "t@x.com", "password": "password1"})[0], 409)
        self.assertEqual(call("GET", "/auth/me", token=res["token"])[1]["user"]["role"], "participant")
        self.assertEqual(call("POST", "/auth/login", {"email": "t@x.com", "password": "wrong"})[0], 401)

    def test_signup_validation(self):
        self.assertEqual(call("POST", "/auth/signup", {"name": "A", "email": "bad", "password": "x"})[0], 400)

    def test_requires_token(self):
        self.assertEqual(call("GET", "/auth/me")[0], 401)
        self.assertEqual(call("GET", "/auth/me", token="garbage")[0], 401)

    # ---- events
    def test_list_and_filter(self):
        status, res = call("GET", "/events")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(res["count"], 10)
        starts = [e["start"] for e in res["events"]]
        self.assertEqual(starts, sorted(starts))
        _, res = call("GET", "/events", query={"category": "Music"})
        self.assertTrue(all(e["category"] == "Music" for e in res["events"]))
        _, res = call("GET", "/events", query={"q": "marathon"})
        self.assertEqual(res["count"], 1)

    def test_admin_only_writes(self):
        body = {"title": "Nope", "category": "Arts", "venue": "x", "start": future(), "capacity": 5}
        self.assertEqual(call("POST", "/events", body)[0], 401)
        self.assertEqual(call("POST", "/events", body, self.user)[0], 403)

    def test_event_validation(self):
        bad = {"title": "Hi", "category": "Arts", "venue": "x", "start": future(), "capacity": 5}
        self.assertEqual(call("POST", "/events", bad, self.admin)[0], 400)
        bad = {"title": "Valid title", "category": "Nonsense", "venue": "x", "start": future(), "capacity": 5}
        self.assertEqual(call("POST", "/events", bad, self.admin)[0], 400)
        past = {"title": "Valid title", "category": "Arts", "venue": "x", "start": "2020-01-01T10:00:00Z", "capacity": 5}
        self.assertEqual(call("POST", "/events", past, self.admin)[0], 400)

    def test_update_and_delete(self):
        event = self.new_event()
        status, res = call("PUT", f"/events/{event['id']}", {"title": "Renamed event", "price": 250}, self.admin)
        self.assertEqual((status, res["event"]["title"], res["event"]["price"]), (200, "Renamed event", 250))
        self.assertEqual(call("DELETE", f"/events/{event['id']}", token=self.admin)[0], 200)
        self.assertEqual(call("GET", f"/events/{event['id']}")[0], 404)

    # ---- registrations
    def test_register_flow(self):
        event = self.new_event(capacity=3)
        status, res = call("POST", f"/events/{event['id']}/register", token=self.user)
        self.assertEqual(status, 201)
        self.assertTrue(res["registration"]["ticket_code"].startswith("EH-"))
        self.assertEqual(res["event"]["registered"], 1)
        self.assertEqual(call("POST", f"/events/{event['id']}/register", token=self.user)[0], 409)
        _, detail = call("GET", f"/events/{event['id']}", token=self.user)
        self.assertEqual(detail["my_registration"]["id"], res["registration"]["id"])
        _, mine = call("GET", "/registrations/me", token=self.user)
        self.assertIn(event["id"], [r["event_id"] for r in mine["registrations"]])

    def test_capacity_and_cancel(self):
        event = self.new_event(capacity=1)
        _, reg = call("POST", f"/events/{event['id']}/register", token=self.user)
        _, other = call("POST", "/auth/signup", {"name": "Second", "email": "s@x.com", "password": "password1"})
        self.assertEqual(call("POST", f"/events/{event['id']}/register", token=other["token"])[0], 409)
        self.assertEqual(call("DELETE", f"/registrations/{reg['registration']['id']}", token=other["token"])[0], 403)
        self.assertEqual(call("DELETE", f"/registrations/{reg['registration']['id']}", token=self.user)[0], 200)
        self.assertEqual(call("POST", f"/events/{event['id']}/register", token=other["token"])[0], 201)

    def test_notifications_written(self):
        event = self.new_event()
        call("POST", f"/events/{event['id']}/register", token=self.user)
        _, res = call("GET", "/admin/notifications", token=self.admin)
        self.assertEqual(res["notifications"][0]["kind"], "registration")

    def test_delete_event_cancels_registrations(self):
        event = self.new_event()
        call("POST", f"/events/{event['id']}/register", token=self.user)
        _, res = call("DELETE", f"/events/{event['id']}", token=self.admin)
        self.assertEqual(res["participants_notified"], 1)

    # ---- admin
    def test_stats_and_attendees(self):
        status, res = call("GET", "/admin/stats", token=self.admin)
        self.assertEqual(status, 200)
        self.assertGreater(res["total_registrations"], 0)
        self.assertEqual(len(res["registrations_by_day"]), 7)
        self.assertEqual(call("GET", "/admin/stats", token=self.user)[0], 403)
        event = res["top_events"][0]
        status, att = call("GET", f"/events/{event['id']}/registrations", token=self.admin)
        self.assertEqual(status, 200)
        self.assertEqual(len(att["registrations"]), event["registrations"])

    def test_reminders(self):
        event = self.new_event(start=(datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(timespec="seconds"))
        call("POST", f"/events/{event['id']}/register", token=self.user)
        _, first = call("POST", "/admin/reminders/run", {}, self.admin)
        self.assertGreaterEqual(first["reminders_sent"], 1)
        _, second = call("POST", "/admin/reminders/run", {}, self.admin)
        self.assertEqual(second["reminders_sent"], 0)  # never reminded twice

    def test_api_gateway_http_api_event_and_cognito_claims(self):
        """Payload v2 (HTTP API) with Cognito claims from the JWT authorizer, as sent on AWS."""
        claims = {"sub": "abc123", "email": "org@example.com", "name": "Org", "cognito:groups": "[admin]"}
        event = {
            "version": "2.0", "rawPath": "/admin/stats", "headers": {}, "isBase64Encoded": False,
            "requestContext": {"http": {"method": "GET"}, "authorizer": {"jwt": {"claims": claims}}},
        }
        self.assertEqual(lambda_handler(event, None)["statusCode"], 200)
        claims["cognito:groups"] = "[]"  # signed in, but not in the admin group
        self.assertEqual(lambda_handler(event, None)["statusCode"], 403)
        # payload v1 / REST API shape with a real list
        v1 = {"httpMethod": "GET", "path": "/auth/me",
              "requestContext": {"authorizer": {"claims": {**claims, "cognito:groups": ["admin"]}}}}
        result = json.loads(lambda_handler(v1, None)["body"])
        self.assertEqual(result["user"]["role"], "admin")

    def test_unknown_route_and_cors(self):
        self.assertEqual(call("GET", "/nope")[0], 404)
        self.assertEqual(call("PATCH", "/events")[0], 405)
        result = lambda_handler({"httpMethod": "OPTIONS", "path": "/events"}, None)
        self.assertEqual(result["statusCode"], 204)
        self.assertIn("Access-Control-Allow-Origin", result["headers"])


if __name__ == "__main__":
    unittest.main()
