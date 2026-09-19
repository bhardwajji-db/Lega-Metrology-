"""
Test Suite for SEC-02: Report Download IDOR / Broken Object-Level Authorization.

Verifies:
1. All report/export endpoints require authentication (401 Unauthorized for unauthenticated requests).
   - /api/report/{id} (PDF)
   - /api/report/{id}/pdf (PDF)
   - /api/report/{id}/csv (CSV)
   - /api/report/{id}/xlsx (Excel)
   - /api/report/{id}/json (JSON)
2. IDOR / Ownership Protection: Merchant A cannot access Merchant B's compliance reports (403 Forbidden).
3. Legitimate Merchant Access: Merchant B can access their own compliance reports (200 OK).
4. Regulatory / Officer Access: Enforcement Officer, Audit Officer, and Admin can access any report for compliance/audit (200 OK).
5. Non-existent ID: Returns 404 Not Found for non-existent reports.
6. Query Parameter Token Authentication: Supports ?token=<token> for direct browser downloads / window.open().
7. Data Protection: No sensitive compliance or product data is leaked in 401/403 responses.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import save_analysis, create_user
from auth.security import hash_password, create_token, ROLE_MERCHANT, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _create_test_environment():
    """Create test users and an analysis record owned by Merchant Bob."""
    _ensure_test_isolation()

    salt_a, pwh_a = hash_password("pass_a_123")
    salt_b, pwh_b = hash_password("pass_b_123")
    salt_off, pwh_off = hash_password("pass_off_123")
    salt_aud, pwh_aud = hash_password("pass_aud_123")
    salt_adm, pwh_adm = hash_password("pass_adm_123")

    for u, p, s, r, f, org in [
        ("sec02_merchant_a", pwh_a, salt_a, ROLE_MERCHANT, "Merchant Alice", "org_sec02_merchant_a"),
        ("sec02_merchant_b", pwh_b, salt_b, ROLE_MERCHANT, "Merchant Bob", "org_sec02_merchant_b"),
        ("sec02_officer", pwh_off, salt_off, ROLE_ENFORCEMENT, "Officer Charlie", "org_sec02_merchant_b"),
        ("sec02_auditor", pwh_aud, salt_aud, ROLE_AUDIT, "Auditor Dave", "org_sec02_merchant_b"),
        ("sec02_admin", pwh_adm, salt_adm, ROLE_ADMIN, "Admin Eve", "org_ministry"),
    ]:
        try:
            await create_user(u, p, s, r, f, organization_id=org)
        except Exception:
            pass

    token_a = create_token("sec02_merchant_a", ROLE_MERCHANT)
    token_b = create_token("sec02_merchant_b", ROLE_MERCHANT)
    token_officer = create_token("sec02_officer", ROLE_ENFORCEMENT)
    token_auditor = create_token("sec02_auditor", ROLE_AUDIT)
    token_admin = create_token("sec02_admin", ROLE_ADMIN)

    analysis_b = {
        "id": "sec02-test-analysis-bob-001",
        "product_name": "Bob's Organic Honey 500g",
        "image_filename": "placeholder.png",
        "images": json.dumps([{
            "filename": "placeholder.png",
            "image_url": "/api/images/placeholder.png",
            "label": "Front",
            "ocr_text": "Bob's Organic Honey Net Qty: 500g MRP: Rs. 350"
        }]),
        "ocr_text": "Bob's Organic Honey Net Qty: 500g MRP: Rs. 350",
        "extracted_data": json.dumps({
            "product_name": "Bob's Organic Honey 500g",
            "brand": "Bob's Organics",
            "net_quantity": "500 g",
            "mrp": "Rs. 350",
            "manufacturer_name": "Bob Honey Ltd",
            "country_of_origin": "India"
        }),
        "compliance_result": json.dumps({
            "status": "COMPLIANT",
            "score": 100.0,
            "passed_rules": 6,
            "failed_rules": 0,
            "warning_rules": 0,
            "needs_review_rules": 0,
            "not_applicable_rules": 0,
            "total_rules": 6,
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "mrp",
                    "field_label": "Maximum Retail Price (MRP)",
                    "status": "PASS",
                    "detected_value": "Rs. 350",
                    "explanation": "MRP declared properly"
                }
            ],
            "recommendations": []
        }),
        "created_at": "2026-03-18T10:00:00Z",
        "owner_user_id": "sec02_merchant_b"
    }
    await save_analysis(analysis_b)

    return {
        "analysis_id": analysis_b["id"],
        "token_a": token_a,
        "token_b": token_b,
        "token_officer": token_officer,
        "token_auditor": token_auditor,
        "token_admin": token_admin,
    }


@pytest.mark.asyncio
async def test_01_unauthenticated_requests_denied_401():
    """Test 1: Unauthenticated requests to all report export formats return 401."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]

    endpoints = [
        f"/api/report/{analysis_id}",
        f"/api/report/{analysis_id}/pdf",
        f"/api/report/{analysis_id}/csv",
        f"/api/report/{analysis_id}/xlsx",
        f"/api/report/{analysis_id}/json",
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for unauthenticated {ep}, got {resp.status_code}"
        assert "detail" in resp.json()
        assert "Bob's Organic Honey" not in resp.text, f"Leak detected in 401 response for {ep}"


@pytest.mark.asyncio
async def test_02_invalid_token_denied_401():
    """Test 2: Requests with invalid/malformed bearer tokens return 401."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]

    headers = {"Authorization": "Bearer invalid.token.value"}
    endpoints = [
        f"/api/report/{analysis_id}",
        f"/api/report/{analysis_id}/csv",
        f"/api/report/{analysis_id}/xlsx",
        f"/api/report/{analysis_id}/json",
    ]

    for ep in endpoints:
        resp = client.get(ep, headers=headers)
        assert resp.status_code == 401, f"Expected 401 for invalid token on {ep}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_03_cross_merchant_idor_denied_403():
    """Test 3: Merchant A cannot access Merchant B's compliance report (403 Forbidden)."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]
    token_a = env["token_a"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    endpoints = [
        f"/api/report/{analysis_id}",
        f"/api/report/{analysis_id}/pdf",
        f"/api/report/{analysis_id}/csv",
        f"/api/report/{analysis_id}/xlsx",
        f"/api/report/{analysis_id}/json",
    ]

    for ep in endpoints:
        resp = client.get(ep, headers=headers_a)
        assert resp.status_code == 403, f"Expected 403 Forbidden for cross-merchant access on {ep}, got {resp.status_code}"
        # Ensure zero data leakage
        assert "Bob's Organic Honey" not in resp.text
        assert "Bob's Organics" not in resp.text


@pytest.mark.asyncio
async def test_04_legitimate_merchant_access_200():
    """Test 4: Merchant B can access their own compliance report across all formats (200 OK)."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]
    token_b = env["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # PDF / default report
    resp_pdf = client.get(f"/api/report/{analysis_id}", headers=headers_b)
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert len(resp_pdf.content) > 1000

    # Explicit PDF endpoint
    resp_pdf_explicit = client.get(f"/api/report/{analysis_id}/pdf", headers=headers_b)
    assert resp_pdf_explicit.status_code == 200
    assert resp_pdf_explicit.headers["content-type"] == "application/pdf"
    assert len(resp_pdf_explicit.content) > 1000

    # CSV report
    resp_csv = client.get(f"/api/report/{analysis_id}/csv", headers=headers_b)
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "Bob's Organic Honey" in resp_csv.text

    # XLSX report
    resp_xlsx = client.get(f"/api/report/{analysis_id}/xlsx", headers=headers_b)
    assert resp_xlsx.status_code == 200
    assert len(resp_xlsx.content) > 1000

    # JSON report
    resp_json = client.get(f"/api/report/{analysis_id}/json", headers=headers_b)
    assert resp_json.status_code == 200
    data = resp_json.json()
    assert data["id"] == analysis_id
    assert data["product_name"] == "Bob's Organic Honey 500g"


@pytest.mark.asyncio
async def test_05_officer_access_200():
    """Test 5: Enforcement Officer can access any merchant's report for statutory inspection."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]
    token_officer = env["token_officer"]
    headers_off = {"Authorization": f"Bearer {token_officer}"}

    resp = client.get(f"/api/report/{analysis_id}", headers=headers_off)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"

    resp_csv = client.get(f"/api/report/{analysis_id}/csv", headers=headers_off)
    assert resp_csv.status_code == 200


@pytest.mark.asyncio
async def test_06_auditor_access_200():
    """Test 6: Audit Officer can access reports for regulatory audits."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]
    token_auditor = env["token_auditor"]
    headers_aud = {"Authorization": f"Bearer {token_auditor}"}

    resp = client.get(f"/api/report/{analysis_id}/json", headers=headers_aud)
    assert resp.status_code == 200
    assert resp.json()["id"] == analysis_id


@pytest.mark.asyncio
async def test_07_admin_access_200():
    """Test 7: Admin can access any report."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]
    token_admin = env["token_admin"]
    headers_adm = {"Authorization": f"Bearer {token_admin}"}

    resp = client.get(f"/api/report/{analysis_id}/xlsx", headers=headers_adm)
    assert resp.status_code == 200
    assert len(resp.content) > 1000


@pytest.mark.asyncio
async def test_08_query_param_token_authentication():
    """Test 8: Query param ?token= authenticates direct browser downloads / window.open()."""
    env = await _create_test_environment()
    client = TestClient(app)
    analysis_id = env["analysis_id"]
    token_b = env["token_b"]

    resp_pdf = client.get(f"/api/report/{analysis_id}?token={token_b}")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"

    resp_csv = client.get(f"/api/report/{analysis_id}/csv?token={token_b}")
    assert resp_csv.status_code == 200
    assert "Bob's Organic Honey" in resp_csv.text

    resp_xlsx = client.get(f"/api/report/{analysis_id}/xlsx?token={token_b}")
    assert resp_xlsx.status_code == 200


@pytest.mark.asyncio
async def test_09_nonexistent_report_returns_404():
    """Test 9: Requesting a non-existent report ID returns 404."""
    env = await _create_test_environment()
    client = TestClient(app)
    token_b = env["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = client.get("/api/report/nonexistent-uuid-9999", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Analysis not found"
