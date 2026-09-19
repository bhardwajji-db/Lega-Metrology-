"""
Unit and Integration Tests for SEC-AUD-03 — Rate Limit IP Spoofing Prevention & Trust Boundary Hardening.

Vulnerability Reference: SEC-AUD-03
Components Under Test:
  - backend/auth/ratelimit.py: get_client_ip, is_trusted_proxy
  - backend/config.py: Settings.TRUSTED_PROXIES
  - frontend/nginx.conf: proxy_set_header X-Real-IP / X-Forwarded-For
  - docker-compose.yml: backend network expose vs ports configuration
  - API Endpoints: /api/auth/login, /api/auth/forgot-password

Security Requirements:
1. Direct untrusted connections cannot bypass IP-based rate limiting via spoofed X-Forwarded-For or X-Real-IP headers.
2. Legitimate client IP is faithfully extracted when requests arrive through a verified trusted reverse proxy (Nginx).
3. Untrusted private-network peers (RFC 1918) cannot spoof forwarded headers.
4. Malformed, empty, or whitespace-only proxy headers safely fall back to the connection socket IP.
5. An attacker rotating X-Forwarded-For headers over a direct socket connection is throttled after the configured threshold.
6. Production docker-compose does not expose backend port 8000 publicly.
7. Settings.TRUSTED_PROXIES supports list, string, and JSON configurations.
"""

import os
import pytest
from starlette.datastructures import Headers, Address
from starlette.requests import Request
from fastapi.testclient import TestClient

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from auth.ratelimit import (
    get_client_ip,
    is_trusted_proxy,
    clear_rate_limits,
    check_login_rate_limit,
    record_login_failure,
    LOGIN_IP_MAX,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


class MockRequest:
    """Mock Starlette Request for unit testing get_client_ip with various topologies."""
    def __init__(self, client_host: str = "127.0.0.1", headers_dict: dict = None):
        self.client = Address(client_host, 50000) if client_host else None
        self.headers = Headers(headers_dict or {})


@pytest.fixture(autouse=True)
def clean_limits_fixture():
    _ensure_test_isolation()
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ═════════════════════════════════════════════════════════════════════════════
# 1. DIRECT UNTRUSTED CONNECTION CHECKS (PUBLIC & PRIVATE)
# ═════════════════════════════════════════════════════════════════════════════

def test_01_direct_request_uses_actual_socket_ip():
    """Direct request without forwarding headers uses actual connection address."""
    req = MockRequest(client_host="198.51.100.25")
    ip = get_client_ip(req)
    assert ip == "198.51.100.25"


def test_02_direct_request_ignores_spoofed_x_forwarded_for():
    """Attacker connecting directly cannot spoof IP using X-Forwarded-For."""
    req = MockRequest(
        client_host="198.51.100.25",
        headers_dict={"x-forwarded-for": "1.2.3.4"}
    )
    ip = get_client_ip(req)
    assert ip == "198.51.100.25", f"Expected socket IP 198.51.100.25, but header was trusted: {ip}"


def test_03_direct_request_ignores_spoofed_x_real_ip():
    """Attacker connecting directly cannot spoof IP using X-Real-IP."""
    req = MockRequest(
        client_host="198.51.100.25",
        headers_dict={"x-real-ip": "1.2.3.4"}
    )
    ip = get_client_ip(req)
    assert ip == "198.51.100.25", f"Expected socket IP 198.51.100.25, but header was trusted: {ip}"


def test_04_direct_request_ignores_multiple_spoofed_headers():
    """Attacker providing both X-Forwarded-For and X-Real-IP directly has all headers ignored."""
    req = MockRequest(
        client_host="198.51.100.25",
        headers_dict={
            "x-forwarded-for": "10.0.0.1, 10.0.0.2, 8.8.8.8",
            "x-real-ip": "9.9.9.9",
        }
    )
    ip = get_client_ip(req)
    assert ip == "198.51.100.25"


def test_05_untrusted_private_network_peer_cannot_spoof():
    """Private network peer not in TRUSTED_PROXIES cannot spoof X-Real-IP or X-Forwarded-For."""
    untrusted_private_ips = ["10.50.1.20", "192.168.10.5", "172.28.0.40"]
    for priv_ip in untrusted_private_ips:
        req = MockRequest(
            client_host=priv_ip,
            headers_dict={"x-real-ip": "1.1.1.1", "x-forwarded-for": "2.2.2.2"}
        )
        assert get_client_ip(req) == priv_ip, f"Private IP {priv_ip} must not be blindly trusted as a proxy"


# ═════════════════════════════════════════════════════════════════════════════
# 2. LEGITIMATE TRUSTED PROXY TOPOLOGY CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def test_06_trusted_proxy_x_real_ip_extracted():
    """When request arrives from trusted proxy (127.0.0.1), X-Real-IP set by Nginx is used."""
    req = MockRequest(
        client_host="127.0.0.1",
        headers_dict={"x-real-ip": "203.0.113.195"}
    )
    ip = get_client_ip(req)
    assert ip == "203.0.113.195"


def test_07_trusted_proxy_x_forwarded_for_fallback():
    """When X-Real-IP is absent, trusted proxy X-Forwarded-For rightmost IP is extracted."""
    req = MockRequest(
        client_host="127.0.0.1",
        headers_dict={"x-forwarded-for": "198.51.100.88"}
    )
    ip = get_client_ip(req)
    assert ip == "198.51.100.88"


def test_08_trusted_proxy_multiple_x_forwarded_for_extracts_rightmost():
    """When multiple X-Forwarded-For IPs exist, rightmost valid IP is chosen."""
    req = MockRequest(
        client_host="127.0.0.1",
        headers_dict={"x-forwarded-for": "1.1.1.1, 2.2.2.2, 203.0.113.50"}
    )
    ip = get_client_ip(req)
    assert ip == "203.0.113.50"


# ═════════════════════════════════════════════════════════════════════════════
# 3. MALFORMED / INVALID / EDGE-CASE HEADER CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def test_09_trusted_proxy_empty_headers_falls_back_to_socket():
    """Empty or blank headers safely fall back to the proxy socket IP."""
    req_empty = MockRequest(client_host="127.0.0.1", headers_dict={"x-real-ip": "", "x-forwarded-for": ""})
    assert get_client_ip(req_empty) == "127.0.0.1"

    req_spaces = MockRequest(client_host="127.0.0.1", headers_dict={"x-real-ip": "   ", "x-forwarded-for": "  ,  "})
    assert get_client_ip(req_spaces) == "127.0.0.1"


def test_10_trusted_proxy_malformed_ip_falls_back():
    """Malformed non-IP values safely fall back to peer socket IP."""
    req_malformed = MockRequest(
        client_host="127.0.0.1",
        headers_dict={"x-real-ip": "not-an-ip-address", "x-forwarded-for": "<script>alert(1)</script>"}
    )
    assert get_client_ip(req_malformed) == "127.0.0.1"


def test_11_none_request_falls_back_safely():
    """Passing None to get_client_ip returns 127.0.0.1."""
    assert get_client_ip(None) == "127.0.0.1"


# ═════════════════════════════════════════════════════════════════════════════
# 4. RATE LIMIT BYPASS ATTEMPT REGRESSION
# ═════════════════════════════════════════════════════════════════════════════

def test_12_attacker_rotating_x_forwarded_for_is_throttled():
    """Demonstrate that an attacker rotating X-Forwarded-For cannot bypass login rate limiting."""
    clear_rate_limits()
    attacker_ip = "198.51.100.99"

    # Simulate 10 failed login attempts with 10 different spoofed X-Forwarded-For headers
    for i in range(LOGIN_IP_MAX):
        req = MockRequest(
            client_host=attacker_ip,
            headers_dict={"x-forwarded-for": f"10.0.0.{i+1}"}
        )
        resolved_ip = get_client_ip(req)
        assert resolved_ip == attacker_ip, "Attacker spoofed IP must NOT be accepted"
        record_login_failure(resolved_ip)

    # 11th attempt from the attacker (even with a brand new fake IP) must be throttled
    req_11 = MockRequest(
        client_host=attacker_ip,
        headers_dict={"x-forwarded-for": "10.0.0.99"}
    )
    resolved_ip_11 = get_client_ip(req_11)
    allowed, msg = check_login_rate_limit(resolved_ip_11)
    assert not allowed, "Attacker must be blocked by rate limiter despite rotating X-Forwarded-For"
    assert "Too many failed login attempts" in msg


# ═════════════════════════════════════════════════════════════════════════════
# 5. ENDPOINT INTEGRATION & REGRESSION (LOGIN & FORGOT PASSWORD)
# ═════════════════════════════════════════════════════════════════════════════

def test_13_login_endpoint_rate_limits_direct_attacker(client):
    """Direct attacker sending spoofed headers to /api/auth/login is throttled."""
    clear_rate_limits()

    # 10 failed login attempts with rotating spoofed headers
    for i in range(10):
        resp = client.post(
            "/api/auth/login",
            json={"username": f"nonexistent_user_{i}", "password": "WrongPassword123!"},
            headers={"X-Forwarded-For": f"203.0.113.{i+1}"}
        )
        assert resp.status_code == 401

    # 11th attempt must be throttled with HTTP 429
    throttled = client.post(
        "/api/auth/login",
        json={"username": "another_user", "password": "WrongPassword123!"},
        headers={"X-Forwarded-For": "203.0.113.99"}
    )
    assert throttled.status_code == 429
    assert "Too many failed login attempts" in throttled.json()["detail"]


def test_14_forgot_password_rate_limits_direct_attacker(client):
    """Direct attacker sending spoofed headers to /api/auth/forgot-password is throttled."""
    clear_rate_limits()

    # 5 forgot password requests from the same direct client with spoofed headers
    for i in range(5):
        resp = client.post(
            "/api/auth/forgot-password",
            json={"identifier": f"merchant_{i}@test.gov.in"},
            headers={"X-Forwarded-For": f"198.51.100.{i+1}"}
        )
        assert resp.status_code == 200

    # 6th attempt must be throttled with HTTP 429
    throttled = client.post(
        "/api/auth/forgot-password",
        json={"identifier": "fresh_identifier@test.gov.in"},
        headers={"X-Forwarded-For": "198.51.100.99"}
    )
    assert throttled.status_code == 429
    assert "Too many password recovery requests" in throttled.json()["detail"]


# ═════════════════════════════════════════════════════════════════════════════
# 6. CONFIGURATION & INFRASTRUCTURE INTEGRITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_15_nginx_configuration_sanitizes_headers():
    """Verify frontend/nginx.conf explicitly sets X-Real-IP and X-Forwarded-For to $remote_addr."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    nginx_conf_path = os.path.join(base_dir, "frontend", "nginx.conf")
    assert os.path.exists(nginx_conf_path), f"nginx.conf not found at {nginx_conf_path}"

    with open(nginx_conf_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "proxy_set_header X-Real-IP $remote_addr;" in content
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in content
    assert "$proxy_add_x_forwarded_for" not in content, "Client-provided X-Forwarded-For must not be chained"


def test_16_docker_compose_does_not_publish_backend_port_8000():
    """Verify docker-compose.yml uses expose instead of publishing backend:8000 on the host."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    compose_path = os.path.join(base_dir, "docker-compose.yml")
    assert os.path.exists(compose_path), f"docker-compose.yml not found at {compose_path}"

    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Backend section must not have '8000:8000' in ports
    assert '"8000:8000"' not in content and "'8000:8000'" not in content
    assert "expose:" in content
    assert "- \"8000\"" in content or "- '8000'" in content or "- 8000" in content


def test_17_trusted_proxies_settings_parsing():
    """Verify TRUSTED_PROXIES parser handles list, comma-separated string, and JSON formats."""
    from config import Settings
    
    # Comma-separated string
    s1 = Settings(TRUSTED_PROXIES="127.0.0.1, 10.0.0.1")
    assert "127.0.0.1" in s1.TRUSTED_PROXIES
    assert "10.0.0.1" in s1.TRUSTED_PROXIES

    # JSON list string
    s2 = Settings(TRUSTED_PROXIES='["127.0.0.1", "192.168.1.0/24"]')
    assert "127.0.0.1" in s2.TRUSTED_PROXIES
    assert "192.168.1.0/24" in s2.TRUSTED_PROXIES
