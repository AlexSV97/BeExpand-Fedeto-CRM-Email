from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any


class JWTError(Exception):
    pass


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def encode(payload: dict[str, Any], secret_key: str, algorithm: str = "HS256") -> str:
    if algorithm != "HS256":
        raise JWTError(f"Unsupported algorithm: {algorithm}")

    header = {"alg": algorithm, "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), default=_json_default).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _b64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode(token: str, secret_key: str, algorithms: list[str] | None = None) -> dict[str, Any]:
    allowed = algorithms or ["HS256"]
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise JWTError("Not enough segments") from exc

    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except Exception as exc:
        raise JWTError("Invalid token encoding") from exc

    algorithm = header.get("alg")
    if algorithm not in allowed:
        raise JWTError("Algorithm not allowed")
    if algorithm != "HS256":
        raise JWTError(f"Unsupported algorithm: {algorithm}")

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    expected_segment = _b64url_encode(expected_signature)
    if not hmac.compare_digest(expected_segment, signature_segment):
        raise JWTError("Signature verification failed")

    exp = payload.get("exp")
    if exp is not None:
        exp_ts = float(exp)
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts >= exp_ts:
            raise JWTError("Token expired")

    return payload
