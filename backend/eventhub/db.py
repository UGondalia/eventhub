"""Storage layer with two interchangeable back ends.

LocalStore    JSON file on disk. Zero setup, used for local development/tests.
DynamoStore   Amazon DynamoDB. Used on AWS (STORAGE=dynamodb).

Both expose exactly the same methods, so handlers.py never knows which one it
is talking to. That is what makes the "upgrade to AWS" a configuration change.

DynamoDB tables expected (see scripts/create_dynamodb_tables.py):
  EventHubEvents          PK: id
  EventHubRegistrations   PK: id   GSI user_id-index (user_id), event_id-index (event_id)
  EventHubUsers           PK: id   GSI email-index (email)   [local auth only]
"""
import json
import os
import threading
from decimal import Decimal

from . import config

_LOCK = threading.RLock()


# --------------------------------------------------------------------------- #
# Local JSON store
# --------------------------------------------------------------------------- #
class LocalStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(path):
            self._write({"users": {}, "events": {}, "registrations": {}})

    # -- file helpers
    def _read(self):
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, self.path)

    def is_empty(self):
        with _LOCK:
            return not self._read()["events"]

    # -- users
    def create_user(self, user):
        with _LOCK:
            data = self._read()
            if any(u["email"] == user["email"] for u in data["users"].values()):
                raise ValueError("email already registered")
            data["users"][user["id"]] = user
            self._write(data)
            return user

    def get_user(self, user_id):
        with _LOCK:
            return self._read()["users"].get(user_id)

    def get_user_by_email(self, email):
        with _LOCK:
            for user in self._read()["users"].values():
                if user["email"] == email:
                    return user
            return None

    # -- events
    def list_events(self):
        with _LOCK:
            return list(self._read()["events"].values())

    def get_event(self, event_id):
        with _LOCK:
            return self._read()["events"].get(event_id)

    def put_event(self, event):
        with _LOCK:
            data = self._read()
            data["events"][event["id"]] = event
            self._write(data)
            return event

    def delete_event(self, event_id):
        with _LOCK:
            data = self._read()
            data["events"].pop(event_id, None)
            self._write(data)

    def reserve_seat(self, event_id):
        """Atomically take one seat. Returns False if the event is full."""
        with _LOCK:
            data = self._read()
            event = data["events"].get(event_id)
            if not event or event.get("registered", 0) >= event["capacity"]:
                return False
            event["registered"] = event.get("registered", 0) + 1
            self._write(data)
            return True

    def release_seat(self, event_id):
        with _LOCK:
            data = self._read()
            event = data["events"].get(event_id)
            if event and event.get("registered", 0) > 0:
                event["registered"] -= 1
                self._write(data)

    # -- registrations
    def put_registration(self, registration):
        with _LOCK:
            data = self._read()
            data["registrations"][registration["id"]] = registration
            self._write(data)
            return registration

    def get_registration(self, registration_id):
        with _LOCK:
            return self._read()["registrations"].get(registration_id)

    def update_registration(self, registration_id, **fields):
        with _LOCK:
            data = self._read()
            registration = data["registrations"][registration_id]
            registration.update(fields)
            self._write(data)
            return registration

    def registrations_for_user(self, user_id):
        with _LOCK:
            return [r for r in self._read()["registrations"].values() if r["user_id"] == user_id]

    def registrations_for_event(self, event_id):
        with _LOCK:
            return [r for r in self._read()["registrations"].values() if r["event_id"] == event_id]

    def all_registrations(self):
        with _LOCK:
            return list(self._read()["registrations"].values())


# --------------------------------------------------------------------------- #
# DynamoDB store
# --------------------------------------------------------------------------- #
def _to_dynamo(obj):
    """DynamoDB rejects Python floats; round-trip through Decimal."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


def _from_dynamo(obj):
    if isinstance(obj, list):
        return [_from_dynamo(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _from_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    return obj


class DynamoStore:
    def __init__(self):
        import boto3  # imported lazily so local mode needs no dependency
        from boto3.dynamodb.conditions import Key
        from botocore.exceptions import ClientError

        self._Key = Key
        self._ClientError = ClientError
        endpoint = config.get("DYNAMODB_ENDPOINT")  # e.g. DynamoDB Local / moto
        resource = boto3.resource(
            "dynamodb",
            region_name=config.get("AWS_REGION", config.get("AWS_DEFAULT_REGION", "us-east-1")),
            endpoint_url=endpoint,
        )
        self.users = resource.Table(config.get("USERS_TABLE", "EventHubUsers"))
        self.events = resource.Table(config.get("EVENTS_TABLE", "EventHubEvents"))
        self.registrations = resource.Table(
            config.get("REGISTRATIONS_TABLE", "EventHubRegistrations")
        )

    @staticmethod
    def _scan_all(table):
        items, kwargs = [], {}
        while True:
            page = table.scan(**kwargs)
            items.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                return [_from_dynamo(i) for i in items]
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def _query_index(self, table, index, key, value):
        items, kwargs = [], {}
        while True:
            page = table.query(
                IndexName=index,
                KeyConditionExpression=self._Key(key).eq(value),
                **kwargs,
            )
            items.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                return [_from_dynamo(i) for i in items]
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def is_empty(self):
        return not self.events.scan(Limit=1).get("Items")

    # users
    def create_user(self, user):
        if self.get_user_by_email(user["email"]):
            raise ValueError("email already registered")
        self.users.put_item(Item=_to_dynamo(user))
        return user

    def get_user(self, user_id):
        item = self.users.get_item(Key={"id": user_id}).get("Item")
        return _from_dynamo(item) if item else None

    def get_user_by_email(self, email):
        found = self._query_index(self.users, "email-index", "email", email)
        return found[0] if found else None

    # events
    def list_events(self):
        return self._scan_all(self.events)

    def get_event(self, event_id):
        item = self.events.get_item(Key={"id": event_id}).get("Item")
        return _from_dynamo(item) if item else None

    def put_event(self, event):
        self.events.put_item(Item=_to_dynamo(event))
        return event

    def delete_event(self, event_id):
        self.events.delete_item(Key={"id": event_id})

    # `capacity` is a DynamoDB reserved word, so attribute names go through
    # ExpressionAttributeNames (#cap, #reg, #id) instead of being written inline.
    def reserve_seat(self, event_id):
        """Conditional atomic increment: two people can never take the last seat."""
        try:
            self.events.update_item(
                Key={"id": event_id},
                UpdateExpression="SET #reg = if_not_exists(#reg, :zero) + :one",
                ConditionExpression="attribute_exists(#id) AND "
                "(attribute_not_exists(#reg) OR #reg < #cap)",
                ExpressionAttributeNames={"#reg": "registered", "#cap": "capacity", "#id": "id"},
                ExpressionAttributeValues={":one": 1, ":zero": 0},
            )
            return True
        except self._ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def release_seat(self, event_id):
        try:
            self.events.update_item(
                Key={"id": event_id},
                UpdateExpression="SET #reg = #reg - :one",
                ConditionExpression="#reg > :zero",
                ExpressionAttributeNames={"#reg": "registered"},
                ExpressionAttributeValues={":one": 1, ":zero": 0},
            )
        except self._ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    # registrations
    def put_registration(self, registration):
        self.registrations.put_item(Item=_to_dynamo(registration))
        return registration

    def get_registration(self, registration_id):
        item = self.registrations.get_item(Key={"id": registration_id}).get("Item")
        return _from_dynamo(item) if item else None

    def update_registration(self, registration_id, **fields):
        names = {f"#f{i}": key for i, key in enumerate(fields)}
        values = {f":v{i}": _to_dynamo(value) for i, value in enumerate(fields.values())}
        expression = "SET " + ", ".join(f"#f{i} = :v{i}" for i in range(len(fields)))
        result = self.registrations.update_item(
            Key={"id": registration_id},
            UpdateExpression=expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return _from_dynamo(result["Attributes"])

    def registrations_for_user(self, user_id):
        return self._query_index(self.registrations, "user_id-index", "user_id", user_id)

    def registrations_for_event(self, event_id):
        return self._query_index(self.registrations, "event_id-index", "event_id", event_id)

    def all_registrations(self):
        return self._scan_all(self.registrations)


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
_CACHE = {}


def get_store():
    mode = config.storage_mode()
    key = (mode, config.data_file() if mode == "local" else "")
    if key not in _CACHE:
        _CACHE[key] = LocalStore(config.data_file()) if mode == "local" else DynamoStore()
    return _CACHE[key]
