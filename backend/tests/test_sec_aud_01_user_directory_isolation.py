"""
Unit and Integration Tests for SEC-AUD-01 — Global User Directory Isolation.

Vulnerability Reference: SEC-AUD-01
Endpoint Under Test: GET /api/auth/users

Security Requirements:
1. GET /api/auth/users must be strictly restricted to ROLE_ADMIN.
2. Non-admin roles (ENFORCEMENT_OFFICER, AUDIT_OFFICER, MERCHANT_PUBLIC) must receive HTTP 403 Forbidden.
3. Unauthenticated requests and requests with invalid/expired tokens must receive HTTP 401 Unauthorized.
4. Query parameters (e.g., ?organization_id=..., ?role=...) cannot bypass authorization.
5. Organization-scoped officer directory (GET /api/reviews/officers) remains available and properly isolated for enforcement officers.
"""

import os
import pytest
from fastapi.testclient import TestClient

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import (
    init_db,
    create_organization,
    create_user,
    get_user_by_username,
)
from auth.security import (
    hash_password,
    create_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _create_test_user_helper(username: str, role: str, org_id: str = ""):
    """Helper to register/create user in DB with specific role and organization_id."""
    salt, pwh = hash_password("TestPass123!")
    existing = await get_user_by_username(username)
    if not existing:
        await create_user(
            username=username,
            password_hash=pwh,
            salt=salt,
            role=role,
            full_name=f"User {username}",
            organization_id=org_id,
        )


def _auth_header(username: str, role: str) -> dict:
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True, scope="module")
def setup_audit_01_fixture():
    _ensure_test_isolation()
    import asyncio
    async def _setup():
        await init_db()
        # Create test organizations
        await create_organization("org_sec_aud_alpha", "Security Org Alpha", "STATE_ENFORCEMENT")
        await create_organization("org_sec_aud_beta", "Security Org Beta", "STATE_ENFORCEMENT")
        await create_organization("org_sec_aud_merchant", "Merchant Corp", "MERCHANT_PUBLIC")

        # Create test users across different roles and orgs
        await _create_test_user_helper("aud01_admin", ROLE_ADMIN, "")
        await _create_test_user_helper("aud01_officer_a", ROLE_ENFORCEMENT, "org_sec_aud_alpha")
        await _create_test_user_helper("aud01_officer_b", ROLE_ENFORCEMENT, "org_sec_aud_beta")
        await _create_test_user_helper("aud01_audit_user", ROLE_AUDIT, "org_sec_aud_alpha")
        await _create_test_user_helper("aud01_merchant", ROLE_MERCHANT, "org_sec_aud_merchant")

    asyncio.run(_setup())


# ═════════════════════════════════════════════════════════════════════════════
# 1. UNAUTHENTICATED & INVALID TOKEN ACCESS CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def test_01_unauthenticated_request_rejected(client):
    """GET /api/auth/users must return 401 Unauthorized when no Authorization header is provided."""
    resp = client.get("/api/auth/users")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_02_invalid_token_rejected(client):
    """GET /api/auth/users must return 401 Unauthorized when an invalid token is provided."""
    resp = client.get("/api/auth/users", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_03_malformed_auth_header_rejected(client):
    """GET /api/auth/users must return 401 Unauthorized when malformed Authorization header is provided."""
    resp = client.get("/api/auth/users", headers={"Authorization": "Basic abc123xyz"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


# ═════════════════════════════════════════════════════════════════════════════
# 2. ROLE-BASED ACCESS CONTROL (NON-ADMIN ROLES DENIED)
# ═════════════════════════════════════════════════════════════════════════════

def test_04_enforcement_officer_org_a_denied_access(client):
    """Enforcement officer in Org Alpha must receive 403 Forbidden on GET /api/auth/users."""
    headers = _auth_header("aud01_officer_a", ROLE_ENFORCEMENT)
    resp = client.get("/api/auth/users", headers=headers)
    assert resp.status_code == 403, f"Expected 403 for enforcement officer, got {resp.status_code}: {resp.text}"


def test_05_enforcement_officer_org_b_denied_access(client):
    """Enforcement officer in Org Beta must receive 403 Forbidden on GET /api/auth/users."""
    headers = _auth_header("aud01_officer_b", ROLE_ENFORCEMENT)
    resp = client.get("/api/auth/users", headers=headers)
    assert resp.status_code == 403, f"Expected 403 for enforcement officer, got {resp.status_code}: {resp.text}"


def test_06_audit_officer_denied_access(client):
    """Audit officer must receive 403 Forbidden on GET /api/auth/users."""
    headers = _auth_header("aud01_audit_user", ROLE_AUDIT)
    resp = client.get("/api/auth/users", headers=headers)
    assert resp.status_code == 403, f"Expected 403 for audit officer, got {resp.status_code}: {resp.text}"


def test_07_merchant_public_denied_access(client):
    """Merchant / public user must receive 403 Forbidden on GET /api/auth/users."""
    headers = _auth_header("aud01_merchant", ROLE_MERCHANT)
    resp = client.get("/api/auth/users", headers=headers)
    assert resp.status_code == 403, f"Expected 403 for merchant, got {resp.status_code}: {resp.text}"


# ═════════════════════════════════════════════════════════════════════════════
# 3. QUERY PARAMETER MANIPULATION / BYPASS ATTEMPTS
# ═════════════════════════════════════════════════════════════════════════════

def test_08_query_param_bypass_attempt_by_officer(client):
    """Attempting to supply query parameters (?organization_id=..., ?role=...) cannot bypass 403."""
    headers = _auth_header("aud01_officer_a", ROLE_ENFORCEMENT)
    
    # Try querying with organization_id
    resp = client.get("/api/auth/users?organization_id=org_sec_aud_alpha", headers=headers)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    # Try querying with role
    resp = client.get("/api/auth/users?role=ADMIN", headers=headers)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    # Try querying with both
    resp = client.get("/api/auth/users?organization_id=org_sec_aud_alpha&role=ENFORCEMENT_OFFICER", headers=headers)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ═════════════════════════════════════════════════════════════════════════════
# 4. ADMIN ACCESS & RESPONSE INTEGRITY
# ═════════════════════════════════════════════════════════════════════════════

def test_09_admin_allowed_access(client):
    """Admin user must receive 200 OK and complete list of users on GET /api/auth/users."""
    headers = _auth_header("aud01_admin", ROLE_ADMIN)
    resp = client.get("/api/auth/users", headers=headers)
    assert resp.status_code == 200, f"Expected 200 for admin, got {resp.status_code}: {resp.text}"

    users = resp.json()
    assert isinstance(users, list), "Response must be a list of users"
    assert len(users) > 0, "User list must not be empty"

    # Verify user object schema
    usernames = [u["username"] for u in users]
    assert "aud01_admin" in usernames
    assert "aud01_officer_a" in usernames
    assert "aud01_officer_b" in usernames
    assert "aud01_audit_user" in usernames
    assert "aud01_merchant" in usernames

    # Verify password / salt not leaked in response
    for u in users:
        assert "password" not in u
        assert "password_hash" not in u
        assert "salt" not in u
        assert "username" in u
        assert "role" in u


# ═════════════════════════════════════════════════════════════════════════════
# 5. REVIEWS/OFFICERS SCOPED DIRECTORY VERIFICATION
# ═════════════════════════════════════════════════════════════════════════════

def test_10_officers_directory_isolation_preserved(client):
    """Verify that /api/reviews/officers remains the legitimate, organization-scoped endpoint."""
    # Unauthenticated -> 401
    resp_unauth = client.get("/api/reviews/officers")
    assert resp_unauth.status_code == 401

    # Merchant -> 403
    headers_merchant = _auth_header("aud01_merchant", ROLE_MERCHANT)
    resp_merch = client.get("/api/reviews/officers", headers=headers_merchant)
    assert resp_merch.status_code == 403

    # Officer in Org Alpha -> 200, sees only Org Alpha officers
    headers_off_a = _auth_header("aud01_officer_a", ROLE_ENFORCEMENT)
    resp_off_a = client.get("/api/reviews/officers", headers=headers_off_a)
    assert resp_off_a.status_code == 200
    data_a = resp_off_a.json()
    assert "officers" in data_a
    usernames_a = [o["username"] for o in data_a["officers"]]
    assert "aud01_officer_a" in usernames_a
    assert "aud01_officer_b" not in usernames_a, "Officer A must not see Officer B from different org"

    # Officer in Org Beta -> 200, sees only Org Beta officers
    headers_off_b = _auth_header("aud01_officer_b", ROLE_ENFORCEMENT)
    resp_off_b = client.get("/api/reviews/officers", headers=headers_off_b)
    assert resp_off_b.status_code == 200
    data_b = resp_off_b.json()
    assert "officers" in data_b
    usernames_b = [o["username"] for o in data_b["officers"]]
    assert "aud01_officer_b" in usernames_b
    assert "aud01_officer_a" not in usernames_b, "Officer B must not see Officer A from different org"
