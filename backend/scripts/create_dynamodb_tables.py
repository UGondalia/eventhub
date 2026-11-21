"""Create the three DynamoDB tables EventHub needs.

    python scripts/create_dynamodb_tables.py                  # uses your AWS credentials/region
    python scripts/create_dynamodb_tables.py --region us-east-1

Tables are PAY_PER_REQUEST (on-demand), so there is nothing to size and you pay
only for the requests you make, which keeps a student account's cost near zero.
"""
import argparse
import os

import boto3
from botocore.exceptions import ClientError

KEY = [{"AttributeName": "id", "KeyType": "HASH"}]


def _index(name, attribute):
    return {
        "IndexName": name,
        "KeySchema": [{"AttributeName": attribute, "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
    }


def _attr(name):
    return {"AttributeName": name, "AttributeType": "S"}


TABLES = [
    {
        "TableName": "EventHubEvents",
        "KeySchema": KEY,
        "AttributeDefinitions": [_attr("id")],
    },
    {
        "TableName": "EventHubRegistrations",
        "KeySchema": KEY,
        "AttributeDefinitions": [_attr("id"), _attr("user_id"), _attr("event_id")],
        "GlobalSecondaryIndexes": [
            _index("user_id-index", "user_id"),
            _index("event_id-index", "event_id"),
        ],
    },
    {
        "TableName": "EventHubUsers",
        "KeySchema": KEY,
        "AttributeDefinitions": [_attr("id"), _attr("email")],
        "GlobalSecondaryIndexes": [_index("email-index", "email")],
    },
]


def create_tables(resource):
    existing = {t.name for t in resource.tables.all()}
    for spec in TABLES:
        if spec["TableName"] in existing:
            print(f"exists   {spec['TableName']}")
            continue
        table = resource.create_table(BillingMode="PAY_PER_REQUEST", **spec)
        table.wait_until_exists()
        print(f"created  {spec['TableName']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--endpoint", default=None, help="e.g. http://localhost:8001 for DynamoDB Local")
    args = parser.parse_args()
    try:
        create_tables(boto3.resource("dynamodb", region_name=args.region, endpoint_url=args.endpoint))
    except ClientError as error:
        raise SystemExit(f"AWS error: {error}")
