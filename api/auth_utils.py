from __future__ import annotations
"""Password hashing and lightweight token helpers for app auth."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


PASSWORD_ITERATIONS = 260000


def hash_password(password: str, salt_hex: str | None = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with per-user salt."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify plaintext password against stored PBKDF2 hash representation."""
    try:
        algo, iterations_s, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_s),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(raw: str) -> bytes:
    pad_len = (-len(raw)) % 4
    return base64.urlsafe_b64decode(raw + ("=" * pad_len))


def _auth_secret() -> bytes:
    secret = os.getenv("AUTH_SECRET", "tradeiq_local_dev_change_me")
    return secret.encode("utf-8")


def issue_auth_token(*, user_id: int, username: str, email: str) -> str:
    """Issue signed auth token with expiration timestamp."""
    ttl_minutes = max(30, int(os.getenv("AUTH_TOKEN_TTL_MINUTES", "720")))
    payload = {
        "uid": int(user_id),
        "usr": str(username),
        "eml": str(email),
        "exp": int(time.time()) + ttl_minutes * 60,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64u_encode(payload_raw)
    signature = hmac.new(_auth_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64u_encode(signature)}"


def decode_auth_token(token: str) -> dict[str, Any] | None:
    """Validate signed auth token and return payload when valid."""
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        return None

    try:
        expected_sig = hmac.new(_auth_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
        got_sig = _b64u_decode(signature_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected_sig, got_sig):
        return None

    try:
        payload = json.loads(_b64u_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        return None
    return payload
