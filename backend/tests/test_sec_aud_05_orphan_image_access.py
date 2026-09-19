"""
Test Suite for SEC-AUD-05: Orphaned / Unlinked Image and File Access Isolation.

Verifies:
1. Unauthenticated requests to /api/images/{filename} are rejected (401 Unauthorized).
2. Merchant cannot access orphaned / unlinked files in UPLOAD_DIR (403 Forbidden).
3. Enforcement Officer cannot access orphaned / unlinked files in UPLOAD_DIR (403 Forbidden).
4. Audit Officer cannot access orphaned / unlinked files in UPLOAD_DIR (403 Forbidden).
5. Administrator (ROLE_ADMIN) CAN access orphaned / unlinked files for statutory maintenance (200 OK).
6. Enforcement Officer CAN access linked analysis images in their assigned organization (200 OK).
7. Enforcement Officer CANNOT access linked analysis images belonging to a different organization (403 Forbidden).
8. Merchant CAN access linked analysis images belonging to their own account/organization (200 OK).
9. Merchant CANNOT access linked analysis images belonging to another merchant/organization (403 Forbidden).
10. Requests for non-existent files return 404 Not Found without leaking system paths.
"""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import save_analysis, create_user, init_db
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


@pytest.fixture(autouse=True)
def setup_env():
    _ensure_test_isolation()


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


@pytest.mark.asyncio
async def test_01_unauthenticated_access_denied():
    """Unauthenticated request to /api/images/{filename} must return 401."""
    await init_db()
    client = TestClient(app)
    filename = f"test_unauth_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"SAMPLE_IMAGE_DATA")

    try:
        res = client.get(f"/api/images/{filename}")
        assert res.status_code == 401
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_02_merchant_cannot_access_orphaned_file():
    """Merchant cannot access unlinked orphaned file in storage."""
    await init_db()
    client = TestClient(app)
    username = f"merchant_orphan_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_MERCHANT, "org_merchant_orphan")
    token = create_token(username, ROLE_MERCHANT)

    filename = f"orphan_file_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"ORPHANED_DATA_BYTES")

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "access denied" in res.json().get("detail", "").lower()
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_03_enforcement_officer_cannot_access_orphaned_file():
    """Enforcement officer cannot access unlinked orphaned file (SEC-AUD-05 fix)."""
    await init_db()
    client = TestClient(app)
    username = f"officer_orphan_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_ENFORCEMENT, "org_dept_orphan")
    token = create_token(username, ROLE_ENFORCEMENT)

    filename = f"orphan_officer_test_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"UNLINKED_EVIDENCE_BYTES")

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "access denied" in res.json().get("detail", "").lower()
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_04_audit_officer_cannot_access_orphaned_file():
    """Audit officer cannot access unlinked orphaned file (SEC-AUD-05 fix)."""
    await init_db()
    client = TestClient(app)
    username = f"audit_orphan_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_AUDIT, "org_dept_audit")
    token = create_token(username, ROLE_AUDIT)

    filename = f"orphan_audit_test_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"UNLINKED_AUDIT_BYTES")

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "access denied" in res.json().get("detail", "").lower()
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_05_admin_can_access_orphaned_file():
    """Admin has statutory oversight to inspect all files including unlinked orphans."""
    await init_db()
    client = TestClient(app)
    username = f"admin_orphan_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_ADMIN, "org_ministry")
    token = create_token(username, ROLE_ADMIN)

    filename = f"orphan_admin_test_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    image_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00ADMIN_TEST_BYTES"
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.content == image_bytes
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_06_officer_access_linked_file_in_own_tenant():
    """Officer can access files linked to analysis records within their own organization."""
    await init_db()
    client = TestClient(app)
    username = f"officer_tenant_a_{os.urandom(4).hex()}"
    org_id = "org_state_north"
    await _create_test_user(username, ROLE_ENFORCEMENT, org_id)
    token = create_token(username, ROLE_ENFORCEMENT)

    filename = f"analysis_north_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    with open(filepath, "wb") as f:
        f.write(png_bytes)

    ana_id = f"ana-north-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="North Region Basmati Rice",
        image_filename=filename,
        extracted_data={"product_name": "North Region Basmati Rice"},
        compliance_result={"score": 90.0, "status": "PASS", "checks": []},
        ocr_text="Basmati Rice 1kg",
        owner_user_id="merchant_north_1",
        organization_id=org_id,
    )

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.content == png_bytes
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_07_officer_cannot_access_linked_file_in_different_tenant():
    """Officer cannot access files linked to analysis records belonging to a different organization."""
    await init_db()
    client = TestClient(app)
    username = f"officer_tenant_b_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_ENFORCEMENT, "org_state_south")
    token = create_token(username, ROLE_ENFORCEMENT)

    filename = f"analysis_north_private_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    with open(filepath, "wb") as f:
        f.write(png_bytes)

    ana_id = f"ana-north-priv-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="North Region Mustard Oil",
        image_filename=filename,
        extracted_data={"product_name": "North Region Mustard Oil"},
        compliance_result={"score": 85.0, "status": "PASS", "checks": []},
        ocr_text="Mustard Oil 1L",
        owner_user_id="merchant_north_1",
        organization_id="org_state_north",
    )

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "access denied" in res.json().get("detail", "").lower()
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_08_merchant_access_own_linked_file():
    """Merchant can access files linked to their own analysis."""
    await init_db()
    client = TestClient(app)
    username = f"merchant_owner_{os.urandom(4).hex()}"
    org_id = f"org_{username}"
    await _create_test_user(username, ROLE_MERCHANT, org_id)
    token = create_token(username, ROLE_MERCHANT)

    filename = f"my_own_product_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    jpg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00MY_PRODUCT_BYTES"
    with open(filepath, "wb") as f:
        f.write(jpg_bytes)

    ana_id = f"ana-own-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="My Organic Oats",
        image_filename=filename,
        extracted_data={"product_name": "My Organic Oats"},
        compliance_result={"score": 95.0, "status": "PASS", "checks": []},
        ocr_text="Oats 500g",
        owner_user_id=username,
        organization_id=org_id,
    )

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.content == jpg_bytes
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_09_merchant_cross_tenant_linked_file_denied():
    """Merchant cannot access files linked to another merchant's analysis."""
    await init_db()
    client = TestClient(app)
    username_a = f"merchant_a_{os.urandom(4).hex()}"
    username_b = f"merchant_b_{os.urandom(4).hex()}"
    await _create_test_user(username_a, ROLE_MERCHANT, f"org_{username_a}")
    await _create_test_user(username_b, ROLE_MERCHANT, f"org_{username_b}")
    token_b = create_token(username_b, ROLE_MERCHANT)

    filename = f"merchant_a_secret_{os.urandom(4).hex()}.jpg"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    jpg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00MERCHANT_A_SECRET"
    with open(filepath, "wb") as f:
        f.write(jpg_bytes)

    ana_id = f"ana-a-secret-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Merchant A Secret Product",
        image_filename=filename,
        extracted_data={"product_name": "Merchant A Secret Product"},
        compliance_result={"score": 80.0, "status": "PASS", "checks": []},
        ocr_text="Secret formula",
        owner_user_id=username_a,
        organization_id=f"org_{username_a}",
    )

    try:
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_b}"})
        assert res.status_code == 403
        assert "access denied" in res.json().get("detail", "").lower()
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.mark.asyncio
async def test_10_non_existent_file_returns_404():
    """Non-existent file request returns 404 with safe error message."""
    await init_db()
    client = TestClient(app)
    username = f"admin_test_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_ADMIN, "org_ministry")
    token = create_token(username, ROLE_ADMIN)

    res = client.get("/api/images/non_existent_file_99999.png", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
    detail = res.json().get("detail", "")
    assert "Requested file not found." in detail
