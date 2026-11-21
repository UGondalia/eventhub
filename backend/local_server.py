"""Run the EventHub API locally.

    python local_server.py              # http://localhost:8000
    python local_server.py --port 9000
    python local_server.py --reset      # wipe local data and re-seed

This is a thin adapter: it turns each HTTP request into an API Gateway
"Lambda proxy" event, calls the very same `lambda_handler` that will run on
AWS, and writes the returned dict back as the HTTP response.
"""
import argparse
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eventhub import config  # noqa: E402
from eventhub.handlers import lambda_handler  # noqa: E402
from eventhub.seed import ADMIN, DEMO, seed  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def _dispatch(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else None
        event = {
            "httpMethod": self.command,
            "path": parsed.path,
            "queryStringParameters": dict(parse_qsl(parsed.query)) or None,
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
            "isBase64Encoded": False,
            "requestContext": {},
        }
        result = lambda_handler(event, None)
        payload = (result.get("body") or "").encode()
        self.send_response(result["statusCode"])
        for key, value in result["headers"].items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = _dispatch

    def log_message(self, *args):  # request logging is done in lambda_handler
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reset", action="store_true", help="delete local data and re-seed")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    if args.reset:
        for path in (config.data_file(), config.outbox_file()):
            if os.path.exists(path):
                os.remove(path)
    if seed():
        print("Seeded demo data.")
    print(f"\nEventHub API running at http://localhost:{args.port}")
    print(f"  Admin       {ADMIN['email']}  /  {ADMIN['password']}")
    print(f"  Participant {DEMO['email']}  /  {DEMO['password']}\n")
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
