"""Runs the *entire* API test-suite again, but against DynamoDB instead of the JSON file.

DynamoDB is simulated in memory by `moto`, so no AWS account is needed. This proves the
DynamoStore class behaves exactly like LocalStore, which is what makes the AWS upgrade safe.

    pip install moto boto3
    python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

try:
    import boto3
    from moto import mock_aws
except ImportError:  # moto is optional
    boto3 = None

import test_api  # noqa: E402  (module import, so its test class is not collected twice)
from eventhub import db  # noqa: E402
from eventhub.seed import ADMIN, DEMO, seed  # noqa: E402


@unittest.skipIf(boto3 is None, "install moto and boto3 to run the DynamoDB tests")
class DynamoApiTests(test_api.ApiTests):
    @classmethod
    def setUpClass(cls):
        from create_dynamodb_tables import create_tables

        cls._saved = {k: os.environ.get(k) for k in (
            "STORAGE", "AUTH_MODE", "NOTIFY_MODE", "OUTBOX_FILE",
            "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION")}
        cls.tmp_dir = tempfile.mkdtemp()
        os.environ.update(
            STORAGE="dynamodb", AUTH_MODE="local", NOTIFY_MODE="local",
            OUTBOX_FILE=os.path.join(cls.tmp_dir, "outbox.jsonl"),
            AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
            AWS_DEFAULT_REGION="us-east-1",
        )
        cls.mock = mock_aws()
        cls.mock.start()
        db._CACHE.clear()
        create_tables(boto3.resource("dynamodb", region_name="us-east-1"))
        seed()  # seeded once; every test creates its own events so they stay independent

    @classmethod
    def tearDownClass(cls):
        cls.mock.stop()
        db._CACHE.clear()
        for key, value in cls._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        db._CACHE.clear()
        _, res = test_api.call("POST", "/auth/login", {"email": ADMIN["email"], "password": ADMIN["password"]})
        self.admin = res["token"]
        _, res = test_api.call("POST", "/auth/login", {"email": DEMO["email"], "password": DEMO["password"]})
        self.user = res["token"]


if __name__ == "__main__":
    unittest.main()
