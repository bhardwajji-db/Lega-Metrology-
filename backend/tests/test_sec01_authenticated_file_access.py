"""
Test Suite for SEC-01: Remove Public Upload Exposure and Implement Authenticated File Access.

Verifies:
1. Public /uploads mount is removed (unauthenticated access returns 404/denied).
2. /api/images/{filename} requires authentication (401 on missing/invalid token).
3. IDOR Protection: Merchant A cannot access Merchant B's analysis images (403 Forbidden).
4. Authorized Access: Merchant A can access their own analysis images (200 OK).
5. Path Traversal Protection: Directory traversal attempts are rejected (400/404).
6. Missing Files: Non-existent files return 404 without leaking internal filesystem paths.
7. Pre-print Artworks & Page Previews: Ownership checked for PDF and preview JPG files.
8. Officer / Admin Access: Officers and Admins can legitimately inspect files for compliance and audit.
9. Query Parameter Authentication: Supports ?token= for HTML <img> rendering.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import save_analysis, save_artwork, create_user
from auth.security import hash_password, create_token, ROLE_MERCHANT, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


@pytest.fixture(autouse=True)
def setup_test_users_and_files():
    _ensure_test_isolation()


@pytest.mark.asyncio
async def test_01_public_uploads_mount_removed():
    """Test 1: Unauthenticated request to legacy /uploads/<file> must be denied (404)."""
    client = TestClient(app)
    filename = "test_public_exposure_check.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"SAMPLE_IMAGE_DATA_BYTES")

    try:
        resp = client.get(f"/uploads/{filename}")
        assert resp.status_code in (404, 401, 403), f"Public access must not be allowed, got status {resp.status_code}"
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_02_new_endpoint_without_authentication():
    """Test 2: Request to /api/images/<file> without auth token must return 401 Unauthorized."""
    client = TestClient(app)
    filename = "test_unauth_file.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"SAMPLE_DATA")

    try:
        resp = client.get(f"/api/images/{filename}")
        assert resp.status_code == 401
        assert "detail" in resp.json()
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_03_merchant_a_accessing_merchant_b_file_denied():
    """Test 3: Merchant A cannot access Merchant B's analysis image (403 Forbidden)."""
    client = TestClient(app)
    
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_alice", pwh, salt, ROLE_MERCHANT, "Alice Merchant")
    except Exception:
        pass
    try:
        await create_user("sec01_bob", pwh, salt, ROLE_MERCHANT, "Bob Merchant")
    except Exception:
        pass

    token_alice = create_token("sec01_alice", ROLE_MERCHANT)
    token_bob = create_token("sec01_bob", ROLE_MERCHANT)

    file_bob = "analysis_bob_123_front.jpg"
    filepath_bob = os.path.join(settings.UPLOAD_DIR, file_bob)
    with open(filepath_bob, "wb") as f:
        f.write(b"BOB_PRIVATE_PACKAGING_IMAGE")

    # Save analysis owned by Bob
    await save_analysis({
        "id": "analysis_bob_123",
        "product_name": "Bob Protein Powder",
        "image_filename": file_bob,
        "ocr_text": "Net Wt 500g MRP 499",
        "extracted_data": {},
        "compliance_result": {},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T10:00:00Z",
        "images": [{"filename": file_bob, "image_url": f"/api/images/{file_bob}"}],
        "owner_user_id": "sec01_bob"
    })

    try:
        # Alice attempts to access Bob's file
        resp = client.get(
            f"/api/images/{file_bob}",
            headers={"Authorization": f"Bearer {token_alice}"}
        )
        assert resp.status_code == 403, f"Expected 403 Forbidden for cross-merchant access, got {resp.status_code}"
        assert "access denied" in resp.json().get("detail", "").lower()
    finally:
        if os.path.exists(filepath_bob):
            os.remove(filepath_bob)


@pytest.mark.asyncio
async def test_04_merchant_accessing_own_file_success():
    """Test 4: Merchant A accessing own analysis image receives 200 OK with correct content."""
    client = TestClient(app)
    
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_alice_own", pwh, salt, ROLE_MERCHANT, "Alice Own")
    except Exception:
        pass
    token_alice = create_token("sec01_alice_own", ROLE_MERCHANT)

    file_alice = "analysis_alice_456_front.jpg"
    filepath_alice = os.path.join(settings.UPLOAD_DIR, file_alice)
    image_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00ALICE_IMAGE_BYTES"
    with open(filepath_alice, "wb") as f:
        f.write(image_content)

    await save_analysis({
        "id": "analysis_alice_456",
        "product_name": "Alice Organic Tea",
        "image_filename": file_alice,
        "ocr_text": "Net Wt 250g MRP 199",
        "extracted_data": {},
        "compliance_result": {},
        "score": 95.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T10:00:00Z",
        "images": [{"filename": file_alice, "image_url": f"/api/images/{file_alice}"}],
        "owner_user_id": "sec01_alice_own"
    })

    try:
        resp = client.get(
            f"/api/images/{file_alice}",
            headers={"Authorization": f"Bearer {token_alice}"}
        )
        assert resp.status_code == 200
        assert resp.content == image_content
        assert "image/jpeg" in resp.headers.get("content-type", "")
    finally:
        if os.path.exists(filepath_alice):
            os.remove(filepath_alice)


@pytest.mark.asyncio
async def test_05_path_traversal_attempts_denied():
    """Test 5: Path traversal attempts must be rejected."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_admin_trav", pwh, salt, ROLE_ADMIN, "Admin User")
    except Exception:
        pass
    token = create_token("sec01_admin_trav", ROLE_ADMIN)

    traversal_payloads = [
        "../../config.py",
        "..\\..\\config.py",
        "../uploads/something.jpg",
        "nested/../../secret.txt",
        "test%2f..%2fsecret.txt",
    ]

    for payload in traversal_payloads:
        resp = client.get(
            f"/api/images/{payload}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code in (400, 404, 422), f"Payload '{payload}' returned unexpected {resp.status_code}"


@pytest.mark.asyncio
async def test_06_non_existent_file_returns_404():
    """Test 6: Request for non-existent file returns 404 without leaking filesystem path."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_admin_404", pwh, salt, ROLE_ADMIN, "Admin User")
    except Exception:
        pass
    token = create_token("sec01_admin_404", ROLE_ADMIN)

    resp = client.get(
        "/api/images/definitely_not_a_real_file_99999.png",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "Requested file not found." in detail
    assert "C:" not in detail
    assert "/data" not in detail
    assert "uploads" not in detail


@pytest.mark.asyncio
async def test_07_preprint_artwork_cross_user_denied():
    """Test 7: Merchant A cannot access Merchant B's pre-print artwork or preview images."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_art_alice", pwh, salt, ROLE_MERCHANT, "Alice Art")
    except Exception:
        pass
    try:
        await create_user("sec01_art_bob", pwh, salt, ROLE_MERCHANT, "Bob Art")
    except Exception:
        pass

    token_alice = create_token("sec01_art_alice", ROLE_MERCHANT)
    token_bob = create_token("sec01_art_bob", ROLE_MERCHANT)

    artwork_id = "art-bob-sec01"
    pdf_filename = f"{artwork_id}.pdf"
    preview_filename = f"preprint_{artwork_id}_p1.jpg"

    pdf_path = os.path.join(settings.UPLOAD_DIR, pdf_filename)
    preview_path = os.path.join(settings.UPLOAD_DIR, preview_filename)

    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 BOB_ARTWORK_PDF")
    with open(preview_path, "wb") as f:
        f.write(b"BOB_PREVIEW_IMAGE")

    await save_artwork({
        "id": artwork_id,
        "filename": "bob_packaging.pdf",
        "file_path": pdf_path,
        "file_type": "PDF",
        "file_size": 1024,
        "page_count": 1,
        "dimensions": {"width": 800, "height": 600},
        "dpi": 150.0,
        "source_identity": "PRE-PRINT ARTWORK",
        "compliance_ruleset": "Legal Metrology Rules 2011",
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "pages_data": [{"page_number": 1, "preview_image_path": f"/api/images/{preview_filename}"}],
        "owner_user_id": "sec01_art_bob",
        "created_at": "2026-09-18T10:00:00Z",
        "updated_at": "2026-09-18T10:00:00Z"
    })

    try:
        # Alice tries to access Bob's PDF artwork
        resp_pdf = client.get(
            f"/api/images/{pdf_filename}",
            headers={"Authorization": f"Bearer {token_alice}"}
        )
        assert resp_pdf.status_code == 403

        # Alice tries to access Bob's page preview JPG
        resp_prev = client.get(
            f"/api/images/{preview_filename}",
            headers={"Authorization": f"Bearer {token_alice}"}
        )
        assert resp_prev.status_code == 403

        # Bob can access his own PDF and preview
        resp_bob_pdf = client.get(
            f"/api/images/{pdf_filename}",
            headers={"Authorization": f"Bearer {token_bob}"}
        )
        assert resp_bob_pdf.status_code == 200
        assert resp_bob_pdf.content == b"%PDF-1.4 BOB_ARTWORK_PDF"

        resp_bob_prev = client.get(
            f"/api/images/{preview_filename}",
            headers={"Authorization": f"Bearer {token_bob}"}
        )
        assert resp_bob_prev.status_code == 200
    finally:
        for p in (pdf_path, preview_path):
            if os.path.exists(p):
                os.remove(p)


@pytest.mark.asyncio
async def test_08_officer_and_admin_authorized_access():
    """Test 8: Admin and Enforcement Officers have authorized access to merchant screening files."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_admin_off", pwh, salt, ROLE_ADMIN, "Admin Officer")
    except Exception:
        pass
    try:
        await create_user("sec01_enf_off", pwh, salt, ROLE_ENFORCEMENT, "Enforcement Officer", organization_id="org_merchant_john")
    except Exception:
        pass
    try:
        await create_user("sec01_aud_off", pwh, salt, ROLE_AUDIT, "Audit Officer", organization_id="org_merchant_john")
    except Exception:
        pass

    token_admin = create_token("sec01_admin_off", ROLE_ADMIN)
    token_officer = create_token("sec01_enf_off", ROLE_ENFORCEMENT)
    token_audit = create_token("sec01_aud_off", ROLE_AUDIT)

    filename = "analysis_sample_merchant_file.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"MERCHANT_UPLOADED_EVIDENCE_BYTES")

    await save_analysis({
        "id": "analysis_merchant_sample",
        "product_name": "Merchant Sample Oats",
        "image_filename": filename,
        "ocr_text": "MRP Rs 150",
        "extracted_data": {},
        "compliance_result": {},
        "score": 85.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T10:00:00Z",
        "images": [{"filename": filename, "image_url": f"/api/images/{filename}"}],
        "owner_user_id": "merchant_john"
    })

    try:
        # Admin access
        resp_admin = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_admin}"})
        assert resp_admin.status_code == 200

        # Enforcement Officer access
        resp_officer = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_officer}"})
        assert resp_officer.status_code == 200

        # Audit Officer access
        resp_audit = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_audit}"})
        assert resp_audit.status_code == 200
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_09_query_param_token_authentication():
    """Test 9: Browser <img> tags authenticate seamlessly via ?token=<token> query parameter."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    try:
        await create_user("sec01_alice_qp", pwh, salt, ROLE_MERCHANT, "Alice QP")
    except Exception:
        pass
    token_alice = create_token("sec01_alice_qp", ROLE_MERCHANT)

    file_alice = "analysis_alice_query_param.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, file_alice)
    with open(filepath, "wb") as f:
        f.write(b"IMAGE_SERVED_VIA_QUERY_TOKEN")

    await save_analysis({
        "id": "analysis_alice_query_param",
        "product_name": "Alice Query Param Test",
        "image_filename": file_alice,
        "ocr_text": "Sample",
        "extracted_data": {},
        "compliance_result": {},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T10:00:00Z",
        "images": [{"filename": file_alice, "image_url": f"/api/images/{file_alice}"}],
        "owner_user_id": "sec01_alice_qp"
    })

    try:
        # Request with ?token=... and NO Authorization header
        resp = client.get(f"/api/images/{file_alice}?token={token_alice}")
        assert resp.status_code == 200
        assert resp.content == b"IMAGE_SERVED_VIA_QUERY_TOKEN"

        # Request with invalid token parameter
        resp_invalid = client.get(f"/api/images/{file_alice}?token=invalid-junk-token")
        assert resp_invalid.status_code == 401
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
