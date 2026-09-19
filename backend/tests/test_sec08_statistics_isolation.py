import pytest
import time
import json
import base64
import hmac
import hashlib
from fastapi.testclient import TestClient
from main import app
from database.db import (
    save_analysis,
    save_review,
    create_organization,
    create_user,
    get_user_by_username
)
from auth.security import (
    create_token,
    _secret_key,
    _b64e,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT
)

client = TestClient(app)


def create_expired_token(username: str, role: str) -> str:
    """Generate an expired HMAC-SHA256 token for auth rejection testing."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) - 3600,
        "iat": int(time.time()) - 7200
    }
    h_b64 = _b64e(json.dumps(header).encode())
    p_b64 = _b64e(json.dumps(payload).encode())
    sig = hmac.new(_secret_key(), f"{h_b64}.{p_b64}".encode(), hashlib.sha256).digest()
    s_b64 = _b64e(sig)
    return f"{h_b64}.{p_b64}.{s_b64}"


_data_seeded = False


async def _ensure_seed_data():
    global _data_seeded
    if _data_seeded:
        return
    # 1. Create Organizations
    await create_organization({
        "id": "org_sec08_alpha",
        "name": "Alpha Corp",
        "org_type": "MANUFACTURER",
        "jurisdiction": "Central Delhi",
        "status": "ACTIVE"
    })
    await create_organization({
        "id": "org_sec08_beta",
        "name": "Beta Industries",
        "org_type": "PACKER",
        "jurisdiction": "South Mumbai",
        "status": "ACTIVE"
    })
    await create_organization({
        "id": "org_sec08_empty",
        "name": "Empty Holdings",
        "org_type": "IMPORTER",
        "jurisdiction": "North Kolkata",
        "status": "ACTIVE"
    })

    # 2. Create Users
    # Admin
    if not await get_user_by_username("sec08_admin"):
        await create_user("sec08_admin", "admin_hash", "salt", role=ROLE_ADMIN, organization_id="org_ministry")

    # Alpha Tenant Users
    if not await get_user_by_username("sec08_merchant_a1"):
        await create_user("sec08_merchant_a1", "hash", "salt", role=ROLE_MERCHANT, organization_id="org_sec08_alpha", full_name="Merchant A1")
    if not await get_user_by_username("sec08_merchant_a2"):
        await create_user("sec08_merchant_a2", "hash", "salt", role=ROLE_MERCHANT, organization_id="org_sec08_alpha", full_name="Merchant A2")
    if not await get_user_by_username("sec08_officer_a"):
        await create_user("sec08_officer_a", "hash", "salt", role=ROLE_ENFORCEMENT, organization_id="org_sec08_alpha", full_name="Officer Alpha")

    # Beta Tenant Users
    if not await get_user_by_username("sec08_merchant_b"):
        await create_user("sec08_merchant_b", "hash", "salt", role=ROLE_MERCHANT, organization_id="org_sec08_beta", full_name="Merchant Beta")
    if not await get_user_by_username("sec08_officer_b"):
        await create_user("sec08_officer_b", "hash", "salt", role=ROLE_ENFORCEMENT, organization_id="org_sec08_beta", full_name="Officer Beta")

    # Empty Tenant User
    if not await get_user_by_username("sec08_merchant_empty"):
        await create_user("sec08_merchant_empty", "hash", "salt", role=ROLE_MERCHANT, organization_id="org_sec08_empty", full_name="Merchant Empty")

    # 3. Seed Analyses for Alpha (Total = 10, Merchant A1 = 4 [3 Pass, 1 Fail], Merchant A2 = 6 [4 Pass, 2 Fail])
    for i in range(4):
        await save_analysis({
            "id": f"sec08-ana-a1-{i}",
            "product_name": "Alpha Organic Oil",
            "score": 95.0 if i < 3 else 45.0,
            "status": "COMPLIANT" if i < 3 else "NON_COMPLIANT",
            "owner_user_id": "sec08_merchant_a1",
            "organization_id": "org_sec08_alpha",
            "created_at": "2026-09-18T10:00:00Z",
            "compliance_result": {
                "score": 95.0 if i < 3 else 45.0,
                "status": "COMPLIANT" if i < 3 else "NON_COMPLIANT",
                "failed_rules": 0 if i < 3 else 2,
                "passed_rules": 12 if i < 3 else 10,
                "needs_review_rules": 0,
                "risk_assessment": {"risk_level": "LOW" if i < 3 else "HIGH"}
            }
        })

    for i in range(6):
        await save_analysis({
            "id": f"sec08-ana-a2-{i}",
            "product_name": "Alpha Ghee 1L",
            "score": 92.0 if i < 4 else 50.0,
            "status": "COMPLIANT" if i < 4 else "NON_COMPLIANT",
            "owner_user_id": "sec08_merchant_a2",
            "organization_id": "org_sec08_alpha",
            "created_at": "2026-09-18T11:00:00Z",
            "compliance_result": {
                "score": 92.0 if i < 4 else 50.0,
                "status": "COMPLIANT" if i < 4 else "NON_COMPLIANT",
                "failed_rules": 0 if i < 4 else 2,
                "passed_rules": 12 if i < 4 else 10,
                "needs_review_rules": 0,
                "risk_assessment": {"risk_level": "LOW" if i < 4 else "HIGH"}
            }
        })

    # 4. Seed Analyses for Beta (Total = 20: 18 Compliant, 2 Fail)
    for i in range(20):
        await save_analysis({
            "id": f"sec08-ana-b-{i}",
            "product_name": "Beta Protein Shake",
            "score": 98.0 if i < 18 else 40.0,
            "status": "COMPLIANT" if i < 18 else "NON_COMPLIANT",
            "owner_user_id": "sec08_merchant_b",
            "organization_id": "org_sec08_beta",
            "created_at": "2026-09-18T12:00:00Z",
            "compliance_result": {
                "score": 98.0 if i < 18 else 40.0,
                "status": "COMPLIANT" if i < 18 else "NON_COMPLIANT",
                "failed_rules": 0 if i < 18 else 3,
                "passed_rules": 12 if i < 18 else 9,
                "needs_review_rules": 0,
                "risk_assessment": {"risk_level": "LOW" if i < 18 else "CRITICAL"}
            }
        })

    # 5. Seed Reviews
    # Alpha Reviews: 2 pending reviews assigned to Officer Alpha
    for i in range(2):
        await save_review({
            "id": f"sec08-rev-a-{i}",
            "analysis_id": f"sec08-ana-a1-{i}",
            "target_type": "ANALYSIS",
            "product_name": "Alpha Organic Oil",
            "status": "PENDING_REVIEW",
            "assigned_officer": "sec08_officer_a",
            "assigned_by": "sec08_officer_a",
            "ai_score": 45.0,
            "ai_risk_level": "HIGH",
            "ai_status": "FAIL",
            "organization_id": "org_sec08_alpha",
            "created_at": "2026-09-18T10:30:00Z"
        })

    # Beta Reviews: 5 pending reviews assigned to Officer Beta
    for i in range(5):
        await save_review({
            "id": f"sec08-rev-b-{i}",
            "analysis_id": f"sec08-ana-b-{i}",
            "target_type": "ANALYSIS",
            "product_name": "Beta Protein Shake",
            "status": "PENDING_REVIEW",
            "assigned_officer": "sec08_officer_b",
            "assigned_by": "sec08_officer_b",
            "ai_score": 40.0,
            "ai_risk_level": "CRITICAL",
            "ai_status": "FAIL",
            "organization_id": "org_sec08_beta",
            "created_at": "2026-09-18T12:30:00Z"
        })
    _data_seeded = True


# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION & TOKEN VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_stats_endpoint_requires_auth():
    """GET /api/stats must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_02_stats_trends_endpoint_requires_auth():
    """GET /api/stats/trends must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/stats/trends")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_03_stats_by_status_endpoint_requires_auth():
    """GET /api/stats/by-status must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/stats/by-status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_04_reviews_dashboard_endpoint_requires_auth():
    """GET /api/reviews/dashboard must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/reviews/dashboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_05_reviews_officers_endpoint_requires_auth():
    """GET /api/reviews/officers must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/reviews/officers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_06_scoring_history_endpoint_requires_auth():
    """GET /api/scoring/history/{id} must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/scoring/history/sec08-ana-a1-0")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_07_scoring_product_history_requires_auth():
    """GET /api/scoring/product/{name}/history must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/scoring/product/Alpha%20Organic%20Oil/history")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_08_scoring_batch_distribution_requires_auth():
    """GET /api/scoring/batch-distribution must reject unauthenticated requests with 401."""
    await _ensure_seed_data()
    resp = client.get("/api/scoring/batch-distribution")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_09_invalid_token_rejected_401():
    """Invalid token format or signature must return 401 Unauthorized across stats endpoints."""
    await _ensure_seed_data()
    headers = {"Authorization": "Bearer invalid.garbage.token"}
    assert client.get("/api/stats", headers=headers).status_code == 401
    assert client.get("/api/stats/trends", headers=headers).status_code == 401
    assert client.get("/api/scoring/batch-distribution", headers=headers).status_code == 401


@pytest.mark.asyncio
async def test_10_expired_token_rejected_401():
    """Expired token must return 401 Unauthorized across stats endpoints."""
    await _ensure_seed_data()
    exp_token = create_expired_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {exp_token}"}
    assert client.get("/api/stats", headers=headers).status_code == 401
    assert client.get("/api/stats/trends", headers=headers).status_code == 401
    assert client.get("/api/scoring/batch-distribution", headers=headers).status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 2. MERCHANT USER-SCOPED ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_11_merchant_a1_sees_only_own_stats():
    """Merchant A1 in Org Alpha must only see their own 4 analyses (not A2's 6, not Beta's 20)."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 4
    assert data["compliant"] == 3
    assert data["failures"] == 2
    # Verify recent records only contain Merchant A1 items
    assert len(data["recent"]) == 4
    for item in data["recent"]:
        assert item["owner_user_id"] == "sec08_merchant_a1"


@pytest.mark.asyncio
async def test_12_merchant_a2_sees_only_own_stats():
    """Merchant A2 in Org Alpha must only see their own 6 analyses (not A1's 4, not Beta's 20)."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a2", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 6
    assert data["compliant"] == 4
    assert data["failures"] == 4
    assert len(data["recent"]) == 5  # capped at 5 recent
    for item in data["recent"]:
        assert item["owner_user_id"] == "sec08_merchant_a2"


@pytest.mark.asyncio
async def test_13_merchant_b_sees_only_own_stats():
    """Merchant B in Org Beta must only see their own 20 analyses."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_b", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 20
    assert data["compliant"] == 18
    assert data["failures"] == 6


@pytest.mark.asyncio
async def test_14_merchant_cannot_spoof_owner_in_batch_distribution():
    """Merchant A1 attempting ?owner_user_id=sec08_merchant_a2 or sec08_merchant_b is overridden to A1."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/batch-distribution?owner_user_id=sec08_merchant_b", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 4
    assert data["low_count"] == 3
    assert data["high_count"] == 1
    assert data["critical_count"] == 0


@pytest.mark.asyncio
async def test_15_merchant_status_distribution_scoped():
    """GET /api/stats/by-status for Merchant A1 must return counts only for A1."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats/by-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    total_status = sum(data["values"])
    assert total_status == 4


@pytest.mark.asyncio
async def test_16_merchant_trends_scoped():
    """GET /api/stats/trends for Merchant A1 returns counts matching A1 dataset."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats/trends?days=14", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert sum(data["total"]) == 4
    assert sum(data["compliant"]) == 3
    assert sum(data["violations"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 3. ENFORCEMENT & AUDIT OFFICER TENANT-SCOPED ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_17_officer_alpha_sees_all_org_alpha_stats():
    """Officer Alpha sees all 10 analyses belonging to Org Alpha (4 from A1 + 6 from A2, 0 from Beta)."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_a", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 10
    assert data["compliant"] == 7
    assert data["failures"] == 6


@pytest.mark.asyncio
async def test_18_officer_beta_sees_all_org_beta_stats():
    """Officer Beta sees all 20 analyses belonging to Org Beta (0 from Alpha)."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_b", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 20
    assert data["compliant"] == 18
    assert data["failures"] == 6


@pytest.mark.asyncio
async def test_19_officer_alpha_reviews_dashboard_scoped():
    """Officer Alpha dashboard returns only Org Alpha reviews (2 pending, 0 from Beta)."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_a", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/reviews/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queue"] == 2
    assert data["pending_review"] == 2
    # Verify workload only contains officers belonging to Org Alpha
    for wl in data["workload"]:
        assert wl["officer_username"] != "sec08_officer_b"


@pytest.mark.asyncio
async def test_20_officer_beta_reviews_dashboard_scoped():
    """Officer Beta dashboard returns only Org Beta reviews (5 pending, 0 from Alpha)."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_b", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/reviews/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queue"] == 5
    assert data["pending_review"] == 5
    for wl in data["workload"]:
        assert wl["officer_username"] != "sec08_officer_a"


@pytest.mark.asyncio
async def test_21_officer_directory_filtered_by_organization():
    """Officer Alpha querying GET /api/reviews/officers sees only officers in Org Alpha."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_a", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/reviews/officers", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    usernames = [u["username"] for u in data["officers"]]
    assert "sec08_officer_a" in usernames
    assert "sec08_officer_b" not in usernames


@pytest.mark.asyncio
async def test_22_officer_batch_distribution_scoped():
    """Officer Alpha batch distribution aggregates only Org Alpha (10 analyses)."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_a", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/batch-distribution", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 10
    assert data["low_count"] == 7
    assert data["high_count"] == 3
    assert data["critical_count"] == 0


@pytest.mark.asyncio
async def test_23_officer_trends_scoped():
    """Officer Alpha trends query returns total of 10."""
    await _ensure_seed_data()
    token = create_token("sec08_officer_a", ROLE_ENFORCEMENT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats/trends?days=14", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert sum(data["total"]) == 10
    assert sum(data["compliant"]) == 7
    assert sum(data["violations"]) == 3


# ══════════════════════════════════════════════════════════════════════════════
# 4. ADMIN STATUTORY GLOBAL OVERSIGHT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_24_admin_statutory_oversight_sees_all_stats():
    """Admin sees system-wide aggregation across all organizations."""
    await _ensure_seed_data()
    token = create_token("sec08_admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # At least 30 (10 Alpha + 20 Beta)
    assert data["total_analyzed"] >= 30


@pytest.mark.asyncio
async def test_25_admin_review_dashboard_sees_all_queues():
    """Admin review dashboard aggregates all queues across all organizations."""
    await _ensure_seed_data()
    token = create_token("sec08_admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/reviews/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queue"] >= 7  # 2 Alpha + 5 Beta


@pytest.mark.asyncio
async def test_26_admin_officers_directory_sees_all_officers():
    """Admin GET /api/reviews/officers returns all registered officers across orgs."""
    await _ensure_seed_data()
    token = create_token("sec08_admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/reviews/officers", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    usernames = [u["username"] for u in data["officers"]]
    assert "sec08_officer_a" in usernames
    assert "sec08_officer_b" in usernames


# ══════════════════════════════════════════════════════════════════════════════
# 5. ZERO-DATA EMPTY TENANT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_27_empty_tenant_returns_zero_stats_no_global_fallback():
    """An organization with 0 analyses must return 0 counts and not fallback to global data."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_empty", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 0
    assert data["compliant"] == 0
    assert data["failures"] == 0
    assert data["average_score"] == 0.0
    assert data["recent"] == []


@pytest.mark.asyncio
async def test_28_empty_tenant_batch_distribution_zero():
    """Empty tenant batch distribution returns 0 counts and 0.0 percentages."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_empty", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/batch-distribution", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 0
    assert data["critical_count"] == 0
    assert data["high_count"] == 0
    assert data["medium_count"] == 0
    assert data["low_count"] == 0


@pytest.mark.asyncio
async def test_29_empty_tenant_trends_all_zeroes():
    """Empty tenant trends returns lists containing only zeroes."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_empty", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/stats/trends?days=7", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert sum(data["total"]) == 0
    assert sum(data["compliant"]) == 0
    assert sum(data["violations"]) == 0


# ══════════════════════════════════════════════════════════════════════════════
# 6. PRODUCT RISK HISTORY & INDIVIDUAL SCORE HISTORY ACCESS CONTROL
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_30_product_risk_history_scoped_to_tenant():
    """Merchant in Org Alpha querying 'Beta Protein Shake' finds 0 records."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/product/Beta%20Protein%20Shake/history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyses"] == 0
    assert data["history_entries"] == []


@pytest.mark.asyncio
async def test_31_product_risk_history_merchant_own_product():
    """Merchant A1 querying 'Alpha Organic Oil' finds 4 records."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/product/Alpha%20Organic%20Oil/history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyses"] == 4
    assert len(data["history_entries"]) == 4


@pytest.mark.asyncio
async def test_32_score_history_detail_cross_tenant_blocked_403():
    """Merchant A1 requesting score history for Beta analysis 'sec08-ana-b-0' is rejected with 403."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/history/sec08-ana-b-0", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_33_score_history_detail_same_tenant_merchant_cross_user_blocked_403():
    """Merchant A1 requesting score history for A2's analysis 'sec08-ana-a2-0' is rejected with 403."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/history/sec08-ana-a2-0", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_34_score_history_detail_authorized_success_200():
    """Merchant A1 requesting score history for their own analysis 'sec08-ana-a1-0' succeeds with 200."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/history/sec08-ana-a1-0", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_id"] == "sec08-ana-a1-0"
    assert data["score"] == 95.0


@pytest.mark.asyncio
async def test_35_score_history_nonexistent_returns_404():
    """Requesting nonexistent score history returns 404 Not Found."""
    await _ensure_seed_data()
    token = create_token("sec08_merchant_a1", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/scoring/history/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_36_scoring_config_public_or_admin():
    """GET /api/scoring/config returns active scoring parameters."""
    await _ensure_seed_data()
    resp = client.get("/api/scoring/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "scoring_version" in data
    assert "weight_pass" in data


@pytest.mark.asyncio
async def test_37_verification_cache_stats_global_reference():
    """GET /api/integrations/cache/stats returns regulatory cache stats."""
    await _ensure_seed_data()
    resp = client.get("/api/integrations/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "cache_engine" in data
