"""
MetrCheck AI — Dedicated Tenant Data Isolation & Database Integrity Test Suite.

Comprehensive validation of fail-closed multi-tenancy rules:
- Merchant, Enforcement Officer, Audit Officer, Admin access control boundaries
- User provisioning and organization lifecycle validation
- Legacy data isolation (ADMIN-only for unassigned records)
- Request-level spoofing resistance and state mutation protection
"""

import os
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import (
    get_db,
    init_db,
    create_organization,
    get_organization,
    list_organizations,
    create_user,
    get_user_by_username,
    save_analysis,
    get_analysis,
    save_artwork,
    get_artwork,
    save_version_comparison,
    get_version_comparison,
    save_review,
    get_review,
    save_evidence_audit_log,
    get_evidence_audit_logs,
)
from auth.security import (
    hash_password,
    create_token,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _create_test_user(username: str, role: str, org_id: str = ""):
    salt, pwh = hash_password("TestPass123!")
    try:
        await create_user(
            username=username,
            password_hash=pwh,
            salt=salt,
            role=role,
            full_name=f"User {username}",
            organization_id=org_id,
        )
    except Exception:
        pass


def make_auth_headers(username: str, role: str) -> dict:
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. MERCHANT TENANT AUTHORIZATION (Tests 1-5)
# =============================================================================

@pytest.mark.asyncio
async def test_01_merchant_own_org_and_resource_allowed():
    """1. Merchant A -> own organization & own resource -> 200 OK."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_1", "Tenant One Corp", status="ACTIVE")
    await _create_test_user("merchant_1a", ROLE_MERCHANT, "org_tenant_1")

    ana_id = f"test-ana-1-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Product 1A",
        image_filename="p1a.png",
        extracted_data={"product_name": "Product 1A", "mrp": "100"},
        compliance_result={"score": 95.0, "status": "PASS", "checks": []},
        ocr_text="P1A text",
        owner_user_id="merchant_1a",
        organization_id="org_tenant_1",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_1a", ROLE_MERCHANT)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["id"] == ana_id


@pytest.mark.asyncio
async def test_02_merchant_cross_tenant_resource_denied():
    """2. Merchant A -> Merchant B resource (different org) -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_1", "Tenant One Corp", status="ACTIVE")
    await create_organization("org_tenant_2", "Tenant Two Corp", status="ACTIVE")
    await _create_test_user("merchant_1a", ROLE_MERCHANT, "org_tenant_1")
    await _create_test_user("merchant_2b", ROLE_MERCHANT, "org_tenant_2")

    ana_id = f"test-ana-2-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Secret Tenant 2 Product",
        image_filename="p2.png",
        extracted_data={"product_name": "Secret Tenant 2 Product", "mrp": "200"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="Secret",
        owner_user_id="merchant_2b",
        organization_id="org_tenant_2",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_1a", ROLE_MERCHANT)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_03_merchant_same_org_different_owner_denied():
    """3. Merchant A -> same organization but different merchant owner -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_shared", "Shared FMCG Org", status="ACTIVE")
    await _create_test_user("merchant_user_1", ROLE_MERCHANT, "org_shared")
    await _create_test_user("merchant_user_2", ROLE_MERCHANT, "org_shared")

    ana_id = f"test-ana-3-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Private Draft User 2",
        image_filename="p_user2.png",
        extracted_data={"product_name": "Private Draft User 2"},
        compliance_result={"score": 85.0, "status": "PASS", "checks": []},
        ocr_text="Private User 2",
        owner_user_id="merchant_user_2",
        organization_id="org_shared",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_user_1", ROLE_MERCHANT)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_04_merchant_empty_organization_denied():
    """4. Merchant with empty organization -> 403 Forbidden (fail-closed)."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("merchant_no_org", ROLE_MERCHANT, "")

    ana_id = f"test-ana-4-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Some Product",
        image_filename="p.png",
        extracted_data={"product_name": "Some Product"},
        compliance_result={"score": 80.0, "status": "PASS", "checks": []},
        ocr_text="Text",
        owner_user_id="merchant_no_org",
        organization_id="org_some_corp",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_no_org", ROLE_MERCHANT)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_05_merchant_accessing_unassigned_resource_denied():
    """5. Merchant accessing resource with empty organization -> 403 Forbidden (fail-closed)."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_merchant_m", "Merchant M Org", status="ACTIVE")
    await _create_test_user("merchant_m", ROLE_MERCHANT, "org_merchant_m")

    ana_id = f"test-ana-5-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Legacy Unassigned Product",
        image_filename="legacy.png",
        extracted_data={"product_name": "Legacy Unassigned Product"},
        compliance_result={"score": 75.0, "status": "PASS", "checks": []},
        ocr_text="Legacy",
        owner_user_id="",
        organization_id="",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_m", ROLE_MERCHANT)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


# =============================================================================
# 2. ENFORCEMENT OFFICER AUTHORIZATION (Tests 6-9)
# =============================================================================

@pytest.mark.asyncio
async def test_06_enforcement_same_org_allowed():
    """6. Officer A -> Organization A -> 200 OK."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_dept_north", "North Directorate", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("officer_north", ROLE_ENFORCEMENT, "org_dept_north")

    ana_id = f"test-ana-6-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="North Jurisdiction Product",
        image_filename="north.png",
        extracted_data={"product_name": "North Jurisdiction Product", "mrp": "150"},
        compliance_result={"score": 60.0, "status": "FAIL", "checks": [{"rule_id": "RULE_MRP", "status": "FAIL"}]},
        ocr_text="North",
        owner_user_id="merchant_north",
        organization_id="org_dept_north",
    )

    client = TestClient(app)
    headers = make_auth_headers("officer_north", ROLE_ENFORCEMENT)
    res = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": ana_id})
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_07_enforcement_cross_org_denied():
    """7. Officer A -> Organization B -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_dept_north", "North Directorate", org_type="REGULATOR", status="ACTIVE")
    await create_organization("org_dept_south", "South Directorate", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("officer_north", ROLE_ENFORCEMENT, "org_dept_north")

    ana_id = f"test-ana-7-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="South Jurisdiction Product",
        image_filename="south.png",
        extracted_data={"product_name": "South Jurisdiction Product", "mrp": "200"},
        compliance_result={"score": 50.0, "status": "FAIL", "checks": []},
        ocr_text="South",
        owner_user_id="merchant_south",
        organization_id="org_dept_south",
    )

    client = TestClient(app)
    headers = make_auth_headers("officer_north", ROLE_ENFORCEMENT)
    res = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": ana_id})
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_08_enforcement_empty_org_denied():
    """8. Officer with empty organization -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("officer_no_org", ROLE_ENFORCEMENT, "")

    ana_id = f"test-ana-8-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Any Product",
        image_filename="any.png",
        extracted_data={"product_name": "Any Product"},
        compliance_result={"score": 50.0, "status": "FAIL", "checks": []},
        ocr_text="Any",
        owner_user_id="merchant_x",
        organization_id="org_dept_north",
    )

    client = TestClient(app)
    headers = make_auth_headers("officer_no_org", ROLE_ENFORCEMENT)
    res = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": ana_id})
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_09_enforcement_unassigned_legacy_resource_denied():
    """9. Officer accessing unassigned legacy resource -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_dept_north", "North Directorate", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("officer_north", ROLE_ENFORCEMENT, "org_dept_north")

    ana_id = f"test-ana-9-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Legacy Unassigned Case",
        image_filename="legacy.png",
        extracted_data={"product_name": "Legacy Unassigned Case"},
        compliance_result={"score": 50.0, "status": "FAIL", "checks": []},
        ocr_text="Legacy",
        owner_user_id="",
        organization_id="",
    )

    client = TestClient(app)
    headers = make_auth_headers("officer_north", ROLE_ENFORCEMENT)
    res = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": ana_id})
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


# =============================================================================
# 3. AUDIT OFFICER AUTHORIZATION (Tests 10-13)
# =============================================================================

@pytest.mark.asyncio
async def test_10_audit_same_org_allowed():
    """10. Audit A -> Organization A -> 200 OK."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_audit_zone_a", "Audit Zone A", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("auditor_a", ROLE_AUDIT, "org_audit_zone_a")

    ana_id = f"test-ana-10-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Audit Target Product",
        image_filename="audit.png",
        extracted_data={"product_name": "Audit Target Product", "mrp": "120"},
        compliance_result={"score": 75.0, "status": "PASS", "checks": []},
        ocr_text="Audit text",
        owner_user_id="merchant_a",
        organization_id="org_audit_zone_a",
    )

    client = TestClient(app)
    headers = make_auth_headers("auditor_a", ROLE_AUDIT)
    res = client.get(f"/api/report/{ana_id}/json", headers=headers)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_11_audit_cross_org_denied():
    """11. Audit A -> Organization B -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_audit_zone_a", "Audit Zone A", org_type="REGULATOR", status="ACTIVE")
    await create_organization("org_audit_zone_b", "Audit Zone B", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("auditor_a", ROLE_AUDIT, "org_audit_zone_a")

    ana_id = f"test-ana-11-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Zone B Protected Dossier",
        image_filename="zone_b.png",
        extracted_data={"product_name": "Zone B Protected Dossier"},
        compliance_result={"score": 80.0, "status": "PASS", "checks": []},
        ocr_text="Zone B",
        owner_user_id="merchant_b",
        organization_id="org_audit_zone_b",
    )

    client = TestClient(app)
    headers = make_auth_headers("auditor_a", ROLE_AUDIT)
    res = client.get(f"/api/report/{ana_id}/json", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_12_audit_empty_org_denied():
    """12. Audit with empty organization -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("auditor_no_org", ROLE_AUDIT, "")

    ana_id = f"test-ana-12-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Audited Product",
        image_filename="aud.png",
        extracted_data={"product_name": "Audited Product"},
        compliance_result={"score": 80.0, "status": "PASS", "checks": []},
        ocr_text="Aud",
        owner_user_id="merchant_x",
        organization_id="org_audit_zone_a",
    )

    client = TestClient(app)
    headers = make_auth_headers("auditor_no_org", ROLE_AUDIT)
    res = client.get(f"/api/report/{ana_id}/json", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_13_audit_unassigned_legacy_resource_denied():
    """13. Audit accessing unassigned legacy resource -> 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_audit_zone_a", "Audit Zone A", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("auditor_a", ROLE_AUDIT, "org_audit_zone_a")

    ana_id = f"test-ana-13-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Unassigned Record",
        image_filename="unassigned.png",
        extracted_data={"product_name": "Unassigned Record"},
        compliance_result={"score": 80.0, "status": "PASS", "checks": []},
        ocr_text="Unassigned",
        owner_user_id="",
        organization_id="",
    )

    client = TestClient(app)
    headers = make_auth_headers("auditor_a", ROLE_AUDIT)
    res = client.get(f"/api/report/{ana_id}/json", headers=headers)
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"


# =============================================================================
# 4. ADMIN AUTHORIZATION (Tests 14-16)
# =============================================================================

@pytest.mark.asyncio
async def test_14_admin_access_org_a_allowed():
    """14. Admin -> Organization A -> 200 OK."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_a", "Tenant A", status="ACTIVE")
    await _create_test_user("admin_user_root", ROLE_ADMIN, "org_ministry")

    ana_id = f"test-ana-14-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Tenant A Product",
        image_filename="a.png",
        extracted_data={"product_name": "Tenant A Product"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="A",
        owner_user_id="merchant_a",
        organization_id="org_tenant_a",
    )

    client = TestClient(app)
    headers = make_auth_headers("admin_user_root", ROLE_ADMIN)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_15_admin_access_org_b_allowed():
    """15. Admin -> Organization B -> 200 OK."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_b", "Tenant B", status="ACTIVE")
    await _create_test_user("admin_user_root", ROLE_ADMIN, "org_ministry")

    ana_id = f"test-ana-15-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Tenant B Product",
        image_filename="b.png",
        extracted_data={"product_name": "Tenant B Product"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="B",
        owner_user_id="merchant_b",
        organization_id="org_tenant_b",
    )

    client = TestClient(app)
    headers = make_auth_headers("admin_user_root", ROLE_ADMIN)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_16_admin_access_unassigned_legacy_resource_allowed():
    """16. Admin -> legacy/unassigned resource -> allowed (statutory oversight)."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("admin_user_root", ROLE_ADMIN, "org_ministry")

    ana_id = f"test-ana-16-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Legacy Unassigned System Record",
        image_filename="legacy.png",
        extracted_data={"product_name": "Legacy Unassigned System Record"},
        compliance_result={"score": 85.0, "status": "PASS", "checks": []},
        ocr_text="Legacy",
        owner_user_id="",
        organization_id="",
    )

    client = TestClient(app)
    headers = make_auth_headers("admin_user_root", ROLE_ADMIN)
    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 200, res.text


# =============================================================================
# 5. PROVISIONING & ORGANIZATION VALIDATION (Tests 17-25)
# =============================================================================

@pytest.mark.asyncio
async def test_17_merchant_registration_creates_valid_organization():
    """17. Merchant registration creates a valid active organization."""
    _ensure_test_isolation()
    await init_db()
    client = TestClient(app)
    uname = f"mreg_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "Password123!",
        "organization_name": "Dedicated FMCG Hub",
    })
    assert res.status_code == 201, res.text
    org = await get_organization(f"org_{uname}")
    assert org is not None
    assert org["status"] == "ACTIVE"
    assert org["name"] == "Dedicated FMCG Hub"


@pytest.mark.asyncio
async def test_18_new_merchant_assigned_created_organization():
    """18. New merchant user record in DB has the expected organization_id."""
    _ensure_test_isolation()
    await init_db()
    client = TestClient(app)
    uname = f"mreg_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "Password123!",
    })
    assert res.status_code == 201, res.text
    user = await get_user_by_username(uname)
    assert user is not None
    assert user["organization_id"] == f"org_{uname}"


@pytest.mark.asyncio
async def test_19_admin_provisioning_merchant_valid_org():
    """19. Admin provisioning of merchant with valid organization succeeds."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_valid_merchant", "Valid Merchant Corp", status="ACTIVE")
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"m_prov_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "Password123!",
        "role": ROLE_MERCHANT,
        "organization_id": "org_valid_merchant",
    })
    assert res.status_code == 201, res.text
    user = await get_user_by_username(uname)
    assert user["organization_id"] == "org_valid_merchant"


@pytest.mark.asyncio
async def test_20_admin_provisioning_enforcement_valid_org():
    """20. Admin provisioning of enforcement officer with valid organization succeeds."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_dept_west", "West Directorate", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"off_prov_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@gov.in",
        "password": "Password123!",
        "role": ROLE_ENFORCEMENT,
        "organization_id": "org_dept_west",
    })
    assert res.status_code == 201, res.text
    user = await get_user_by_username(uname)
    assert user["organization_id"] == "org_dept_west"


@pytest.mark.asyncio
async def test_21_admin_provisioning_audit_valid_org():
    """21. Admin provisioning of audit officer with valid organization succeeds."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_audit_central", "Central Audit Wing", org_type="REGULATOR", status="ACTIVE")
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"aud_prov_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@gov.in",
        "password": "Password123!",
        "role": ROLE_AUDIT,
        "organization_id": "org_audit_central",
    })
    assert res.status_code == 201, res.text
    user = await get_user_by_username(uname)
    assert user["organization_id"] == "org_audit_central"


@pytest.mark.asyncio
async def test_22_enforcement_officer_without_organization_rejected():
    """22. Enforcement officer creation without organization returns 400."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"no_org_enf_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@gov.in",
        "password": "Password123!",
        "role": ROLE_ENFORCEMENT,
        "organization_id": "",
    })
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "Explicit organization_id is required" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_23_audit_officer_without_organization_rejected():
    """23. Audit officer creation without organization returns 400."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"no_org_aud_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@gov.in",
        "password": "Password123!",
        "role": ROLE_AUDIT,
        "organization_id": "",
    })
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "Explicit organization_id is required" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_23b_nonexistent_organization_rejected():
    """23b. Nonexistent organization is rejected (400)."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"ghost_org_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "Password123!",
        "role": ROLE_ENFORCEMENT,
        "organization_id": "org_nonexistent_xyz",
    })
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"


@pytest.mark.asyncio
async def test_23c_no_officer_silently_assigned_ministry():
    """23c. DB helper create_user does NOT silently invent org_ministry for officers."""
    _ensure_test_isolation()
    await init_db()
    pwh, salt = hash_password("Password123!")
    uname_enf = f"db_enf_{uuid.uuid4().hex[:6]}"
    uname_aud = f"db_aud_{uuid.uuid4().hex[:6]}"

    await create_user(uname_enf, pwh, salt, ROLE_ENFORCEMENT, organization_id="")
    await create_user(uname_aud, pwh, salt, ROLE_AUDIT, organization_id="")

    u_enf = await get_user_by_username(uname_enf)
    u_aud = await get_user_by_username(uname_aud)

    assert u_enf["organization_id"] == ""
    assert u_enf["organization_id"] != "org_ministry"
    assert u_aud["organization_id"] == ""
    assert u_aud["organization_id"] != "org_ministry"


@pytest.mark.asyncio
async def test_24_inactive_organization_rejected():
    """24. Inactive organization is rejected (400)."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_inactive_dept", "Defunct Dept", status="INACTIVE")
    await _create_test_user("admin_prov_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_prov_root", ROLE_ADMIN)

    client = TestClient(app)
    uname = f"inact_org_{uuid.uuid4().hex[:6]}"
    res = client.post("/api/auth/users", headers=admin_headers, json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "Password123!",
        "role": ROLE_AUDIT,
        "organization_id": "org_inactive_dept",
    })
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"


@pytest.mark.asyncio
async def test_25_public_merchant_cannot_select_existing_organization():
    """25. Public merchant registration cannot select another existing organization."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_ministry", "Ministry Directorate", status="ACTIVE")
    client = TestClient(app)

    uname = f"spoof_m_{uuid.uuid4().hex[:6]}"
    # Attempting to inject role or hijack org_ministry
    res = client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "Password123!",
        "organization_name": "Ministry Imposter",
    })
    assert res.status_code == 201
    data = res.json()["user"]
    assert data["organization_id"] == f"org_{uname}"
    assert data["organization_id"] != "org_ministry"


# =============================================================================
# 6. INTEGRITY & ATTACK SURFACE (Tests 26-30)
# =============================================================================

@pytest.mark.asyncio
async def test_26_no_new_tenant_user_has_empty_org():
    """26. No newly created tenant-scoped user can have an empty organization."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_legal_dept", "Legal Dept", status="ACTIVE")
    await _create_test_user("admin_root", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_root", ROLE_ADMIN)
    client = TestClient(app)

    # 1. Via legacy route without org -> user gets assigned deterministic org, never empty
    u1 = f"u_no_org_{uuid.uuid4().hex[:6]}"
    r1 = client.post("/api/auth/users", headers=admin_headers, json={
        "username": u1,
        "email": f"{u1}@test.com",
        "password": "Password123!",
        "role": ROLE_MERCHANT,
    })
    assert r1.status_code == 201
    user1 = await get_user_by_username(u1)
    assert user1["organization_id"] != ""
    assert user1["organization_id"] == f"org_{u1}"

    # 2. Via update route attempting to clear org -> 400
    u2 = f"u_valid_{uuid.uuid4().hex[:6]}"
    r2 = client.post("/api/auth/users", headers=admin_headers, json={
        "username": u2,
        "email": f"{u2}@test.com",
        "password": "Password123!",
        "role": ROLE_MERCHANT,
        "organization_id": "org_legal_dept",
    })
    assert r2.status_code == 201

    r3 = client.put(f"/api/auth/users/{u2}", headers=admin_headers, json={
        "organization_id": "",
    })
    assert r3.status_code == 400


@pytest.mark.asyncio
async def test_27_authorization_failure_causes_no_state_mutation():
    """27. Authorization failure causes no sensitive state mutation."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_x", "Tenant X", status="ACTIVE")
    await create_organization("org_tenant_y", "Tenant Y", status="ACTIVE")
    await _create_test_user("attacker_y", ROLE_MERCHANT, "org_tenant_y")

    ana_id = f"immutable-ana-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Original Protected Product",
        image_filename="orig.png",
        extracted_data={"product_name": "Original Protected Product", "mrp": "100"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="Original",
        owner_user_id="victim_x",
        organization_id="org_tenant_x",
    )

    client = TestClient(app)
    attacker_headers = make_auth_headers("attacker_y", ROLE_MERCHANT)

    # Attempt to delete victim analysis
    res = client.delete(f"/api/history/{ana_id}", headers=attacker_headers)
    assert res.status_code == 403

    # Verify record in DB is unchanged
    unchanged = await get_analysis(ana_id)
    assert unchanged is not None
    assert unchanged["product_name"] == "Original Protected Product"
    assert unchanged["owner_user_id"] == "victim_x"
    assert unchanged["organization_id"] == "org_tenant_x"


@pytest.mark.asyncio
async def test_28_parameter_spoofing_cannot_bypass_authorization():
    """28. Organization spoofing through request parameters cannot bypass authorization."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_alpha", "Tenant Alpha", status="ACTIVE")
    await create_organization("org_tenant_beta", "Tenant Beta", status="ACTIVE")
    await _create_test_user("merchant_beta", ROLE_MERCHANT, "org_tenant_beta")

    ana_id = f"target-ana-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Alpha Dossier",
        image_filename="alpha.png",
        extracted_data={"product_name": "Alpha Dossier"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="Alpha",
        owner_user_id="merchant_alpha",
        organization_id="org_tenant_alpha",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_beta", ROLE_MERCHANT)

    # Attacker adds spoofed organization_id query parameter
    res = client.get(f"/api/history/{ana_id}?organization_id=org_tenant_alpha", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_29_header_spoofing_cannot_bypass_authorization():
    """29. Organization spoofing through headers cannot bypass authorization."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_tenant_alpha", "Tenant Alpha", status="ACTIVE")
    await create_organization("org_tenant_beta", "Tenant Beta", status="ACTIVE")
    await _create_test_user("merchant_beta", ROLE_MERCHANT, "org_tenant_beta")

    ana_id = f"target-ana-h-{uuid.uuid4().hex[:8]}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Alpha Private Dossier",
        image_filename="alpha.png",
        extracted_data={"product_name": "Alpha Private Dossier"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="Alpha",
        owner_user_id="merchant_alpha",
        organization_id="org_tenant_alpha",
    )

    client = TestClient(app)
    headers = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    # Inject spoofed headers
    headers["X-Organization-ID"] = "org_tenant_alpha"
    headers["X-Tenant-ID"] = "org_tenant_alpha"

    res = client.get(f"/api/history/{ana_id}", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_30_resource_organization_cannot_be_mutated_unauthorized():
    """30. Resource organization cannot be changed through unauthorized requests."""
    _ensure_test_isolation()
    await init_db()
    await create_organization("org_clean", "Clean Org", status="ACTIVE")
    await create_organization("org_rogue", "Rogue Org", status="ACTIVE")
    await _create_test_user("rogue_merchant", ROLE_MERCHANT, "org_rogue")

    art_id = f"art-protect-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await save_artwork({
        "id": art_id,
        "filename": "original_design.pdf",
        "file_path": "/tmp/orig.pdf",
        "file_type": "PDF",
        "file_size": 1024,
        "page_count": 1,
        "dimensions": {"width": 800, "height": 600},
        "dpi": 72.0,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "owner_user_id": "clean_designer",
        "organization_id": "org_clean",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    client = TestClient(app)
    rogue_headers = make_auth_headers("rogue_merchant", ROLE_MERCHANT)

    # Rogue merchant tries to approve / re-tag artwork
    res = client.post(f"/api/preprint/{art_id}/approval", headers=rogue_headers, json={
        "decision": "APPROVED",
        "legal_disclaimer_acknowledged": True,
    })
    assert res.status_code == 403

    art = await get_artwork(art_id)
    assert art["organization_id"] == "org_clean"
    assert art["approval_status"] == "PENDING"
