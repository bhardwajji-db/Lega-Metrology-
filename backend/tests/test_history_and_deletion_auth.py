import pytest
import os
import json
import asyncio
from fastapi.testclient import TestClient
from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import create_token, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT, hash_password
from database.db import create_user, save_analysis, get_analysis, get_analyses


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


@pytest.mark.asyncio
async def test_merchant_ownership_delete_success():
    """Merchant can successfully delete their own analysis record and uploaded assets."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("merchant_alice", pwh, salt, ROLE_MERCHANT, "Alice Merchant")
    token_alice = create_token("merchant_alice", ROLE_MERCHANT)

    analysis_id = "item-alice-001"
    test_file = os.path.join(settings.UPLOAD_DIR, f"{analysis_id}_front.png")
    with open(test_file, "wb") as f:
        f.write(b'ALICE_IMAGE_BYTES')

    await save_analysis({
        "id": analysis_id,
        "product_name": "Alice Organic Juice",
        "image_filename": f"{analysis_id}_front.png",
        "ocr_text": "Net Qty 1L MRP Rs 120",
        "extracted_data": {"net_quantity": "1L", "mrp": "Rs 120"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-12T12:00:00Z",
        "images": [{"filename": f"{analysis_id}_front.png", "image_url": f"/api/images/{analysis_id}_front.png"}],
        "owner_user_id": "merchant_alice"
    })

    # Alice deletes her own record
    resp = client.delete(
        f"/api/history/{analysis_id}",
        headers={"Authorization": f"Bearer {token_alice}"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == analysis_id
    assert not os.path.exists(test_file), "Alice's uploaded file must be cleaned up"
    assert await get_analysis(analysis_id) is None, "Record must be deleted from DB"


@pytest.mark.asyncio
async def test_merchant_cannot_delete_other_merchant_record():
    """Merchant Bob cannot delete Merchant Alice's record."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("alice_m", pwh, salt, ROLE_MERCHANT, "Alice")
    await create_user("bob_m", pwh, salt, ROLE_MERCHANT, "Bob")

    token_bob = create_token("bob_m", ROLE_MERCHANT)

    analysis_id = "item-alice-protected"
    test_file = os.path.join(settings.UPLOAD_DIR, f"{analysis_id}_front.png")
    with open(test_file, "wb") as f:
        f.write(b'PROTECTED_BYTES')

    await save_analysis({
        "id": analysis_id,
        "product_name": "Alice Protected Tea",
        "image_filename": f"{analysis_id}_front.png",
        "ocr_text": "Net Qty 250g MRP Rs 150",
        "extracted_data": {"net_quantity": "250g", "mrp": "Rs 150"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-12T12:00:00Z",
        "images": [{"filename": f"{analysis_id}_front.png", "image_url": f"/api/images/{analysis_id}_front.png"}],
        "owner_user_id": "alice_m"
    })

    # Bob attempts to delete Alice's record -> 403 Forbidden
    resp = client.delete(
        f"/api/history/{analysis_id}",
        headers={"Authorization": f"Bearer {token_bob}"}
    )
    assert resp.status_code == 403
    assert "Merchants can only delete their own records" in resp.json()["detail"]
    assert os.path.exists(test_file), "File must not be deleted by unauthorized merchant"
    assert await get_analysis(analysis_id) is not None, "Record must remain in DB"


@pytest.mark.asyncio
async def test_merchant_cannot_delete_unowned_record():
    """Merchant cannot delete a record without owner_user_id or owned by system/officer."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("charlie_m", pwh, salt, ROLE_MERCHANT, "Charlie")
    token_charlie = create_token("charlie_m", ROLE_MERCHANT)

    analysis_id = "item-unowned-legacy"
    await save_analysis({
        "id": analysis_id,
        "product_name": "Legacy Unowned Snack",
        "image_filename": f"{analysis_id}.png",
        "ocr_text": "Sample",
        "extracted_data": {},
        "compliance_result": {"checks": []},
        "score": 80.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-12T12:00:00Z",
        "images": [],
        "owner_user_id": ""
    })

    resp = client.delete(
        f"/api/history/{analysis_id}",
        headers={"Authorization": f"Bearer {token_charlie}"}
    )
    assert resp.status_code == 403
    assert await get_analysis(analysis_id) is not None


@pytest.mark.asyncio
async def test_privileged_officer_and_admin_deletion():
    """Admin and Enforcement Officer can delete any user analysis."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("admin_del", pwh, salt, ROLE_ADMIN, "Admin User")
    await create_user("officer_del", pwh, salt, ROLE_ENFORCEMENT, "Officer User", organization_id="org_merchant_owner")
    await create_user("merchant_owner", pwh, salt, ROLE_MERCHANT, "Merchant User")

    token_admin = create_token("admin_del", ROLE_ADMIN)
    token_officer = create_token("officer_del", ROLE_ENFORCEMENT)

    # 1. Enforcement Officer deletes merchant record
    aid_1 = "item-merchant-del-1"
    await save_analysis({
        "id": aid_1,
        "product_name": "Merchant Item 1",
        "image_filename": f"{aid_1}.png",
        "ocr_text": "Sample",
        "extracted_data": {},
        "compliance_result": {"checks": []},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-12T12:00:00Z",
        "images": [],
        "owner_user_id": "merchant_owner"
    })
    r1 = client.delete(f"/api/history/{aid_1}", headers={"Authorization": f"Bearer {token_officer}"})
    assert r1.status_code == 200
    assert await get_analysis(aid_1) is None

    # 2. Admin deletes merchant record
    aid_2 = "item-merchant-del-2"
    await save_analysis({
        "id": aid_2,
        "product_name": "Merchant Item 2",
        "image_filename": f"{aid_2}.png",
        "ocr_text": "Sample",
        "extracted_data": {},
        "compliance_result": {"checks": []},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-12T12:00:00Z",
        "images": [],
        "owner_user_id": "merchant_owner"
    })
    r2 = client.delete(f"/api/history/{aid_2}", headers={"Authorization": f"Bearer {token_admin}"})
    assert r2.status_code == 200
    assert await get_analysis(aid_2) is None


@pytest.mark.asyncio
async def test_audit_officer_cannot_delete():
    """Audit officer has read-only access and cannot delete screening records."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("audit_inspector", pwh, salt, ROLE_AUDIT, "Audit Inspector", organization_id="org_ministry")
    token_audit = create_token("audit_inspector", ROLE_AUDIT)

    aid = "item-audit-test"
    await save_analysis({
        "id": aid,
        "product_name": "Audit Test Product",
        "image_filename": f"{aid}.png",
        "ocr_text": "Sample",
        "extracted_data": {},
        "compliance_result": {"checks": []},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-12T12:00:00Z",
        "images": [],
        "owner_user_id": "audit_inspector",
        "organization_id": "org_ministry",
    })

    resp = client.delete(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token_audit}"})
    assert resp.status_code == 403
    assert "Insufficient privileges to delete screening records" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_and_not_found_delete():
    """Unauthenticated delete returns 401, non-existent returns 404, demo returns 403."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("admin_user_x", pwh, salt, ROLE_ADMIN, "Admin")
    token_admin = create_token("admin_user_x", ROLE_ADMIN)

    # 1. Unauthenticated -> 401
    r_noauth = client.delete("/api/history/some-random-id")
    assert r_noauth.status_code == 401

    # 2. Non-existent -> 404
    r_404 = client.delete("/api/history/non-existent-id-999", headers={"Authorization": f"Bearer {token_admin}"})
    assert r_404.status_code == 404

    # 3. Demo protected -> 403
    r_demo = client.delete("/api/history/demo-1", headers={"Authorization": f"Bearer {token_admin}"})
    assert r_demo.status_code == 403
    assert "Demonstration benchmark cases are protected" in r_demo.json()["detail"]


@pytest.mark.asyncio
async def test_clear_all_history_admin_only():
    """Clear all history is strictly restricted to ADMIN only."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("admin_clear", pwh, salt, ROLE_ADMIN, "Admin User")
    await create_user("officer_clear", pwh, salt, ROLE_ENFORCEMENT, "Officer User", organization_id="org_ministry")
    await create_user("audit_clear", pwh, salt, ROLE_AUDIT, "Audit User", organization_id="org_ministry")
    await create_user("merchant_clear", pwh, salt, ROLE_MERCHANT, "Merchant User")

    token_admin = create_token("admin_clear", ROLE_ADMIN)
    token_officer = create_token("officer_clear", ROLE_ENFORCEMENT)
    token_audit = create_token("audit_clear", ROLE_AUDIT)
    token_merchant = create_token("merchant_clear", ROLE_MERCHANT)

    # Insert items
    for aid in ["clear-item-1", "clear-item-2"]:
        await save_analysis({
            "id": aid,
            "product_name": f"Product {aid}",
            "image_filename": f"{aid}.png",
            "ocr_text": "Sample",
            "extracted_data": {},
            "compliance_result": {"checks": []},
            "score": 90.0,
            "status": "COMPLIANT",
            "created_at": "2026-09-12T12:00:00Z",
            "images": []
        })

    # Merchant cannot clear all -> 403
    r_m = client.delete("/api/history", headers={"Authorization": f"Bearer {token_merchant}"})
    assert r_m.status_code == 403

    # Officer cannot clear all (only single delete) -> 403
    r_o = client.delete("/api/history", headers={"Authorization": f"Bearer {token_officer}"})
    assert r_o.status_code == 403

    # Audit officer cannot clear all -> 403
    r_aud = client.delete("/api/history", headers={"Authorization": f"Bearer {token_audit}"})
    assert r_aud.status_code == 403

    # Admin can clear all -> 200
    r_a = client.delete("/api/history", headers={"Authorization": f"Bearer {token_admin}"})
    assert r_a.status_code == 200
    assert r_a.json()["deleted_count"] >= 2


@pytest.mark.asyncio
async def test_image_vs_text_analysis_history_and_item_contracts():
    """Verify that image analyses preserve real URLs and text-only analyses do not fabricate fake images."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("contract_user", pwh, salt, ROLE_MERCHANT, "Contract User")
    token = create_token("contract_user", ROLE_MERCHANT)

    # 1. Type A: Image Analysis
    img_id = "img-analysis-001"
    await save_analysis({
        "id": img_id,
        "product_name": "Image Oats",
        "image_filename": f"{img_id}_front.png",
        "ocr_text": "Real OCR text from Oats packaging",
        "extracted_data": {"product_name": "Image Oats", "net_quantity": "1 kg"},
        "compliance_result": {
            "checks": [
                {"rule_id": "LM-001", "field": "mrp", "field_label": "Maximum Retail Price (MRP)", "status": "PASS", "required": True, "detected": True, "detected_value": "Rs 250", "severity": "CRITICAL", "description": "MRP declaration", "source": "Rule 6(1)(e)", "explanation": "Valid", "recommendation": None}
            ],
            "status": "COMPLIANT",
            "compliance_score": 100.0,
            "passed_rules": 1,
            "total_rules": 1,
            "failed_rules": 0
        },
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-13T10:00:00Z",
        "images": [
            {"filename": f"{img_id}_front.png", "image_url": f"/api/images/{img_id}_front.png", "label": "Front", "word_count": 32, "ocr_text": "Real front text"}
        ],
        "owner_user_id": "contract_user"
    })

    # 2. Type B: Text / Listing Analysis (no physical image)
    txt_id = "txt-analysis-001"
    await save_analysis({
        "id": txt_id,
        "product_name": "Listing Oats",
        "image_filename": "",
        "ocr_text": "Text declarations entered manually",
        "extracted_data": {"product_name": "Listing Oats", "net_quantity": "500 g"},
        "compliance_result": {
            "checks": [
                {"rule_id": "LM-001", "field": "mrp", "field_label": "Maximum Retail Price (MRP)", "status": "PASS", "required": True, "detected": True, "detected_value": "Rs 150", "severity": "CRITICAL", "description": "MRP declaration", "source": "Rule 6(1)(e)", "explanation": "Valid", "recommendation": None}
            ],
            "status": "COMPLIANT",
            "compliance_score": 100.0,
            "passed_rules": 1,
            "total_rules": 1,
            "failed_rules": 0
        },
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-13T11:00:00Z",
        "images": [],
        "owner_user_id": "contract_user"
    })

    # Query list history
    resp_list = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp_list.status_code == 200
    items = {item["id"]: item for item in resp_list.json()}

    assert img_id in items
    assert items[img_id]["image_url"] == f"/api/images/{img_id}_front.png"

    assert txt_id in items
    assert items[txt_id]["image_url"] == "/placeholder.png"

    # Query individual history items
    resp_img = client.get(f"/api/history/{img_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp_img.status_code == 200
    img_data = resp_img.json()
    assert len(img_data["images"]) == 1
    assert img_data["images"][0]["image_url"] == f"/api/images/{img_id}_front.png"
    assert img_data["compliance_result"]["checks"][0]["field_label"] == "Maximum Retail Price (MRP)"

    resp_txt = client.get(f"/api/history/{txt_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp_txt.status_code == 200
    txt_data = resp_txt.json()
    assert len(txt_data["images"]) == 0
    assert txt_data["image_url"] == "/placeholder.png"


