from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ITERATIONS = 210_000
_SALT_BYTES = 16
_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_PREFIX}${_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        prefix, iterations, salt_b64, digest_b64 = encoded.split("$")
    except ValueError:
        return False
    if prefix != _PREFIX:
        return False
    try:
        iterations_int = int(iterations)
        salt = _decode(salt_b64)
        expected = _decode(digest_b64)
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations_int)
    return hmac.compare_digest(actual, expected)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))
