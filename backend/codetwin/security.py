"""Password hashing, signed session tokens and login throttling."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()   # Argon2id with the library's recommended parameters

# A real hash to verify against when the email is unknown, so a missing account
# takes as long to reject as a wrong password.
_DUMMY_HASH = _hasher.hash("codetwin-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: int, role: str, secret: str, minutes: int) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expires, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, secret, algorithm="HS256"), expires


def decode_token(token: str, secret: str) -> dict:
    """Raises jwt.PyJWTError when the token is invalid, expired or revoked."""
    payload = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub", "jti"]})
    if _revoked.contains(payload["jti"]):
        raise jwt.InvalidTokenError("token revoked")
    return payload


class _RevokedTokens:
    """Token IDs ended by logout, kept until they would have expired anyway.

    Held in process memory: with several API instances, use a shared store
    such as Azure Cache for Redis instead.
    """

    def __init__(self):
        self._items: dict[str, float] = {}
        self._lock = threading.Lock()

    def add(self, jti: str, exp: float) -> None:
        with self._lock:
            now = time.time()
            self._items = {k: v for k, v in self._items.items() if v > now}
            self._items[jti] = exp

    def contains(self, jti: str) -> bool:
        with self._lock:
            return jti in self._items


_revoked = _RevokedTokens()


def revoke_token(payload: dict) -> None:
    _revoked.add(payload["jti"], float(payload["exp"]))


class LoginThrottle:
    """Temporary lockout after repeated failed logins for one email."""

    def __init__(self, max_failures: int, lockout_seconds: int):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: str) -> bool:
        with self._lock:
            recent = [t for t in self._failures.get(key, []) if t > time.time() - self.lockout_seconds]
            self._failures[key] = recent
            return len(recent) >= self.max_failures

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(time.time())

    def succeed(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
