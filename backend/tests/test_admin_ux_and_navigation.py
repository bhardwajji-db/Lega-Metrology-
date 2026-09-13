import os
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings
from auth.security import create_token, hash_password, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT
from database.db import create_user, get_db

@pytest.fixture(scope="module")
def client():
    os.environ["TEST_MODE"] = "1"
    os.environ["METRCHECK_ENV"] = "development"
    settings.TEST_MODE = True
    with TestClient(app) as c:
        yield c

@pytest.mark.asyncio
async def test_01_admin_workspace_and_admin_api_access(client):
    # 1. Admin login
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200
    token = admin_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Admin access to all 3 workspaces
    assert client.get("/api/history", headers=headers).status_code == 200        # Merchant
    assert client.get("/api/demo/cases", headers=headers).status_code == 200     # Audit
    assert client.post("/api/enforcement/penalty", json={"analysis_id": "dummy"}, headers=headers).status_code == 404 # Enforcement (404 = authorized)

    # Admin access to Administration endpoints
    users_resp = client.get("/api/admin/users", headers=headers)
    assert users_resp.status_code == 200
    assert isinstance(users_resp.json(), list)

    audit_resp = client.get("/api/admin/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    assert isinstance(audit_resp.json(), list)


@pytest.mark.asyncio
async def test_02_enforcement_officer_cannot_access_admin_apis(client):
    # Setup Enforcement Officer
    pw_hash, salt = hash_password("OfficerPass123!")
    await create_user("officer_ux_test", pw_hash, salt, ROLE_ENFORCEMENT, email="officer_ux@test.gov.in")
    
    login_resp = client.post("/api/auth/login", json={"username": "officer_ux_test", "password": "OfficerPass123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Allowed in Merchant, Audit, Enforcement
    assert client.get("/api/history", headers=headers).status_code == 200
    assert client.get("/api/demo/cases", headers=headers).status_code == 200
    assert client.post("/api/enforcement/penalty", json={"analysis_id": "dummy"}, headers=headers).status_code == 404

    # FORBIDDEN in Administration APIs
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403
    assert client.post("/api/admin/users", json={"username": "fake", "email": "fake@test.com", "role": "AUDIT_OFFICER"}, headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_03_audit_officer_cannot_access_admin_or_enforcement_apis(client):
    # Setup Audit Officer
    pw_hash, salt = hash_password("AuditPass123!")
    await create_user("audit_ux_test", pw_hash, salt, ROLE_AUDIT, email="audit_ux@test.gov.in")

    login_resp = client.post("/api/auth/login", json={"username": "audit_ux_test", "password": "AuditPass123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Allowed in Audit
    assert client.get("/api/demo/cases", headers=headers).status_code == 200

    # FORBIDDEN in Enforcement
    assert client.post("/api/enforcement/penalty", json={"analysis_id": "dummy"}, headers=headers).status_code == 403

    # FORBIDDEN in Administration APIs
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_04_merchant_cannot_access_admin_or_enforcement_apis(client):
    # Merchant login
    pw_hash, salt = hash_password("MerchantPass123!")
    await create_user("merchant_ux_test", pw_hash, salt, ROLE_MERCHANT, email="merchant_ux@test.com")

    login_resp = client.post("/api/auth/login", json={"username": "merchant_ux_test", "password": "MerchantPass123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Allowed in Merchant history
    assert client.get("/api/history", headers=headers).status_code == 200

    # FORBIDDEN in Enforcement
    assert client.post("/api/enforcement/penalty", json={"analysis_id": "dummy"}, headers=headers).status_code == 403

    # FORBIDDEN in Administration APIs
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_05_admin_portal_authentication_and_user_response(client):
    """Admin credentials authenticate successfully with authoritative ADMIN role."""
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["role"] == ROLE_ADMIN
    assert data["user"]["is_admin"] is True
    assert "token" in data

    token = data["token"]
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == ROLE_ADMIN


@pytest.mark.asyncio
async def test_06_public_registration_cannot_create_admin_account(client):
    """Public registration cannot fabricate an ADMIN role."""
    reg_resp = client.post("/api/auth/register", json={
        "username": "attacker_admin_attempt",
        "email": "attacker@example.com",
        "password": "Password123!",
        "role": ROLE_ADMIN
    })
    assert reg_resp.status_code == 403
    assert "administrator" in reg_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_07_workspace_header_or_payload_cannot_elevate_non_admin(client):
    """Client cannot supply headers or payload fields to bypass admin restrictions."""
    merchant_login = client.post("/api/auth/login", json={"username": "merchant", "password": "merchant123"})
    assert merchant_login.status_code == 200
    m_token = merchant_login.json()["token"]

    spoofed_headers = {
        "Authorization": f"Bearer {m_token}",
        "X-Role": "ADMIN",
        "X-Workspace": "ADMINISTRATION"
    }
    assert client.get("/api/admin/users", headers=spoofed_headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=spoofed_headers).status_code == 403
    assert client.post("/api/admin/users", json={"username": "hacked", "email": "hacked@test.com", "role": "ADMIN"}, headers=spoofed_headers).status_code == 403

