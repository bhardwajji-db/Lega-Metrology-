"""
Unit and Integration Tests for SEC-AUD-06 — Rate Limiting on AI/OCR and Registration Endpoints.

Vulnerability Reference: SEC-AUD-06
Components Under Test:
  - backend/auth/ratelimit.py: check_analysis_rate_limit, check_ocr_rate_limit, check_register_rate_limit
  - API Endpoints:
      * POST /api/analyze
      * POST /api/analyze/text
      * POST /api/ocr
      * POST /api/auth/register

Security Requirements:
1. Compute-heavy image analysis (POST /api/analyze) is rate-limited per IP (429 on exhaustion).
2. Compute-heavy text analysis (POST /api/analyze/text) is rate-limited per IP (429 on exhaustion).
3. Compute-heavy raw OCR extraction (POST /api/ocr) is rate-limited per IP (429 on exhaustion).
4. Compute-heavy user registration (POST /api/auth/register) is rate-limited per IP to prevent PBKDF2 DoS (429 on exhaustion).
5. Rate limits are IP-scoped and do not block other legitimate clients.
6. Resetting rate limits restores allowance.
"""

import io
import os
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import init_db
from auth.ratelimit import (
    clear_rate_limits,
    ANALYSIS_IP_MAX,
    OCR_IP_MAX,
    REGISTER_IP_MAX,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


def _create_dummy_image_bytes() -> bytes:
    img = Image.new("RGB", (60, 30), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def setup_env():
    _ensure_test_isolation()
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.mark.asyncio
async def test_01_analyze_endpoint_rate_limits_after_threshold():
    """POST /api/analyze returns 429 Too Many Requests when ANALYSIS_IP_MAX is exceeded."""
    await init_db()
    client = TestClient(app)
    img_bytes = _create_dummy_image_bytes()

    # Exhaust analysis rate limit for default test client IP
    for i in range(ANALYSIS_IP_MAX):
        # We supply an invalid file parameter to trigger fast return if rate limit check precedes it
        # But here rate limit check is right at the start of the endpoint before heavy processing
        resp = client.post(
            "/api/analyze",
            files={"file": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code != 429, f"Request {i+1} was unexpectedly throttled"

    # Request ANALYSIS_IP_MAX + 1 must receive HTTP 429
    throttled = client.post(
        "/api/analyze",
        files={"file": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    )
    assert throttled.status_code == 429
    assert "rate limit exceeded" in throttled.json()["detail"].lower()


@pytest.mark.asyncio
async def test_02_analyze_text_endpoint_rate_limits():
    """POST /api/analyze/text returns 429 when rate limit is exhausted."""
    await init_db()
    client = TestClient(app)

    for i in range(ANALYSIS_IP_MAX):
        resp = client.post("/api/analyze/text", json={"text": "Net Wt 500g MRP 250"})
        assert resp.status_code != 429, f"Text request {i+1} was unexpectedly throttled"

    throttled = client.post("/api/analyze/text", json={"text": "Net Wt 500g MRP 250"})
    assert throttled.status_code == 429
    assert "rate limit exceeded" in throttled.json()["detail"].lower()


@pytest.mark.asyncio
async def test_03_ocr_endpoint_rate_limits_after_threshold():
    """POST /api/ocr returns 429 Too Many Requests when OCR_IP_MAX is exceeded."""
    await init_db()
    client = TestClient(app)
    img_bytes = _create_dummy_image_bytes()

    for i in range(OCR_IP_MAX):
        resp = client.post(
            "/api/ocr",
            files={"file": ("ocr_test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
        )
        assert resp.status_code != 429, f"OCR request {i+1} was unexpectedly throttled"

    throttled = client.post(
        "/api/ocr",
        files={"file": ("ocr_test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    )
    assert throttled.status_code == 429
    assert "rate limit exceeded" in throttled.json()["detail"].lower()


@pytest.mark.asyncio
async def test_04_register_endpoint_rate_limits_after_threshold():
    """POST /api/auth/register returns 429 Too Many Requests when REGISTER_IP_MAX is exceeded."""
    await init_db()
    client = TestClient(app)

    for i in range(REGISTER_IP_MAX):
        u = f"reg_user_{i}_{os.urandom(3).hex()}"
        resp = client.post(
            "/api/auth/register",
            json={
                "username": u,
                "email": f"{u}@merchant.com",
                "password": "SecurePassword123!",
                "full_name": f"Merchant {u}",
                "organization_name": f"Org {u}",
            }
        )
        assert resp.status_code in (200, 201), f"Registration {i+1} failed with {resp.status_code}: {resp.text}"

    # REGISTER_IP_MAX + 1 must be throttled with HTTP 429
    u_blocked = f"reg_blocked_{os.urandom(3).hex()}"
    throttled = client.post(
        "/api/auth/register",
        json={
            "username": u_blocked,
            "email": f"{u_blocked}@merchant.com",
            "password": "SecurePassword123!",
            "full_name": "Blocked Merchant",
            "organization_name": "Blocked Corp",
        }
    )
    assert throttled.status_code == 429
    assert "too many registration attempts" in throttled.json()["detail"].lower()


@pytest.mark.asyncio
async def test_05_clear_rate_limits_restores_allowance():
    """Calling clear_rate_limits() immediately unblocks throttled endpoints."""
    await init_db()
    client = TestClient(app)

    # Exhaust registration rate limits
    for i in range(REGISTER_IP_MAX):
        u = f"reg_rst_{i}_{os.urandom(3).hex()}"
        client.post(
            "/api/auth/register",
            json={
                "username": u,
                "email": f"{u}@merchant.com",
                "password": "SecurePassword123!",
            }
        )

    # Throttled
    throttled = client.post(
        "/api/auth/register",
        json={
            "username": "will_fail",
            "email": "will_fail@merchant.com",
            "password": "SecurePassword123!",
        }
    )
    assert throttled.status_code == 429

    # Reset
    clear_rate_limits()

    # Now allowed
    u_after = f"reg_allowed_{os.urandom(3).hex()}"
    restored = client.post(
        "/api/auth/register",
        json={
            "username": u_after,
            "email": f"{u_after}@merchant.com",
            "password": "SecurePassword123!",
        }
    )
    assert restored.status_code in (200, 201)
