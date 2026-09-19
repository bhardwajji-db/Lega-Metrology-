import pytest
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from main import app
from models.verification_schemas import (
    CrossCheckStatus,
    VerificationConfidenceTier,
    ApiAvailabilityState,
    ExternalVerificationSummary,
    CrossCheckRequest,
    CacheSeedItem,
)
from integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus
from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus
from integrations.fssai.verifier import FSSAILicenceVerifier, fssai_verifier
from integrations.gs1.verifier import GS1BarcodeVerifier, gs1_verifier
from integrations.cross_checker import (
    CrossCheckEngine,
    cross_check_engine,
    normalize_entity_text,
    compute_similarity
)
from database.db import (
    save_cached_verification,
    get_cached_verification,
    delete_cached_verification,
    clear_expired_verification_cache,
    get_verification_cache_stats,
    list_cached_verifications,
    init_db
)


# ── Requirement 1: FSSAI Number Format Validation ──────────────────────────

def test_fssai_format_validation():
    # Valid 14-digit licence (Category 1 = Central/State Licence)
    assert FSSAILicenceVerifier.validate_format("10014011000123") is True
    # Valid 14-digit registration (Category 2 = Registration)
    assert FSSAILicenceVerifier.validate_format("20019022000456") is True
    # Invalid: 13 digits
    assert FSSAILicenceVerifier.validate_format("1001401100012") is False
    # Invalid: 15 digits
    assert FSSAILicenceVerifier.validate_format("100140110001234") is False
    # Invalid: Starting digit not 1 or 2
    assert FSSAILicenceVerifier.validate_format("30014011000123") is False
    # Invalid: Non-numeric / Empty
    assert FSSAILicenceVerifier.validate_format("") is False
    assert FSSAILicenceVerifier.validate_format(None) is False


# ── Requirement 2: FoSCoS Verification ─────────────────────────────────────

@pytest.mark.asyncio
async def test_fssai_foscos_verification_flow():
    # Empty or unprovided licence
    rec_empty = await fssai_verifier.verify(None)
    assert rec_empty.status == FSSAIVerificationStatus.NOT_APPLICABLE

    # Structurally invalid licence
    rec_inv = await fssai_verifier.verify("12345")
    assert rec_inv.status == FSSAIVerificationStatus.INVALID_FORMAT

    # Valid format with local fallback (when live unconfigured)
    rec_valid = await fssai_verifier.verify("10014011000123")
    assert rec_valid.licence_number == "10014011000123"
    assert rec_valid.status in (FSSAIVerificationStatus.NOT_VERIFIED, FSSAIVerificationStatus.VERIFIED)
    assert rec_valid.verification_timestamp is not None


# ── Requirement 3: GS1 Checksum Validation ─────────────────────────────────

def test_gs1_modulo10_checksum_validation():
    # Valid GTIN-13: "8901030383458"
    # Modulo-10 checksum algorithm test:
    # 8*1 + 9*3 + 0*1 + 1*3 + 0*1 + 3*3 + 0*1 + 3*3 + 8*1 + 3*3 + 4*1 + 5*3 = 92 -> 10 - 2 = 8
    prefix = "890103038345"
    expected_check = GS1BarcodeVerifier.calculate_check_digit(prefix)
    assert expected_check == 8
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901030383458") is True

    # Valid GTIN-12 (UPC-A): "012345678905"
    prefix12 = "01234567890"
    check12 = GS1BarcodeVerifier.calculate_check_digit(prefix12)
    assert check12 == 5
    assert GS1BarcodeVerifier.validate_gtin_checksum("012345678905") is True

    # Valid GTIN-8 (EAN-8): "96385074"
    prefix8 = "9638507"
    check8 = GS1BarcodeVerifier.calculate_check_digit(prefix8)
    assert check8 == 4
    assert GS1BarcodeVerifier.validate_gtin_checksum("96385074") is True

    # Invalid Checksum
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901030383459") is False
    # Invalid Length
    assert GS1BarcodeVerifier.validate_gtin_checksum("123456") is False


# ── Requirement 4: GS1 External Verification ───────────────────────────────

@pytest.mark.asyncio
async def test_gs1_datakart_verification_flow():
    # Empty barcode
    rec_empty = await gs1_verifier.verify(None)
    assert rec_empty.status == GS1VerificationStatus.NOT_APPLICABLE

    # Invalid Checksum Barcode
    rec_inv = await gs1_verifier.verify("8901030383459")
    assert rec_inv.status == GS1VerificationStatus.INVALID_FORMAT

    # Valid Checksum with local fallback
    rec_valid = await gs1_verifier.verify("8901030383458")
    assert rec_valid.gtin == "8901030383458"
    assert rec_valid.status in (GS1VerificationStatus.NOT_VERIFIED, GS1VerificationStatus.VERIFIED)
    assert rec_valid.verification_timestamp is not None


# ── Requirements 5 & 6: Barcode & QR Vision Safety ──────────────────────────

def test_qr_safe_decoding_and_sanitization():
    from vision.qr_detector import qr_detector
    import numpy as np
    
    # Empty / Black image returns safe non-detected result
    empty_img = np.zeros((100, 100, 3), dtype=np.uint8)
    res = qr_detector.detect_and_decode(empty_img)
    assert res.detected is False
    assert res.is_safe_payload is True


# ── Requirements 7 & 10: GS1 ↔ Product Consistency Check ───────────────────

def test_gs1_product_consistency_matching():
    engine = CrossCheckEngine()
    
    # Exact Match
    rec_match = GS1VerificationRecord(
        gtin="8901030383458",
        status=GS1VerificationStatus.VERIFIED,
        brand_name="Britannia",
        product_description="Good Day Butter Cookies 100g",
        company_name="Britannia Industries Limited"
    )
    res = engine.check_gs1_product_consistency(
        gs1_record=rec_match,
        extracted_product_name="Good Day Butter Cookies",
        extracted_brand_name="Britannia"
    )
    assert res.status == CrossCheckStatus.MATCH
    assert res.similarity_score >= 0.65
    assert not res.is_critical_mismatch

    # Mismatch
    res_mismatch = engine.check_gs1_product_consistency(
        gs1_record=rec_match,
        extracted_product_name="Sunfeast Dark Fantasy Choco Fills",
        extracted_brand_name="ITC"
    )
    assert res_mismatch.status == CrossCheckStatus.MISMATCH
    assert res_mismatch.similarity_score < 0.35
    assert res_mismatch.is_critical_mismatch is True


# ── Requirements 8 & 9: FSSAI ↔ Manufacturer Consistency Check ─────────────

def test_fssai_manufacturer_consistency_matching():
    engine = CrossCheckEngine()

    # Match with corporate suffix normalization
    rec_fssai = FSSAIVerificationRecord(
        licence_number="10014011000123",
        status=FSSAIVerificationStatus.VERIFIED,
        business_name="Nestle India Limited - Moga Factory",
        licence_type="Central Licence"
    )
    res_match = engine.check_fssai_manufacturer_consistency(
        fssai_record=rec_fssai,
        extracted_manufacturer="Nestle India Ltd",
        extracted_address="Moga, Punjab"
    )
    assert res_match.status in (CrossCheckStatus.MATCH, CrossCheckStatus.PARTIAL_MATCH)
    assert res_match.similarity_score >= 0.40
    assert not res_match.is_critical_mismatch

    # Mismatch
    res_mismatch = engine.check_fssai_manufacturer_consistency(
        fssai_record=rec_fssai,
        extracted_manufacturer="Hindustan Unilever Limited",
        extracted_address="Mumbai"
    )
    assert res_mismatch.status == CrossCheckStatus.MISMATCH
    assert res_mismatch.similarity_score < 0.40
    assert res_mismatch.is_critical_mismatch is True


# ── Requirement 11: Verification Confidence ─────────────────────────────────

def test_verification_confidence_calculation():
    engine = CrossCheckEngine()

    fssai_verified = FSSAIVerificationRecord(
        licence_number="10014011000123",
        status=FSSAIVerificationStatus.VERIFIED,
        business_name="Amul Dairy"
    )
    gs1_verified = GS1VerificationRecord(
        gtin="8901262010014",
        status=GS1VerificationStatus.VERIFIED,
        brand_name="Amul",
        product_description="Amul Pure Ghee 1L"
    )

    # High confidence case: both verified + fields agree
    checks_pass = [
        engine.check_fssai_manufacturer_consistency(fssai_verified, "Amul Dairy"),
        engine.check_gs1_product_consistency(gs1_verified, "Pure Ghee 1L", "Amul")
    ]
    conf_high = engine.compute_verification_confidence(fssai_verified, gs1_verified, checks_pass)
    assert conf_high.score >= 0.75
    assert conf_high.tier == VerificationConfidenceTier.HIGH
    assert conf_high.checksum_passed is True
    assert conf_high.registry_confirmed is True

    # Zero confidence case: no identifiers present
    conf_zero = engine.compute_verification_confidence(None, None, [])
    assert conf_zero.score == 0.0
    assert conf_zero.tier == VerificationConfidenceTier.ZERO


# ── Requirements 12 & 13: API Availability Status & Offline Mode ───────────

def test_api_availability_and_offline_evaluation():
    engine = CrossCheckEngine()
    extracted = {
        "product_name": "Haldiram Bhujia",
        "brand": "Haldiram",
        "manufacturer": "Haldiram Snacks Pvt Ltd",
        "fssai_license": "10012011000456",
        "mrp": "₹120"
    }

    summary = engine.evaluate_all(
        extracted_data=extracted,
        fssai_record=None,
        gs1_record=None,
        offline_mode=True
    )
    assert summary.offline_mode is True
    assert "foscos" in summary.api_availability
    assert "gs1_datakart" in summary.api_availability
    assert summary.verification_timestamp is not None


# ── Requirement 14: Persistent Verification Cache CRUD ─────────────────────

@pytest.mark.asyncio
async def test_persistent_verification_cache_lifecycle():
    await init_db()

    fssai_id = "10019011000999"
    test_data = {
        "licence_number": fssai_id,
        "business_name": "Tata Consumer Products Limited",
        "licence_type": "Central Licence",
        "status": "VERIFIED"
    }

    # 1. Save to cache
    await save_cached_verification(
        identifier_type="FSSAI",
        identifier_value=fssai_id,
        record_data=test_data,
        source="TEST_SUITE_SEED",
        ttl_seconds=3600
    )

    # 2. Retrieve from cache
    cached = await get_cached_verification("FSSAI", fssai_id)
    assert cached is not None
    assert cached["business_name"] == "Tata Consumer Products Limited"
    assert cached["_cache_source"] == "TEST_SUITE_SEED"

    # 3. Check cache stats
    stats = await get_verification_cache_stats()
    assert stats["total_cached_records"] >= 1
    assert stats["fssai_cached_count"] >= 1

    # 4. Delete cached record
    deleted = await delete_cached_verification("FSSAI", fssai_id)
    assert deleted is True

    # 5. Confirm deletion
    cached_after = await get_cached_verification("FSSAI", fssai_id)
    assert cached_after is None


# ── Requirements 15 & 16: Verification Timestamp & Source Provenance ───────

def test_timestamp_and_provenance():
    engine = CrossCheckEngine()
    fssai_rec = FSSAIVerificationRecord(
        licence_number="10014011000123",
        status=FSSAIVerificationStatus.VERIFIED,
        provider="FoSCoS Official Registry API (Live)",
        business_name="Cadbury India"
    )
    summary = engine.evaluate_all(
        extracted_data={"manufacturer": "Cadbury India"},
        fssai_record=fssai_rec,
        gs1_record=None
    )
    assert summary.verification_timestamp != ""
    assert "FoSCoS Official Registry API (Live)" in summary.verification_sources


# ── Requirements 17 & 18: Endpoints & Compliance Integration ───────────────

def test_cross_check_endpoint_integration():
    client = TestClient(app)

    payload = {
        "product_name": "Bournvita Chocolate Drink",
        "brand_name": "Cadbury",
        "manufacturer_name": "Mondelez India Foods Private Limited",
        "fssai_license": "10014011000123",
        "gtin_barcode": "8901233024545",
        "offline_mode": False
    }

    response = client.post("/api/integrations/cross-check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "cross_checks" in data
    assert "confidence" in data
    assert "api_availability" in data
    assert "verification_timestamp" in data
    assert len(data["cross_checks"]) >= 2


from auth.security import create_token, ROLE_ADMIN, hash_password
from database.db import create_user, get_user_by_username


@pytest.mark.asyncio
async def test_integrations_status_and_cache_seed():
    client = TestClient(app)

    # Ensure admin user exists for token authentication
    admin_user = await get_user_by_username("admin_seed_test")
    if not admin_user:
        h, s = hash_password("AdminSeedPass123!")
        await create_user("admin_seed_test", h, s, ROLE_ADMIN, "Admin Seed", "Central")

    admin_token = create_token("admin_seed_test", ROLE_ADMIN)

    # 1. Get status
    status_resp = client.get("/api/integrations/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "OPERATIONAL"
    assert status_data["offline_mode_ready"] is True

    # 2. Seed cache with Admin authentication
    seed_payload = [
        {
            "identifier_type": "FSSAI",
            "identifier_value": "10015011000888",
            "record_data": {
                "licence_number": "10015011000888",
                "business_name": "Dabur India Limited",
                "status": "VERIFIED"
            },
            "source": "SEED_TEST",
            "ttl_seconds": 86400
        }
    ]
    seed_resp = client.post(
        "/api/integrations/cache/seed",
        json=seed_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert seed_resp.status_code == 200
    assert seed_resp.json()["seeded_count"] == 1

    # 3. Get cache stats
    cache_stats_resp = client.get("/api/integrations/cache/stats")
    assert cache_stats_resp.status_code == 200
    assert cache_stats_resp.json()["fssai_cached_count"] >= 1
