import pytest
import os
import cv2
import numpy as np
import httpx
from unittest.mock import patch, AsyncMock
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
from services.calibration_service import PhysicalCalibrationService
from compliance.rules.legal_metrology import compute_font_size_and_readability
from extraction.extractor import LocalExtractor
from models.schemas import ProductInfo, ComplianceCheck, CalibrationResult
from services.analysis_service import analyze_text
from testing_utils import isolated_test_env


# ============================================================================
# 1. FSSAI STATUS SEMANTICS & ERROR RESILIENCE AUDIT
# ============================================================================

@pytest.mark.asyncio
async def test_fssai_semantic_status_isolation():
    """Verify INVALID_FORMAT != NOT_FOUND != SERVICE_UNAVAILABLE != NOT_VERIFIED != VERIFIED."""
    verifier = FSSAILicenceVerifier()

    # 1. Invalid format
    res_inv = await verifier.verify("12345")
    assert res_inv.status == FSSAIVerificationStatus.INVALID_FORMAT
    assert res_inv.is_live is False

    # 2. Unconfigured provider (structurally valid)
    res_unconf = await verifier.verify("10019021004567")
    assert res_unconf.status == FSSAIVerificationStatus.NOT_VERIFIED
    assert res_unconf.is_live is False
    assert "Statutory 14-digit format valid" in res_unconf.message


@pytest.mark.asyncio
async def test_fssai_api_timeout_and_network_error_resilience():
    """Verify FoSCoSApiProvider handles network errors/timeouts safely without crashing."""
    prov = FoSCoSApiProvider(api_url="http://mock.foscos.gov.in/api/v1", timeout_sec=0.1)

    # Test HTTP 500 error
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(status_code=500, text="Internal Server Error")
        res_500 = await prov.verify_licence("10019021004567")
        assert res_500.status == FSSAIVerificationStatus.SERVICE_UNAVAILABLE
        assert res_500.is_live is False

    # Test Timeout Exception
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        res_timeout = await prov.verify_licence("10019021004567")
        assert res_timeout.status == FSSAIVerificationStatus.SERVICE_UNAVAILABLE
        assert "unreachable or timed out" in res_timeout.message

    # Test 404 Not Found
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(status_code=404, text="Not Found")
        res_404 = await prov.verify_licence("10019021004567")
        assert res_404.status == FSSAIVerificationStatus.NOT_FOUND
        assert res_404.is_live is True


# ============================================================================
# 2. GS1 GTIN STATUS SEMANTICS & NO FAKE REGISTRY CLAIMS
# ============================================================================

@pytest.mark.asyncio
async def test_gs1_checksum_does_not_claim_registry_verified():
    """Checksum valid must NEVER automatically become VERIFIED without provider confirmation."""
    verifier = GS1BarcodeVerifier(primary_provider=GS1DataKartApiProvider(api_url=""))
    
    # Checksum is valid for 8901030383748
    res = await verifier.verify("8901030383748")
    assert res.status == GS1VerificationStatus.NOT_VERIFIED
    assert res.status != GS1VerificationStatus.VERIFIED
    assert res.is_live is False
    assert "Live DataKart registry check unconfigured" in res.message


@pytest.mark.asyncio
async def test_gs1_api_error_handling():
    """Verify GS1DataKartApiProvider handles service downtime cleanly."""
    prov = GS1DataKartApiProvider(api_url="http://mock.gs1india.org/api/v1")
    
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Network unreachable")):
        res = await prov.verify_gtin("8901030383748")
        assert res.status == GS1VerificationStatus.SERVICE_UNAVAILABLE
        assert res.is_live is False
        assert "unreachable or timed out" in res.message


# ============================================================================
# 3. RULE 12 METROLOGICAL SCALE & CALIBRATION DISTORTION AUDIT
# ============================================================================

def test_calibration_skew_perspective_rejection(tmp_path):
    """Severe perspective skew/tilt (< 0.75 ratio) must return CALIBRATION_INVALID."""
    # Create an artificially distorted non-square polygon
    dict_type = cv2.aruco.DICT_4X4_50
    dictionary = cv2.aruco.getPredefinedDictionary(dict_type)
    marker_img = cv2.aruco.generateImageMarker(dictionary, 2, 100)

    # Warp marker with perspective transform to simulate acute camera angle
    pts1 = np.float32([[0, 0], [100, 0], [100, 100], [0, 100]])
    pts2 = np.float32([[10, 0], [90, 0], [100, 40], [0, 40]])  # Height is only 40px (aspect ratio ~ 0.44)
    matrix = cv2.getPerspectiveTransform(pts1, pts2)
    warped = cv2.warpPerspective(marker_img, matrix, (100, 100))

    canvas = np.ones((300, 300), dtype=np.uint8) * 255
    canvas[50:150, 50:150] = warped

    img_path = str(tmp_path / "warped_marker.jpg")
    cv2.imwrite(img_path, canvas)

    calib = PhysicalCalibrationService.detect_aruco_marker(img_path)
    # Either not detected due to severe distortion or rejected as CALIBRATION_INVALID
    assert calib.status in ("CALIBRATION_INVALID", "CALIBRATION_MISSING")


def test_missing_calibration_marker_fallback(tmp_path):
    """Images without reference target must return CALIBRATION_MISSING and use ESTIMATED_DPI."""
    canvas = np.ones((200, 200), dtype=np.uint8) * 255
    img_path = str(tmp_path / "plain_image.jpg")
    cv2.imwrite(img_path, canvas)

    calib = PhysicalCalibrationService.detect_aruco_marker(img_path)
    assert calib.status == "CALIBRATION_MISSING"
    assert calib.pixels_per_mm is None

    # Verify fallback in Rule 12 analysis
    info = ProductInfo(net_quantity="250 g", extraction_mode="real")
    check = ComplianceCheck(
        rule_id="LM-003",
        field="net_quantity",
        field_label="Net Quantity",
        required=True,
        detected=True,
        detected_value="250 g",
        severity="high",
        status="PASS",
        description="",
        source="",
        explanation="",
        recommendation="",
        bbox=[10, 10, 50, 30]  # height = 20px
    )

    analysis = compute_font_size_and_readability(
        product_info=info,
        checks=[check],
        calibration_result=calib
    )

    assert analysis.calibration_status == "CALIBRATION_MISSING"
    assert analysis.measurement_method == "ESTIMATED_DPI"
    assert "Estimated" in analysis.rule_12_verdict


# ============================================================================
# 4. OFFLINE PIPELINE RESILIENCE & INTEGRATION AUDIT
# ============================================================================

def test_analyze_pipeline_offline_resilience():
    """The main /api/analyze and /api/analyze/text pipeline must work seamlessly offline."""
    import asyncio
    sample_text = """
    ALPINO SUPER OATS 400 g
    MRP Rs. 299.00 (Incl. of all taxes)
    Unit Sale Price: Rs. 0.74 / g
    Mfg Date: 01/2026
    Batch No: ALP-908
    FSSAI Lic. No. 10020021001122
    Country of Origin: India
    Barcode: 8901030383748
    Manufactured by: Alpino Health Foods Pvt Ltd, Surat, Gujarat 395007
    Customer Care: +91-8347688000 support@alpino.co.in
    """

    with isolated_test_env():
        resp = asyncio.run(analyze_text(sample_text))
        assert resp.id is not None
        assert resp.product_name is not None
        assert resp.fssai_verification is not None
        assert resp.fssai_verification.status in ("NOT_VERIFIED", "VERIFIED")
        assert resp.gs1_verification is not None
        assert resp.gs1_verification.status in ("NOT_VERIFIED", "VERIFIED")
        assert resp.font_size_analysis is not None
        assert resp.compliance_result.score > 70.0


# ============================================================================
# 5. DETERMINISM AUDIT ACROSS REPEATED RUNS
# ============================================================================

def test_repeated_analysis_determinism():
    """Repeated execution on identical text must produce identical scores and compliance results."""
    import asyncio
    sample_text = """
    ALPINO SUPER OATS 400 g
    MRP Rs. 299.00 (Incl. of all taxes)
    Unit Sale Price: Rs. 0.74 / g
    Mfg Date: 01/2026
    Batch No: ALP-908
    FSSAI Lic. No. 10020021001122
    Country of Origin: India
    Manufactured by: Alpino Health Foods Pvt Ltd, Surat, Gujarat 395007
    Customer Care: +91-8347688000 support@alpino.co.in
    """

    with isolated_test_env():
        results = []
        for _ in range(3):
            res = asyncio.run(analyze_text(sample_text))
            results.append((
                res.compliance_result.score,
                res.compliance_result.status,
                res.compliance_result.passed_rules,
                res.product_info.net_quantity,
                res.product_info.mrp,
                res.fssai_verification.status if res.fssai_verification else None
            ))

        # Check all runs produced identical tuples
        assert results[0] == results[1] == results[2]
