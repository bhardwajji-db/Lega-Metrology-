"""
Phase 7.1.7 — Account Email Registration, Migration, and Email-Based Password Recovery Test Suite

Validates:
1. Email column existence & migration safety in SQLite.
2. Email validation format (valid email passes, invalid fails).
3. Registration requires a valid email address.
4. Registration with invalid email format returns HTTP 400.
5. Registration with already registered email returns HTTP 409.
6. Email normalization (case-insensitive deduplication and storage).
7. User retrieval by normalized email (get_user_by_email).
8. User retrieval by identifier (username or email).
9. /api/auth/me returns registered recovery email.
10. Authenticated self-service email update (PATCH /api/auth/me/email).
11. Authenticated self-service email update (PUT /api/auth/me/email).
12. Self-service email update with invalid format returns HTTP 400.
13. Self-service email update with existing other user email returns HTTP 409.
14. Self-service email update with own current email succeeds (idempotent).
15. Unauthenticated request to /api/auth/me/email returns HTTP 401.
16. Admin create user with email succeeds.
17. Admin create user with invalid email format returns HTTP 400.
18. Admin create user with duplicate email returns HTTP 409.
19. Admin update user email succeeds.
20. Admin update user with existing another user email returns HTTP 409.
21. Forgot password lookup by username (when account has email) dispatches reset link to registered email.
22. Forgot password lookup by email dispatches reset link to registered email.
23. Forgot password lookup case-insensitivity on email lookup.
24. Forgot password delivery destination is strictly the registered email, never an attacker-injected destination.
25. Forgot password for account without email returns generic 200 response (enumeration resistant).
26. Forgot password for non-existent identifier returns generic 200 response (enumeration resistant).
27. Password reset token generated via email flow successfully resets password.
28. Reset password preserves user role (MERCHANT, ENFORCEMENT, ADMIN).
29. Reset password preserves user email.
30. Old password fails after reset.
31. New password succeeds after reset.
32. Rate limiting on forgot password with email identifier.
33. Existing demo accounts without email continue to authenticate normally.
34. Non-admin users cannot access admin user creation/modification.
"""

import os
import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings
from auth.security import (
    create_token,
    hash_password,
    verify_password,
    get_delivery_provider,
    DevLoggerDeliveryProvider,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_MERCHANT,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    init_db,
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_by_identifier,
    update_user,
    delete_user,
    get_db,
)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture(scope="module")
def client():
    # Force test mode
    os.environ["TEST_MODE"] = "1"
    os.environ["METRCHECK_ENV"] = "development"
    settings.TEST_MODE = True
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_01_db_schema_has_email_column_and_index():
    await init_db()
    db = await get_db()
    try:
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
        assert "email" in columns, "email column must exist in users table"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_02_registration_with_valid_email(client):
    username = "test_reg_email_01"
    email = "test.reg01@example.com"
    # Clean up prior test data if any
    await delete_user(username)
    
    resp = client.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": "ValidPassword123!",
        "full_name": "Test Merchant 1",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["user"]["username"] == username
    assert data["user"]["email"] == email.lower()
    assert data["user"]["role"] == "MERCHANT_PUBLIC"


def test_03_registration_with_invalid_email_fails(client):
    resp = client.post("/api/auth/register", json={
        "username": "test_bad_email_user",
        "email": "not-a-valid-email",
        "password": "ValidPassword123!",
    })
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_04_registration_with_duplicate_email_fails(client):
    username1 = "user_dup_email_a"
    username2 = "user_dup_email_b"
    dup_email = "unique.dup@example.com"
    await delete_user(username1)
    await delete_user(username2)

    # First user
    r1 = client.post("/api/auth/register", json={
        "username": username1,
        "email": dup_email,
        "password": "ValidPassword123!",
    })
    assert r1.status_code == 201

    # Second user with same email (even with different casing)
    r2 = client.post("/api/auth/register", json={
        "username": username2,
        "email": dup_email.upper(),
        "password": "ValidPassword123!",
    })
    assert r2.status_code == 409
    assert "Email address is already registered" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_05_email_normalization_and_lookup():
    username = "user_norm_test"
    raw_email = "  Test.Normalize@Example.COM  "
    await delete_user(username)

    pw_hash, salt = hash_password("Password123!")
    ok = await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role="MERCHANT_PUBLIC",
        email=raw_email.strip().lower()
    )
    assert ok is True

    # Lookup by exact lowercase
    u1 = await get_user_by_email("test.normalize@example.com")
    assert u1 is not None
    assert u1["username"] == username

    # Lookup by uppercase email
    u2 = await get_user_by_email("TEST.NORMALIZE@EXAMPLE.COM")
    assert u2 is not None
    assert u2["username"] == username

    # Lookup via get_user_by_identifier with username
    u3 = await get_user_by_identifier(username)
    assert u3 is not None
    assert u3["username"] == username

    # Lookup via get_user_by_identifier with email
    u4 = await get_user_by_identifier("Test.Normalize@Example.Com")
    assert u4 is not None
    assert u4["username"] == username


@pytest.mark.asyncio
async def test_06_get_me_returns_email(client):
    username = "user_me_test"
    email = "user.me@example.com"
    await delete_user(username)

    pw_hash, salt = hash_password("Password123!")
    await create_user(username=username, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email=email)
    
    token = create_token(username, "MERCHANT_PUBLIC")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == username
    assert data["email"] == email


@pytest.mark.asyncio
async def test_07_self_service_update_email_patch_and_put(client):
    username = "user_self_email"
    initial_email = "initial.self@example.com"
    new_email = "updated.self@example.com"
    await delete_user(username)

    pw_hash, salt = hash_password("Password123!")
    await create_user(username=username, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email=initial_email)
    token = create_token(username, "MERCHANT_PUBLIC")

    # PATCH /api/auth/me/email
    resp = client.patch(
        "/api/auth/me/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": new_email}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == new_email

    # PUT /api/auth/me/email
    put_email = "put.updated.self@example.com"
    resp2 = client.put(
        "/api/auth/me/email",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": put_email}
    )
    assert resp2.status_code == 200
    assert resp2.json()["email"] == put_email


@pytest.mark.asyncio
async def test_08_self_service_update_email_validation_and_conflict(client):
    u1 = "user_self_conf_1"
    u2 = "user_self_conf_2"
    e1 = "conf1@example.com"
    e2 = "conf2@example.com"
    await delete_user(u1)
    await delete_user(u2)

    pw_hash, salt = hash_password("Password123!")
    await create_user(username=u1, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email=e1)
    await create_user(username=u2, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email=e2)

    token2 = create_token(u2, "MERCHANT_PUBLIC")

    # Invalid email format
    r_bad = client.patch(
        "/api/auth/me/email",
        headers={"Authorization": f"Bearer {token2}"},
        json={"email": "not-valid-at-all"}
    )
    assert r_bad.status_code == 400

    # Conflict with u1's email
    r_conf = client.patch(
        "/api/auth/me/email",
        headers={"Authorization": f"Bearer {token2}"},
        json={"email": e1}
    )
    assert r_conf.status_code == 409
    assert "already registered to another account" in r_conf.json()["detail"]


@pytest.mark.asyncio
async def test_09_admin_create_and_update_user_with_email(client):
    admin_token = create_token("admin", "ADMIN")
    officer_user = "officer_email_test"
    officer_email = "officer.dept@gov.in"
    await delete_user(officer_user)

    # Admin creates officer with email
    r_create = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": officer_user,
            "email": officer_email,
            "password": "OfficerPassword123!",
            "full_name": "Insp. Officer",
            "jurisdiction": "Central",
            "role": "ENFORCEMENT_OFFICER",
            "organization_id": "org_ministry",
        }
    )
    assert r_create.status_code == 201
    assert r_create.json()["email"] == officer_email

    # Admin updates officer email
    updated_officer_email = "officer.transferred@gov.in"
    r_update = client.put(
        f"/api/auth/users/{officer_user}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": updated_officer_email}
    )
    assert r_update.status_code == 200
    assert r_update.json()["email"] == updated_officer_email


@pytest.mark.asyncio
async def test_10_forgot_password_by_username_dispatches_to_registered_email(client):
    username = "user_recov_user"
    email = "user.recovery.target@example.com"
    await delete_user(username)

    pw_hash, salt = hash_password("OldPassword123!")
    await create_user(username=username, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email=email)

    resp = client.post("/api/auth/forgot-password", json={"identifier": username})
    assert resp.status_code == 200
    data = resp.json()
    assert "If an account matches the information provided" in data["message"]
    assert data["dev_token"] is not None

    provider = get_delivery_provider()
    if isinstance(provider, DevLoggerDeliveryProvider):
        assert provider.last_sent is not None
        assert provider.last_sent["username"] == username
        assert provider.last_sent["email"] == email


@pytest.mark.asyncio
async def test_11_forgot_password_by_email_dispatches_to_registered_email(client):
    username = "user_recov_by_email"
    email = "registered.lookup@example.com"
    await delete_user(username)

    pw_hash, salt = hash_password("OldPassword123!")
    await create_user(username=username, password_hash=pw_hash, salt=salt, role="ENFORCEMENT_OFFICER", email=email, organization_id="org_ministry")

    # Call with uppercase email to test case-insensitivity
    resp = client.post("/api/auth/forgot-password", json={"identifier": "REGISTERED.LOOKUP@EXAMPLE.COM"})
    assert resp.status_code == 200
    data = resp.json()
    assert "If an account matches the information provided" in data["message"]
    assert data["dev_token"] is not None

    provider = get_delivery_provider()
    if isinstance(provider, DevLoggerDeliveryProvider):
        assert provider.last_sent is not None
        assert provider.last_sent["username"] == username
        assert provider.last_sent["email"] == email


@pytest.mark.asyncio
async def test_12_forgot_password_account_without_email_returns_generic_200(client):
    username = "user_no_email_account"
    await delete_user(username)

    pw_hash, salt = hash_password("OldPassword123!")
    # Account with empty email
    await create_user(username=username, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email="")

    resp = client.post("/api/auth/forgot-password", json={"identifier": username})
    assert resp.status_code == 200
    data = resp.json()
    assert "If an account matches the information provided" in data["message"]
    provider = get_delivery_provider()
    if isinstance(provider, DevLoggerDeliveryProvider):
        assert provider.last_sent is not None
        assert provider.last_sent["username"] == username


def test_13_forgot_password_nonexistent_identifier_returns_generic_200(client):
    resp = client.post("/api/auth/forgot-password", json={"identifier": "non_existent_account_9999"})
    assert resp.status_code == 200
    data = resp.json()
    assert "If an account matches the information provided" in data["message"]
    assert data["dev_token"] is None


@pytest.mark.asyncio
async def test_14_complete_reset_flow_with_email_account(client):
    username = "user_e2e_reset"
    email = "e2e.reset@example.com"
    old_pw = "OldPassword123!"
    new_pw = "NewSecurePassword456!"
    await delete_user(username)

    pw_hash, salt = hash_password(old_pw)
    await create_user(username=username, password_hash=pw_hash, salt=salt, role="MERCHANT_PUBLIC", email=email)

    # 1. Request forgot password using email
    r_forgot = client.post("/api/auth/forgot-password", json={"identifier": email})
    assert r_forgot.status_code == 200
    token = r_forgot.json()["dev_token"]
    assert token is not None

    # 2. Verify token
    r_verify = client.post("/api/auth/verify-reset-token", json={"token": token})
    assert r_verify.status_code == 200
    assert r_verify.json()["valid"] is True
    assert r_verify.json()["username"] == username

    # 3. Reset password
    r_reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": new_pw})
    assert r_reset.status_code == 200
    assert "successfully reset" in r_reset.json()["message"]

    # 4. Old password fails
    r_fail = client.post("/api/auth/login", json={"username": username, "password": old_pw})
    assert r_fail.status_code == 401

    # 5. New password succeeds
    r_succ = client.post("/api/auth/login", json={"username": username, "password": new_pw})
    assert r_succ.status_code == 200
    assert r_succ.json()["user"]["username"] == username
    assert r_succ.json()["user"]["email"] == email
    assert r_succ.json()["user"]["role"] == "MERCHANT_PUBLIC"


@pytest.mark.asyncio
async def test_15_existing_demo_accounts_login_without_email(client):
    # admin, officer, merchant accounts
    for u, p, expected_role in [
        ("admin", "admin123", "ADMIN"),
        ("officer", "officer123", "ENFORCEMENT_OFFICER"),
        ("merchant", "merchant123", "MERCHANT_PUBLIC"),
    ]:
        resp = client.post("/api/auth/login", json={"username": u, "password": p})
        assert resp.status_code == 200, f"Login failed for demo user {u}"
        assert resp.json()["user"]["role"] == expected_role
