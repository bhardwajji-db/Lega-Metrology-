"""MetrCheck AI — In-Memory Rate Limiting for Authentication & Password Recovery.

Features:
- Thread-safe sliding-window rate limiting (process-local, designed for prototype/single-instance server).
- IP-based and identifier-based throttling.
- Generic error messages to prevent account enumeration.
- Easy testing hooks (clear_all / reset).
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List, Tuple


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter for login & password reset protection."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_attempts: int, window_sec: int) -> bool:
        """Check if request is within allowed rate limits without recording an attempt."""
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            timestamps = self._records[key]
            # Prune old timestamps
            self._records[key] = [t for t in timestamps if t > cutoff]
            return len(self._records[key]) < max_attempts

    def record_attempt(self, key: str, window_sec: int = 600) -> None:
        """Record an attempt for the given key."""
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            timestamps = self._records[key]
            timestamps.append(now)
            self._records[key] = [t for t in timestamps if t > cutoff]

    def reset(self, key: str) -> None:
        """Reset records for a specific key (e.g. upon successful login)."""
        with self._lock:
            if key in self._records:
                del self._records[key]

    def clear_all(self) -> None:
        """Clear all rate limit records (useful for test isolation)."""
        with self._lock:
            self._records.clear()


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


def get_client_ip(request) -> str:
    """Extract client IP safely from request or proxy headers."""
    if not request:
        return "127.0.0.1"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# ── Login Rate Limiting ──────────────────────────────────────────────────
# Default: 10 failed attempts per IP per 5 minutes, 5 failed attempts per username per 5 minutes
LOGIN_IP_MAX = 10
LOGIN_USER_MAX = 5
LOGIN_WINDOW_SEC = 300


def check_login_rate_limit(client_ip: str, username: str = "") -> Tuple[bool, str]:
    """Return (allowed, error_message). Does not leak whether username exists."""
    ip_key = f"login_fail_ip:{client_ip}"
    if not _rate_limiter.is_allowed(ip_key, LOGIN_IP_MAX, LOGIN_WINDOW_SEC):
        return False, "Too many failed login attempts. Please wait 5 minutes before trying again."

    if username:
        user_key = f"login_fail_user:{username.lower().strip()}"
        if not _rate_limiter.is_allowed(user_key, LOGIN_USER_MAX, LOGIN_WINDOW_SEC):
            return False, "Too many failed login attempts for this account. Please wait 5 minutes or reset your password."

    return True, ""


def record_login_failure(client_ip: str, username: str = "") -> None:
    ip_key = f"login_fail_ip:{client_ip}"
    _rate_limiter.record_attempt(ip_key, LOGIN_WINDOW_SEC)
    if username:
        user_key = f"login_fail_user:{username.lower().strip()}"
        _rate_limiter.record_attempt(user_key, LOGIN_WINDOW_SEC)


def record_login_success(client_ip: str, username: str = "") -> None:
    ip_key = f"login_fail_ip:{client_ip}"
    _rate_limiter.reset(ip_key)
    if username:
        user_key = f"login_fail_user:{username.lower().strip()}"
        _rate_limiter.reset(user_key)


# ── Password Recovery Rate Limiting ──────────────────────────────────────
# Default: 5 recovery requests per IP per 10 minutes, 3 per identifier per 10 minutes
RESET_IP_MAX = 5
RESET_ID_MAX = 3
RESET_WINDOW_SEC = 600


def check_forgot_password_rate_limit(client_ip: str, identifier: str = "") -> Tuple[bool, str]:
    """Return (allowed, error_message). Identical generic message for IP and identifier throttling."""
    ip_key = f"reset_req_ip:{client_ip}"
    if not _rate_limiter.is_allowed(ip_key, RESET_IP_MAX, RESET_WINDOW_SEC):
        return False, "Too many password recovery requests. Please wait a few minutes before trying again."

    if identifier:
        id_key = f"reset_req_id:{identifier.lower().strip()}"
        if not _rate_limiter.is_allowed(id_key, RESET_ID_MAX, RESET_WINDOW_SEC):
            return False, "Too many password recovery requests for this identifier. Please wait a few minutes before trying again."

    return True, ""


def record_forgot_password_attempt(client_ip: str, identifier: str = "") -> None:
    ip_key = f"reset_req_ip:{client_ip}"
    _rate_limiter.record_attempt(ip_key, RESET_WINDOW_SEC)
    if identifier:
        id_key = f"reset_req_id:{identifier.lower().strip()}"
        _rate_limiter.record_attempt(id_key, RESET_WINDOW_SEC)


def clear_rate_limits() -> None:
    """Helper to reset all rate limits during testing."""
    _rate_limiter.clear_all()
