"""Account service: email+password auth with PBKDF2 hashing and sessions.

Password hashing uses stdlib ``hashlib.pbkdf2_hmac`` (SHA-256, 600k
iterations, per-user salt). Upgrade path: swap ``hash_password`` /
``verify_password`` for argon2-cffi — the stored format keeps an
algorithm tag so migration is possible (see PRODUCTION.md).

Session tokens are 256-bit secrets; only their SHA-256 is stored.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time

from .db import Database, sha256_hex

ALGORITHM = "pbkdf2-sha256"
ITERATIONS = 600_000
MIN_PASSWORD_LEN = 12
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> tuple[str, str]:
    """Return (salt_b64, stored_hash). Stored format: ``algo$iterations$salt$hash``."""
    salt = secrets.token_bytes(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode()
    hash_b64 = base64.b64encode(dk).decode()
    return salt_b64, f"{ALGORITHM}${ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, salt_b64: str, stored: str) -> bool:
    try:
        algo, iters, salt_stored, hash_b64 = stored.split("$", 3)
        if algo != ALGORITHM or salt_stored != salt_b64:
            return False
        salt = base64.b64decode(salt_stored)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(base64.b64encode(dk).decode(), hash_b64)
    except Exception:
        return False


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


class AccountError(Exception):
    pass


def signup(db: Database, email: str, password: str, display_name: str = "") -> dict:
    email = email.strip()
    if not validate_email(email):
        raise AccountError("invalid email address")
    if len(password) < MIN_PASSWORD_LEN:
        raise AccountError(f"password must be at least {MIN_PASSWORD_LEN} characters")
    if db.get_user_by_email(email):
        # Same message as bad-credential login: do not reveal which emails exist.
        raise AccountError("invalid email or password")
    salt, stored = hash_password(password)
    user_id = db.create_user(email, salt, stored, display_name.strip()[:80])
    return {"id": user_id, "email": email.lower(), "display_name": display_name.strip()[:80]}


def login(db: Database, email: str, password: str, session_ttl: int,
          device_label: str = "") -> tuple[dict, str]:
    """Return (user_dict, session_token). Raises AccountError on failure.

    The failure message is deliberately identical for unknown email and
    wrong password (no user enumeration).
    """
    row = db.get_user_by_email(email)
    ok = bool(row) and verify_password(password, row["password_salt"], row["password_hash"])
    if not ok:
        # Constant-time-ish: still hash even when the user is missing so
        # timing doesn't leak existence.
        hash_password(secrets.token_hex(16))
        raise AccountError("invalid email or password")
    token = secrets.token_urlsafe(48)
    db.create_session(sha256_hex(token), row["id"], device_label[:80],
                      int(time.time()) + session_ttl)
    user = {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}
    return user, token


def get_user_from_token(db: Database, token: str):
    """Return the user row for a session token, or None."""
    if not token:
        return None
    row = db.get_session(sha256_hex(token))
    if not row or row["expires_at"] < int(time.time()):
        return None
    return db.get_user(row["user_id"])


def logout(db: Database, token: str) -> None:
    db.delete_session(sha256_hex(token))


def change_password(db: Database, user_id: int, current_password: str, new_password: str) -> None:
    row = db.get_user(user_id)
    if not row or not verify_password(current_password, row["password_salt"], row["password_hash"]):
        raise AccountError("current password is incorrect")
    if len(new_password) < MIN_PASSWORD_LEN:
        raise AccountError(f"password must be at least {MIN_PASSWORD_LEN} characters")
    salt, stored = hash_password(new_password)
    db.set_password(user_id, salt, stored)
