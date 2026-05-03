import hashlib
import hmac
import os
import time
from urllib.parse import urlencode


def _secret() -> str:
    return os.getenv("SSO_SHARED_SECRET", "change-me-sso-secret")


def build_signature(username: str, role: str, employee_id: str, issued_at: int) -> str:
    payload = f"{username}|{role}|{employee_id}|{issued_at}"
    return hmac.new(_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def build_sso_query(username: str, role: str, employee_id: str, ttl_seconds: int = 3600) -> str:
    issued_at = int(time.time())
    sig = build_signature(username, role, employee_id, issued_at)
    return urlencode(
        {
            "user": username,
            "role": role,
            "employee_id": employee_id,
            "ts": issued_at,
            "sig": sig,
            "ttl": ttl_seconds,
        }
    )


def verify_sso_payload(username: str, role: str, employee_id: str, issued_at: int, signature: str, ttl_seconds: int = 3600) -> bool:
    if abs(int(time.time()) - int(issued_at)) > int(ttl_seconds):
        return False
    expected = build_signature(username, role, employee_id, int(issued_at))
    return hmac.compare_digest(signature, expected)

