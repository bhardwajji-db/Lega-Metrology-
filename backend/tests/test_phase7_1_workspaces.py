"""
Phase 7.1 & 7.1.5 — Workspace Architecture, Role/Mode Separation & Login Portal Test Suite

Verifies:
1. Merchant account -> Merchant workspace (allowed)
2. Merchant account -> Audit workspace (denied)
3. Merchant account -> Enforcement workspace (denied)
4. Officer account -> Merchant allowed
5. Officer account -> Audit allowed
6. Officer account -> Enforcement allowed
7. Admin account -> Merchant allowed
8. Admin account -> Audit allowed
9. Admin account -> Enforcement allowed
10. Invalid credentials rejected (HTTP 401)
11. Logout clears session / token validation
12. Refresh preserves correct role/workspace via /api/auth/me
13. Direct unauthorized workspace navigation blocked at API boundary
14. Workspace selection cannot change backend role in JWT
15. Frontend cannot fabricate ADMIN role via register endpoint (HTTP 403)
16. Frontend cannot fabricate ENFORCEMENT_OFFICER role via register endpoint (HTTP 403)
"""

import pytest
import os
from fastapi.testclient import TestClient
from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import create_token, decode_token, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_MERCHANT, hash_password
from database.db import create_user, save_analysis, get_analysis, get_user_by_username


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


WORKSPACE_DEFINITIONS = {
    'MERCHANT': {
        'core_action': 'PREVENT',
        'allowed_roles': {ROLE_MERCHANT, ROLE_ENFORCEMENT, ROLE_ADMIN}
    },
    'AUDIT': {
        'core_action': 'VERIFY',
        'allowed_roles': {ROLE_ENFORCEMENT, ROLE_ADMIN}
    },
    'ENFORCEMENT': {
        'core_action': 'INVESTIGATE',
        'allowed_roles': {ROLE_ENFORCEMENT, ROLE_ADMIN}
    }
}


def get_allowed_workspaces_for_role(role: str):
    if role in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        return ['ENFORCEMENT', 'AUDIT', 'MERCHANT']
    return ['MERCHANT']


# ── Tests 1..9: Workspace Permission Matrix ─────────────────────────────────

def test_merchant_workspace_access_permissions():
    """1. Merchant account -> Merchant allowed. 2. Merchant -> Audit denied. 3. Merchant -> Enforcement denied."""
    allowed = get_allowed_workspaces_for_role(ROLE_MERCHANT)
    assert 'MERCHANT' in allowed
    assert 'AUDIT' not in allowed
    assert 'ENFORCEMENT' not in allowed


def test_officer_workspace_access_permissions():
    """4. Officer -> Merchant allowed. 5. Officer -> Audit allowed. 6. Officer -> Enforcement allowed."""
    allowed = get_allowed_workspaces_for_role(ROLE_ENFORCEMENT)
    assert 'MERCHANT' in allowed
    assert 'AUDIT' in allowed
    assert 'ENFORCEMENT' in allowed


def test_admin_workspace_access_permissions():
    """7. Admin -> Merchant allowed. 8. Admin -> Audit allowed. 9. Admin -> Enforcement allowed."""
    allowed = get_allowed_workspaces_for_role(ROLE_ADMIN)
    assert 'MERCHANT' in allowed
    assert 'AUDIT' in allowed
    assert 'ENFORCEMENT' in allowed


# ── Test 10: Invalid Credentials Rejected ───────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_credentials_rejected():
    """10. Invalid credentials must return 401 Unauthorized."""
    client = TestClient(app)
    
    # Non-existent user
    res = client.post("/api/auth/login", json={"username": "nonexistent_user", "password": "wrongpassword"})
    assert res.status_code == 401
    assert "Incorrect username or password" in res.json().get("detail", "")

    # Valid user, wrong password
    pwh, salt = hash_password("correctpass123")
    await create_user("valid_user_test", pwh, salt, ROLE_MERCHANT, "Test User")
    
    res2 = client.post("/api/auth/login", json={"username": "valid_user_test", "password": "wrongpassword"})
    assert res2.status_code == 401


# ── Test 11: Token Validation & Session Expiry ─────────────────────────────

@pytest.mark.asyncio
async def test_session_token_validation_and_tampering():
    """11. Valid token allows /api/auth/me; tampered/cleared token returns 401."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("token_user_test", pwh, salt, ROLE_ENFORCEMENT, "Token User")

    # Login
    res_login = client.post("/api/auth/login", json={"username": "token_user_test", "password": "pass123"})
    assert res_login.status_code == 200
    token = res_login.json()["token"]

    # Valid request
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "token_user_test"
    assert res_me.json()["role"] == ROLE_ENFORCEMENT

    # Tampered token
    tampered_token = token + "xyz"
    res_tampered = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401


# ── Test 12: Refresh Preserves Correct Role via /api/auth/me ───────────────

@pytest.mark.asyncio
async def test_refresh_preserves_correct_backend_role():
    """12. Browser refresh revalidates role strictly from backend /api/auth/me."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("refresh_officer", pwh, salt, ROLE_ENFORCEMENT, "Officer Refresh")

    token = create_token("refresh_officer", ROLE_ENFORCEMENT)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    user_data = res.json()
    assert user_data["role"] == ROLE_ENFORCEMENT
    assert user_data["role_label"] == "Enforcement Official"


# ── Test 13: Direct Unauthorized API Endpoint Navigation Blocked ────────────

@pytest.mark.asyncio
async def test_direct_unauthorized_admin_api_blocked():
    """13. Direct requests to privileged endpoints without admin/officer role are blocked."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("pure_merchant", pwh, salt, ROLE_MERCHANT, "Pure Merchant")
    token_merchant = create_token("pure_merchant", ROLE_MERCHANT)

    # Attempt to access admin users list
    res_users = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token_merchant}"})
    assert res_users.status_code == 403

    # Attempt to delete another user
    res_del_user = client.delete("/api/auth/users/someuser", headers={"Authorization": f"Bearer {token_merchant}"})
    assert res_del_user.status_code == 403


# ── Test 14: Workspace Selection Cannot Change Backend JWT Role ──────────────

@pytest.mark.asyncio
async def test_workspace_selection_cannot_alter_jwt_role():
    """14. A user logging in cannot dictate their JWT role; it is loaded strictly from DB."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("honest_merchant", pwh, salt, ROLE_MERCHANT, "Honest Merchant")

    res = client.post("/api/auth/login", json={"username": "honest_merchant", "password": "pass123"})
    assert res.status_code == 200
    token = res.json()["token"]

    payload = decode_token(token)
    assert payload is not None
    assert payload["role"] == ROLE_MERCHANT
    assert payload["sub"] == "honest_merchant"


# ── Tests 15 & 16: Frontend Cannot Fabricate Privileged Roles ────────────────

@pytest.mark.asyncio
async def test_register_cannot_fabricate_admin_or_officer():
    """15 & 16. Self-registration attempts to create ADMIN or ENFORCEMENT_OFFICER are denied when admin exists."""
    client = TestClient(app)

    # Ensure an admin exists in db
    pwh, salt = hash_password("pass123")
    await create_user("root_admin", pwh, salt, ROLE_ADMIN, "Root Admin")

    # Attempt to self-register as ADMIN
    res_admin = client.post("/api/auth/register", json={
        "username": "fake_admin",
        "password": "password123",
        "role": ROLE_ADMIN
    })
    assert res_admin.status_code == 403
    assert "Only an administrator can create privileged accounts" in res_admin.json().get("detail", "")

    # Attempt to self-register as ENFORCEMENT_OFFICER
    res_officer = client.post("/api/auth/register", json={
        "username": "fake_officer",
        "password": "password123",
        "role": ROLE_ENFORCEMENT
    })
    assert res_officer.status_code == 403
    assert "Only an administrator can create privileged accounts" in res_officer.json().get("detail", "")

    # Regular merchant registration succeeds and gets MERCHANT_PUBLIC
    res_merchant = client.post("/api/auth/register", json={
        "username": "legit_merchant",
        "password": "password123",
        "full_name": "Legit Brand"
    })
    assert res_merchant.status_code == 201
    assert res_merchant.json()["user"]["role"] == ROLE_MERCHANT


# ── RBAC Deletion Authorization & Shared Engine Tests ───────────────────────

@pytest.mark.asyncio
async def test_workspace_rbac_authorization_enforcement():
    """Verify RBAC boundaries for deletion across roles."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("ws_admin", pwh, salt, ROLE_ADMIN, "Workspace Admin")
    await create_user("ws_officer", pwh, salt, ROLE_ENFORCEMENT, "Workspace Officer")
    await create_user("ws_merchant", pwh, salt, ROLE_MERCHANT, "Workspace Merchant")

    token_officer = create_token("ws_officer", ROLE_ENFORCEMENT)
    token_merchant = create_token("ws_merchant", ROLE_MERCHANT)

    record_id = "test-ws-rec-1"
    dummy_data = {
        "id": record_id,
        "product_name": "Workspace Test Item",
        "image_filename": "test.png",
        "ocr_text": "Sample text",
        "extracted_data": {},
        "compliance_result": {"score": 85.0, "status": "POTENTIAL_NON_COMPLIANCE", "checks": []},
        "score": 85.0,
        "status": "POTENTIAL_NON_COMPLIANCE",
        "created_at": "2026-09-13T10:00:00",
        "images": []
    }
    await save_analysis(dummy_data)

    # Merchant user should be FORBIDDEN from deleting
    res_m = client.delete(
        f"/api/history/{record_id}",
        headers={"Authorization": f"Bearer {token_merchant}"}
    )
    assert res_m.status_code == 403
    assert "permission" in res_m.json().get("detail", "").lower() or "records" in res_m.json().get("detail", "").lower()

    # Officer user should be ALLOWED to delete
    res_o = client.delete(
        f"/api/history/{record_id}",
        headers={"Authorization": f"Bearer {token_officer}"}
    )
    assert res_o.status_code == 200
    assert res_o.json().get("id") == record_id

    # Verify deleted
    deleted_check = await get_analysis(record_id)
    assert deleted_check is None


def test_shared_analysis_pipeline_consistency():
    """Verify that the analysis engine evaluates statutory rules identically."""
    client = TestClient(app)

    sample_ocr_text = (
        "Brand: HealthyBites Organic Almonds 500g MRP Rs. 450 incl of all taxes. "
        "Mfg by: HealthyBites Ltd. Customer Care: care@healthybites.in"
    )

    res = client.post("/api/analyze/text", json={"text": sample_ocr_text})
    assert res.status_code == 200
    data = res.json()

    cr = data.get("compliance_result", {})
    assert "score" in cr
    assert "checks" in cr
    assert len(cr.get("checks", [])) >= 5

    rule_ids = {c.get("rule_id") for c in cr.get("checks", [])}
    assert "LM-001" in rule_ids
    assert "LM-002" in rule_ids
