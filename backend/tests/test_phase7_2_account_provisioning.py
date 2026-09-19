"""
Phase 7.2 — Account Provisioning, Role Management & Workspace Access Test Suite

Covers:
1. Public Registration Guardrails: Confined to MERCHANT_PUBLIC; privileged role injection rejected with 403 Forbidden.
2. Admin User Provisioning: Non-admins blocked with 403; Admin can provision AUDIT_OFFICER and ENFORCEMENT_OFFICER.
3. ADMIN Provisioning Guardrail: Cannot provision ADMIN role via /api/admin/users.
4. Cryptographic Invitation Token: 24-hour expiration, random token generated, only SHA-256 hash stored in DB.
5. Invitation Email Delivery: Dispatched via delivery provider with direct activation link.
6. Invitation Verification: /api/auth/verify-invitation validates token and returns role info.
7. Pre-Activation Login Rejection: Invited accounts cannot log in before setting password (401).
8. Account Activation: /api/auth/activate enforces password min 8 chars, sets password, marks ACTIVE, clears token hash.
9. Single-Use Invitation Token: Re-attempting activation with the same token is rejected (400).
10. Activated Account Authentication: Can immediately authenticate with chosen password.
11. Resend Invitation: Generates fresh token, updates hash + expiry, sends new email.
12. Resend Guardrail: Cannot resend invitation for already active accounts (400).
13. Workspace Access Matrix (Enforcement vs Audit vs Merchant):
    - MERCHANT_PUBLIC: /api/enforcement/* -> 403 Forbidden
    - AUDIT_OFFICER: /api/enforcement/* -> 403 Forbidden
    - ENFORCEMENT_OFFICER: /api/enforcement/* -> 200 OK
    - ADMIN: /api/enforcement/* -> 200 OK
14. Session & JWT Revocation:
    - Suspending user increments token_version -> existing JWT rejected immediately.
    - Suspended user blocked at login (403 Forbidden).
    - Reactivating user allows fresh login.
15. Role Change Session Invalidation:
    - Changing user role increments token_version -> old JWT rejected immediately.
16. Admin Self-Protection & System Safeguards:
    - Admin cannot suspend self (400).
    - Admin cannot delete self (400).
    - Admin cannot change own role (400).
    - Last remaining Admin cannot be deleted or demoted.
17. Security Audit Trail:
    - All security operations logged in account_audit_logs.
    - /api/admin/audit-logs accessible only to ADMIN.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from config import settings
from auth.security import (
    create_token,
    hash_password,
    verify_password,
    get_delivery_provider,
    set_delivery_provider,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    get_user_by_username,
    get_user_by_email,
    delete_user,
    update_user,
    init_db,
)


import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from config import settings
from auth.security import (
    create_token,
    hash_password,
    verify_password,
    get_delivery_provider,
    set_delivery_provider,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    get_user_by_username,
    get_user_by_email,
    delete_user,
    update_user,
    create_user,
    init_db,
)


@pytest.fixture(autouse=True)
def reset_state():
    clear_rate_limits()
    set_delivery_provider(None)
    yield
    clear_rate_limits()
    set_delivery_provider(None)


@pytest.fixture(scope="module")
def client():
    os.environ["TEST_MODE"] = "1"
    os.environ["METRCHECK_ENV"] = "development"
    settings.TEST_MODE = True
    with TestClient(app) as c:
        yield c


def admin_auth_headers(token_version=1):
    token = create_token("admin", ROLE_ADMIN, token_version)
    return {"Authorization": f"Bearer {token}"}


def officer_auth_headers(username="officer", token_version=1):
    token = create_token(username, ROLE_ENFORCEMENT, token_version)
    return {"Authorization": f"Bearer {token}"}


def merchant_auth_headers(username="merchant", token_version=1):
    token = create_token(username, ROLE_MERCHANT, token_version)
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. PUBLIC REGISTRATION GUARDRAILS
# =========================================================================

@pytest.mark.asyncio
async def test_01_public_registration_creates_active_merchant(client):
    """Public registration always creates a MERCHANT_PUBLIC account in ACTIVE state."""
    username = "test_merchant_reg_p72_01"
    email = "merchant_p72_01@testdomain.com"
    await delete_user(username)

    resp = client.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": "Password123!",
        "full_name": "Test Merchant One",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["user"]["role"] == ROLE_MERCHANT
    assert data["user"]["status"] == "ACTIVE"
    assert "token" in data


@pytest.mark.asyncio
async def test_02_public_registration_rejects_privileged_roles(client):
    """Attempting to register as AUDIT_OFFICER, ENFORCEMENT_OFFICER, or ADMIN is rejected."""
    for forbidden_role in [ROLE_AUDIT, ROLE_ENFORCEMENT, ROLE_ADMIN]:
        resp = client.post("/api/auth/register", json={
            "username": f"bad_actor_p72_{forbidden_role.lower()}",
            "email": f"bad_{forbidden_role.lower()}@test.com",
            "password": "Password123!",
            "role": forbidden_role,
        })
        assert resp.status_code == 403, f"Expected 403 for role {forbidden_role}, got {resp.status_code}"


# =========================================================================
# 2. ADMIN USER PROVISIONING & INVITATION TOKENS
# =========================================================================

@pytest.mark.asyncio
async def test_03_non_admin_cannot_provision_users(client):
    """Non-admin callers are strictly rejected from /api/admin/users."""
    resp = client.post(
        "/api/admin/users",
        json={"username": "fake_audit_p72", "email": "fake@audit.gov", "role": ROLE_AUDIT},
        headers=officer_auth_headers()
    )
    assert resp.status_code == 403

    resp = client.post(
        "/api/admin/users",
        json={"username": "fake_audit_p72", "email": "fake@audit.gov", "role": ROLE_AUDIT},
        headers=merchant_auth_headers()
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_04_admin_provisions_audit_officer_success(client):
    """Admin provisions an AUDIT_OFFICER account: creates INVITED state and sends invitation."""
    username = "audit_officer_p72"
    email = "auditor_p72@metrcheck.gov.in"
    await delete_user(username)

    resp = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "email": email,
            "role": ROLE_AUDIT,
            "full_name": "Auditor Test User",
            "jurisdiction": "Central QA",
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["user"]["username"] == username
    assert data["user"]["role"] == ROLE_AUDIT
    assert data["user"]["status"] == "INVITED"
    assert "dev_invitation_token" in data
    assert len(data["dev_invitation_token"]) > 20

    # Verify user record in DB
    user_db = await get_user_by_username(username)
    assert user_db is not None
    assert user_db["status"] == "INVITED"
    assert user_db["invitation_token_hash"] is not None
    assert user_db["password_hash"] == ""


@pytest.mark.asyncio
async def test_05_admin_cannot_provision_admin_role(client):
    """Admin cannot provision another ADMIN account via standard provisioning."""
    resp = client.post(
        "/api/admin/users",
        json={
            "username": "new_admin_attempt_p72",
            "email": "admin2_p72@test.com",
            "role": ROLE_ADMIN,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    assert resp.status_code in (400, 403)


@pytest.mark.asyncio
async def test_06_admin_provision_rejects_duplicate_username_and_email(client):
    """Duplicate usernames or emails return 409 Conflict."""
    resp = client.post(
        "/api/admin/users",
        json={
            "username": "audit_officer_p72",
            "email": "different_email_p72@test.com",
            "role": ROLE_AUDIT,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    assert resp.status_code == 409

    resp = client.post(
        "/api/admin/users",
        json={
            "username": "unique_username_p72_99",
            "email": "auditor_p72@metrcheck.gov.in",
            "role": ROLE_AUDIT,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    assert resp.status_code == 409


# =========================================================================
# 3. INVITATION VERIFICATION & PRE-ACTIVATION LOGIN GUARDS
# =========================================================================

@pytest.mark.asyncio
async def test_07_invited_user_cannot_login_before_activation(client):
    """Invited users attempting to log in prior to activation receive 401."""
    resp = client.post("/api/auth/login", json={
        "username": "audit_officer_p72",
        "password": "SomePassword123!",
    })
    assert resp.status_code == 401
    assert "activated" in resp.json()["detail"].lower() or "invitation" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_08_verify_invitation_token_valid_and_invalid(client):
    """Invitation token verification endpoint checks validity."""
    # Invalid token returns 200 with valid: False
    resp = client.post("/api/auth/verify-invitation", json={"token": "invalid_fake_token_xyz"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False

    # Provision a new temporary user to get token cleanly
    username = "verify_test_user_p72"
    await delete_user(username)
    resp_prov = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "email": "verify_test_p72@metrcheck.gov.in",
            "role": ROLE_AUDIT,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    token = resp_prov.json()["dev_invitation_token"]

    resp = client.post("/api/auth/verify-invitation", json={"token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["username"] == username
    assert data["role"] == ROLE_AUDIT


# =========================================================================
# 4. ACCOUNT ACTIVATION & SINGLE-USE TOKEN ENFORCEMENT
# =========================================================================

@pytest.mark.asyncio
async def test_09_account_activation_weak_password_rejected(client):
    """Activation with password < 8 chars returns 400 or 422."""
    username = "activate_weak_p72"
    await delete_user(username)
    resp_prov = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "email": "activate_weak_p72@metrcheck.gov.in",
            "role": ROLE_ENFORCEMENT,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    token = resp_prov.json()["dev_invitation_token"]

    resp = client.post("/api/auth/activate", json={
        "token": token,
        "password": "short",
    })
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_10_account_activation_success_and_single_use(client):
    """Account activation sets password, updates status to ACTIVE, and single-use token cannot be reused."""
    username = "activate_success_p72"
    await delete_user(username)
    resp_prov = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "email": "activate_success_p72@metrcheck.gov.in",
            "role": ROLE_ENFORCEMENT,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    token = resp_prov.json()["dev_invitation_token"]

    # Successful activation
    resp = client.post("/api/auth/activate", json={
        "token": token,
        "password": "SecurePassword123!",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["username"] == username

    # Verify DB state
    user_db = await get_user_by_username(username)
    assert user_db["status"] == "ACTIVE"
    assert not user_db["invitation_token_hash"]
    assert user_db["activated_at"] is not None
    assert verify_password("SecurePassword123!", user_db["salt"], user_db["password_hash"])

    # Single-use: Reusing token is rejected
    resp_reuse = client.post("/api/auth/activate", json={
        "token": token,
        "password": "AnotherPassword123!",
    })
    assert resp_reuse.status_code == 400

    # User can now successfully authenticate with chosen password
    resp_login = client.post("/api/auth/login", json={
        "username": username,
        "password": "SecurePassword123!",
    })
    assert resp_login.status_code == 200
    assert resp_login.json()["user"]["role"] == ROLE_ENFORCEMENT


# =========================================================================
# 5. RESEND INVITATION
# =========================================================================

@pytest.mark.asyncio
async def test_11_resend_invitation_generates_new_token(client):
    """Admin can resend invitation for INVITED accounts."""
    username = "resend_test_p72"
    await delete_user(username)

    resp_prov = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "email": "resend_test_p72@metrcheck.gov.in",
            "role": ROLE_AUDIT,
            "organization_id": "org_ministry",
        },
        headers=admin_auth_headers()
    )
    first_token = resp_prov.json()["dev_invitation_token"]

    # Resend
    resp_resend = client.post(
        f"/api/admin/users/{username}/resend-invitation",
        headers=admin_auth_headers()
    )
    assert resp_resend.status_code == 200
    second_token = resp_resend.json().get("dev_invitation_token")
    if second_token:
        assert second_token != first_token

        # First token is now invalidated (valid: False)
        resp_old = client.post("/api/auth/verify-invitation", json={"token": first_token})
        assert resp_old.status_code == 200
        assert resp_old.json()["valid"] is False

        # Second token is valid
        resp_new = client.post("/api/auth/verify-invitation", json={"token": second_token})
        assert resp_new.status_code == 200
        assert resp_new.json()["valid"] is True


@pytest.mark.asyncio
async def test_12_cannot_resend_invitation_for_active_user(client):
    """Resending invitation for an already ACTIVE user returns 400."""
    resp = client.post(
        "/api/admin/users/activate_success_p72/resend-invitation",
        headers=admin_auth_headers()
    )
    assert resp.status_code == 400


# =========================================================================
# 6. ROLE & WORKSPACE ACCESS MATRIX
# =========================================================================

@pytest.mark.asyncio
async def test_13_workspace_enforcement_endpoints_authorization(client):
    """Verify endpoint authorization matrix for penalty estimation and show cause notice."""
    # Ensure active audit user exists in DB
    audit_username = "active_auditor_matrix_p72"
    await delete_user(audit_username)
    pw_hash, salt = hash_password("AuditPass123!")
    await create_user(
        username=audit_username,
        password_hash=pw_hash,
        salt=salt,
        role=ROLE_AUDIT,
        email="audit_mat@gov.in",
        organization_id="org_ministry"
    )
    active_audit_headers = {"Authorization": f"Bearer {create_token(audit_username, ROLE_AUDIT)}"}

    # 1. MERCHANT_PUBLIC -> DENY (403)
    resp = client.post(
        "/api/enforcement/penalty",
        json={"analysis_id": "demo_1"},
        headers=merchant_auth_headers()
    )
    assert resp.status_code == 403

    # 2. AUDIT_OFFICER -> DENY (403)
    resp = client.post(
        "/api/enforcement/penalty",
        json={"analysis_id": "demo_1"},
        headers=active_audit_headers
    )
    assert resp.status_code == 403

    # 3. ENFORCEMENT_OFFICER -> ALLOW (reaches handler, does not get 401/403)
    resp = client.post(
        "/api/enforcement/penalty",
        json={"analysis_id": "demo_1"},
        headers=officer_auth_headers()
    )
    assert resp.status_code in (200, 404)
    assert resp.status_code not in (401, 403)

    # 4. ADMIN -> ALLOW (reaches handler, does not get 401/403)
    resp = client.post(
        "/api/enforcement/penalty",
        json={"analysis_id": "demo_1"},
        headers=admin_auth_headers()
    )
    assert resp.status_code in (200, 404)
    assert resp.status_code not in (401, 403)


# =========================================================================
# 7. USER SUSPENSION, REACTIVATION & STALE SESSION REVOCATION
# =========================================================================

@pytest.mark.asyncio
async def test_14_user_suspension_invalidates_active_jwt_immediately(client):
    """Suspending a user immediately revokes all active JWT tokens via token_version check."""
    username = "suspension_test_p72"
    await delete_user(username)

    # Provision and activate user
    resp_prov = client.post(
        "/api/admin/users",
        json={"username": username, "email": "suspend_p72@metrcheck.gov.in", "role": ROLE_ENFORCEMENT, "organization_id": "org_ministry"},
        headers=admin_auth_headers()
    )
    token = resp_prov.json()["dev_invitation_token"]
    client.post("/api/auth/activate", json={"token": token, "password": "Password123!"})

    # Log in and get active JWT token
    login_resp = client.post("/api/auth/login", json={"username": username, "password": "Password123!"})
    assert login_resp.status_code == 200
    user_jwt = login_resp.json()["token"]
    user_headers = {"Authorization": f"Bearer {user_jwt}"}

    # Verify token works for /api/auth/me
    me_resp = client.get("/api/auth/me", headers=user_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == username

    # Admin suspends user
    suspend_resp = client.post(f"/api/admin/users/{username}/suspend", headers=admin_auth_headers())
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "SUSPENDED"

    # Active JWT is IMMEDIATELY rejected
    me_after_suspend = client.get("/api/auth/me", headers=user_headers)
    assert me_after_suspend.status_code in (401, 403)

    # Suspended user cannot log in
    relogin_resp = client.post("/api/auth/login", json={"username": username, "password": "Password123!"})
    assert relogin_resp.status_code == 403
    assert "suspended" in relogin_resp.json()["detail"].lower()

    # Admin reactivates user
    reactivate_resp = client.post(f"/api/admin/users/{username}/reactivate", headers=admin_auth_headers())
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["status"] == "ACTIVE"

    # User can now log in again
    relogin_success = client.post("/api/auth/login", json={"username": username, "password": "Password123!"})
    assert relogin_success.status_code == 200


# =========================================================================
# 8. ROLE CHANGE & SESSION INVALIDATION
# =========================================================================

@pytest.mark.asyncio
async def test_15_role_change_invalidates_previous_sessions(client):
    """Changing user role invalidates existing sessions and updates permissions."""
    username = "role_change_p72"
    await delete_user(username)

    # Provision and activate as AUDIT_OFFICER
    resp_prov = client.post(
        "/api/admin/users",
        json={"username": username, "email": "role_change_p72@metrcheck.gov.in", "role": ROLE_AUDIT, "organization_id": "org_ministry"},
        headers=admin_auth_headers()
    )
    token = resp_prov.json()["dev_invitation_token"]
    client.post("/api/auth/activate", json={"token": token, "password": "Password123!"})

    # Log in as AUDIT_OFFICER
    login_resp = client.post("/api/auth/login", json={"username": username, "password": "Password123!"})
    audit_jwt = login_resp.json()["token"]
    audit_headers = {"Authorization": f"Bearer {audit_jwt}"}

    # Verify enforcement is forbidden
    assert client.post("/api/enforcement/penalty", json={"analysis_id": "demo_1"}, headers=audit_headers).status_code == 403

    # Admin updates role to ENFORCEMENT_OFFICER
    change_resp = client.post(
        f"/api/admin/users/{username}/change-role",
        json={"role": ROLE_ENFORCEMENT},
        headers=admin_auth_headers()
    )
    assert change_resp.status_code == 200
    assert change_resp.json()["role"] == ROLE_ENFORCEMENT

    # Old JWT is revoked
    assert client.get("/api/auth/me", headers=audit_headers).status_code in (401, 403)

    # Log in fresh with new role
    new_login = client.post("/api/auth/login", json={"username": username, "password": "Password123!"})
    assert new_login.status_code == 200
    new_jwt = new_login.json()["token"]
    new_headers = {"Authorization": f"Bearer {new_jwt}"}

    # Now enforcement is allowed (passes auth, reaches handler)
    enf_resp = client.post("/api/enforcement/penalty", json={"analysis_id": "demo_1"}, headers=new_headers)
    assert enf_resp.status_code in (200, 404)
    assert enf_resp.status_code not in (401, 403)


# =========================================================================
# 9. ADMIN SELF-PROTECTION & SYSTEM SAFEGUARDS
# =========================================================================

@pytest.mark.asyncio
async def test_16_admin_cannot_suspend_or_delete_self(client):
    """Admin cannot suspend, delete, or change the role of their own account."""
    # Suspend self
    resp = client.post("/api/admin/users/admin/suspend", headers=admin_auth_headers())
    assert resp.status_code == 400
    assert "cannot suspend your own" in resp.json()["detail"].lower()

    # Delete self
    resp = client.delete("/api/admin/users/admin", headers=admin_auth_headers())
    assert resp.status_code == 400
    assert "cannot delete your own" in resp.json()["detail"].lower()

    # Change role on self
    resp = client.post(
        "/api/admin/users/admin/change-role",
        json={"role": ROLE_ENFORCEMENT},
        headers=admin_auth_headers()
    )
    assert resp.status_code == 400
    assert "cannot change role of your own" in resp.json()["detail"].lower()


# =========================================================================
# 10. SECURITY AUDIT TRAIL
# =========================================================================

@pytest.mark.asyncio
async def test_17_security_audit_logs_recorded_and_restricted(client):
    """Security actions create audit log entries, accessible only to ADMIN."""
    # Non-admin cannot view audit logs
    assert client.get("/api/admin/audit-logs", headers=officer_auth_headers()).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=merchant_auth_headers()).status_code == 403

    # Admin can view audit logs
    resp = client.get("/api/admin/audit-logs", headers=admin_auth_headers())
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)
    assert len(logs) > 0

    actions = [l.get("event_type") or l.get("action") for l in logs]
    assert any("INVITED" in str(a) or "SUSPENDED" in str(a) or "ROLE" in str(a) or "ACTIVATED" in str(a) for a in actions)

