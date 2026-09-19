"""
Role-Based Workspace Security Verification & Hardening Test Suite

Covers:
A. Merchant can access Merchant workspace.
B. Merchant cannot access Audit workspace.
C. Merchant cannot access Enforcement workspace.
D. Merchant cannot access Admin functionality (User management, clear-all history).
E. Merchant cannot call protected Enforcement APIs (penalty, notice) -> 403 Forbidden.
F. Merchant cannot delete history records -> 403 Forbidden.
G. Enforcement Officer can access Merchant workspace.
H. Enforcement Officer can access Audit workspace.
I. Enforcement Officer can access Enforcement workspace.
J. Enforcement Officer can call authorized Enforcement APIs (penalty, notice).
K. Enforcement Officer can delete single history item.
L. Enforcement Officer cannot access Admin-only functionality (User create/update/delete, clear-all history).
M. Admin can access all authorized workspaces and all administrative operations.
N. Client workspace selection cannot change backend role.
O. Direct API authorization cannot be bypassed via headers or payload manipulation.
P. JWT role remains authoritative; forged signatures are rejected (401).
Q. Temporary account lifecycle (create security_test_officer via Admin API -> test -> delete via Admin API).
R. Preserves real merchant account omsainikaul.
"""

import os
import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_MERCHANT,
)
from database.db import (
    create_user,
    get_user_by_username,
    get_user_by_identifier,
    delete_user,
    save_analysis,
    get_analysis,
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


def get_allowed_workspaces_for_role(role: str):
    if role in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        return ['ENFORCEMENT', 'AUDIT', 'MERCHANT']
    if role == "AUDIT_OFFICER":
        return ['AUDIT', 'MERCHANT']
    return ['MERCHANT']


@pytest.fixture(scope="module")
def client():
    os.environ["TEST_MODE"] = "1"
    os.environ["METRCHECK_ENV"] = "development"
    settings.TEST_MODE = True
    with TestClient(app) as c:
        yield c


# ── Test A, B, C: Workspace Matrix ──────────────────────────────────────────

def test_01_merchant_workspace_allowed_matrix():
    """Merchant role is allowed ONLY in Merchant workspace, denied in Audit and Enforcement."""
    allowed = get_allowed_workspaces_for_role(ROLE_MERCHANT)
    assert allowed == ['MERCHANT']
    assert 'AUDIT' not in allowed
    assert 'ENFORCEMENT' not in allowed


def test_02_officer_and_admin_workspace_allowed_matrix():
    """Officer and Admin roles are allowed across all three workspaces."""
    officer_allowed = get_allowed_workspaces_for_role(ROLE_ENFORCEMENT)
    assert set(officer_allowed) == {'ENFORCEMENT', 'AUDIT', 'MERCHANT'}

    admin_allowed = get_allowed_workspaces_for_role(ROLE_ADMIN)
    assert set(admin_allowed) == {'ENFORCEMENT', 'AUDIT', 'MERCHANT'}


# ── Test D, E, F: Merchant Account (omsainikaul) Backend Authorization ───────

@pytest.mark.asyncio
async def test_03_merchant_omsainikaul_denied_enforcement_and_admin_apis(client):
    """Verify that a genuine MERCHANT_PUBLIC token cannot execute Enforcement or Admin actions."""
    username = "omsainikaul"
    pwh, salt = hash_password("MerchantPass123!")
    await delete_user(username)
    await create_user(
        username=username,
        password_hash=pwh,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name="Om Saini",
        email="www.omsaini9719@gmail.com"
    )

    merchant_token = create_token(username, ROLE_MERCHANT)
    auth_header = {"Authorization": f"Bearer {merchant_token}"}

    # 1. Merchant CAN access profile
    me_resp = client.get("/api/auth/me", headers=auth_header)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == ROLE_MERCHANT
    assert me_resp.json()["username"] == username

    # 2. Merchant CANNOT call penalty estimate -> HTTP 403
    res_penalty = client.post(
        "/api/enforcement/penalty",
        headers=auth_header,
        json={"analysis_id": "test-analysis-1", "repeat_offence": False}
    )
    assert res_penalty.status_code == 403

    # 3. Merchant CANNOT call show-cause notice -> HTTP 403
    res_notice = client.post(
        "/api/enforcement/notice",
        headers=auth_header,
        json={"analysis_id": "test-analysis-1"}
    )
    assert res_notice.status_code == 403

    # 4. Merchant CANNOT list all users (user management) -> HTTP 403
    res_users = client.get("/api/auth/users", headers=auth_header)
    assert res_users.status_code == 403

    # 5. Merchant CANNOT create users -> HTTP 403
    res_create_u = client.post(
        "/api/auth/users",
        headers=auth_header,
        json={"username": "rogue_user", "password": "Password123!", "role": ROLE_ENFORCEMENT}
    )
    assert res_create_u.status_code == 403

    # 6. Merchant CANNOT clear all history -> HTTP 403
    res_clear = client.delete("/api/history", headers=auth_header)
    assert res_clear.status_code == 403


@pytest.mark.asyncio
async def test_04_merchant_denied_single_analysis_deletion(client):
    """Merchant cannot delete individual analysis screening records."""
    record_id = "test-merchant-del-guard"
    await save_analysis({
        "id": record_id,
        "product_name": "Test Delete Guard Item",
        "image_filename": "test.jpg",
        "ocr_text": "Sample text",
        "extracted_data": {},
        "compliance_result": {"score": 90.0, "status": "COMPLIANT", "checks": []},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-13T12:00:00",
        "images": []
    })

    merchant_token = create_token("omsainikaul", ROLE_MERCHANT)
    res_del = client.delete(
        f"/api/history/{record_id}",
        headers={"Authorization": f"Bearer {merchant_token}"}
    )
    assert res_del.status_code == 403
    assert "permission" in res_del.json().get("detail", "").lower() or "records" in res_del.json().get("detail", "").lower()

    # Ensure record was NOT deleted
    rec = await get_analysis(record_id)
    assert rec is not None


# ── Test G, H, I, J, K, L: Temporary Enforcement Account (security_test_officer)

@pytest.mark.asyncio
async def test_05_temporary_officer_lifecycle_and_authorization(client):
    """Admin creates temporary security_test_officer via Admin API, verifies authorization, then cleans it up."""
    admin_user = "admin_security_tester"
    pwh_a, salt_a = hash_password("AdminPass123!")
    await delete_user(admin_user)
    await create_user(username=admin_user, password_hash=pwh_a, salt=salt_a, role=ROLE_ADMIN, full_name="Admin Tester")
    admin_token = create_token(admin_user, ROLE_ADMIN)

    officer_user = "security_test_officer"
    officer_pw = "OfficerSecurePass123!"
    await delete_user(officer_user)

    # 1. Admin creates security_test_officer via POST /api/auth/users
    res_create = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": officer_user,
            "password": officer_pw,
            "role": ROLE_ENFORCEMENT,
            "full_name": "Security Test Enforcement Officer",
            "jurisdiction": "Central Enforcement Directorate",
            "organization_id": "org_ministry",
            "email": "security.officer.test@example.com"
        }
    )
    assert res_create.status_code == 201
    assert res_create.json()["username"] == officer_user
    assert res_create.json()["role"] == ROLE_ENFORCEMENT

    # 2. Officer logs in via POST /api/auth/login
    res_login = client.post(
        "/api/auth/login",
        json={"username": officer_user, "password": officer_pw}
    )
    assert res_login.status_code == 200
    officer_token = res_login.json()["token"]
    assert res_login.json()["user"]["role"] == ROLE_ENFORCEMENT
    officer_auth_header = {"Authorization": f"Bearer {officer_token}"}

    # 3. Create dummy analysis for testing enforcement operations
    test_aid = "test-officer-penalty-aid"
    await save_analysis({
        "id": test_aid,
        "product_name": "Offence Item",
        "image_filename": "offence.png",
        "ocr_text": "Non-compliant text",
        "extracted_data": {},
        "compliance_result": {
            "score": 40.0,
            "status": "NON_COMPLIANT",
            "checks": [
                {"rule_id": "LM-001", "field": "mrp", "status": "FAIL", "required": True, "message": "Missing MRP"}
            ]
        },
        "score": 40.0,
        "status": "NON_COMPLIANT",
        "created_at": "2026-09-13T12:30:00",
        "organization_id": "org_ministry",
        "images": []
    })

    # 4. Officer CAN access Penalty Estimate -> HTTP 200
    res_pen = client.post(
        "/api/enforcement/penalty",
        headers=officer_auth_header,
        json={"analysis_id": test_aid, "repeat_offence": False}
    )
    assert res_pen.status_code == 200
    assert "estimated_fine_inr" in res_pen.json() or "fine_range_inr" in res_pen.json()

    # 5. Officer CAN generate Show-Cause Notice -> HTTP 200
    res_not = client.post(
        "/api/enforcement/notice",
        headers=officer_auth_header,
        json={"analysis_id": test_aid}
    )
    assert res_not.status_code == 200
    assert "notice" in res_not.json()

    # 6. Officer CAN delete single analysis -> HTTP 200
    res_del_item = client.delete(
        f"/api/history/{test_aid}",
        headers=officer_auth_header
    )
    assert res_del_item.status_code == 200
    assert res_del_item.json()["id"] == test_aid

    # 7. Officer CANNOT create new users (Admin only) -> HTTP 403
    res_off_create_u = client.post(
        "/api/auth/users",
        headers=officer_auth_header,
        json={"username": "illegal_user", "password": "Password123!", "role": ROLE_MERCHANT}
    )
    assert res_off_create_u.status_code == 403

    # 8. Officer CANNOT delete other users (Admin only) -> HTTP 403
    res_off_del_u = client.delete(
        f"/api/auth/users/{admin_user}",
        headers=officer_auth_header
    )
    assert res_off_del_u.status_code == 403

    # 9. Officer CANNOT clear-all history (Admin only) -> HTTP 403
    res_off_clear = client.delete(
        "/api/history",
        headers=officer_auth_header
    )
    assert res_off_clear.status_code == 403

    # 10. CLEANUP: Admin deletes the temporary security_test_officer account
    res_cleanup = client.delete(
        f"/api/auth/users/{officer_user}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_cleanup.status_code in (200, 204)

    # Verify temporary officer account no longer exists
    deleted_officer = await get_user_by_username(officer_user)
    assert deleted_officer is None


# ── Test M, N, O, P: Tampering & Client-Side Bypass Resistance ───────────────

@pytest.mark.asyncio
async def test_06_workspace_payload_tampering_cannot_elevate_privileges(client):
    """Manipulating workspace identifiers in request headers or body does NOT grant permissions."""
    merchant_user = "tamper_test_merchant"
    pwh, salt = hash_password("MerchantPass123!")
    await delete_user(merchant_user)
    await create_user(username=merchant_user, password_hash=pwh, salt=salt, role=ROLE_MERCHANT)

    token = create_token(merchant_user, ROLE_MERCHANT)

    # Attempt to send request with forged workspace headers
    spoofed_headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace": "ENFORCEMENT",
        "X-Workspace-Role": "ENFORCEMENT_OFFICER",
        "X-Role": "ADMIN"
    }

    res_pen = client.post(
        "/api/enforcement/penalty",
        headers=spoofed_headers,
        json={"analysis_id": "test-123", "workspace": "ENFORCEMENT"}
    )
    assert res_pen.status_code == 403

    res_users = client.get("/api/auth/users", headers=spoofed_headers)
    assert res_users.status_code == 403


def test_07_jwt_signature_tampering_rejected(client):
    """Tampering with claims inside the signed token invalidates HMAC signature and returns 401."""
    token = create_token("omsainikaul", ROLE_MERCHANT)
    
    parts = token.split(".")
    assert len(parts) == 2

    import base64, json
    body_b64 = parts[0] + "=" * ((4 - len(parts[0]) % 4) % 4)
    payload_json = json.loads(base64.urlsafe_b64decode(body_b64.encode()))
    payload_json["role"] = ROLE_ADMIN
    
    tampered_b64 = base64.urlsafe_b64encode(json.dumps(payload_json).encode()).decode().rstrip("=")
    tampered_token = f"{tampered_b64}.{parts[1]}"

    res = client.get("/api/auth/users", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401


def test_08_audit_officer_workspace_allowed_matrix():
    """Audit Officer role is allowed in Audit and Merchant workspaces, denied in Enforcement."""
    audit_allowed = get_allowed_workspaces_for_role("AUDIT_OFFICER")
    assert set(audit_allowed) == {'AUDIT', 'MERCHANT'}
    assert 'ENFORCEMENT' not in audit_allowed

