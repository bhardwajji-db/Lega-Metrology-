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


import ipaddress
from config import settings


def _is_valid_ip(ip_str: str) -> bool:
    """Validate whether string is a valid IPv4 or IPv6 address."""
    if not ip_str or not isinstance(ip_str, str):
        return False
    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except ValueError:
        return False


def is_trusted_proxy(client_host: str) -> bool:
    """Check whether client_host matches any configured trusted proxy IP, hostname, or subnet."""
    if not client_host:
        return False

    host_clean = client_host.strip().lower()

    trusted_list = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1", "localhost", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])
    if isinstance(trusted_list, str):
        trusted_list = [p.strip() for p in trusted_list.split(",") if p.strip()]

    for item in trusted_list:
        item_clean = item.strip().lower()
        if host_clean == item_clean:
            return True
        try:
            net = ipaddress.ip_network(item_clean, strict=False)
            addr = ipaddress.ip_address(host_clean)
            if addr in net:
                return True
        except ValueError:
            pass

    return False


def get_client_ip(request) -> str:
    """Extract client IP safely from request or trusted proxy headers.

    Security Policy:
    - If the request is direct from an untrusted peer, forwarding headers (X-Forwarded-For, X-Real-IP)
      are strictly ignored to prevent attacker-controlled rate-limit spoofing or bypass.
    - If the request arrives from a verified trusted reverse proxy (e.g., Nginx):
      1. X-Real-IP is prioritized (overwritten by Nginx using $remote_addr).
      2. If X-Real-IP is missing, the rightmost valid IP in X-Forwarded-For is extracted.
    - If headers are invalid, malformed, or missing, falls back to the direct peer socket IP.
    """
    if not request:
        return "127.0.0.1"

    peer_ip = "127.0.0.1"
    if hasattr(request, "client") and request.client and request.client.host:
        peer_ip = request.client.host.strip()

    # If connection does not originate from a trusted reverse proxy,
    # reject all forwarding headers to prevent attacker spoofing.
    if not is_trusted_proxy(peer_ip):
        return peer_ip

    headers = getattr(request, "headers", None)
    if not headers:
        return peer_ip

    # 1. Prefer X-Real-IP (sanitized/overwritten by Nginx)
    real_ip = headers.get("x-real-ip")
    if real_ip:
        candidate = real_ip.strip()
        if _is_valid_ip(candidate):
            return candidate

    # 2. Fallback to X-Forwarded-For (inspect rightmost valid IP added by trusted proxy)
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        for candidate in reversed(ips):
            if _is_valid_ip(candidate):
                return candidate

    return peer_ip


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


# ── Analysis & Expensive Operations Rate Limiting (Section 15 & SEC-AUD-06) ──
ANALYSIS_IP_MAX = 60
ANALYSIS_WINDOW_SEC = 60

OCR_IP_MAX = 40
OCR_WINDOW_SEC = 60

REGISTER_IP_MAX = 10
REGISTER_WINDOW_SEC = 300


def check_analysis_rate_limit(client_ip: str) -> Tuple[bool, str]:
    """Protects expensive deep-learning analysis from abuse."""
    key = f"analysis_ip:{client_ip}"
    if not _rate_limiter.is_allowed(key, ANALYSIS_IP_MAX, ANALYSIS_WINDOW_SEC):
        return False, "Rate limit exceeded for product analyses. Please wait a minute before submitting more requests."
    _rate_limiter.record_attempt(key, ANALYSIS_WINDOW_SEC)
    return True, ""


def check_ocr_rate_limit(client_ip: str) -> Tuple[bool, str]:
    """Protects raw OCR endpoint from compute exhaustion."""
    key = f"ocr_ip:{client_ip}"
    if not _rate_limiter.is_allowed(key, OCR_IP_MAX, OCR_WINDOW_SEC):
        return False, "Rate limit exceeded for OCR extraction. Please wait a minute."
    _rate_limiter.record_attempt(key, OCR_WINDOW_SEC)
    return True, ""


def check_register_rate_limit(client_ip: str) -> Tuple[bool, str]:
    """Protects registration endpoint from automated abuse and PBKDF2 compute exhaustion."""
    key = f"register_ip:{client_ip}"
    if not _rate_limiter.is_allowed(key, REGISTER_IP_MAX, REGISTER_WINDOW_SEC):
        return False, "Too many registration attempts from this IP address. Please wait 5 minutes before trying again."
    _rate_limiter.record_attempt(key, REGISTER_WINDOW_SEC)
    return True, ""

