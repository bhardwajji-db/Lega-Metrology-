"""
Unit and Integration Tests for SEC-06 — Organization / Tenant Isolation.
Verifies multi-tenant database schema, authorization boundaries, and data isolation
across all endpoints in MetrCheck AI.
"""

import os
import json
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
    get_analyses,
    save_artwork,
    get_artwork,
    list_artworks,
    save_version_comparison,
    get_version_comparison,
    list_version_comparisons,
    save_review,
    get_review,
    list_reviews,
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
    """Helper to register/create user in DB with specific organization_id."""
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
    """Helper to generate Authorization header for test requests."""
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


# ═════════════════════════════════════════════════════════════════════════════
# 1. DATABASE SCHEMA & INDEX VERIFICATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_schema_organizations_table_exists():
    """Verify that the organizations table exists with correct schema."""
    _ensure_test_isolation()
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(organizations)")
        columns = {row["name"]: row["type"] for row in await cursor.fetchall()}
        assert "id" in columns
        assert "name" in columns
        assert "org_type" in columns
        assert "status" in columns
        assert "created_at" in columns
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_02_schema_organization_id_in_all_core_tables():
    """Verify that organization_id exists across all core multi-tenant tables."""
    _ensure_test_isolation()
    await init_db()
    db = await get_db()
    try:
        tables = [
            "users",
            "analyses",
            "artworks",
            "version_comparisons",
            "officer_reviews",
            "evidence_audit_logs",
        ]
        for tbl in tables:
            cursor = await db.execute(f"PRAGMA table_info({tbl})")
            columns = [row["name"] for row in await cursor.fetchall()]
            assert "organization_id" in columns, f"Table '{tbl}' is missing 'organization_id' column."
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_03_schema_organization_indexes_exist():
    """Verify that indexes on organization_id exist for query performance."""
    _ensure_test_isolation()
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row["name"] for row in await cursor.fetchall()]
        expected_indexes = [
            "idx_users_org",
            "idx_analyses_org",
            "idx_artworks_org",
            "idx_version_comp_org",
            "idx_reviews_org",
            "idx_evidence_audit_org",
        ]
        for idx in expected_indexes:
            assert idx in indexes, f"Index '{idx}' was not created."
    finally:
        await db.close()


# ═════════════════════════════════════════════════════════════════════════════
# 2. ORGANIZATION CRUD & SEEDING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_04_organization_crud_lifecycle():
    """Test creating, fetching, and listing organizations."""
    _ensure_test_isolation()
    await init_db()
    org_id = f"test_org_{os.urandom(4).hex()}"
    created = await create_organization({
        "id": org_id,
        "name": "Test FMCG Enterprise",
        "org_type": "MERCHANT",
        "jurisdiction": "National",
        "status": "ACTIVE",
    })
    assert created["id"] == org_id
    assert created["name"] == "Test FMCG Enterprise"

    fetched = await get_organization(org_id)
    assert fetched is not None
    assert fetched["name"] == "Test FMCG Enterprise"

    orgs = await list_organizations()
    assert any(o["id"] == org_id for o in orgs)


@pytest.mark.asyncio
async def test_05_default_organizations_seeded():
    """Verify default ministry and merchant organizations are pre-seeded."""
    _ensure_test_isolation()
    await init_db()
    ministry_org = await get_organization("org_ministry")
    assert ministry_org is not None
    assert ministry_org["org_type"] == "REGULATOR"

    merchant_org = await get_organization("org_merchant_demo")
    assert merchant_org is not None
    assert merchant_org["org_type"] == "MERCHANT"


# ═════════════════════════════════════════════════════════════════════════════
# 3. AUTH & USER REGISTRATION TENANT PROVISIONING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_06_self_registration_provisions_dedicated_tenant():
    """Test that self-registering as a merchant creates and links a dedicated organization."""
    _ensure_test_isolation()
    await init_db()
    client = TestClient(app)
    username = f"merchant_new_{os.urandom(4).hex()}"

    res = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "SecurePassword123!",
        "full_name": "New Merchant Ltd",
        "organization_name": "New FMCG Retailers Ltd",
    })
    assert res.status_code in (200, 201), res.text
    data = res.json()
    user_data = data.get("user", data)
    assert user_data["username"] == username
    assert "organization_id" in user_data
    assert user_data["organization_id"] == f"org_{username}"

    # Check organization was created in DB
    org = await get_organization(f"org_{username}")
    assert org is not None
    assert org["name"] == "New FMCG Retailers Ltd"


@pytest.mark.asyncio
async def test_07_admin_user_provisioning_assigns_organization():
    """Test that admin user provisioning assigns the user to specified organization."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("admin_user_p", ROLE_ADMIN, "org_ministry")
    admin_headers = make_auth_headers("admin_user_p", ROLE_ADMIN)
    new_officer = f"officer_state_{os.urandom(4).hex()}"
    client = TestClient(app)

    res = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": new_officer,
            "email": f"{new_officer}@dept.gov.in",
            "password": "OfficerPass123!",
            "full_name": "State Metrology Officer",
            "role": ROLE_ENFORCEMENT,
            "organization_id": "org_ministry",
        }
    )
    assert res.status_code in (200, 201), res.text
    data = res.json()
    user_data = data.get("user", data)
    assert user_data["organization_id"] == "org_ministry"


# ═════════════════════════════════════════════════════════════════════════════
# 4. TENANT ACCESS SECURITY GUARD (`check_tenant_access`)
# ═════════════════════════════════════════════════════════════════════════════

def test_08_check_tenant_access_admin_supervision():
    """Admin has universal statutory oversight regardless of tenant."""
    admin_user = {"username": "admin", "role": ROLE_ADMIN, "organization_id": "org_ministry"}
    resource_a = {"organization_id": "org_tenant_a", "owner_user_id": "merchant_a"}
    resource_b = {"organization_id": "org_tenant_b", "owner_user_id": "merchant_b"}
    assert check_tenant_access(admin_user, resource_a) is True
    assert check_tenant_access(admin_user, resource_b) is True


def test_09_check_tenant_access_officer_scoped():
    """Officers can only access data within their organization. Unassigned legacy data is ADMIN-only."""
    officer_dept_a = {"username": "officer_a", "role": ROLE_ENFORCEMENT, "organization_id": "org_dept_a"}
    record_same_org = {"organization_id": "org_dept_a", "owner_user_id": "merchant_a"}
    record_other_org = {"organization_id": "org_dept_b", "owner_user_id": "merchant_b"}
    record_legacy_unassigned = {"organization_id": "", "owner_user_id": ""}

    assert check_tenant_access(officer_dept_a, record_same_org) is True
    assert check_tenant_access(officer_dept_a, record_other_org) is False
    assert check_tenant_access(officer_dept_a, record_legacy_unassigned) is False


def test_10_check_tenant_access_merchant_strict_ownership():
    """Merchants are strictly isolated to their organization AND own records."""
    merchant_user = {"username": "merchant_1", "role": ROLE_MERCHANT, "organization_id": "org_merchant_1"}
    own_record = {"organization_id": "org_merchant_1", "owner_user_id": "merchant_1"}
    diff_owner_same_org = {"organization_id": "org_merchant_1", "owner_user_id": "merchant_2"}
    other_org_record = {"organization_id": "org_merchant_2", "owner_user_id": "merchant_1"}

    assert check_tenant_access(merchant_user, own_record) is True
    assert check_tenant_access(merchant_user, diff_owner_same_org) is False
    assert check_tenant_access(merchant_user, other_org_record) is False


# ═════════════════════════════════════════════════════════════════════════════
# 5. ANALYSIS & HISTORY TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_11_analysis_saved_with_tenant_org():
    """Verify that saving an analysis persists the caller's organization_id."""
    _ensure_test_isolation()
    await init_db()
    analysis_id = f"test-analysis-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="Tenant Isolated Product",
        image_filename="test.png",
        extracted_data={"product_name": "Tenant Isolated Product", "mrp": "100"},
        compliance_result={"score": 95.0, "status": "PASS", "checks": []},
        ocr_text="Test OCR text",
        owner_user_id="merchant_a",
        organization_id="org_tenant_a",
    )

    saved = await get_analysis(analysis_id)
    assert saved is not None
    assert saved["organization_id"] == "org_tenant_a"
    assert saved["owner_user_id"] == "merchant_a"


@pytest.mark.asyncio
async def test_12_cross_tenant_history_detail_blocked():
    """Verify that a merchant in Org B cannot fetch an analysis belonging to Org A (403)."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("merchant_b_user", ROLE_MERCHANT, "org_tenant_b")

    analysis_id = f"test-ana-org-a-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="Tenant A Secret Formula",
        image_filename="test_a.png",
        extracted_data={"product_name": "Tenant A Secret Formula", "mrp": "250"},
        compliance_result={"score": 88.0, "status": "PASS", "checks": []},
        ocr_text="Confidential Product A",
        owner_user_id="merchant_a_user",
        organization_id="org_tenant_a",
    )

    merchant_b_headers = make_auth_headers("merchant_b_user", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.get(f"/api/history/{analysis_id}", headers=merchant_b_headers)
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
    assert "Secret Formula" not in res.text


@pytest.mark.asyncio
async def test_13_history_list_scoped_by_tenant():
    """Verify that history listing only returns records within the caller's tenant."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("user_org_alpha", ROLE_MERCHANT, "org_tenant_alpha")

    id_a = f"test-list-a-{os.urandom(4).hex()}"
    id_b = f"test-list-b-{os.urandom(4).hex()}"

    await save_analysis(
        analysis_id=id_a,
        product_name="Product Alpha",
        image_filename="a.png",
        extracted_data={"product_name": "Product Alpha"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="",
        owner_user_id="user_org_alpha",
        organization_id="org_tenant_alpha",
    )
    await save_analysis(
        analysis_id=id_b,
        product_name="Product Beta",
        image_filename="b.png",
        extracted_data={"product_name": "Product Beta"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="",
        owner_user_id="user_org_beta",
        organization_id="org_tenant_beta",
    )

    headers_alpha = make_auth_headers("user_org_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.get("/api/history", headers=headers_alpha)
    assert res.status_code == 200
    data = res.json()
    items = data if isinstance(data, list) else data.get("history", [])
    ids = [it["id"] for it in items]
    assert id_a in ids
    assert id_b not in ids


# ═════════════════════════════════════════════════════════════════════════════
# 6. REPORT DOWNLOAD TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_14_cross_tenant_report_pdf_download_denied():
    """Verify cross-tenant report PDF download returns 403 Forbidden."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("merchant_corp_b", ROLE_MERCHANT, "org_corp_b")

    ana_id = f"report-test-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Sensitive Product Dossier",
        image_filename="dossier.png",
        extracted_data={"product_name": "Sensitive Product Dossier", "mrp": "500"},
        compliance_result={"score": 92.0, "status": "PASS", "checks": []},
        ocr_text="Private text",
        owner_user_id="merchant_corp_a",
        organization_id="org_corp_a",
    )

    merchant_b_headers = make_auth_headers("merchant_corp_b", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.get(f"/api/report/{ana_id}/pdf", headers=merchant_b_headers)
    assert res.status_code == 403
    assert "Sensitive" not in res.text


@pytest.mark.asyncio
async def test_15_cross_tenant_report_csv_json_xlsx_download_denied():
    """Verify CSV, JSON, and XLSX report formats are protected against cross-tenant access."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("merchant_corp_b2", ROLE_MERCHANT, "org_corp_b")

    ana_id = f"export-test-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Corporate Trade Secret",
        image_filename="secret.png",
        extracted_data={"product_name": "Corporate Trade Secret", "mrp": "999"},
        compliance_result={"score": 85.0, "status": "PASS", "checks": []},
        ocr_text="Confidential data",
        owner_user_id="merchant_corp_a",
        organization_id="org_corp_a",
    )

    merchant_b_headers = make_auth_headers("merchant_corp_b2", ROLE_MERCHANT)
    client = TestClient(app)

    for fmt in ["csv", "json", "xlsx"]:
        res = client.get(f"/api/report/{ana_id}/{fmt}", headers=merchant_b_headers)
        assert res.status_code == 403, f"Format {fmt} returned {res.status_code} instead of 403"


# ═════════════════════════════════════════════════════════════════════════════
# 7. AUTHENTICATED FILE & IMAGE ACCESS TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_16_cross_tenant_image_access_denied():
    """Verify that a merchant cannot view or download images linked to another tenant's analysis."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("merchant_img_b", ROLE_MERCHANT, "org_tenant_b")

    filename = f"product_image_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    ana_id = f"img-ana-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Proprietary Design",
        image_filename=filename,
        extracted_data={"product_name": "Proprietary Design"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="",
        owner_user_id="merchant_img_a",
        organization_id="org_tenant_a",
    )

    merchant_b_headers = make_auth_headers("merchant_img_b", ROLE_MERCHANT)
    client = TestClient(app)

    try:
        res = client.get(f"/api/images/{filename}", headers=merchant_b_headers)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_17_authorized_tenant_image_access_allowed():
    """Verify that the owning merchant can retrieve their own uploaded image."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("merchant_img_a_auth", ROLE_MERCHANT, "org_tenant_a")

    filename = f"my_product_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    ana_id = f"my-ana-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="My Product",
        image_filename=filename,
        extracted_data={"product_name": "My Product"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="",
        owner_user_id="merchant_img_a_auth",
        organization_id="org_tenant_a",
    )

    merchant_a_headers = make_auth_headers("merchant_img_a_auth", ROLE_MERCHANT)
    client = TestClient(app)

    try:
        res = client.get(f"/api/images/{filename}", headers=merchant_a_headers)
        assert res.status_code == 200
        assert res.headers.get("content-type") == "image/png"
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ═════════════════════════════════════════════════════════════════════════════
# 8. PRE-PRINT ARTWORK TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_18_artwork_saved_with_tenant_org():
    """Verify artwork upload records caller's organization_id."""
    _ensure_test_isolation()
    await init_db()
    art_id = f"art-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await save_artwork({
        "id": art_id,
        "filename": "package_label.pdf",
        "file_path": "/tmp/test.pdf",
        "file_type": "PDF",
        "file_size": 1024,
        "page_count": 1,
        "dimensions": {"width": 800, "height": 600},
        "dpi": 72.0,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "pages_data": [],
        "owner_user_id": "designer_a",
        "organization_id": "org_studio_a",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    art = await get_artwork(art_id)
    assert art is not None
    assert art["organization_id"] == "org_studio_a"
    assert art["owner_user_id"] == "designer_a"


@pytest.mark.asyncio
async def test_19_cross_tenant_artwork_operations_blocked():
    """Verify that a merchant in Org B cannot read, analyze, approve, or delete Org A artwork."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("designer_b_user", ROLE_MERCHANT, "org_studio_b")

    art_id = f"art-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await save_artwork({
        "id": art_id,
        "filename": "confidential_packaging.pdf",
        "file_path": "/tmp/conf.pdf",
        "file_type": "PDF",
        "file_size": 2048,
        "page_count": 1,
        "dimensions": {"width": 1000, "height": 800},
        "dpi": 300.0,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "pages_data": [],
        "owner_user_id": "designer_a_user",
        "organization_id": "org_studio_a",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    merchant_b_headers = make_auth_headers("designer_b_user", ROLE_MERCHANT)
    client = TestClient(app)

    # 1. Read
    res = client.get(f"/api/preprint/{art_id}", headers=merchant_b_headers)
    assert res.status_code == 403

    # 2. Analyze
    res = client.post(f"/api/preprint/{art_id}/analyze", headers=merchant_b_headers)
    assert res.status_code == 403

    # 3. Approve
    res = client.post(f"/api/preprint/{art_id}/approval", headers=merchant_b_headers, json={
        "decision": "APPROVED",
        "legal_disclaimer_acknowledged": True,
    })
    assert res.status_code == 403

    # 4. Delete
    res = client.delete(f"/api/preprint/{art_id}", headers=merchant_b_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_20_preprint_list_filtered_by_tenant():
    """Verify that pre-print artworks listing filters by tenant."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("brand_a_user", ROLE_MERCHANT, "org_brand_a")

    art_a = f"art-a-{os.urandom(4).hex()}"
    art_b = f"art-b-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    await save_artwork({
        "id": art_a,
        "filename": "art_a.pdf",
        "file_path": "",
        "file_type": "PDF",
        "file_size": 500,
        "page_count": 1,
        "dimensions": {},
        "dpi": 72.0,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "pages_data": [],
        "owner_user_id": "brand_a_user",
        "organization_id": "org_brand_a",
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await save_artwork({
        "id": art_b,
        "filename": "art_b.pdf",
        "file_path": "",
        "file_type": "PDF",
        "file_size": 500,
        "page_count": 1,
        "dimensions": {},
        "dpi": 72.0,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "pages_data": [],
        "owner_user_id": "brand_b_user",
        "organization_id": "org_brand_b",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    headers_a = make_auth_headers("brand_a_user", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.get("/api/preprint", headers=headers_a)
    assert res.status_code == 200
    arts = res.json()["artworks"]
    art_ids = [a["id"] for a in arts]
    assert art_a in art_ids
    assert art_b not in art_ids


# ═════════════════════════════════════════════════════════════════════════════
# 9. VERSION COMPARISON TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_21_cross_tenant_version_comparison_denied():
    """Verify that comparing versions across tenant boundaries is forbidden."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("user_tenant_b", ROLE_MERCHANT, "org_tenant_b")

    ana_a = f"comp-a-{os.urandom(4).hex()}"
    ana_b = f"comp-b-{os.urandom(4).hex()}"

    await save_analysis(
        analysis_id=ana_a,
        product_name="Product A",
        image_filename="a.png",
        extracted_data={"product_name": "Product A", "mrp": "100"},
        compliance_result={"score": 80.0, "status": "PASS", "checks": []},
        ocr_text="",
        owner_user_id="user_tenant_a",
        organization_id="org_tenant_a",
    )
    await save_analysis(
        analysis_id=ana_b,
        product_name="Product B",
        image_filename="b.png",
        extracted_data={"product_name": "Product B", "mrp": "120"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="",
        owner_user_id="user_tenant_b",
        organization_id="org_tenant_b",
    )

    headers_b = make_auth_headers("user_tenant_b", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.post("/api/versions/compare", headers=headers_b, json={
        "version_a_id": ana_a,
        "version_b_id": ana_b,
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS",
    })
    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"


@pytest.mark.asyncio
async def test_22_saved_comparison_detail_isolation():
    """Verify that a saved version comparison cannot be accessed by another tenant."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("corp_b_user", ROLE_MERCHANT, "org_corp_b")

    comp_id = f"cmp-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await save_version_comparison({
        "id": comp_id,
        "product_name": "Private Comparison",
        "version_a_id": "v1",
        "version_b_id": "v2",
        "version_a_score": 75.0,
        "version_b_score": 95.0,
        "score_delta": 20.0,
        "overall_verdict": "IMPROVED",
        "field_diffs": [],
        "rule_transitions": [],
        "owner_user_id": "corp_a_user",
        "organization_id": "org_corp_a",
        "created_at": now_iso,
    })

    headers_b = make_auth_headers("corp_b_user", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.get(f"/api/versions/comparisons/{comp_id}", headers=headers_b)
    assert res.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 10. OFFICER REVIEW WORKFLOW TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_23_review_saved_with_tenant_org():
    """Verify that officer review records preserve organization_id."""
    _ensure_test_isolation()
    await init_db()
    rev_id = f"rev-test-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await save_review({
        "id": rev_id,
        "analysis_id": f"ana-{rev_id}",
        "organization_id": "org_state_dept_1",
        "target_type": "ANALYSIS",
        "product_name": "State Inspected Product",
        "status": "PENDING_REVIEW",
        "assigned_officer": "",
        "assigned_by": "",
        "assigned_at": None,
        "verified_by": "",
        "verified_at": None,
        "final_human_status": "",
        "ai_score": 65.0,
        "ai_risk_level": "HIGH",
        "ai_status": "WARNING",
        "ai_snapshot": json.dumps({"score": 65.0}),
        "human_verified_result": json.dumps({}),
        "field_corrections": json.dumps([]),
        "evidence_modifications": json.dumps([]),
        "comments": json.dumps([]),
        "history": json.dumps([]),
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    rev = await get_review(rev_id)
    assert rev is not None
    assert rev["organization_id"] == "org_state_dept_1"


@pytest.mark.asyncio
async def test_24_review_queue_scoped_to_officer_department():
    """Verify that an enforcement officer in Dept 1 only sees Dept 1 reviews in their queue."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("officer_north_user", ROLE_ENFORCEMENT, "org_dept_north")

    rev_1 = f"rev-dept1-{os.urandom(4).hex()}"
    rev_2 = f"rev-dept2-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    await save_review({
        "id": rev_1,
        "analysis_id": f"ana-{rev_1}",
        "organization_id": "org_dept_north",
        "target_type": "ANALYSIS",
        "product_name": "North Region Product",
        "status": "PENDING_REVIEW",
        "assigned_officer": "",
        "assigned_by": "",
        "assigned_at": None,
        "verified_by": "",
        "verified_at": None,
        "final_human_status": "",
        "ai_score": 50.0,
        "ai_risk_level": "CRITICAL",
        "ai_status": "FAIL",
        "ai_snapshot": json.dumps({"compliance_result": {"score": 50.0, "checks": []}}),
        "human_verified_result": json.dumps({}),
        "field_corrections": json.dumps([]),
        "evidence_modifications": json.dumps([]),
        "comments": json.dumps([]),
        "history": json.dumps([]),
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    await save_review({
        "id": rev_2,
        "analysis_id": f"ana-{rev_2}",
        "organization_id": "org_dept_south",
        "target_type": "ANALYSIS",
        "product_name": "South Region Product",
        "status": "PENDING_REVIEW",
        "assigned_officer": "",
        "assigned_by": "",
        "assigned_at": None,
        "verified_by": "",
        "verified_at": None,
        "final_human_status": "",
        "ai_score": 55.0,
        "ai_risk_level": "HIGH",
        "ai_status": "WARNING",
        "ai_snapshot": json.dumps({"compliance_result": {"score": 55.0, "checks": []}}),
        "human_verified_result": json.dumps({}),
        "field_corrections": json.dumps([]),
        "evidence_modifications": json.dumps([]),
        "comments": json.dumps([]),
        "history": json.dumps([]),
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    officer_north_headers = make_auth_headers("officer_north_user", ROLE_ENFORCEMENT)
    client = TestClient(app)

    res = client.get("/api/reviews/queue", headers=officer_north_headers)
    assert res.status_code == 200
    items = res.json()
    rev_ids = [it["review_id"] for it in items]
    assert rev_1 in rev_ids
    assert rev_2 not in rev_ids


@pytest.mark.asyncio
async def test_25_cross_tenant_review_action_blocked():
    """Verify that an officer cannot mutate a review belonging to another department."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("officer_mumbai_user", ROLE_ENFORCEMENT, "org_dept_mumbai")

    rev_id = f"rev-locked-{os.urandom(4).hex()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await save_review({
        "id": rev_id,
        "analysis_id": f"ana-{rev_id}",
        "organization_id": "org_dept_delhi",
        "target_type": "ANALYSIS",
        "product_name": "Delhi Packaged Good",
        "status": "PENDING_REVIEW",
        "assigned_officer": "",
        "assigned_by": "",
        "assigned_at": None,
        "verified_by": "",
        "verified_at": None,
        "final_human_status": "",
        "ai_score": 60.0,
        "ai_risk_level": "HIGH",
        "ai_status": "WARNING",
        "ai_snapshot": json.dumps({}),
        "human_verified_result": json.dumps({}),
        "field_corrections": json.dumps([]),
        "evidence_modifications": json.dumps([]),
        "comments": json.dumps([]),
        "history": json.dumps([]),
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    officer_mumbai_headers = make_auth_headers("officer_mumbai_user", ROLE_ENFORCEMENT)
    client = TestClient(app)

    res = client.post(f"/api/reviews/{rev_id}/accept", headers=officer_mumbai_headers, json={
        "comments": "Unauthorized cross-department sign off attempt"
    })
    assert res.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 11. EVIDENCE SYSTEM TENANT ISOLATION
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_26_cross_tenant_evidence_actions_blocked():
    """Verify that evidence correction, heatmap, and review actions are tenant-isolated."""
    _ensure_test_isolation()
    await init_db()
    await _create_test_user("officer_beta_user", ROLE_ENFORCEMENT, "org_dept_beta")

    ana_id = f"ev-tenant-test-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Evidence Target",
        image_filename="ev.png",
        extracted_data={"product_name": "Evidence Target", "net_quantity": "500g"},
        compliance_result={
            "score": 70.0,
            "status": "WARNING",
            "checks": [{"rule_id": "RULE_NET_QTY", "status": "FAIL", "severity": "major", "field_label": "Net Qty"}],
        },
        ocr_text="Net Wt 500g",
        owner_user_id="merchant_a",
        organization_id="org_dept_alpha",
    )

    officer_beta_headers = make_auth_headers("officer_beta_user", ROLE_ENFORCEMENT)
    client = TestClient(app)

    # 1. Evidence correction
    res = client.post(f"/api/evidence/{ana_id}/correct", headers=officer_beta_headers, json={
        "rule_id": "RULE_NET_QTY",
        "corrected_value": "500 g",
        "comments": "Unauthorized correction",
    })
    assert res.status_code == 403

    # 2. Evidence review action
    res = client.post(f"/api/evidence/{ana_id}/review-action", headers=officer_beta_headers, json={
        "rule_id": "RULE_NET_QTY",
        "action": "APPROVE",
        "comments": "Unauthorized approval",
    })
    assert res.status_code == 403

    # 3. Heatmap
    res = client.get(f"/api/evidence/{ana_id}/heatmap", headers=officer_beta_headers)
    assert res.status_code == 403

    # 4. History
    res = client.get(f"/api/evidence/{ana_id}/history", headers=officer_beta_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_27_evidence_audit_logs_record_organization():
    """Verify that evidence audit logs persist organization_id."""
    _ensure_test_isolation()
    await init_db()
    ana_id = f"audit-org-{os.urandom(4).hex()}"
    await save_evidence_audit_log(
        analysis_id=ana_id,
        evidence_id="ev-123",
        rule_id="RULE_MRP",
        actor_username="officer_alpha",
        action_type="CORRECTION",
        previous_value="100",
        new_value="120",
        comments="Statutory correction",
        organization_id="org_state_alpha",
    )

    logs = await get_evidence_audit_logs(ana_id)
    assert len(logs) == 1
    assert logs[0]["organization_id"] == "org_state_alpha"
    assert logs[0]["actor_username"] == "officer_alpha"