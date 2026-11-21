"""Local authentication: PBKDF2 password hashing and HS256 JSON Web Tokens.

This replaces Amazon Cognito while developing locally. The token payload uses
the same claim names Cognito puts in its ID token (sub, email, name,
cognito:groups), so the handlers never need to know which one issued it.
Standard library only, no dependencies.
"""
import base64
import hashlib
import hmac
import json
import os
import time

from . import config


def hash_password(password, iterations=200_000):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _algo, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(check.hex(), digest)
    except Exception:
        return False


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(message):
    secret = config.get("JWT_SECRET", "dev-secret-change-me").encode()
    return _b64(hmac.new(secret, message.encode(), hashlib.sha256).digest())


def create_token(user, ttl_seconds=8 * 3600):
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"],
        "cognito:groups": [user["role"]],
        "iat": now,
        "exp": now + ttl_seconds,
    }
    head = _b64(json.dumps(header, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{head}.{body}.{_sign(head + '.' + body)}"


def decode_token(token):
    """Return the claims dict, or None if the token is invalid or expired."""
    try:
        head, body, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(head + "." + body)):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
