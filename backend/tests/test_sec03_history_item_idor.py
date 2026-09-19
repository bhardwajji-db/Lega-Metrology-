"""
Test Suite for SEC-03: History Item IDOR / Broken Object-Level Authorization.

Verifies:
1. Unauthenticated history item requests return 401 Unauthorized.
2. Invalid or malformed tokens return 401 Unauthorized.
3. Merchant A accessing own history record returns 200 OK.
4. Merchant A accessing Merchant B history record returns 403 Forbidden (IDOR protection).
5. Merchant B accessing Merchant A history record returns 403 Forbidden (bidirectional isolation).
6. Cross-user 403 responses leak ZERO sensitive data (product names, OCR text, manufacturer, etc.).
7. Nonexistent history IDs return 404 Not Found without leaking filesystem paths or SQL details.
8. Enforcement Officers can access merchant screening records for statutory inspection (200 OK).
9. Audit Officers can access merchant screening records for regulatory audit (200 OK).
10. Admins can access merchant screening records (200 OK).
11. History list (/api/history) continues to filter and display only the merchant's own records.
12. Direct-ID manipulation (tampering analysis UUIDs) is strictly blocked by ownership authorization.
13. Demo benchmark cases remain accessible to all authenticated users.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import save_analysis, create_user
from auth.security import (
    hash_password,
    create_token,
    ROLE_MERCHANT,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _setup_sec03_test_data():
    """Create test users and isolated analysis records for Merchant A and Merchant B."""
    _ensure_test_isolation()

    salt_a, pwh_a = hash_password("pass_a_123")
    salt_b, pwh_b = hash_password("pass_b_123")
    salt_off, pwh_off = hash_password("pass_off_123")
    salt_aud, pwh_aud = hash_password("pass_aud_123")
    salt_adm, pwh_adm = hash_password("pass_adm_123")

    for u, p, s, r, f, org in [
        ("sec03_merchant_a", pwh_a, salt_a, ROLE_MERCHANT, "Merchant Alice", "org_sec03_merchant_a"),
        ("sec03_merchant_b", pwh_b, salt_b, ROLE_MERCHANT, "Merchant Bob", "org_sec03_merchant_b"),
        ("sec03_officer", pwh_off, salt_off, ROLE_ENFORCEMENT, "Officer Charlie", "org_sec03_merchant_b"),
        ("sec03_auditor", pwh_aud, salt_aud, ROLE_AUDIT, "Auditor Dave", "org_sec03_merchant_a"),
        ("sec03_admin", pwh_adm, salt_adm, ROLE_ADMIN, "Admin Eve", "org_ministry"),
    ]:
        try:
            await create_user(u, p, s, r, f, organization_id=org)
        except Exception:
            pass

    token_a = create_token("sec03_merchant_a", ROLE_MERCHANT)
    token_b = create_token("sec03_merchant_b", ROLE_MERCHANT)
    token_officer = create_token("sec03_officer", ROLE_ENFORCEMENT)
    token_auditor = create_token("sec03_auditor", ROLE_AUDIT)
    token_admin = create_token("sec03_admin", ROLE_ADMIN)

    # Analysis A owned by Merchant Alice
    analysis_a = {
        "id": "sec03-analysis-alice-001",
        "product_name": "Alice Premium Almonds 200g",
        "image_filename": "alice_almonds.jpg",
        "images": json.dumps([{
            "filename": "alice_almonds.jpg",
            "image_url": "/api/images/alice_almonds.jpg",
            "label": "Front",
            "ocr_text": "Alice Premium Almonds Net Wt: 200g MRP: Rs. 299"
        }]),
        "ocr_text": "Alice Premium Almonds Net Wt: 200g MRP: Rs. 299",
        "extracted_data": json.dumps({
            "product_name": "Alice Premium Almonds 200g",
            "brand": "Alice Naturals",
            "net_quantity": "200 g",
            "mrp": "Rs. 299",
            "manufacturer_name": "Alice Agro Foods Pvt Ltd",
            "country_of_origin": "India"
        }),
        "compliance_result": json.dumps({
            "status": "COMPLIANT",
            "score": 98.0,
            "passed_rules": 5,
            "failed_rules": 0,
            "warning_rules": 0,
            "needs_review_rules": 0,
            "not_applicable_rules": 0,
            "total_rules": 5,
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "mrp",
                    "field_label": "Maximum Retail Price (MRP)",
                    "status": "PASS",
                    "detected_value": "Rs. 299",
                    "explanation": "MRP declared properly"
                }
            ],
            "recommendations": []
        }),
        "created_at": "2026-03-18T10:00:00Z",
        "owner_user_id": "sec03_merchant_a"
    }
    await save_analysis(analysis_a)

    # Analysis B owned by Merchant Bob
    analysis_b = {
        "id": "sec03-analysis-bob-002",
        "product_name": "Bob Secret Protein Shake 500ml",
        "image_filename": "bob_shake.jpg",
        "images": json.dumps([{
            "filename": "bob_shake.jpg",
            "image_url": "/api/images/bob_shake.jpg",
            "label": "Front",
            "ocr_text": "Bob Secret Protein Shake Net Vol: 500ml MRP: Rs. 180"
        }]),
        "ocr_text": "Bob Secret Protein Shake Net Vol: 500ml MRP: Rs. 180",
        "extracted_data": json.dumps({
            "product_name": "Bob Secret Protein Shake 500ml",
            "brand": "Bob Nutrition",
            "net_quantity": "500 ml",
            "mrp": "Rs. 180",
            "manufacturer_name": "Bob Beverages Ltd",
            "country_of_origin": "India"
        }),
        "compliance_result": json.dumps({
            "status": "NON_COMPLIANT",
            "score": 60.0,
            "passed_rules": 3,
            "failed_rules": 2,
            "warning_rules": 0,
            "needs_review_rules": 0,
            "not_applicable_rules": 0,
            "total_rules": 5,
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "mrp",
                    "field_label": "Maximum Retail Price (MRP)",
                    "status": "PASS",
                    "detected_value": "Rs. 180",
                    "explanation": "MRP declared properly"
                }
            ],
            "recommendations": []
        }),
        "created_at": "2026-03-18T11:00:00Z",
        "owner_user_id": "sec03_merchant_b"
    }
    await save_analysis(analysis_b)

    return {
        "id_a": analysis_a["id"],
        "id_b": analysis_b["id"],
        "token_a": token_a,
        "token_b": token_b,
        "token_officer": token_officer,
        "token_auditor": token_auditor,
        "token_admin": token_admin,
    }


@pytest.mark.asyncio
async def test_01_unauthenticated_history_detail_returns_401():
    """Test 1: Unauthenticated request to /api/history/{id} must return 401."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    resp = client.get(f"/api/history/{data['id_a']}")
    assert resp.status_code == 401
    assert "Bob Secret Protein Shake" not in resp.text
    assert "Alice Premium Almonds" not in resp.text


@pytest.mark.asyncio
async def test_02_invalid_token_returns_401():
    """Test 2: Request with invalid/malformed bearer token returns 401."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": "Bearer invalid.jwt.token.value"}
    resp = client.get(f"/api/history/{data['id_a']}", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_03_merchant_a_accesses_own_history_200():
    """Test 3: Merchant Alice can access her own analysis record."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get(f"/api/history/{data['id_a']}", headers=headers)
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["id"] == data["id_a"]
    assert res_json["product_name"] == "Alice Premium Almonds 200g"
    assert res_json["owner_user_id"] == "sec03_merchant_a"


@pytest.mark.asyncio
async def test_04_merchant_a_accesses_merchant_b_history_denied_403():
    """Test 4: Merchant Alice attempting to access Merchant Bob's record returns 403 Forbidden."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get(f"/api/history/{data['id_b']}", headers=headers)
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_05_merchant_b_accesses_merchant_a_history_denied_403():
    """Test 5: Merchant Bob attempting to access Merchant Alice's record returns 403 Forbidden."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_b']}"}
    resp = client.get(f"/api/history/{data['id_a']}", headers=headers)
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_06_cross_user_denied_zero_data_leakage():
    """Test 6: Cross-user 403 responses contain ZERO sensitive data."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get(f"/api/history/{data['id_b']}", headers=headers)
    assert resp.status_code == 403

    raw_text = resp.text
    # Verify no sensitive data from Bob's record leaked in response
    assert "Bob Secret Protein Shake" not in raw_text
    assert "Bob Nutrition" not in raw_text
    assert "Bob Beverages" not in raw_text
    assert "bob_shake.jpg" not in raw_text
    assert "sec03_merchant_b" not in raw_text
    assert "500ml" not in raw_text
    assert "180" not in raw_text


@pytest.mark.asyncio
async def test_07_nonexistent_history_id_returns_404():
    """Test 7: Requesting a non-existent history ID returns 404."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get("/api/history/non-existent-analysis-id-9999", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Analysis not found"
    assert "SELECT" not in resp.text
    assert "traceback" not in resp.text.lower()


@pytest.mark.asyncio
async def test_08_enforcement_officer_access_200():
    """Test 8: Enforcement Officer can access merchant analysis records for regulatory inspection."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_officer']}"}
    resp = client.get(f"/api/history/{data['id_b']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == data["id_b"]
    assert resp.json()["product_name"] == "Bob Secret Protein Shake 500ml"


@pytest.mark.asyncio
async def test_09_audit_officer_access_200():
    """Test 9: Audit Officer can access merchant analysis records for regulatory audit."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_auditor']}"}
    resp = client.get(f"/api/history/{data['id_a']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == data["id_a"]


@pytest.mark.asyncio
async def test_10_admin_access_200():
    """Test 10: Admin can access any merchant analysis record."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_admin']}"}
    resp = client.get(f"/api/history/{data['id_b']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == data["id_b"]


@pytest.mark.asyncio
async def test_11_history_list_isolation():
    """Test 11: GET /api/history returns only the authenticated merchant's records."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    # Merchant Alice history list
    headers_a = {"Authorization": f"Bearer {data['token_a']}"}
    resp_a = client.get("/api/history", headers=headers_a)
    assert resp_a.status_code == 200
    items_a = resp_a.json()
    ids_a = [item["id"] for item in items_a]
    assert data["id_a"] in ids_a
    assert data["id_b"] not in ids_a

    # Merchant Bob history list
    headers_b = {"Authorization": f"Bearer {data['token_b']}"}
    resp_b = client.get("/api/history", headers=headers_b)
    assert resp_b.status_code == 200
    items_b = resp_b.json()
    ids_b = [item["id"] for item in items_b]
    assert data["id_b"] in ids_b
    assert data["id_a"] not in ids_b


@pytest.mark.asyncio
async def test_12_direct_id_manipulation_idor_attack():
    """Test 12: Direct parameter manipulation of UUIDs in history requests is blocked."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    # Alice token requesting Bob's UUID -> 403
    r1 = client.get(f"/api/history/{data['id_b']}", headers={"Authorization": f"Bearer {data['token_a']}"})
    assert r1.status_code == 403

    # Bob token requesting Alice's UUID -> 403
    r2 = client.get(f"/api/history/{data['id_a']}", headers={"Authorization": f"Bearer {data['token_b']}"})
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_13_demo_benchmark_accessible_to_authenticated_users():
    """Test 13: Demo benchmark cases remain accessible to all authenticated roles."""
    data = await _setup_sec03_test_data()
    client = TestClient(app)

    # Merchant access to demo-1
    resp_m = client.get("/api/history/demo-1", headers={"Authorization": f"Bearer {data['token_a']}"})
    assert resp_m.status_code == 200
    assert resp_m.json()["id"] in ("demo-1", "1")

    # Officer access to demo-2
    resp_off = client.get("/api/history/demo-2", headers={"Authorization": f"Bearer {data['token_officer']}"})
    assert resp_off.status_code == 200
