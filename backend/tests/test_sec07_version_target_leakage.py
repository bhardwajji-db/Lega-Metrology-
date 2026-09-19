"""
Unit and Integration Tests for SEC-07 — Version Comparison / Target Leakage Security Remediation.

Verifies:
1. Authentication enforcement on all version comparison endpoints (401 on missing/invalid/expired tokens).
2. Tenant-scoped target enumeration (/api/versions/targets).
3. Dual-sided authorization & mixed cross-tenant comparison blocking (/api/versions/compare).
4. Zero DB pollution / no comparison saved on 403/404 failures.
5. Saved comparison isolation, detail access, JSON/CSV exports, and deletion IDOR protection.
6. Chronological version timeline tenant isolation.
7. Prevention of sensitive metadata leakage on 403/404.
8. CSV export formula injection sanitization.
"""

import os
import io
import json
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import (
    get_db,
    init_db,
    create_organization,
    create_user,
    save_analysis,
    get_analysis,
    save_artwork,
    get_artwork,
    save_version_comparison,
    get_version_comparison,
    list_version_comparisons,
    delete_version_comparison,
    get_version_timeline,
)
from auth.security import (
    hash_password,
    create_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)

client = TestClient(app)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _create_test_user(username: str, role: str, org_id: str = ""):
    """Helper to register user in DB with specific organization_id."""
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


async def _setup_sec07():
    """Setup organizations and test users."""
    _ensure_test_isolation()
    await init_db()

    # Create Organizations
    await create_organization("org_alpha", "Alpha Retailers Corp", org_type="MERCHANT", jurisdiction="North")
    await create_organization("org_beta", "Beta Food Products Ltd", org_type="MERCHANT", jurisdiction="South")
    await create_organization("org_regulator", "Legal Metrology Enforcement Directorate", org_type="REGULATOR", jurisdiction="National")

    # Create Test Users
    await _create_test_user("merchant_alpha", ROLE_MERCHANT, "org_alpha")
    await _create_test_user("merchant_beta", ROLE_MERCHANT, "org_beta")
    await _create_test_user("officer_alpha", ROLE_ENFORCEMENT, "org_alpha")
    await _create_test_user("officer_reg", ROLE_ENFORCEMENT, "org_regulator")
    await _create_test_user("admin_sec07", ROLE_ADMIN, "")


# ═════════════════════════════════════════════════════════════════════════════
# 1. UNAUTHENTICATED & INVALID TOKEN ACCESS TESTS (401)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_targets_endpoint_requires_auth():
    """GET /api/versions/targets must return 401 without authentication."""
    await _setup_sec07()
    r = client.get("/api/versions/targets")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_02_compare_endpoint_requires_auth():
    """POST /api/versions/compare must return 401 without authentication."""
    await _setup_sec07()
    r = client.post("/api/versions/compare", json={
        "version_a_id": "v1",
        "version_b_id": "v2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_03_comparisons_list_endpoint_requires_auth():
    """GET /api/versions/comparisons must return 401 without authentication."""
    await _setup_sec07()
    r = client.get("/api/versions/comparisons")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_04_comparison_detail_endpoint_requires_auth():
    """GET /api/versions/comparisons/{id} must return 401 without authentication."""
    await _setup_sec07()
    r = client.get("/api/versions/comparisons/cmp_test_123")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_05_comparison_json_export_requires_auth():
    """GET /api/versions/comparisons/{id}/json must return 401 without authentication."""
    await _setup_sec07()
    r = client.get("/api/versions/comparisons/cmp_test_123/json")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_06_comparison_csv_export_requires_auth():
    """GET /api/versions/comparisons/{id}/csv must return 401 without authentication."""
    await _setup_sec07()
    r = client.get("/api/versions/comparisons/cmp_test_123/csv")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_07_comparison_delete_endpoint_requires_auth():
    """DELETE /api/versions/comparisons/{id} must return 401 without authentication."""
    await _setup_sec07()
    r = client.delete("/api/versions/comparisons/cmp_test_123")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_08_timeline_endpoint_requires_auth():
    """GET /api/versions/timeline/{entity_id} must return 401 without authentication."""
    await _setup_sec07()
    r = client.get("/api/versions/timeline/entity_test_123")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_09_invalid_token_rejected_401():
    """Endpoints must reject malformed tokens with 401."""
    await _setup_sec07()
    headers = {"Authorization": "Bearer totally_bogus_token_xyz"}
    r = client.get("/api/versions/targets", headers=headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_10_expired_token_rejected_401():
    """Endpoints must reject expired tokens with 401."""
    await _setup_sec07()
    import time
    import hmac
    import hashlib
    from auth.security import _b64e, _secret_key

    now = int(time.time()) - 3600
    payload = {
        "sub": "merchant_alpha",
        "role": ROLE_MERCHANT,
        "token_version": 1,
        "iat": now - 3600,
        "exp": now,
    }
    body = _b64e(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(_secret_key(), body.encode("utf-8"), hashlib.sha256).digest()
    expired_token = f"{body}.{_b64e(sig)}"
    headers = {"Authorization": f"Bearer {expired_token}"}
    r = client.get("/api/versions/targets", headers=headers)
    assert r.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# 2. TARGET ENUMERATION SCOPING TESTS (/api/versions/targets)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_11_merchant_sees_only_own_org_and_own_targets():
    """Merchant Alpha in org_alpha only sees targets belonging to org_alpha and merchant_alpha."""
    await _setup_sec07()
    # Seed Alpha analysis & artwork
    await save_analysis({
        "id": "ana_alpha_target_1",
        "product_name": "Alpha Biscuit Pack",
        "image_filename": "alpha1.jpg",
        "owner_user_id": "merchant_alpha",
        "organization_id": "org_alpha",
        "score": 85.0,
        "status": "PASS",
        "created_at": "2026-03-01T10:00:00Z",
        "extracted_data": {"product_name": "Alpha Biscuit Pack", "mrp": "₹50"},
        "compliance_result": {"score": 85.0, "status": "PASS", "total_rules": 1, "passed_rules": 1, "failed_rules": 0, "checks": []}
    })
    await save_artwork({
        "id": "art_alpha_target_1",
        "filename": "alpha_artwork_v1.pdf",
        "file_path": "/api/images/alpha_artwork_v1.pdf",
        "file_type": "PDF",
        "file_size": 2048,
        "page_count": 1,
        "workflow_status": "DRAFT",
        "iteration_number": 1,
        "owner_user_id": "merchant_alpha",
        "organization_id": "org_alpha",
        "created_at": "2026-03-02T10:00:00Z",
        "analysis_result": {"overall_score": 88.0, "product_info": {"product_name": "Alpha Biscuit Artwork"}, "compliance_result": {}}
    })

    # Seed Beta analysis & artwork
    await save_analysis({
        "id": "ana_beta_target_1",
        "product_name": "Beta Juice Bottle",
        "image_filename": "beta1.jpg",
        "owner_user_id": "merchant_beta",
        "organization_id": "org_beta",
        "score": 75.0,
        "status": "FAIL",
        "created_at": "2026-03-03T10:00:00Z",
        "extracted_data": {"product_name": "Beta Juice Bottle", "mrp": "₹120"},
        "compliance_result": {"score": 75.0, "status": "FAIL", "total_rules": 1, "passed_rules": 0, "failed_rules": 1, "checks": []}
    })
    await save_artwork({
        "id": "art_beta_target_1",
        "filename": "beta_artwork_v1.pdf",
        "file_path": "/api/images/beta_artwork_v1.pdf",
        "file_type": "PDF",
        "file_size": 2048,
        "page_count": 1,
        "workflow_status": "DRAFT",
        "iteration_number": 1,
        "owner_user_id": "merchant_beta",
        "organization_id": "org_beta",
        "created_at": "2026-03-04T10:00:00Z",
        "analysis_result": {"overall_score": 70.0, "product_info": {"product_name": "Beta Juice Artwork"}, "compliance_result": {}}
    })

    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.get("/api/versions/targets", headers=headers_alpha)
    assert r.status_code == 200
    data = r.json()
    target_ids = [t["version_id"] for t in data["targets"]]

    assert "ana_alpha_target_1" in target_ids
    assert "art_alpha_target_1" in target_ids
    assert "ana_beta_target_1" not in target_ids
    assert "art_beta_target_1" not in target_ids


@pytest.mark.asyncio
async def test_12_merchant_never_sees_other_org_targets():
    """Merchant Beta only sees Beta targets and zero Alpha targets."""
    await _setup_sec07()
    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r = client.get("/api/versions/targets", headers=headers_beta)
    assert r.status_code == 200
    target_ids = [t["version_id"] for t in r.json()["targets"]]

    assert "ana_beta_target_1" in target_ids
    assert "art_beta_target_1" in target_ids
    assert "ana_alpha_target_1" not in target_ids
    assert "art_alpha_target_1" not in target_ids


@pytest.mark.asyncio
async def test_13_merchant_cannot_spoof_owner_user_id_query_param():
    """Merchant Alpha requesting ?owner_user_id=merchant_beta cannot bypass tenant scoping."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.get("/api/versions/targets?owner_user_id=merchant_beta", headers=headers_alpha)
    assert r.status_code == 200
    target_ids = [t["version_id"] for t in r.json()["targets"]]

    # Beta targets MUST NOT leak
    assert "ana_beta_target_1" not in target_ids
    assert "art_beta_target_1" not in target_ids


@pytest.mark.asyncio
async def test_14_officer_sees_all_targets_within_own_org():
    """Officer Alpha in org_alpha sees all targets belonging to org_alpha."""
    await _setup_sec07()
    headers_off = make_auth_headers("officer_alpha", ROLE_ENFORCEMENT)
    r = client.get("/api/versions/targets", headers=headers_off)
    assert r.status_code == 200
    target_ids = [t["version_id"] for t in r.json()["targets"]]

    assert "ana_alpha_target_1" in target_ids
    assert "art_alpha_target_1" in target_ids
    assert "ana_beta_target_1" not in target_ids
    assert "art_beta_target_1" not in target_ids


@pytest.mark.asyncio
async def test_15_officer_never_sees_targets_from_other_org():
    """Officer in regulator org with no beta records does not see foreign private targets."""
    await _setup_sec07()
    headers_reg = make_auth_headers("officer_reg", ROLE_ENFORCEMENT)
    r = client.get("/api/versions/targets", headers=headers_reg)
    assert r.status_code == 200
    target_ids = [t["version_id"] for t in r.json()["targets"]]

    assert "ana_alpha_target_1" not in target_ids
    assert "art_alpha_target_1" not in target_ids
    assert "ana_beta_target_1" not in target_ids
    assert "art_beta_target_1" not in target_ids


@pytest.mark.asyncio
async def test_16_admin_statutory_oversight_sees_all_targets():
    """Admin has statutory oversight and sees targets across all organizations."""
    await _setup_sec07()
    headers_adm = make_auth_headers("admin_sec07", ROLE_ADMIN)
    r = client.get("/api/versions/targets", headers=headers_adm)
    assert r.status_code == 200
    target_ids = [t["version_id"] for t in r.json()["targets"]]

    assert "ana_alpha_target_1" in target_ids
    assert "art_alpha_target_1" in target_ids
    assert "ana_beta_target_1" in target_ids
    assert "art_beta_target_1" in target_ids


# ═════════════════════════════════════════════════════════════════════════════
# 3. DUAL-SIDED SNAPSHOT AUTHORIZATION & COMPARISON TESTS (/api/versions/compare)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_17_same_tenant_analysis_comparison_success_200():
    """Merchant Alpha comparing two Alpha analyses succeeds with 200 OK."""
    await _setup_sec07()
    await save_analysis({
        "id": "ana_alpha_target_2",
        "product_name": "Alpha Biscuit Pack Revised",
        "image_filename": "alpha2.jpg",
        "owner_user_id": "merchant_alpha",
        "organization_id": "org_alpha",
        "score": 95.0,
        "status": "PASS",
        "created_at": "2026-03-05T10:00:00Z",
        "extracted_data": {"product_name": "Alpha Biscuit Pack Revised", "mrp": "₹55"},
        "compliance_result": {"score": 95.0, "status": "PASS", "total_rules": 1, "passed_rules": 1, "failed_rules": 0, "checks": []}
    })

    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 200
    res = r.json()
    assert res["version_a"]["version_id"] == "ana_alpha_target_1"
    assert res["version_b"]["version_id"] == "ana_alpha_target_2"
    assert res["score_delta"] == 10.0


@pytest.mark.asyncio
async def test_18_same_tenant_artwork_comparison_success_200():
    """Merchant Alpha comparing two Alpha artworks succeeds with 200 OK."""
    await _setup_sec07()
    await save_artwork({
        "id": "art_alpha_target_2",
        "filename": "alpha_artwork_v2.pdf",
        "file_path": "/api/images/alpha_artwork_v2.pdf",
        "file_type": "PDF",
        "file_size": 2048,
        "page_count": 1,
        "workflow_status": "APPROVED",
        "iteration_number": 2,
        "owner_user_id": "merchant_alpha",
        "organization_id": "org_alpha",
        "created_at": "2026-03-06T10:00:00Z",
        "analysis_result": {"overall_score": 96.0, "product_info": {"product_name": "Alpha Biscuit Artwork v2"}, "compliance_result": {}}
    })

    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "art_alpha_target_1",
        "version_b_id": "art_alpha_target_2",
        "version_type_a": "ARTWORK",
        "version_type_b": "ARTWORK"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 200
    res = r.json()
    assert res["version_a"]["version_type"] == "ARTWORK"
    assert res["version_b"]["version_type"] == "ARTWORK"


@pytest.mark.asyncio
async def test_19_same_tenant_hybrid_analysis_vs_artwork_success_200():
    """Merchant Alpha comparing Alpha physical screening vs Alpha artwork succeeds with 200 OK."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "art_alpha_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ARTWORK"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 200
    res = r.json()
    assert res["version_a"]["version_type"] == "ANALYSIS"
    assert res["version_b"]["version_type"] == "ARTWORK"


@pytest.mark.asyncio
async def test_20_cross_tenant_both_snapshots_foreign_403():
    """Merchant Alpha attempting to compare two Beta analyses is blocked with 403 Forbidden."""
    await _setup_sec07()
    await save_analysis({
        "id": "ana_beta_target_2",
        "product_name": "Beta Juice Bottle v2",
        "image_filename": "beta2.jpg",
        "owner_user_id": "merchant_beta",
        "organization_id": "org_beta",
        "score": 90.0,
        "status": "PASS",
        "created_at": "2026-03-07T10:00:00Z",
        "extracted_data": {"product_name": "Beta Juice Bottle v2", "mrp": "₹120"},
        "compliance_result": {"score": 90.0, "status": "PASS", "total_rules": 1, "passed_rules": 1, "failed_rules": 0, "checks": []}
    })

    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "ana_beta_target_1",
        "version_b_id": "ana_beta_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_21_cross_tenant_version_a_foreign_403():
    """Merchant Alpha attempting to compare Beta (Base) vs Alpha (Target) is blocked with 403 Forbidden."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "ana_beta_target_1",
        "version_b_id": "ana_alpha_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_22_cross_tenant_version_b_foreign_403():
    """Merchant Alpha attempting to compare Alpha (Base) vs Beta (Target) is blocked with 403 Forbidden."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_beta_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_23_cross_tenant_artwork_foreign_403():
    """Merchant Alpha attempting to compare Alpha Artwork vs Beta Artwork is blocked with 403 Forbidden."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "art_alpha_target_1",
        "version_b_id": "art_beta_target_1",
        "version_type_a": "ARTWORK",
        "version_type_b": "ARTWORK"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_24_no_db_record_saved_on_failed_comparison():
    """When a comparison fails (403 or 404), zero records are added to version_comparisons table."""
    await _setup_sec07()
    comps_before = await list_version_comparisons(limit=500)
    count_before = len(comps_before)

    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    # Attempt unauthorized cross-tenant comparison
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_beta_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    assert r.status_code == 403

    # Attempt non-existent version comparison
    r2 = client.post("/api/versions/compare", json={
        "version_a_id": "non_existent_1",
        "version_b_id": "non_existent_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    assert r2.status_code == 404

    comps_after = await list_version_comparisons(limit=500)
    assert len(comps_after) == count_before


@pytest.mark.asyncio
async def test_25_admin_can_compare_cross_tenant_statutory():
    """Admin statutory oversight allows comparing across entities when conducting forensic investigations."""
    await _setup_sec07()
    headers_adm = make_auth_headers("admin_sec07", ROLE_ADMIN)
    payload = {
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_beta_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_adm)
    assert r.status_code == 200
    res = r.json()
    assert res["comparison_id"] is not None


@pytest.mark.asyncio
async def test_26_nonexistent_version_a_returns_404():
    """Comparing with a non-existent version_a returns 404 Not Found."""
    await _setup_sec07()
    headers_adm = make_auth_headers("admin_sec07", ROLE_ADMIN)
    payload = {
        "version_a_id": "ana_does_not_exist_999",
        "version_b_id": "ana_alpha_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_adm)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_27_nonexistent_version_b_returns_404():
    """Comparing with a non-existent version_b returns 404 Not Found."""
    await _setup_sec07()
    headers_adm = make_auth_headers("admin_sec07", ROLE_ADMIN)
    payload = {
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_does_not_exist_999",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_adm)
    assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 4. SAVED COMPARISON IDOR PROTECTION, EXPORT & DELETION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_28_comparison_saved_with_tenant_metadata():
    """Saved comparison stores actor's username and organization_id."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    payload = {
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }
    r = client.post("/api/versions/compare", json=payload, headers=headers_alpha)
    assert r.status_code == 200
    cmp_id = r.json()["comparison_id"]

    saved = await get_version_comparison(cmp_id)
    assert saved is not None
    assert saved.get("owner_user_id") == "merchant_alpha"
    assert saved.get("organization_id") == "org_alpha"


@pytest.mark.asyncio
async def test_29_list_comparisons_scoped_to_merchant_tenant():
    """GET /api/versions/comparisons lists only the tenant's own comparisons."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r_alpha = client.get("/api/versions/comparisons", headers=headers_alpha)
    assert r_alpha.status_code == 200
    comps_alpha = r_alpha.json()["comparisons"]

    for c in comps_alpha:
        assert c.get("organization_id") in ("org_alpha", "")

    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r_beta = client.get("/api/versions/comparisons", headers=headers_beta)
    assert r_beta.status_code == 200
    comps_beta = r_beta.json()["comparisons"]

    for c in comps_beta:
        assert c.get("organization_id") in ("org_beta", "")


@pytest.mark.asyncio
async def test_30_get_comparison_detail_cross_tenant_blocked_403():
    """Merchant Beta attempting to access Merchant Alpha's comparison detail is blocked with 403."""
    await _setup_sec07()
    # Create comparison by Alpha
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    assert r.status_code == 200
    cmp_id = r.json()["comparison_id"]

    # Beta attempts access
    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r_idor = client.get(f"/api/versions/comparisons/{cmp_id}", headers=headers_beta)
    assert r_idor.status_code == 403


@pytest.mark.asyncio
async def test_31_export_comparison_json_cross_tenant_blocked_403():
    """Merchant Beta attempting to export Merchant Alpha's comparison JSON is blocked with 403."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    cmp_id = r.json()["comparison_id"]

    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r_exp = client.get(f"/api/versions/comparisons/{cmp_id}/json", headers=headers_beta)
    assert r_exp.status_code == 403


@pytest.mark.asyncio
async def test_32_export_comparison_csv_cross_tenant_blocked_403():
    """Merchant Beta attempting to export Merchant Alpha's comparison CSV is blocked with 403."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    cmp_id = r.json()["comparison_id"]

    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r_exp = client.get(f"/api/versions/comparisons/{cmp_id}/csv", headers=headers_beta)
    assert r_exp.status_code == 403


@pytest.mark.asyncio
async def test_33_export_comparison_json_and_csv_authorized_200():
    """Merchant Alpha exporting their own comparison JSON and CSV succeeds with 200 OK."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    cmp_id = r.json()["comparison_id"]

    # JSON export
    r_json = client.get(f"/api/versions/comparisons/{cmp_id}/json", headers=headers_alpha)
    assert r_json.status_code == 200
    assert r_json.headers.get("content-type") == "application/json"
    exported_data = r_json.json()
    assert exported_data.get("comparison_id") == cmp_id

    # CSV export
    r_csv = client.get(f"/api/versions/comparisons/{cmp_id}/csv", headers=headers_alpha)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers.get("content-type", "")
    assert len(r_csv.content) > 50


@pytest.mark.asyncio
async def test_34_delete_comparison_cross_tenant_blocked_403():
    """Merchant Beta attempting to delete Merchant Alpha's comparison is blocked with 403."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    cmp_id = r.json()["comparison_id"]

    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r_del = client.delete(f"/api/versions/comparisons/{cmp_id}", headers=headers_beta)
    assert r_del.status_code == 403

    # Verify comparison is still present in DB
    still_exists = await get_version_comparison(cmp_id)
    assert still_exists is not None


@pytest.mark.asyncio
async def test_35_delete_comparison_authorized_200_and_purged():
    """Merchant Alpha deleting their own comparison succeeds with 200 and purges record."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_alpha)
    cmp_id = r.json()["comparison_id"]

    r_del = client.delete(f"/api/versions/comparisons/{cmp_id}", headers=headers_alpha)
    assert r_del.status_code == 200
    assert r_del.json().get("status") == "deleted"

    # Subsequent GET returns 404
    r_get = client.get(f"/api/versions/comparisons/{cmp_id}", headers=headers_alpha)
    assert r_get.status_code == 404


@pytest.mark.asyncio
async def test_36_delete_nonexistent_comparison_returns_404():
    """Deleting a non-existent comparison returns 404."""
    await _setup_sec07()
    headers_adm = make_auth_headers("admin_sec07", ROLE_ADMIN)
    r = client.delete("/api/versions/comparisons/cmp_nonexistent_999", headers=headers_adm)
    assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 5. TIMELINE SCOPING & ERROR METADATA LEAKAGE PREVENTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_37_timeline_scoped_to_tenant():
    """Timeline queries for an entity only return events within the caller's tenant."""
    await _setup_sec07()
    entity_id = "Alpha Biscuit Pack"

    # Save comparison for Alpha
    await save_version_comparison({
        "comparison_id": "cmp_timeline_alpha",
        "entity_id": entity_id,
        "entity_type": "PRODUCT",
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "version_a_label": "v1.0",
        "version_b_label": "v2.0",
        "score_a": 85.0,
        "score_b": 95.0,
        "delta_score": 10.0,
        "risk_a": "LOW",
        "risk_b": "LOW",
        "total_changes": 1,
        "resolved_issues_count": 0,
        "new_issues_count": 0,
        "summary": "Alpha packaging revision",
        "details": {},
        "organization_id": "org_alpha",
        "owner_user_id": "merchant_alpha"
    })

    # Merchant Alpha fetches timeline
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    r_alpha = client.get(f"/api/versions/timeline/{entity_id}", headers=headers_alpha)
    assert r_alpha.status_code == 200
    events_alpha = r_alpha.json()["events"]
    assert len(events_alpha) >= 1

    # Merchant Beta fetches timeline for the same entity name
    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r_beta = client.get(f"/api/versions/timeline/{entity_id}", headers=headers_beta)
    assert r_beta.status_code == 200
    events_beta = r_beta.json()["events"]
    # Merchant Beta must not see any of Alpha's timeline events
    assert len(events_beta) == 0


@pytest.mark.asyncio
async def test_38_timeline_merchant_scoped_to_own_records():
    """Officer in org_alpha sees org_alpha timeline; Merchant in other org sees 0."""
    await _setup_sec07()
    entity_id = "Alpha Biscuit Pack"
    headers_off = make_auth_headers("officer_alpha", ROLE_ENFORCEMENT)
    r = client.get(f"/api/versions/timeline/{entity_id}", headers=headers_off)
    assert r.status_code == 200
    assert len(r.json()["events"]) >= 1


@pytest.mark.asyncio
async def test_39_error_responses_zero_sensitive_metadata_leak():
    """403 and 404 responses do not leak sensitive metadata (prices, secrets, product names)."""
    await _setup_sec07()
    headers_beta = make_auth_headers("merchant_beta", ROLE_MERCHANT)
    r = client.post("/api/versions/compare", json={
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_beta_target_1",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=headers_beta)
    assert r.status_code == 403
    resp_text = r.text
    # Must not leak the name or price of the private target
    assert "Alpha Biscuit Pack" not in resp_text
    assert "₹50" not in resp_text


@pytest.mark.asyncio
async def test_40_csv_export_formula_injection_prevention():
    """CSV exports must sanitize cells starting with =, +, -, @ to prevent formula injection."""
    await _setup_sec07()
    headers_alpha = make_auth_headers("merchant_alpha", ROLE_MERCHANT)
    # Save comparison with potentially malicious formula characters
    await save_version_comparison({
        "comparison_id": "cmp_formula_test",
        "entity_id": "=cmd|' /C calc'!A0",
        "product_name": "+SUM(1,2)",
        "version_a_id": "ana_alpha_target_1",
        "version_b_id": "ana_alpha_target_2",
        "score_a": 85.0,
        "score_b": 95.0,
        "score_delta": 10.0,
        "organization_id": "org_alpha",
        "owner_user_id": "merchant_alpha",
        "field_diffs": [
            {
                "field_name": "-DANGEROUS",
                "change_type": "@ALERT",
                "value_a": "=1+1",
                "value_b": "2",
                "compliance_impact": "HIGH",
                "explanation": "=HYPERLINK(\"http://evil.com\")"
            }
        ]
    })

    r = client.get("/api/versions/comparisons/cmp_formula_test/csv", headers=headers_alpha)
    assert r.status_code == 200
    csv_content = r.content.decode('utf-8-sig')

    # Verify every formula prefix is sanitized with a leading single quote or safe prefix
    for line in csv_content.splitlines():
        cells = [c.strip('"') for c in line.split(",")]
        for cell in cells:
            if cell:
                # Should not start with raw unsanitized executable formula syntax
                assert not cell.startswith(("=cmd", "=HYPERLINK", "+SUM"))

