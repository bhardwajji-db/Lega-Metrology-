import pytest
import os
import cv2
import numpy as np
from httpx import AsyncClient, ASGITransport
from main import app
from integrations.fssai import (
    FSSAILicenceVerifier,
    FSSAIVerificationStatus,
    FoSCoSApiProvider,
    LocalFSSAICacheProvider,
)
from integrations.gs1 import (
    GS1BarcodeVerifier,
    GS1VerificationStatus,
    GS1DataKartApiProvider,
    LocalGS1CacheProvider,
)
from services.calibration_service import PhysicalCalibrationService, calibration_service
from compliance.rules.legal_metrology import compute_font_size_and_readability
from extraction.extractor import LocalExtractor
from models.schemas import ProductInfo, OCRResult, CalibrationResult


# ============================================================================
# 1. FSSAI LICENCE VERIFICATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_fssai_format_validation():
    # Valid 14-digit format starting with 1 (Central/State Licence) or 2 (Registration)
    assert FSSAILicenceVerifier.validate_format("10019021004567") is True
    assert FSSAILicenceVerifier.validate_format("20020011007890") is True

    # Invalid formats
    assert FSSAILicenceVerifier.validate_format("30019021004567") is False  # Must start with 1 or 2
    assert FSSAILicenceVerifier.validate_format("1001902100456") is False   # 13 digits
    assert FSSAILicenceVerifier.validate_format("100190210045678") is False # 15 digits
    assert FSSAILicenceVerifier.validate_format("1001902100456A") is False # Non-digits
    assert FSSAILicenceVerifier.validate_format("") is False


@pytest.mark.asyncio
async def test_fssai_verifier_unconfigured():
    verifier = FSSAILicenceVerifier(primary_provider=FoSCoSApiProvider(api_url=""))
    res = await verifier.verify("10019021004567")
    assert res.status == FSSAIVerificationStatus.NOT_VERIFIED
    assert "Statutory 14-digit format valid" in res.message
    assert res.licence_number == "10019021004567"
    assert res.is_live is False


@pytest.mark.asyncio
async def test_fssai_invalid_format():
    verifier = FSSAILicenceVerifier()
    res = await verifier.verify("999999")
    assert res.status == FSSAIVerificationStatus.INVALID_FORMAT
    assert "does not conform" in res.message


@pytest.mark.asyncio
async def test_fssai_cache_provider():
    cache_prov = LocalFSSAICacheProvider()
    cache_prov.set_cache_record("10020021001122", {
        "status": FSSAIVerificationStatus.VERIFIED,
        "business_name": "Alpino Health Foods Pvt Ltd",
        "licence_type": "Central Licence",
        "valid_upto": "2028-12-31"
    })
    
    verifier = FSSAILicenceVerifier(fallback_provider=cache_prov)
    res = await verifier.verify("10020021001122")
    assert res.status == FSSAIVerificationStatus.VERIFIED
    assert res.business_name == "Alpino Health Foods Pvt Ltd"
    assert res.provider == "MetrCheck Verified FSSAI Local Cache"


# ============================================================================
# 2. GS1 BARCODE & GTIN VERIFICATION TESTS
# ============================================================================

def test_gs1_checksum_calculation():
    # Standard GTIN-13 examples with valid check digits:
    # 8901030383748 (Prefix 890103038374 -> Check digit 8)
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901030383748") is True
    # 8901234567890 (Prefix 890123456789 -> Check digit 0)
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901234567890") is True
    
    # Invalid check digit (tampered last digit)
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901030383749") is False
    # Invalid length
    assert GS1BarcodeVerifier.validate_gtin_checksum("12345") is False


@pytest.mark.asyncio
async def test_gs1_verifier_unconfigured():
    verifier = GS1BarcodeVerifier(primary_provider=GS1DataKartApiProvider(api_url=""))
    res = await verifier.verify("8901030383748")
    assert res.status == GS1VerificationStatus.NOT_VERIFIED
    assert "GTIN-13" in res.message
    assert res.is_live is False


@pytest.mark.asyncio
async def test_gs1_verifier_invalid_checksum():
    verifier = GS1BarcodeVerifier()
    res = await verifier.verify("8901030383740")  # Wrong check digit
    assert res.status == GS1VerificationStatus.INVALID_FORMAT
    assert "checksum validation" in res.message


@pytest.mark.asyncio
async def test_gs1_cache_provider():
    cache_prov = LocalGS1CacheProvider()
    cache_prov.set_cache_record("8901030383748", {
        "status": GS1VerificationStatus.VERIFIED,
        "brand_name": "Alpino",
        "product_description": "Super Muesli Nut Delight 400g",
        "company_name": "Alpino Health Foods Pvt Ltd"
    })

    verifier = GS1BarcodeVerifier(fallback_provider=cache_prov)
    res = await verifier.verify("8901030383748")
    assert res.status == GS1VerificationStatus.VERIFIED
    assert res.brand_name == "Alpino"
    assert res.company_name == "Alpino Health Foods Pvt Ltd"


# ============================================================================
# 3. RULE 12 OPTICAL CALIBRATION & MEASUREMENT TESTS
# ============================================================================

def test_aruco_optical_calibration(tmp_path):
    # Create synthetic test image containing a 50mm ArUco marker (100x100 px -> 2 px/mm)
    dict_type = cv2.aruco.DICT_4X4_50
    dictionary = cv2.aruco.getPredefinedDictionary(dict_type)
    marker_img = cv2.aruco.generateImageMarker(dictionary, 5, 100)

    canvas = np.ones((400, 400), dtype=np.uint8) * 255
    canvas[50:150, 50:150] = marker_img

    img_path = str(tmp_path / "test_marker.jpg")
    cv2.imwrite(img_path, canvas)

    # Detect calibration
    calib = PhysicalCalibrationService.detect_aruco_marker(img_path, target_size_mm=50.0)
    assert calib.status == "PHYSICAL_MEASUREMENT_VERIFIED"
    assert calib.pixels_per_mm is not None
    # 100px / 50mm ~= 1.98 to 2.02 px/mm
    assert 1.90 <= calib.pixels_per_mm <= 2.10
    assert "ArUco" in calib.message


def test_font_size_optical_calibration_integration():
    info = ProductInfo(
        product_name="Muesli 400g",
        net_quantity="400 g",
        mrp="₹299",
        other_declarations={},
        extraction_mode="real"
    )
    
    # 2.0 px/mm calibration
    calib = CalibrationResult(
        status="PHYSICAL_MEASUREMENT_VERIFIED",
        target_type="ARUCO_4X4_ID_5",
        pixels_per_mm=2.0,
        message="Calibrated"
    )

    # Net qty bounding box is 8px high -> 8px / 2.0 px/mm = 4.0 mm
    from models.schemas import ComplianceCheck
    check = ComplianceCheck(
        rule_id="LM-003",
        field="net_quantity",
        field_label="Net Quantity",
        required=True,
        detected=True,
        detected_value="400 g",
        severity="high",
        status="PASS",
        description="",
        source="",
        explanation="",
        recommendation="",
        bbox=[100, 100, 200, 108]  # height = 8 px
    )

    analysis = compute_font_size_and_readability(
        product_info=info,
        checks=[check],
        calibration_result=calib
    )

    assert analysis.calibration_status == "PHYSICAL_MEASUREMENT_VERIFIED"
    assert analysis.measurement_method == "ARUCO_OPTICAL_SCALE"
    assert analysis.net_quantity_font_height_mm == 4.0
    assert analysis.is_font_compliant is True
    assert "Verified Optical Measurement" in analysis.rule_12_verdict


# ============================================================================
# 4. MULTILINGUAL (HINDI / DEVANAGARI) EXTRACTION TESTS
# ============================================================================

def test_devanagari_statutory_extraction():
    extractor = LocalExtractor()
    hindi_text = """
    Patanjali Pure Cow Ghee
    शुद्ध मात्रा: 500 ग्राम
    अधिकतम खुदरा मूल्य: ₹ 350.00
    निर्माता: पतंजलि आयुर्वेद लिमिटेड, हरिद्वार, उत्तराखंड 249401
    उपभोक्ता सेवा: 1800-180-4108
    ईमेल: customercare@patanjaliayurved.org
    बैच संख्या: PAT-2026-GH50
    निर्माण तिथि: 01/08/2026
    उपयोग की अंतिम तिथि: 01/08/2027
    उत्पत्ति का देश: भारत
    एफएसएसएआई लाइसेंस संख्या: 10014012000266
    """

    info = extractor.extract(hindi_text)
    assert info.net_quantity == "500 g"
    assert "350" in (info.mrp or "")
    assert info.fssai_license == "10014012000266"
    assert info.consumer_care_phone == "1800-180-4108"
    assert info.consumer_care_email == "customercare@patanjaliayurved.org"


# ============================================================================
# 5. INTEGRATION API ENDPOINTS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_api_integrations_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. FSSAI verify endpoint
        fssai_resp = await client.post("/api/integrations/fssai/verify", json={"licence_number": "10019021004567"})
        assert fssai_resp.status_code == 200
        f_data = fssai_resp.json()
        assert f_data["licence_number"] == "10019021004567"
        assert f_data["status"] in ("NOT_VERIFIED", "VERIFIED")

        # 2. GS1 verify endpoint
        gs1_resp = await client.post("/api/integrations/gs1/verify", json={"gtin": "8901030383748"})
        assert gs1_resp.status_code == 200
        g_data = gs1_resp.json()
        assert g_data["gtin"] == "8901030383748"
        assert g_data["status"] in ("NOT_VERIFIED", "VERIFIED")
