"""Server-assisted device pairing for cross-device handoff.

The server is *signaling only*: it brokers short pairing codes so two
devices can find each other, then the actual handoff payload travels
device-to-device via the existing P2P ``core/handoff.py`` flow (which
verifies the payload contains no credentials and requires explicit
accept on the receiving device).

The server NEVER stores conversation content, memory, or credentials
here — only pairing metadata (ids, device names, short endpoint hints).

Flow:
  1. Owner device:  POST /v1/pairing/create      -> {pairing_id, code}
  2. New device:    POST /v1/pairing/claim {code} -> {pairing_id, claim_receipt}
  3. Owner polls:   GET  /v1/pairing/{id}/status  -> pending|claimed|accepted|rejected
  4. Owner:         POST /v1/pairing/{id}/accept {endpoint_hint}
                    (or .../reject)
  5. New device polls its status with the claim_receipt and receives a
     one-time accept token + endpoint hint, then performs the direct
     P2P handoff itself.
"""

from __future__ import annotations

import secrets
import string
import time

from .db import Database, new_id, sha256_hex

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # unambiguous, no 0/O/1/I/L
CODE_PREFIX = "CORT"
MAX_ATTEMPTS = 5


class PairingError(Exception):
    pass


def _make_code() -> str:
    return CODE_PREFIX + "-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def create_pairing(db: Database, user_id: int, owner_device: str, ttl: int) -> dict:
    db.purge_expired_pairings()
    for _ in range(5):  # retry on (astronomically unlikely) code collision
        code = _make_code()
        if db.get_pairing_by_code_hash(sha256_hex(code)):
            continue
        pairing_id = new_id("pair_")
        db.create_pairing(pairing_id, sha256_hex(code), user_id,
                          owner_device[:80], int(time.time()) + ttl)
        return {"pairing_id": pairing_id, "code": code, "expires_in": ttl}
    raise PairingError("could not generate a unique pairing code")


def _live_pairing(db: Database, pairing_id: str, user_id: int | None = None):
    db.purge_expired_pairings()
    row = db.get_pairing(pairing_id)
    if not row:
        raise PairingError("pairing not found or expired")
    if user_id is not None and row["user_id"] != user_id:
        raise PairingError("pairing not found or expired")
    return row


def claim_pairing(db: Database, code: str, device_name: str) -> dict:
    db.purge_expired_pairings()
    row = db.get_pairing_by_code_hash(sha256_hex(code.strip().upper()))
    if not row:
        raise PairingError("invalid or expired pairing code")
    if row["attempts"] >= MAX_ATTEMPTS:
        db.delete_pairing(row["id"])
        raise PairingError("pairing locked after too many attempts")
    if row["status"] != "pending":
        raise PairingError("pairing code already used")
    receipt = secrets.token_urlsafe(32)
    db.update_pairing(row["id"], status="claimed",
                      claim_device=device_name[:80],
                      claim_receipt=sha256_hex(receipt))
    return {"pairing_id": row["id"], "claim_receipt": receipt, "status": "claimed"}


def record_attempt(db: Database, code: str) -> None:
    row = db.get_pairing_by_code_hash(sha256_hex(code.strip().upper()))
    if row:
        db.update_pairing(row["id"], attempts=row["attempts"] + 1)


def owner_status(db: Database, pairing_id: str, user_id: int) -> dict:
    row = _live_pairing(db, pairing_id, user_id)
    return {
        "pairing_id": row["id"],
        "status": row["status"],
        "claim_device": row["claim_device"],
        "expires_in": max(0, row["expires_at"] - int(time.time())),
    }


def claimer_status(db: Database, pairing_id: str, claim_receipt: str) -> dict:
    row = _live_pairing(db, pairing_id)
    if not claim_receipt or not secrets.compare_digest(
            sha256_hex(claim_receipt), row["claim_receipt"]):
        raise PairingError("invalid claim receipt")
    out = {"pairing_id": row["id"], "status": row["status"]}
    if row["status"] == "accepted":
        # One-time accept token: the claiming device exchanges it for the
        # endpoint hint, then it is burned.
        token = secrets.token_urlsafe(32)
        db.update_pairing(row["id"], accept_token_hash=sha256_hex(token),
                          status="consumed")
        out["accept_token"] = token
        out["endpoint_hint"] = row["endpoint_hint"]
    return out


def accept_pairing(db: Database, pairing_id: str, user_id: int, endpoint_hint: str) -> dict:
    row = _live_pairing(db, pairing_id, user_id)
    if row["status"] not in ("pending", "claimed"):
        raise PairingError(f"cannot accept pairing in status '{row['status']}'")
    db.update_pairing(pairing_id, status="accepted",
                      endpoint_hint=endpoint_hint[:256])
    return {"pairing_id": pairing_id, "status": "accepted"}


def reject_pairing(db: Database, pairing_id: str, user_id: int) -> dict:
    row = _live_pairing(db, pairing_id, user_id)
    if row["status"] not in ("pending", "claimed"):
        raise PairingError(f"cannot reject pairing in status '{row['status']}'")
    db.update_pairing(pairing_id, status="rejected")
    return {"pairing_id": pairing_id, "status": "rejected"}
