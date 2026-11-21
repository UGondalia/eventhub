"""Central configuration.

Everything is read from environment variables *at call time*, so the exact same
code runs on your laptop and inside AWS Lambda. Only the environment changes.

Local defaults                      AWS (set as Lambda environment variables)
---------------------------------   ------------------------------------------
STORAGE=local   (JSON file)         STORAGE=dynamodb
AUTH_MODE=local (own JWT)           AUTH_MODE=cognito   (API Gateway authorizer)
NOTIFY_MODE=local (outbox file)     NOTIFY_MODE=sns     (+ SNS_TOPIC_ARN)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def get(name, default=None):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def storage_mode():
    return get("STORAGE", "local")


def auth_mode():
    return get("AUTH_MODE", "local")


def notify_mode():
    return get("NOTIFY_MODE", "local")


def data_file():
    return get("DATA_FILE", str(BASE_DIR / "data" / "db.json"))


def outbox_file():
    return get("OUTBOX_FILE", str(BASE_DIR / "data" / "outbox.jsonl"))
