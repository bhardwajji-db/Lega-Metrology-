"""
Unit and Integration Tests for SEC-AUD-02 — Cross-Tenant Enforcement Penalty & Show-Cause Notice IDOR.

Vulnerability Reference: SEC-AUD-02
Endpoints Under Test:
  - POST /api/enforcement/penalty
  - POST /api/enforcement/notice

Security Requirements:
1. POST /api/enforcement/penalty and POST /api/enforcement/notice must require authentication (401).
2. Non-enforcement/admin roles (MERCHANT_PUBLIC, AUDIT_OFFICER) must receive 403 Forbidden.
3. Enforcement officers must only access analyses within their assigned organization_id.
4. Cross-tenant analysis requests by enforcement officers must be rejected with 403 Forbidden.
5. Administrators retain global statutory oversight across all organizations (200 OK).
6. Nonexistent analysis IDs return 404 Not Found.
7. Downstream calculation and notice generation functions must NOT be called on unauthorized requests (no sensitive processing or side-effects).
"""

import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import (
    init_db,
    create_organization,
    create_user,
    get_user_by_username,
    save_analysis,
    get_analysis,
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
def setup_audit_02_fixture():
    _ensure_test_isolation()
    import asyncio
    async def _setup():
        await init_db()
        # Create test organizations
        await create_organization("org_sec_aud02_alpha", "Enforcement Org Alpha", "STATE_ENFORCEMENT")
        await create_organization("org_sec_aud02_beta", "Enforcement Org Beta", "STATE_ENFORCEMENT")
        await create_organization("org_sec_aud02_merchant", "Merchant Org", "MERCHANT_PUBLIC")

        # Create test users
        await _create_test_user_helper("aud02_admin", ROLE_ADMIN, "")
        await _create_test_user_helper("aud02_officer_a", ROLE_ENFORCEMENT, "org_sec_aud02_alpha")
        await _create_test_user_helper("aud02_officer_b", ROLE_ENFORCEMENT, "org_sec_aud02_beta")
        await _create_test_user_helper("aud02_audit_user", ROLE_AUDIT, "org_sec_aud02_alpha")
        await _create_test_user_helper("aud02_merchant", ROLE_MERCHANT, "org_sec_aud02_merchant")

        # Create sample non-compliant analyses for Org Alpha and Org Beta
        analysis_a_data = {
            "id": "analysis-sec-aud02-org-alpha",
            "organization_id": "org_sec_aud02_alpha",
            "owner_user_id": "aud02_officer_a",
            "product_name": "Organic Honey Alpha 500g",
            "manufacturer": "Alpha Honey Processors Ltd",
            "image_filename": "honey_alpha.jpg",
            "ocr_text": "Sample Net Qty 500g Honey",
            "extracted_data": {"net_quantity": "500g", "mrp": "Rs 250"},
            "compliance_result": json.dumps({
                "score": 60.0,
                "status": "NON_COMPLIANT",
                "checks": [
                    {
                        "field": "mrp",
                        "field_label": "Maximum Retail Price (MRP)",
                        "rule_id": "Rule 6(1)(e)",
                        "status": "FAIL",
                        "required": True,
                        "message": "Inclusive of all taxes statement missing",
                    }
                ]
            }),
            "font_size_analysis": json.dumps({
                "rule_12_verdict": "FAIL",
                "net_quantity_font_height_mm": 1.5,
                "min_required_font_height_mm": 4.0,
            }),
        }
        await save_analysis(analysis_a_data)

        analysis_b_data = {
            "id": "analysis-sec-aud02-org-beta",
            "organization_id": "org_sec_aud02_beta",
            "owner_user_id": "aud02_officer_b",
            "product_name": "Sunflower Oil Beta 1L",
            "manufacturer": "Beta Oil Refineries Ltd",
            "image_filename": "oil_beta.jpg",
            "ocr_text": "Refined Sunflower Oil 1 Litre",
            "extracted_data": {"net_quantity": "1L", "mrp": "Rs 180"},
            "compliance_result": json.dumps({
                "score": 55.0,
                "status": "NON_COMPLIANT",
                "checks": [
                    {
                        "field": "customer_care",
                        "field_label": "Consumer Care Details",
                        "rule_id": "Rule 6(1)(f)",
                        "status": "FAIL",
                        "required": True,
                        "message": "Consumer care telephone / email missing",
                    }
                ]
            }),
        }
        await save_analysis(analysis_b_data)

    asyncio.run(_setup())


# ═════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION (401 UNAUTHORIZED)
# ═════════════════════════════════════════════════════════════════════════════

def test_01_unauthenticated_penalty_rejected(client):
    """POST /api/enforcement/penalty must return 401 when unauthenticated."""
    resp = client.post("/api/enforcement/penalty", json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_02_unauthenticated_notice_rejected(client):
    """POST /api/enforcement/notice must return 401 when unauthenticated."""
    resp = client.post("/api/enforcement/notice", json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_03_invalid_token_rejected(client):
    """POST /api/enforcement/penalty and /notice must return 401 on invalid token."""
    invalid_header = {"Authorization": "Bearer invalid.token.value"}
    resp_penalty = client.post("/api/enforcement/penalty", headers=invalid_header, json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp_penalty.status_code == 401

    resp_notice = client.post("/api/enforcement/notice", headers=invalid_header, json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp_notice.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# 2. ROLE AUTHORIZATION (403 FORBIDDEN FOR UNAUTHORIZED ROLES)
# ═════════════════════════════════════════════════════════════════════════════

def test_04_merchant_penalty_denied(client):
    """Merchant role cannot call penalty calculation -> 403."""
    headers = _auth_header("aud02_merchant", ROLE_MERCHANT)
    resp = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp.status_code == 403


def test_05_merchant_notice_denied(client):
    """Merchant role cannot generate show-cause notices -> 403."""
    headers = _auth_header("aud02_merchant", ROLE_MERCHANT)
    resp = client.post("/api/enforcement/notice", headers=headers, json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp.status_code == 403


def test_06_audit_officer_penalty_denied(client):
    """Audit officer role cannot call penalty calculation -> 403."""
    headers = _auth_header("aud02_audit_user", ROLE_AUDIT)
    resp = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp.status_code == 403


def test_07_audit_officer_notice_denied(client):
    """Audit officer role cannot generate show-cause notices -> 403."""
    headers = _auth_header("aud02_audit_user", ROLE_AUDIT)
    resp = client.post("/api/enforcement/notice", headers=headers, json={"analysis_id": "analysis-sec-aud02-org-alpha"})
    assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 3. SAME-TENANT AUTHORIZATION (200 ALLOWED)
# ═════════════════════════════════════════════════════════════════════════════

def test_08_officer_a_analysis_a_penalty_allowed(client):
    """Officer A accessing Analysis A (same Org Alpha) for penalty calculation -> 200."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-alpha", "repeat_offence": False}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["analysis_id"] == "analysis-sec-aud02-org-alpha"
    assert "Organic Honey" in data.get("product_name", "")
    assert "total_min" in data or "estimated_total" in data or "base_penalty" in data or "violations" in data


def test_09_officer_a_analysis_a_notice_allowed(client):
    """Officer A accessing Analysis A (same Org Alpha) for notice generation -> 200."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={
            "analysis_id": "analysis-sec-aud02-org-alpha",
            "officer_name": "Inspector Alpha",
            "officer_designation": "Legal Metrology Inspector",
            "jurisdiction": "District Alpha",
            "deadline_days": 15
        }
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["analysis_id"] == "analysis-sec-aud02-org-alpha"
    assert "SHOW-CAUSE NOTICE" in data.get("notice", "").upper() or "LEGAL METROLOGY" in data.get("notice", "").upper()


def test_10_officer_b_analysis_b_penalty_allowed(client):
    """Officer B accessing Analysis B (same Org Beta) for penalty calculation -> 200."""
    headers = _auth_header("aud02_officer_b", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-beta", "repeat_offence": False}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["analysis_id"] == "analysis-sec-aud02-org-beta"
    assert "Sunflower Oil" in data.get("product_name", "")


def test_11_officer_b_analysis_b_notice_allowed(client):
    """Officer B accessing Analysis B (same Org Beta) for notice generation -> 200."""
    headers = _auth_header("aud02_officer_b", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={
            "analysis_id": "analysis-sec-aud02-org-beta",
            "officer_name": "Inspector Beta",
            "officer_designation": "Legal Metrology Inspector",
            "jurisdiction": "District Beta",
            "deadline_days": 15
        }
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["analysis_id"] == "analysis-sec-aud02-org-beta"
    assert "SHOW-CAUSE NOTICE" in data.get("notice", "").upper() or "LEGAL METROLOGY" in data.get("notice", "").upper()


# ═════════════════════════════════════════════════════════════════════════════
# 4. CROSS-TENANT AUTHORIZATION (403 FORBIDDEN)
# ═════════════════════════════════════════════════════════════════════════════

def test_12_officer_a_cross_tenant_penalty_denied(client):
    """Officer A (Org Alpha) attempting penalty calculation on Analysis B (Org Beta) -> 403."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-beta"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    # Verify no information leakage in error detail
    assert "Sunflower Oil" not in resp.text
    assert "Beta Oil" not in resp.text


def test_13_officer_a_cross_tenant_notice_denied(client):
    """Officer A (Org Alpha) attempting notice generation on Analysis B (Org Beta) -> 403."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-beta"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    # Verify no information leakage in error detail
    assert "Sunflower Oil" not in resp.text
    assert "Beta Oil" not in resp.text


def test_14_officer_b_cross_tenant_penalty_denied(client):
    """Officer B (Org Beta) attempting penalty calculation on Analysis A (Org Alpha) -> 403."""
    headers = _auth_header("aud02_officer_b", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-alpha"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    # Verify no information leakage in error detail
    assert "Organic Honey" not in resp.text
    assert "Alpha Honey" not in resp.text


def test_15_officer_b_cross_tenant_notice_denied(client):
    """Officer B (Org Beta) attempting notice generation on Analysis A (Org Alpha) -> 403."""
    headers = _auth_header("aud02_officer_b", ROLE_ENFORCEMENT)
    resp = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-alpha"}
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    # Verify no information leakage in error detail
    assert "Organic Honey" not in resp.text
    assert "Alpha Honey" not in resp.text


# ═════════════════════════════════════════════════════════════════════════════
# 5. ADMIN GLOBAL STATUTORY OVERSIGHT (200 ALLOWED ACROSS TENANTS)
# ═════════════════════════════════════════════════════════════════════════════

def test_16_admin_analysis_a_penalty_allowed(client):
    """Admin accessing Analysis A (Org Alpha) for penalty calculation -> 200."""
    headers = _auth_header("aud02_admin", ROLE_ADMIN)
    resp = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-alpha"}
    )
    assert resp.status_code == 200


def test_17_admin_analysis_b_penalty_allowed(client):
    """Admin accessing Analysis B (Org Beta) for penalty calculation -> 200."""
    headers = _auth_header("aud02_admin", ROLE_ADMIN)
    resp = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-beta"}
    )
    assert resp.status_code == 200


def test_18_admin_analysis_a_notice_allowed(client):
    """Admin accessing Analysis A (Org Alpha) for notice generation -> 200."""
    headers = _auth_header("aud02_admin", ROLE_ADMIN)
    resp = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-alpha"}
    )
    assert resp.status_code == 200


def test_19_admin_analysis_b_notice_allowed(client):
    """Admin accessing Analysis B (Org Beta) for notice generation -> 200."""
    headers = _auth_header("aud02_admin", ROLE_ADMIN)
    resp = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={"analysis_id": "analysis-sec-aud02-org-beta"}
    )
    assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# 6. ID MANIPULATION & NOT FOUND CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def test_20_nonexistent_analysis_id_returns_404(client):
    """Non-existent analysis ID returns 404 Not Found."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    resp_penalty = client.post(
        "/api/enforcement/penalty",
        headers=headers,
        json={"analysis_id": "nonexistent-analysis-id-9999"}
    )
    assert resp_penalty.status_code == 404

    resp_notice = client.post(
        "/api/enforcement/notice",
        headers=headers,
        json={"analysis_id": "nonexistent-analysis-id-9999"}
    )
    assert resp_notice.status_code == 404


def test_21_uuid_id_substitution_cannot_cross_tenant_boundaries(client):
    """Attempting random UUID/ID substitution cannot cross tenant boundaries."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    fake_uuids = [
        "00000000-0000-0000-0000-000000000000",
        "../../analysis-sec-aud02-org-beta",
        "analysis-sec-aud02-org-beta%00",
    ]
    for fid in fake_uuids:
        resp = client.post("/api/enforcement/penalty", headers=headers, json={"analysis_id": fid})
        assert resp.status_code in (404, 403, 422)


# ═════════════════════════════════════════════════════════════════════════════
# 7. SENSITIVE PROCESSING SPIES (NO DOWNSTREAM EXECUTION ON 403)
# ═════════════════════════════════════════════════════════════════════════════

def test_22_cross_tenant_penalty_does_not_execute_computation(client):
    """Verify estimate_penalty is NOT called when cross-tenant request is rejected."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    with patch("api.enforcement.estimate_penalty") as mock_estimate:
        resp = client.post(
            "/api/enforcement/penalty",
            headers=headers,
            json={"analysis_id": "analysis-sec-aud02-org-beta"}
        )
        assert resp.status_code == 403
        mock_estimate.assert_not_called()


def test_23_cross_tenant_notice_does_not_execute_generation(client):
    """Verify generate_show_cause is NOT called when cross-tenant request is rejected."""
    headers = _auth_header("aud02_officer_a", ROLE_ENFORCEMENT)
    with patch("api.enforcement.generate_show_cause") as mock_gen_notice:
        resp = client.post(
            "/api/enforcement/notice",
            headers=headers,
            json={"analysis_id": "analysis-sec-aud02-org-beta"}
        )
        assert resp.status_code == 403
        mock_gen_notice.assert_not_called()
