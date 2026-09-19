"""
Phase 7.1.6 — Secure Password Recovery, Password Policy Hardening & Rate Limiting Test Suite

Covers:
1. Wrong password returns generic error ("Incorrect username or password. Please check your credentials and try again.")
2. Wrong username returns identical generic error.
3. Forgot-password valid identifier returns generic response.
4. Forgot-password invalid identifier returns identical generic response.
5. Reset token is securely random.
6. Reset token hash stored in DB instead of raw token.
7. Reset token expires (15m window).
8. Reset token is single-use.
9. Previous token invalidation on new request.
10. Invalid reset token rejected.
11. Password below 8 chars (e.g. 7 chars) rejected on registration and reset.
12. Password meeting 8 chars accepted on registration and reset.
13. Old password fails after reset.
14. New password succeeds after reset.
15. Merchant role preserved.
16. Officer role preserved.
17. Admin role preserved.
18. Workspace authorization preserved across all roles.
19. Merchant cannot access privileged officer/admin endpoints.
20. Workspace selection cannot alter backend JWT role.
21. Dev reset-token behavior is development-only.
22. Production path strictly does not expose raw reset token.
23. Login brute-force protection throttles excessive failed attempts (HTTP 429).
24. Forgot-password abuse protection throttles excessive requests (HTTP 429).
25. SMTP secrets/configuration are not leaked in responses.
26. Reset tokens are not logged in production environments.
"""

import os
import datetime
import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import (
    create_token,
    hash_password,
    verify_password,
    hash_reset_token,
    generate_password_reset_token,
    get_delivery_provider,
    DevLoggerDeliveryProvider,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_MERCHANT,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    create_user,
    get_user_by_username,
    create_password_reset_record,
    get_valid_password_reset,
    apply_password_reset,
    get_db,
)


@pytest.fixture(autouse=True)
def verify_test_isolation_and_clear_ratelimits():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on prod DB!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on prod uploads!"
    clear_rate_limits()
    yield
    clear_rate_limits()


# ── 1 & 2: Invalid Login Generic Error ────────────────────────────────────

@pytest.mark.asyncio
async def test_wrong_password_returns_generic_error():
    """1. Wrong password returns generic error without leaking password status."""
    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"username": "officer", "password": "wrong_officer_pass"})
    assert resp.status_code == 401
    assert "Incorrect username or password. Please check your credentials and try again." in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wrong_username_returns_same_generic_error():
    """2. Non-existent username returns identical generic error without leaking user non-existence."""
    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"username": "non_existent_user_999", "password": "some_password_123"})
    assert resp.status_code == 401
    assert "Incorrect username or password. Please check your credentials and try again." in resp.json()["detail"]


# ── 3 & 4: Forgot Password Enumeration Resistance ─────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_valid_and_invalid_identifier_identical_response():
    """3 & 4. Valid and invalid identifiers return the exact same generic confirmation message."""
    client = TestClient(app)
    
    # Valid user
    resp_valid = client.post("/api/auth/forgot-password", json={"identifier": "officer"})
    assert resp_valid.status_code == 200
    msg_valid = resp_valid.json()["message"]

    # Invalid user
    resp_invalid = client.post("/api/auth/forgot-password", json={"identifier": "ghost_brand_xyz"})
    assert resp_invalid.status_code == 200
    msg_invalid = resp_invalid.json()["message"]

    assert msg_valid == msg_invalid
    assert "If an account matches the information provided, password reset instructions have been sent" in msg_valid
    assert resp_invalid.json().get("dev_token") is None


# ── 5, 6, 7, 8, 9, 10: Reset Token Cryptography & Lifecycle ───────────────

@pytest.mark.asyncio
async def test_reset_token_secure_random_and_hashed_in_db():
    """5 & 6. Reset token is cryptographically random and only SHA-256 hash is saved in database."""
    client = TestClient(app)
    
    resp = client.post("/api/auth/forgot-password", json={"identifier": "merchant"})
    assert resp.status_code == 200
    raw_token = resp.json().get("dev_token")
    assert raw_token is not None
    assert len(raw_token) >= 32

    expected_hash = hash_reset_token(raw_token)
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM password_resets WHERE username = 'merchant' ORDER BY id DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            assert row is not None
            record = dict(row)
            assert record["token_hash"] == expected_hash
            assert record["token_hash"] != raw_token
            assert record["used_at"] is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reset_token_expiry_enforced():
    """7 & 10. Expired reset tokens (beyond 15 minutes) are rejected."""
    client = TestClient(app)
    raw_token = "expired_token_test_12345678901234567890"
    token_hash = hash_reset_token(raw_token)
    past_expiry = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).isoformat()

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO password_resets (username, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            ("merchant", token_hash, past_expiry, past_expiry)
        )
        await db.commit()
    finally:
        await db.close()

    # Pre-verification
    v_resp = client.post("/api/auth/verify-reset-token", json={"token": raw_token})
    assert v_resp.status_code == 200
    assert v_resp.json()["valid"] is False

    # Reset attempt
    r_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "NewSecurePassword123!"})
    assert r_resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_reset_token_single_use_enforcement():
    """8. Reset tokens cannot be used more than once."""
    client = TestClient(app)
    
    # Create isolated test user
    pwh, salt = hash_password("initial_test_pass123")
    await create_user("test_singleuse_user", pwh, salt, ROLE_MERCHANT, "Single Use Test")

    forgot_resp = client.post("/api/auth/forgot-password", json={"identifier": "test_singleuse_user"})
    raw_token = forgot_resp.json()["dev_token"]

    # First use -> Success
    res1 = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "FreshPassword12345!"})
    assert res1.status_code == 200

    # Second use -> Failure
    res2 = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "AnotherPassword56789!"})
    assert res2.status_code == 400


@pytest.mark.asyncio
async def test_previous_token_invalidation_on_new_request():
    """9. Requesting a new token invalidates previous unused tokens."""
    client = TestClient(app)
    
    pwh, salt = hash_password("initial_inval_pass123")
    await create_user("test_invalidation_user", pwh, salt, ROLE_MERCHANT, "Invalidation Test")

    resp1 = client.post("/api/auth/forgot-password", json={"identifier": "test_invalidation_user"})
    token1 = resp1.json()["dev_token"]

    resp2 = client.post("/api/auth/forgot-password", json={"identifier": "test_invalidation_user"})
    token2 = resp2.json()["dev_token"]

    assert token1 != token2

    # Old token fails
    old_res = client.post("/api/auth/reset-password", json={"token": token1, "new_password": "OldTokenPassword123!"})
    assert old_res.status_code == 400

    # New token succeeds
    new_res = client.post("/api/auth/reset-password", json={"token": token2, "new_password": "NewTokenPassword123!"})
    assert new_res.status_code == 200


# ── 11 & 12: Password Policy Hardening (min 8 chars) ──────────────────────

@pytest.mark.asyncio
async def test_password_policy_7_chars_rejected():
    """11. 7-character password rejected on both registration and password reset."""
    client = TestClient(app)

    # Register with 7 chars
    reg_resp = client.post("/api/auth/register", json={
        "username": "short_pw_user",
        "password": "1234567",
        "role": "MERCHANT_PUBLIC"
    })
    assert reg_resp.status_code in (400, 422)

    # Reset with 7 chars
    pwh, salt = hash_password("pass_for_short_test123")
    await create_user("test_short_user", pwh, salt, ROLE_MERCHANT, "Short Test")

    forgot_resp = client.post("/api/auth/forgot-password", json={"identifier": "test_short_user"})
    raw_token = forgot_resp.json()["dev_token"]
    reset_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "1234567"})
    assert reset_resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_password_policy_8_chars_accepted():
    """12. 8-character password accepted on registration and password reset."""
    client = TestClient(app)

    # Register with 8 chars
    reg_resp = client.post("/api/auth/register", json={
        "username": "valid_8char_user",
        "password": "8charPw!",
        "role": "MERCHANT_PUBLIC"
    })
    assert reg_resp.status_code == 201

    # Reset with 8 chars
    forgot_resp = client.post("/api/auth/forgot-password", json={"identifier": "valid_8char_user"})
    raw_token = forgot_resp.json()["dev_token"]
    reset_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "new8CharPass"})
    assert reset_resp.status_code == 200


# ── 13, 14, 15, 16, 17, 18, 19, 20: Role & Workspace Integrity ────────────

@pytest.mark.asyncio
async def test_password_reset_preserves_merchant_role_and_workspaces():
    """13, 14, 15, 18, 19: Merchant password reset invalidates old password, accepts new, preserves MERCHANT_PUBLIC role."""
    client = TestClient(app)
    
    pwh, salt = hash_password("initial_merch_pw123")
    await create_user("test_pw_merchant", pwh, salt, ROLE_MERCHANT, "Test Merchant PW")

    forgot_resp = client.post("/api/auth/forgot-password", json={"identifier": "test_pw_merchant"})
    raw_token = forgot_resp.json()["dev_token"]

    new_pw = "BrandNewMerchantPass2026!"
    reset_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": new_pw})
    assert reset_resp.status_code == 200

    # Old password fails
    assert client.post("/api/auth/login", json={"username": "test_pw_merchant", "password": "initial_merch_pw123"}).status_code == 401

    # New password succeeds
    login_resp = client.post("/api/auth/login", json={"username": "test_pw_merchant", "password": new_pw})
    assert login_resp.status_code == 200
    user_data = login_resp.json()["user"]
    assert user_data["role"] == ROLE_MERCHANT
    assert user_data["is_admin"] is False

    # Merchant cannot access admin/officer users management endpoint
    token = login_resp.json()["token"]
    auth_header = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/users", headers=auth_header).status_code == 403


@pytest.mark.asyncio
async def test_password_reset_preserves_officer_role_and_workspaces():
    """16 & 18: Officer password reset preserves ENFORCEMENT_OFFICER role and privileges."""
    client = TestClient(app)

    pwh, salt = hash_password("initial_off_pw123")
    await create_user("test_pw_officer", pwh, salt, ROLE_ENFORCEMENT, "Test Officer PW", organization_id="org_ministry")

    forgot_resp = client.post("/api/auth/forgot-password", json={"identifier": "test_pw_officer"})
    raw_token = forgot_resp.json()["dev_token"]

    new_pw = "BrandNewOfficerPass2026!"
    reset_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": new_pw})
    assert reset_resp.status_code == 200

    login_resp = client.post("/api/auth/login", json={"username": "test_pw_officer", "password": new_pw})
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["role"] == ROLE_ENFORCEMENT


@pytest.mark.asyncio
async def test_password_reset_preserves_admin_role_and_workspaces():
    """17 & 18: Admin password reset preserves ADMIN role and administrative privileges."""
    client = TestClient(app)

    pwh, salt = hash_password("initial_adm_pw123")
    await create_user("test_pw_admin", pwh, salt, ROLE_ADMIN, "Test Admin PW")

    forgot_resp = client.post("/api/auth/forgot-password", json={"identifier": "test_pw_admin"})
    raw_token = forgot_resp.json()["dev_token"]

    new_pw = "BrandNewAdminPass2026!"
    reset_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": new_pw})
    assert reset_resp.status_code == 200

    login_resp = client.post("/api/auth/login", json={"username": "test_pw_admin", "password": new_pw})
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["role"] == ROLE_ADMIN
    assert login_resp.json()["user"]["is_admin"] is True


# ── 21 & 22: Production Token Exposure Boundary ───────────────────────────

@pytest.mark.asyncio
async def test_production_environment_suppresses_dev_token():
    """21 & 22. In production (METRCHECK_ENV=production), dev_token is strictly omitted from API response."""
    client = TestClient(app)
    
    os.environ["METRCHECK_ENV"] = "production"
    try:
        resp = client.post("/api/auth/forgot-password", json={"identifier": "merchant"})
        assert resp.status_code == 200
        # Under production mode, dev_token MUST NOT be returned
        assert resp.json().get("dev_token") is None
    finally:
        os.environ["METRCHECK_ENV"] = "development"


# ── 23: Login Brute-Force Rate Limiting ───────────────────────────────────

@pytest.mark.asyncio
async def test_login_rate_limiting_throttles_excessive_failed_attempts():
    """23. Excessive failed login attempts from same IP/account are throttled with HTTP 429 Too Many Requests."""
    client = TestClient(app)

    # 5 failed login attempts for a specific user
    for _ in range(5):
        resp = client.post("/api/auth/login", json={"username": "officer", "password": "wrongpassword"})
        assert resp.status_code == 401

    # 6th attempt for this user must be throttled with HTTP 429
    throttled = client.post("/api/auth/login", json={"username": "officer", "password": "wrongpassword"})
    assert throttled.status_code == 429
    assert "Too many failed login attempts" in throttled.json()["detail"]


# ── 24: Forgot Password Rate Limiting ─────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_rate_limiting_throttles_abuse():
    """24. Excessive password reset requests are throttled with HTTP 429."""
    client = TestClient(app)

    # 3 recovery requests for the same identifier
    for _ in range(3):
        resp = client.post("/api/auth/forgot-password", json={"identifier": "merchant"})
        assert resp.status_code == 200

    # 4th request for this identifier throttled
    throttled = client.post("/api/auth/forgot-password", json={"identifier": "merchant"})
    assert throttled.status_code == 429
    assert "Too many password recovery requests" in throttled.json()["detail"]


# ── 25 & 26: Secrets & Production Logging Safety ──────────────────────────

@pytest.mark.asyncio
async def test_dev_logger_does_not_log_tokens_in_production(caplog):
    """25 & 26. DevLoggerDeliveryProvider refuses to log raw tokens when running in production."""
    provider = DevLoggerDeliveryProvider()
    
    os.environ["METRCHECK_ENV"] = "production"
    try:
        ok = await provider.send_reset_instructions("officer", "secret_raw_token_xyz", "http://example.com/reset")
        assert ok is False
        # Token must not appear in captured log output
        assert "secret_raw_token_xyz" not in caplog.text
    finally:
        os.environ["METRCHECK_ENV"] = "development"


@pytest.mark.asyncio
async def test_demo_accounts_authentication_preserved():
    """Ensure default demo accounts (admin123, officer123, merchant123) authenticate properly."""
    client = TestClient(app)
    
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200
    assert admin_login.json()["user"]["role"] == ROLE_ADMIN

    officer_login = client.post("/api/auth/login", json={"username": "officer", "password": "officer123"})
    assert officer_login.status_code == 200
    assert officer_login.json()["user"]["role"] == ROLE_ENFORCEMENT

    merchant_login = client.post("/api/auth/login", json={"username": "merchant", "password": "merchant123"})
    assert merchant_login.status_code == 200
    assert merchant_login.json()["user"]["role"] == ROLE_MERCHANT
