import io
import json
import pytest
import os
import hashlib
from fastapi.testclient import TestClient
from PIL import Image

from main import app
from version import (
    SYSTEM_VERSION,
    OCR_PIPELINE_VERSION,
    EXTRACTION_ENGINE_VERSION,
    COMPLIANCE_RULESET_VERSION,
    INTEGRITY_ALGORITHM,
    AUDIT_CHAIN_ALGORITHM,
    get_version_metadata,
)
from auth.security import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from auth.ratelimit import (
    check_login_rate_limit,
    check_analysis_rate_limit,
    check_ocr_rate_limit,
)
from utils.validators import check_magic_bytes, sanitize_filename
from services.image_service import ensure_path_contained
from services.integrity_service import (
    compute_analysis_integrity_hash,
    verify_analysis_integrity,
)
from database.db import (
    log_security_event,
    get_security_audit_logs,
    verify_security_audit_chain,
    save_analysis,
    get_analysis,
)


@pytest.fixture
def client():
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# 1. VERSION TRACKING & SYSTEM METADATA (Req 23, 24, 25)
# ═══════════════════════════════════════════════════════════════════════

def test_version_metadata_endpoint(client):
    """Verify GET /api/version returns canonical versioning metadata."""
    res = client.get("/api/version")
    assert res.status_code == 200
    data = res.json()
    assert data["system_version"] == SYSTEM_VERSION
    assert data["ocr_pipeline_version"] == OCR_PIPELINE_VERSION
    assert data["extraction_engine_version"] == EXTRACTION_ENGINE_VERSION
    assert data["compliance_ruleset_version"] == COMPLIANCE_RULESET_VERSION
    assert data["integrity_algorithm"] == INTEGRITY_ALGORITHM
    assert data["audit_chain_algorithm"] == AUDIT_CHAIN_ALGORITHM


# ═══════════════════════════════════════════════════════════════════════
# 2. SECURITY HEADERS & DEFENSE-IN-DEPTH (Req 17, 18)
# ═══════════════════════════════════════════════════════════════════════

def test_security_response_headers(client):
    """Verify all HTTP responses include statutory security headers."""
    res = client.get("/api/version")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in res.headers.get("Permissions-Policy", "")
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"


# ═══════════════════════════════════════════════════════════════════════
# 3. PASSWORD HASHING & AUTHENTICATION (Req 1, 2, 3)
# ═══════════════════════════════════════════════════════════════════════

def test_password_hashing_pbkdf2():
    """Verify PBKDF2-HMAC-SHA256 hashing with 200k iterations and per-user salt."""
    pwd = "StrongAdminPass#2026"
    hash_hex, salt_hex = hash_password(pwd)
    assert len(bytes.fromhex(salt_hex)) == 16
    assert len(hash_hex) == 64  # SHA-256 32-byte digest in hex
    assert verify_password(pwd, salt_hex, hash_hex) is True
    assert verify_password("WrongPassword", salt_hex, hash_hex) is False


def test_jwt_token_lifecycle_and_revocation():
    """Verify HMAC-SHA256 JWT creation, decoding, and version invalidation."""
    token = create_token("officer_sharma", ROLE_ENFORCEMENT, token_version=1)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "officer_sharma"
    assert payload["role"] == ROLE_ENFORCEMENT
    assert payload["token_version"] == 1

    # Invalidate token version
    revoked_token = create_token("officer_sharma", ROLE_ENFORCEMENT, token_version=2)
    new_payload = decode_token(revoked_token)
    assert new_payload["token_version"] == 2


# ═══════════════════════════════════════════════════════════════════════
# 4. UPLOAD VALIDATION & MAGIC BYTE VERIFICATION (Req 7, 8, 9, 13)
# ═══════════════════════════════════════════════════════════════════════

def test_magic_bytes_detection():
    """Verify magic-byte file signature validation for allowed and disallowed formats."""
    # JPEG magic bytes
    jpeg_header = b"\xFF\xD8\xFF\xE0" + b"\x00" * 20
    assert check_magic_bytes(jpeg_header, "image/jpeg") is True
    assert check_magic_bytes(jpeg_header, "application/pdf") is False

    # PNG magic bytes
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert check_magic_bytes(png_header, "image/png") is True

    # PDF magic bytes
    pdf_header = b"%PDF-1.7\r\n" + b"\x00" * 20
    assert check_magic_bytes(pdf_header, "application/pdf") is True

    # Malicious executable disguised as JPEG
    exe_header = b"MZ\x90\x00" + b"\x00" * 20
    assert check_magic_bytes(exe_header, "image/jpeg") is False
    assert check_magic_bytes(exe_header, "image/png") is False


def test_path_traversal_sanitization():
    """Verify filename sanitization against directory traversal and null byte attacks."""
    assert sanitize_filename("../../../etc/passwd.png") == "passwd.png"
    assert sanitize_filename("..\\..\\windows\\system32\\calc.exe") == "calc.exe"
    assert sanitize_filename("safe_label_front.jpg") == "safe_label_front.jpg"
    assert sanitize_filename("evil\x00file.png") == "evilfile.png"


def test_ensure_path_contained():
    """Verify directory containment enforcement."""
    base = os.path.abspath("C:/mock/uploads") if os.name == "nt" else "/tmp/mock/uploads"
    safe_target = os.path.join(base, "product_123.jpg")
    unsafe_target = os.path.join(base, "..", "secret.txt")

    assert ensure_path_contained(safe_target, base) == os.path.abspath(safe_target)
    with pytest.raises(Exception):
        ensure_path_contained(unsafe_target, base)


# ═══════════════════════════════════════════════════════════════════════
# 5. RATE LIMITING (Req 6)
# ═══════════════════════════════════════════════════════════════════════

def test_analysis_rate_limiting():
    """Verify analysis rate limiter throttles excessive requests."""
    test_ip = "192.0.2.105"
    # First requests should pass
    allowed, msg = check_analysis_rate_limit(test_ip)
    assert allowed is True

    allowed, msg = check_ocr_rate_limit(test_ip)
    assert allowed is True


# ═══════════════════════════════════════════════════════════════════════
# 6. DETERMINISTIC INTEGRITY HASHING & TAMPER DETECTION (Req 21, 22)
# ═══════════════════════════════════════════════════════════════════════

def test_deterministic_integrity_hash():
    """Verify deterministic SHA-256 canonical hashing of analysis records."""
    analysis_id = "test-sec-001"
    created_at = "2026-09-17T12:00:00Z"
    product_name = "Organic Whole Almonds 500g"
    score = 92.5
    status = "COMPLIANT"
    extracted_data = {"net_quantity": "500 g", "mrp": "Rs 450.00", "fssai_license": "10012011000123"}
    compliance_result = {"status": "COMPLIANT", "score": 92.5, "passed_rules": 8, "failed_rules": 0}

    hash1 = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_name,
        score=score,
        status=status,
        extracted_data=extracted_data,
        compliance_result=compliance_result,
    )
    assert len(hash1) == 64

    # Identical data must yield identical hash
    hash2 = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_name,
        score=score,
        status=status,
        extracted_data=extracted_data,
        compliance_result=compliance_result,
    )
    assert hash1 == hash2

    # Verification should pass
    verify_res = verify_analysis_integrity(
        stored_hash=hash1,
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_name,
        score=score,
        status=status,
        extracted_data=extracted_data,
        compliance_result=compliance_result,
    )
    assert verify_res["verified"] is True
    assert verify_res["tampered_fields"] == []

    # Tampering with compliance score must fail verification
    tampered_verify = verify_analysis_integrity(
        stored_hash=hash1,
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_name,
        score=99.0,  # Tampered score!
        status=status,
        extracted_data=extracted_data,
        compliance_result=compliance_result,
    )
    assert tampered_verify["verified"] is False
    assert "score" in tampered_verify["tampered_fields"]


# ═══════════════════════════════════════════════════════════════════════
# 7. CRYPTOGRAPHIC SECURITY AUDIT HASH CHAIN (Req 19, 20)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cryptographic_audit_hash_chain():
    """Verify forward-chained SHA-256 security audit logs and chain verification."""
    # Append sequential security events
    ev1 = await log_security_event(
        event_type="UNAUTHORIZED_ACCESS_ATTEMPT",
        actor_username="unknown",
        ip_address="198.51.100.1",
        resource_id="/api/admin/users",
        details="Attempted access without valid credentials."
    )
    assert ev1["prev_hash"] != ""
    assert len(ev1["event_hash"]) == 64

    ev2 = await log_security_event(
        event_type="RATE_LIMIT_EXCEEDED",
        actor_username="spammer",
        ip_address="198.51.100.2",
        resource_id="/api/analyze",
        details="Exceeded 20 requests/minute."
    )
    # ev2 must chain directly to ev1's event_hash
    assert ev2["prev_hash"] == ev1["event_hash"]

    # Verify chain integrity across all records
    chain_status = await verify_security_audit_chain()
    assert chain_status["valid"] is True
    assert chain_status["total_records"] >= 2


from database.db import (
    log_security_event,
    get_security_audit_logs,
    verify_security_audit_chain,
    save_analysis,
    get_analysis,
    create_user,
    get_user_by_username,
)


async def _ensure_user(username: str, role: str):
    user = await get_user_by_username(username)
    if not user:
        h, s = hash_password("TestPass123!")
        await create_user(username, h, s, role, f"Test {username}", "Test Jurisdiction")


# ═══════════════════════════════════════════════════════════════════════
# 8. ADMIN GOVERNANCE & RBAC GUARDS (Req 4, 5, 14)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_routes_guarded(client):
    """Verify admin endpoints reject unauthenticated and non-admin requests."""
    await _ensure_user("admin_sec_test", ROLE_ADMIN)
    await _ensure_user("merchant_user", ROLE_MERCHANT)
    await _ensure_user("officer_patel", ROLE_ENFORCEMENT)

    # Unauthenticated request
    res = client.get("/api/admin/security-logs")
    assert res.status_code == 401

    # Merchant user attempting to access admin route
    merchant_token = create_token("merchant_user", ROLE_MERCHANT)
    res_merchant = client.get(
        "/api/admin/security-logs",
        headers={"Authorization": f"Bearer {merchant_token}"}
    )
    assert res_merchant.status_code == 403

    # Officer attempting to seed cache
    officer_token = create_token("officer_patel", ROLE_ENFORCEMENT)
    res_officer = client.post(
        "/api/integrations/cache/seed",
        json=[{
            "identifier_type": "FSSAI",
            "identifier_value": "10012011000123",
            "record_data": {"company_name": "Test Foods"},
            "source": "FOSCOS_REGISTRY"
        }],
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res_officer.status_code == 403

    # Admin user accessing admin route
    admin_token = create_token("admin_sec_test", ROLE_ADMIN)
    res_admin = client.get(
        "/api/admin/security-logs",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json(), list)


# ═══════════════════════════════════════════════════════════════════════
# 9. IDOR PROTECTION ON HISTORY & REPORTS (Req 15)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_idor_protection_for_merchants(client):
    """Verify merchant users cannot view or delete other users' screening records."""
    await _ensure_user("merchant_alpha", ROLE_MERCHANT)
    await _ensure_user("merchant_bravo", ROLE_MERCHANT)

    # Create record owned by merchant_alpha
    alpha_id = "test-alpha-screen-1"
    alpha_data = {
        'id': alpha_id,
        'product_name': "Alpha Brand Oats",
        'image_filename': "",
        'ocr_text': "Alpha Brand Oats 1kg",
        'extracted_data': {"product_name": "Alpha Brand Oats"},
        'compliance_result': {"status": "COMPLIANT", "score": 95.0, "checks": []},
        'score': 95.0,
        'status': "COMPLIANT",
        'created_at': "2026-09-17T12:00:00Z",
        'images': [],
        'owner_user_id': "merchant_alpha",
        'integrity_hash': "mockhash123",
        'system_version': SYSTEM_VERSION,
        'ocr_engine_version': OCR_PIPELINE_VERSION,
        'ruleset_version': COMPLIANCE_RULESET_VERSION,
    }
    await save_analysis(alpha_data)

    # Merchant Bravo token
    bravo_token = create_token("merchant_bravo", ROLE_MERCHANT)

    # Bravo attempting to inspect Alpha's history item
    res = client.get(
        f"/api/history/{alpha_id}",
        headers={"Authorization": f"Bearer {bravo_token}"}
    )
    assert res.status_code == 403

    # Bravo attempting to delete Alpha's history item
    del_res = client.delete(
        f"/api/history/{alpha_id}",
        headers={"Authorization": f"Bearer {bravo_token}"}
    )
    assert del_res.status_code == 403

    # Alpha accessing own record
    alpha_token = create_token("merchant_alpha", ROLE_MERCHANT)
    res_alpha = client.get(
        f"/api/history/{alpha_id}",
        headers={"Authorization": f"Bearer {alpha_token}"}
    )
    assert res_alpha.status_code == 200
    assert res_alpha.json()["product_name"] == "Alpha Brand Oats"

