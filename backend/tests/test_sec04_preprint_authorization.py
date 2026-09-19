"""
Test Suite for SEC-04: Preprint Authorization / Broken Object-Level Authorization.

Verifies:
1. Unauthenticated requests to preprint endpoints return 401 Unauthorized.
2. Invalid or malformed bearer tokens return 401 Unauthorized.
3. Merchant A can view/retrieve their own preprint packaging artwork (200 OK).
4. Merchant A attempting to view Merchant B's artwork returns 403 Forbidden (IDOR protection).
5. Merchant B attempting to view Merchant A's artwork returns 403 Forbidden (bidirectional isolation).
6. Merchant A can delete their own artwork (200 OK) with clean file removal.
7. Merchant A attempting to delete Merchant B's artwork returns 403 Forbidden and preserves DB record & files.
8. Merchant B attempting to delete Merchant A's artwork returns 403 Forbidden.
9. Merchant cross-user approval attempts (Merchant A approving/rejecting Merchant B's artwork) return 403 Forbidden with state unchanged.
10. Authorized approval role (Officer / Admin / Owner) can submit valid approval decisions with disclaimer.
11. Non-existent artwork IDs return 404 Not Found without disclosing internal details.
12. Direct-ID manipulation (tampering artwork IDs) is strictly blocked by ownership authorization.
13. Artwork preview images remain protected by SEC-01 authenticated file access.
14. Zero sensitive data leakage in all 403 Forbidden responses.
15. State integrity: Denied operations make 0 mutations to database or filesystem.
"""

import os
import io
import json
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import save_artwork, get_artwork, create_user
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


def _create_sample_png_bytes(label: str = "Artwork") -> bytes:
    """Helper to generate in-memory synthetic PNG."""
    img = Image.new("RGB", (600, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), f"BRAND: {label}", fill=(0, 0, 0))
    draw.text((20, 50), "Net Qty: 500g", fill=(0, 0, 0))
    draw.text((20, 80), "MRP: Rs. 150", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _setup_sec04_test_data():
    """Create test users and isolated artwork records for Merchant Alice and Merchant Bob."""
    _ensure_test_isolation()

    salt_a, pwh_a = hash_password("pass_a_123")
    salt_b, pwh_b = hash_password("pass_b_123")
    salt_off, pwh_off = hash_password("pass_off_123")
    salt_aud, pwh_aud = hash_password("pass_aud_123")
    salt_adm, pwh_adm = hash_password("pass_adm_123")

    for u, p, s, r, f, org in [
        ("sec04_merchant_a", pwh_a, salt_a, ROLE_MERCHANT, "Merchant Alice", "org_sec04_merchant_a"),
        ("sec04_merchant_b", pwh_b, salt_b, ROLE_MERCHANT, "Merchant Bob", "org_sec04_merchant_b"),
        ("sec04_officer", pwh_off, salt_off, ROLE_ENFORCEMENT, "Officer Charlie", "org_sec04_merchant_a"),
        ("sec04_auditor", pwh_aud, salt_aud, ROLE_AUDIT, "Auditor Dave", "org_sec04_merchant_a"),
        ("sec04_admin", pwh_adm, salt_adm, ROLE_ADMIN, "Admin Eve", "org_ministry"),
    ]:
        try:
            await create_user(u, p, s, r, f, organization_id=org)
        except Exception:
            pass

    token_a = create_token("sec04_merchant_a", ROLE_MERCHANT)
    token_b = create_token("sec04_merchant_b", ROLE_MERCHANT)
    token_officer = create_token("sec04_officer", ROLE_ENFORCEMENT)
    token_auditor = create_token("sec04_auditor", ROLE_AUDIT)
    token_admin = create_token("sec04_admin", ROLE_ADMIN)

    # Artwork A for Merchant Alice
    art_a_id = "art-alice-secret-001"
    art_a_file = f"{art_a_id}.png"
    art_a_path = os.path.join(settings.UPLOAD_DIR, art_a_file)
    with open(art_a_path, "wb") as f:
        f.write(_create_sample_png_bytes("Alice Secret Recipe Tea"))

    art_a_doc = {
        "id": art_a_id,
        "filename": "alice_tea_artwork.png",
        "file_path": art_a_path,
        "file_type": "PNG",
        "file_size": os.path.getsize(art_a_path),
        "page_count": 1,
        "dimensions": {"width": 600, "height": 800},
        "dpi": 72.0,
        "source_identity": "PRE-PRINT ARTWORK",
        "compliance_ruleset": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "parent_artwork_id": None,
        "iteration_number": 1,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "approval_record": None,
        "analysis_result": {"overall_status": "COMPLIANT", "score": 95.0},
        "pages_data": [
            {
                "page_number": 1,
                "width": 600,
                "height": 800,
                "dpi": 72.0,
                "image_path": art_a_path,
                "image_url": f"/api/images/{art_a_file}",
            }
        ],
        "owner_user_id": "sec04_merchant_a",
        "created_at": "2026-03-18T10:00:00Z",
        "updated_at": "2026-03-18T10:00:00Z",
    }
    await save_artwork(art_a_doc)

    # Artwork B for Merchant Bob
    art_b_id = "art-bob-confidential-002"
    art_b_file = f"{art_b_id}.png"
    art_b_path = os.path.join(settings.UPLOAD_DIR, art_b_file)
    with open(art_b_path, "wb") as f:
        f.write(_create_sample_png_bytes("Bob Confidential Supplement"))

    art_b_doc = {
        "id": art_b_id,
        "filename": "bob_supplement_artwork.png",
        "file_path": art_b_path,
        "file_type": "PNG",
        "file_size": os.path.getsize(art_b_path),
        "page_count": 1,
        "dimensions": {"width": 600, "height": 800},
        "dpi": 72.0,
        "source_identity": "PRE-PRINT ARTWORK",
        "compliance_ruleset": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "parent_artwork_id": None,
        "iteration_number": 1,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "approval_record": None,
        "analysis_result": {"overall_status": "COMPLIANT", "score": 90.0},
        "pages_data": [
            {
                "page_number": 1,
                "width": 600,
                "height": 800,
                "dpi": 72.0,
                "image_path": art_b_path,
                "image_url": f"/api/images/{art_b_file}",
            }
        ],
        "owner_user_id": "sec04_merchant_b",
        "created_at": "2026-03-18T11:00:00Z",
        "updated_at": "2026-03-18T11:00:00Z",
    }
    await save_artwork(art_b_doc)

    return {
        "art_a_id": art_a_id,
        "art_a_path": art_a_path,
        "art_a_file": art_a_file,
        "art_b_id": art_b_id,
        "art_b_path": art_b_path,
        "art_b_file": art_b_file,
        "token_a": token_a,
        "token_b": token_b,
        "token_officer": token_officer,
        "token_auditor": token_auditor,
        "token_admin": token_admin,
    }


@pytest.mark.asyncio
async def test_01_unauthenticated_get_artwork_returns_401():
    """Test 1: Unauthenticated GET /api/preprint/{artwork_id} returns 401."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    resp = client.get(f"/api/preprint/{data['art_a_id']}")
    assert resp.status_code == 401
    assert "Alice Secret Recipe" not in resp.text


@pytest.mark.asyncio
async def test_02_invalid_token_returns_401():
    """Test 2: Invalid/malformed token on GET /api/preprint/{artwork_id} returns 401."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": "Bearer invalid.jwt.token.here"}
    resp = client.get(f"/api/preprint/{data['art_a_id']}", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_03_merchant_a_accesses_own_artwork_200():
    """Test 3: Merchant Alice can access her own artwork record."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get(f"/api/preprint/{data['art_a_id']}", headers=headers)
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["id"] == data["art_a_id"]
    assert res_json["filename"] == "alice_tea_artwork.png"
    assert res_json["owner_user_id"] == "sec04_merchant_a"


@pytest.mark.asyncio
async def test_04_merchant_a_accesses_merchant_b_artwork_denied_403():
    """Test 4: Merchant Alice attempting to access Merchant Bob's artwork returns 403 Forbidden."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get(f"/api/preprint/{data['art_b_id']}", headers=headers)
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_05_merchant_b_accesses_merchant_a_artwork_denied_403():
    """Test 5: Merchant Bob attempting to access Merchant Alice's artwork returns 403 Forbidden (bidirectional)."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_b']}"}
    resp = client.get(f"/api/preprint/{data['art_a_id']}", headers=headers)
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_06_merchant_a_deletes_own_artwork_200():
    """Test 6: Merchant Alice can delete her own artwork and its files."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.delete(f"/api/preprint/{data['art_a_id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # DB record is gone
    assert await get_artwork(data["art_a_id"]) is None
    # File is cleaned up
    assert not os.path.exists(data["art_a_path"])


@pytest.mark.asyncio
async def test_07_merchant_a_deletes_merchant_b_artwork_denied_403():
    """Test 7: Merchant Alice cannot delete Merchant Bob's artwork (403 Forbidden, state intact)."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.delete(f"/api/preprint/{data['art_b_id']}", headers=headers)
    assert resp.status_code == 403

    # Verify artwork B still exists in database
    art_b = await get_artwork(data["art_b_id"])
    assert art_b is not None
    assert art_b["id"] == data["art_b_id"]

    # Verify artwork B file is still intact
    assert os.path.exists(data["art_b_path"])


@pytest.mark.asyncio
async def test_08_merchant_b_deletes_merchant_a_artwork_denied_403():
    """Test 8: Merchant Bob cannot delete Merchant Alice's artwork."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_b']}"}
    resp = client.delete(f"/api/preprint/{data['art_a_id']}", headers=headers)
    assert resp.status_code == 403

    # Verify artwork A remains in database and filesystem
    art_a = await get_artwork(data["art_a_id"])
    assert art_a is not None
    assert os.path.exists(data["art_a_path"])


@pytest.mark.asyncio
async def test_09_merchant_cross_user_approval_denied_403():
    """Test 9: Merchant Alice cannot approve or modify Merchant Bob's artwork status."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    body = {
        "reviewer_name": "Alice Attacker",
        "reviewer_role": "MERCHANT_PUBLIC",
        "decision": "APPROVED",
        "comments": "Malicious approval attempt",
        "legal_disclaimer_acknowledged": True,
    }
    resp = client.post(f"/api/preprint/{data['art_b_id']}/approval", json=body, headers=headers)
    assert resp.status_code == 403

    # Verify state was not modified
    art_b = await get_artwork(data["art_b_id"])
    assert art_b["approval_status"] == "PENDING"
    assert art_b["workflow_status"] == "DRAFT"


@pytest.mark.asyncio
async def test_10_merchant_b_cross_user_approval_denied_403():
    """Test 10: Merchant Bob cannot submit approval decisions on Merchant Alice's artwork."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_b']}"}
    body = {
        "reviewer_name": "Bob Attacker",
        "reviewer_role": "MERCHANT_PUBLIC",
        "decision": "REJECTED",
        "comments": "Malicious rejection attempt",
        "legal_disclaimer_acknowledged": True,
    }
    resp = client.post(f"/api/preprint/{data['art_a_id']}/approval", json=body, headers=headers)
    assert resp.status_code == 403

    # Verify state remains unchanged
    art_a = await get_artwork(data["art_a_id"])
    assert art_a["approval_status"] == "PENDING"
    assert art_a["workflow_status"] == "DRAFT"


@pytest.mark.asyncio
async def test_11_authorized_approval_workflow_success():
    """Test 11: Enforcement Officer / Owner can submit legitimate approval decisions."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers_off = {"Authorization": f"Bearer {data['token_officer']}"}
    body = {
        "reviewer_name": "Officer Charlie",
        "reviewer_role": "ENFORCEMENT_OFFICER",
        "decision": "APPROVED",
        "comments": "All statutory PDP dimensions verified.",
        "legal_disclaimer_acknowledged": True,
    }
    resp = client.post(f"/api/preprint/{data['art_a_id']}/approval", json=body, headers=headers_off)
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["success"] is True
    assert res_json["approval_status"] == "APPROVED"
    assert res_json["workflow_status"] == "READY_FOR_PRINT"


@pytest.mark.asyncio
async def test_12_nonexistent_artwork_returns_404():
    """Test 12: Requesting non-existent artwork ID returns 404."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get("/api/preprint/art-nonexistent-9999", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Artwork 'art-nonexistent-9999' not found."
    assert "SELECT" not in resp.text


@pytest.mark.asyncio
async def test_13_direct_artwork_id_manipulation_idor():
    """Test 13: Direct parameter manipulation on GET, DELETE, and approval routes is blocked."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    # 1. GET with swapped ID
    r_get = client.get(f"/api/preprint/{data['art_b_id']}", headers={"Authorization": f"Bearer {data['token_a']}"})
    assert r_get.status_code == 403

    # 2. DELETE with swapped ID
    r_del = client.delete(f"/api/preprint/{data['art_b_id']}", headers={"Authorization": f"Bearer {data['token_a']}"})
    assert r_del.status_code == 403

    # 3. Analyze with swapped ID
    r_ana = client.post(f"/api/preprint/{data['art_b_id']}/analyze", headers={"Authorization": f"Bearer {data['token_a']}"})
    assert r_ana.status_code == 403


@pytest.mark.asyncio
async def test_14_protected_preview_file_access():
    """Test 14: Merchant A cannot access Merchant B's rendered page preview image via /api/images/{filename}."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    # Alice attempts to access Bob's artwork preview image
    resp = client.get(
        f"/api/images/{data['art_b_file']}",
        headers={"Authorization": f"Bearer {data['token_a']}"}
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_15_zero_sensitive_data_leakage_in_403_responses():
    """Test 15: Denied 403 responses contain zero sensitive data from target artwork."""
    data = await _setup_sec04_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['token_a']}"}
    resp = client.get(f"/api/preprint/{data['art_b_id']}", headers=headers)
    assert resp.status_code == 403

    raw_text = resp.text
    assert "bob_supplement_artwork.png" not in raw_text
    assert "Bob Confidential" not in raw_text
    assert "sec04_merchant_b" not in raw_text
    assert data["art_b_path"] not in raw_text
