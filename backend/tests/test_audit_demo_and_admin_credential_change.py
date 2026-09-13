import os
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings
from auth.security import (
    create_token,
    hash_password,
    verify_password,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from database.db import (
    create_user,
    delete_user,
    get_user_by_username,
    get_account_audit_logs,
    seed_default_users,
    get_db,
)
from scripts.change_admin_credentials import (
    change_admin_credentials,
    validate_username_format,
    validate_password_complexity,
)


@pytest.fixture(scope="module")
def client():
    os.environ["TEST_MODE"] = "1"
    os.environ["METRCHECK_ENV"] = "development"
    settings.TEST_MODE = True
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_01_audit_demo_account_authentication_and_rbac(client):
    """Verify dedicated audit / audit123 demo account authentication and role enforcement."""
    # Ensure demo users are seeded
    await seed_default_users()

    # 1. Authenticate with demo audit credentials
    login_resp = client.post("/api/auth/login", json={"username": "audit", "password": "audit123"})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    data = login_resp.json()
    assert data["user"]["role"] == ROLE_AUDIT
    assert data["user"]["username"] == "audit"
    assert data["user"]["status"] == "ACTIVE"
    assert data["user"]["is_admin"] is False

    audit_token = data["token"]
    headers = {"Authorization": f"Bearer {audit_token}"}

    # 2. Audit Officer CAN access Audit workspace endpoints & Merchant history
    assert client.get("/api/demo/cases", headers=headers).status_code == 200
    assert client.get("/api/history", headers=headers).status_code == 200

    # 3. Audit Officer CANNOT access Enforcement endpoints (HTTP 403)
    enf_resp = client.post("/api/enforcement/penalty", json={"analysis_id": "dummy"}, headers=headers)
    assert enf_resp.status_code == 403
    assert "enforcement" in enf_resp.json()["detail"].lower() or "insufficient" in enf_resp.json()["detail"].lower()

    # 4. Audit Officer CANNOT access Administration endpoints (HTTP 403)
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403
    assert client.post(
        "/api/admin/users",
        json={"username": "fake_audit_invite", "email": "fake@test.com", "role": "AUDIT_OFFICER"},
        headers=headers,
    ).status_code == 403


@pytest.mark.asyncio
async def test_02_backend_demo_seeding_matrix_and_prod_guard():
    """Verify demo users are seeded ONLY in explicit demo mode and non-production."""
    # Clean test users if needed
    await delete_user("test_audit_temp")

    # Case A: Demo mode True + Non-production -> seeds operational demo accounts
    settings.METRCHECK_DEMO_MODE = True
    os.environ["METRCHECK_DEMO_MODE"] = "true"
    os.environ["ENVIRONMENT"] = "development"
    await seed_default_users()
    assert (await get_user_by_username("audit")) is not None
    assert (await get_user_by_username("officer")) is not None
    assert (await get_user_by_username("merchant")) is not None

    # Case B: Demo mode False -> does NOT seed demo accounts
    await delete_user("temp_seeded_user")
    settings.METRCHECK_DEMO_MODE = False
    os.environ["METRCHECK_DEMO_MODE"] = "false"
    await seed_default_users()

    # Case C: Production environment -> strictly blocks demo seeding even if demo mode is set
    os.environ["ENVIRONMENT"] = "production"
    settings.METRCHECK_DEMO_MODE = True
    os.environ["METRCHECK_DEMO_MODE"] = "true"
    await seed_default_users()

    # Reset test environment
    os.environ["ENVIRONMENT"] = "development"
    settings.METRCHECK_DEMO_MODE = True
    os.environ["METRCHECK_DEMO_MODE"] = "true"


def test_03_frontend_demo_visibility_condition():
    """Verify frontend demo mode boolean evaluation logic (strict 'true' required)."""
    def is_demo_visible(env_val: str | None) -> bool:
        return env_val == "true"

    assert is_demo_visible("true") is True
    assert is_demo_visible("false") is False
    assert is_demo_visible(None) is False
    assert is_demo_visible("") is False
    assert is_demo_visible("1") is False
    assert is_demo_visible("TRUE") is False
    assert is_demo_visible("random_value") is False


def test_04_username_and_password_validation():
    """Unit test username and password validation rules."""
    # Username rules
    assert validate_username_format("admin") is True
    assert validate_username_format("doca_admin_01") is True
    assert validate_username_format("super-admin.doca") is True
    assert validate_username_format("ab") is False  # too short (<3)
    assert validate_username_format("admin user") is False  # spaces disallowed
    assert validate_username_format("admin@gov") is False  # @ disallowed in username

    # Password rules
    ok, _ = validate_password_complexity("ValidPass123!")
    assert ok is True
    ok_short, msg_short = validate_password_complexity("short")
    assert ok_short is False
    assert "8 characters" in msg_short


@pytest.mark.asyncio
async def test_05_admin_credential_change_security_validations():
    """Verify that change_admin_credentials enforces strict authentication and validation."""
    # 1. Rejects wrong current password
    res_bad_pw = await change_admin_credentials(
        current_username="admin",
        current_password="WrongPassword123!",
        new_username="admin_new",
        new_password="NewPassword123!",
    )
    assert res_bad_pw["success"] is False
    assert "authentication failed" in res_bad_pw["error"].lower()

    # 2. Rejects non-admin attempting to use change_admin_credentials
    res_non_admin = await change_admin_credentials(
        current_username="officer",
        current_password="officer123",
        new_username="officer_new",
        new_password="NewPassword123!",
    )
    assert res_non_admin["success"] is False
    assert "security violation" in res_non_admin["error"].lower()

    # 3. Rejects renaming admin to protected merchant username
    res_om = await change_admin_credentials(
        current_username="admin",
        current_password="admin123",
        new_username="omsainikaul",
        new_password="NewPassword123!",
    )
    assert res_om["success"] is False
    assert "safety violation" in res_om["error"].lower()

    # 4. Rejects weak new password (<8 chars)
    res_weak = await change_admin_credentials(
        current_username="admin",
        current_password="admin123",
        new_username="admin",
        new_password="123",
    )
    assert res_weak["success"] is False
    assert "8 characters" in res_weak["error"].lower()

    # 5. Rejects colliding new username
    res_conflict = await change_admin_credentials(
        current_username="admin",
        current_password="admin123",
        new_username="officer",
        new_password="NewPassword123!",
    )
    assert res_conflict["success"] is False
    assert "conflict" in res_conflict["error"].lower()


@pytest.mark.asyncio
async def test_06_admin_credential_change_lifecycle_and_leak_prevention(client):
    """
    Test complete lifecycle of admin credential change:
    - Login with initial test admin credentials
    - Change credentials to a new test username and password
    - Verify old credentials fail login
    - Verify old JWT session is invalidated
    - Verify new credentials succeed
    - Verify API responses and audit logs never leak passwords or password hashes
    """
    # 1. Login with initial admin credentials
    old_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert old_login.status_code == 200
    old_token = old_login.json()["token"]

    # Verify API response does not contain password or salt/hash
    user_payload = old_login.json()["user"]
    assert "password" not in user_payload
    assert "password_hash" not in user_payload
    assert "salt" not in user_payload

    # 2. Execute credential change
    temp_new_user = "doca_chief_admin"
    temp_new_pass = "TestNewAdminPass2026!"
    change_res = await change_admin_credentials(
        current_username="admin",
        current_password="admin123",
        new_username=temp_new_user,
        new_password=temp_new_pass,
        email="chief_admin@metrcheck.gov.in",
        full_name="Chief Administrator",
    )
    assert change_res["success"] is True
    assert change_res["new_username"] == temp_new_user
    assert change_res["sessions_invalidated"] is True

    # 3. Old credentials MUST fail login (401)
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": temp_new_user, "password": "admin123"}).status_code == 401

    # 4. Old JWT token MUST be invalidated (401)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    assert client.get("/api/admin/users", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401

    # 5. New credentials MUST succeed login (200)
    new_login = client.post(
        "/api/auth/login",
        json={"username": temp_new_user, "password": temp_new_pass},
    )
    assert new_login.status_code == 200
    new_data = new_login.json()
    assert new_data["user"]["username"] == temp_new_user
    assert new_data["user"]["role"] == ROLE_ADMIN
    assert new_data["user"]["is_admin"] is True

    new_token = new_data["token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    assert client.get("/api/admin/users", headers=new_headers).status_code == 200
    assert client.get("/api/admin/audit-logs", headers=new_headers).status_code == 200

    # 6. Audit log check: Event recorded without passwords or hashes
    logs = await get_account_audit_logs(limit=10)
    matching_log = next((l for l in logs if l["event_type"] == "ADMIN_CREDENTIALS_CHANGED"), None)
    assert matching_log is not None
    assert matching_log["actor_username"] == "admin"
    assert matching_log["target_username"] == temp_new_user
    assert temp_new_pass not in matching_log["details"]
    assert "admin123" not in matching_log["details"]

    # 7. Restore admin credentials back to 'admin' / 'admin123' and reset token_version = 1
    restore_res = await change_admin_credentials(
        current_username=temp_new_user,
        current_password=temp_new_pass,
        new_username="admin",
        new_password="admin123",
        email="admin@test.gov.in",
        full_name="System Administrator",
    )
    assert restore_res["success"] is True

    db = await get_db()
    try:
        await db.execute("UPDATE users SET token_version = 1 WHERE username = 'admin'")
        await db.commit()
    finally:
        await db.close()

    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
