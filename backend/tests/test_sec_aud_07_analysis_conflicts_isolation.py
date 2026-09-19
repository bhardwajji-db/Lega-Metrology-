"""
Unit and Integration Tests for SEC-AUD-07 — Analysis Conflicts Endpoint Authentication and Tenant Isolation.

Vulnerability Reference: SEC-AUD-07
Endpoint Under Test: GET /api/compliance/conflicts/{analysis_id}

Security Requirements:
1. Unauthenticated requests must receive HTTP 401 Unauthorized.
2. Requests with invalid or malformed tokens must receive HTTP 401 Unauthorized.
3. Merchant users can view conflicts for their own analyses within their organization (200 OK).
4. Merchant users cannot view conflicts for analyses belonging to another merchant/organization (403 Forbidden).
5. Merchant users cannot view conflicts for analyses belonging to another user in the same organization (403 Forbidden).
6. Enforcement and Audit Officers can view conflicts for analyses within their assigned organization (200 OK).
7. Enforcement and Audit Officers cannot view conflicts for analyses belonging to another organization (403 Forbidden).
8. Administrators have universal oversight and can view conflicts across all organizations (200 OK).
9. Requests for non-existent analyses return HTTP 404 Not Found.
10. Query parameters or header manipulation cannot bypass tenant authorization.
"""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import init_db, save_analysis, create_user
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


async def _create_test_user(username: str, role: str, org_id: str = ""):
    salt, pwh = hash_password("TestPassword123!")
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


@pytest.fixture(autouse=True)
def setup_env():
    _ensure_test_isolation()


@pytest.mark.asyncio
async def test_01_unauthenticated_request_rejected():
    """GET /api/compliance/conflicts/{id} without token must return 401."""
    await init_db()
    client = TestClient(app)
    resp = client.get("/api/compliance/conflicts/any-analysis-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_02_invalid_token_rejected():
    """GET /api/compliance/conflicts/{id} with invalid token must return 401."""
    await init_db()
    client = TestClient(app)
    resp = client.get(
        "/api/compliance/conflicts/any-analysis-id",
        headers={"Authorization": "Bearer invalid.jwt.token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_03_merchant_access_own_analysis_conflicts_succeeds():
    """Merchant can retrieve conflict declarations for their own analysis."""
    await init_db()
    client = TestClient(app)
    username = f"merchant_c1_{os.urandom(3).hex()}"
    org_id = f"org_{username}"
    await _create_test_user(username, ROLE_MERCHANT, org_id)
    token = create_token(username, ROLE_MERCHANT)

    analysis_id = f"ana-conflicts-own-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="Merchant Product with Conflicts",
        image_filename="product.jpg",
        extracted_data={"product_name": "Merchant Product with Conflicts"},
        compliance_result={
            "score": 70.0,
            "status": "WARNING",
            "compliance": {
                "conflicts": [
                    {
                        "rule_id": "LMR_2011_NET_WT",
                        "field": "net_weight",
                        "severity": "HIGH",
                        "conflict_description": "Net quantity unit conflict between front and back label.",
                    }
                ]
            }
        },
        ocr_text="Sample text",
        owner_user_id=username,
        organization_id=org_id,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] == analysis_id
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["rule_id"] == "LMR_2011_NET_WT"


@pytest.mark.asyncio
async def test_04_merchant_access_cross_tenant_conflicts_denied():
    """Merchant in Org B cannot retrieve conflict declarations for Org A's analysis (403)."""
    await init_db()
    client = TestClient(app)
    username_a = f"merchant_c_a_{os.urandom(3).hex()}"
    username_b = f"merchant_c_b_{os.urandom(3).hex()}"
    org_a = f"org_{username_a}"
    org_b = f"org_{username_b}"

    await _create_test_user(username_a, ROLE_MERCHANT, org_a)
    await _create_test_user(username_b, ROLE_MERCHANT, org_b)
    token_b = create_token(username_b, ROLE_MERCHANT)

    analysis_id = f"ana-conflicts-priv-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="Confidential Competitor Product",
        image_filename="secret.jpg",
        extracted_data={"product_name": "Confidential Competitor Product"},
        compliance_result={
            "score": 60.0,
            "status": "NON_COMPLIANT",
            "compliance": {
                "conflicts": [
                    {
                        "rule_id": "LMR_2011_MRP",
                        "field": "mrp",
                        "severity": "CRITICAL",
                        "conflict_description": "Dual MRP pricing violation detected.",
                    }
                ]
            }
        },
        ocr_text="Confidential OCR text",
        owner_user_id=username_a,
        organization_id=org_a,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_05_merchant_access_same_org_different_user_denied():
    """Merchant 2 in Org A cannot view Merchant 1's conflicts in Org A (strict ownership isolation)."""
    await init_db()
    client = TestClient(app)
    org_shared = f"org_shared_{os.urandom(3).hex()}"
    user_1 = f"user1_{os.urandom(3).hex()}"
    user_2 = f"user2_{os.urandom(3).hex()}"

    await _create_test_user(user_1, ROLE_MERCHANT, org_shared)
    await _create_test_user(user_2, ROLE_MERCHANT, org_shared)
    token_2 = create_token(user_2, ROLE_MERCHANT)

    analysis_id = f"ana-user1-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="User 1 Private Product",
        image_filename="u1.jpg",
        extracted_data={"product_name": "User 1 Private Product"},
        compliance_result={
            "score": 85.0,
            "status": "PASS",
            "compliance": {"conflicts": []}
        },
        ocr_text="",
        owner_user_id=user_1,
        organization_id=org_shared,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}",
        headers={"Authorization": f"Bearer {token_2}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_06_enforcement_officer_same_tenant_succeeds():
    """Enforcement Officer in Org A can view conflicts for analyses in Org A."""
    await init_db()
    client = TestClient(app)
    org_dept = f"org_dept_north_{os.urandom(3).hex()}"
    officer = f"officer_north_{os.urandom(3).hex()}"
    merchant = f"merchant_north_{os.urandom(3).hex()}"

    await _create_test_user(officer, ROLE_ENFORCEMENT, org_dept)
    await _create_test_user(merchant, ROLE_MERCHANT, org_dept)
    token_officer = create_token(officer, ROLE_ENFORCEMENT)

    analysis_id = f"ana-dept-north-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="North Region Inspected Goods",
        image_filename="goods.jpg",
        extracted_data={"product_name": "North Region Inspected Goods"},
        compliance_result={
            "score": 50.0,
            "status": "NON_COMPLIANT",
            "compliance": {
                "conflicts": [
                    {
                        "rule_id": "LMR_2011_MFG_DATE",
                        "field": "manufacturing_date",
                        "severity": "HIGH",
                        "conflict_description": "Missing manufacturing month and year.",
                    }
                ]
            }
        },
        ocr_text="Inspected text",
        owner_user_id=merchant,
        organization_id=org_dept,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}",
        headers={"Authorization": f"Bearer {token_officer}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] == analysis_id
    assert len(data["conflicts"]) == 1


@pytest.mark.asyncio
async def test_07_enforcement_officer_cross_tenant_denied():
    """Enforcement Officer in Org South cannot view conflicts for analysis in Org North (403)."""
    await init_db()
    client = TestClient(app)
    org_north = f"org_north_{os.urandom(3).hex()}"
    org_south = f"org_south_{os.urandom(3).hex()}"
    officer_south = f"officer_south_{os.urandom(3).hex()}"

    await _create_test_user(officer_south, ROLE_ENFORCEMENT, org_south)
    token_south = create_token(officer_south, ROLE_ENFORCEMENT)

    analysis_id = f"ana-north-rec-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="North Jurisdiction Record",
        image_filename="north.jpg",
        extracted_data={"product_name": "North Jurisdiction Record"},
        compliance_result={
            "score": 75.0,
            "status": "WARNING",
            "compliance": {"conflicts": []}
        },
        ocr_text="North text",
        owner_user_id="merchant_north",
        organization_id=org_north,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}",
        headers={"Authorization": f"Bearer {token_south}"}
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_08_admin_universal_access_succeeds():
    """Admin has statutory oversight to view conflicts across any organization."""
    await init_db()
    client = TestClient(app)
    admin = f"admin_audit_{os.urandom(3).hex()}"
    org_tenant = f"org_tenant_xyz_{os.urandom(3).hex()}"

    await _create_test_user(admin, ROLE_ADMIN, "org_ministry")
    token_admin = create_token(admin, ROLE_ADMIN)

    analysis_id = f"ana-xyz-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="XYZ Enterprise Product",
        image_filename="xyz.jpg",
        extracted_data={"product_name": "XYZ Enterprise Product"},
        compliance_result={
            "score": 65.0,
            "status": "NON_COMPLIANT",
            "compliance": {
                "conflicts": [
                    {
                        "rule_id": "LMR_2011_COUNTRY_OF_ORIGIN",
                        "field": "country_of_origin",
                        "severity": "CRITICAL",
                        "conflict_description": "Import declaration discrepancy.",
                    }
                ]
            }
        },
        ocr_text="Imported item",
        owner_user_id="merchant_xyz",
        organization_id=org_tenant,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] == analysis_id
    assert len(data["conflicts"]) == 1


@pytest.mark.asyncio
async def test_09_nonexistent_analysis_returns_404():
    """Requesting conflicts for a non-existent analysis ID returns 404."""
    await init_db()
    client = TestClient(app)
    admin = f"admin_404_{os.urandom(3).hex()}"
    await _create_test_user(admin, ROLE_ADMIN, "org_ministry")
    token_admin = create_token(admin, ROLE_ADMIN)

    resp = client.get(
        "/api/compliance/conflicts/non_existent_analysis_99999",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp.status_code == 404
    assert "not found" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_10_query_manipulation_cannot_bypass_isolation():
    """Supplying query parameters (?organization_id=..., ?role=...) cannot bypass 403."""
    await init_db()
    client = TestClient(app)
    username_a = f"merch_qa_{os.urandom(3).hex()}"
    username_b = f"merch_qb_{os.urandom(3).hex()}"
    org_a = f"org_{username_a}"
    org_b = f"org_{username_b}"

    await _create_test_user(username_a, ROLE_MERCHANT, org_a)
    await _create_test_user(username_b, ROLE_MERCHANT, org_b)
    token_b = create_token(username_b, ROLE_MERCHANT)

    analysis_id = f"ana-qa-{os.urandom(3).hex()}"
    await save_analysis(
        analysis_id=analysis_id,
        product_name="Target Analysis",
        image_filename="t.jpg",
        extracted_data={"product_name": "Target Analysis"},
        compliance_result={"score": 80.0, "status": "PASS", "compliance": {"conflicts": []}},
        ocr_text="",
        owner_user_id=username_a,
        organization_id=org_a,
    )

    resp = client.get(
        f"/api/compliance/conflicts/{analysis_id}?organization_id={org_a}&role=ADMIN",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403
