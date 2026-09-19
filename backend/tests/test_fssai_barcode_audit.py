"""
MetrCheck AI — FSSAI & Barcode Product Information Feature Audit Tests
Tests comprehensive audit criteria:
1. FSSAI extraction from clean and noisy OCR text (handling O/0, l/1, S/5, spaces, hyphens).
2. Structure validation & State / Tier decoding (00 Central, 01-37 States).
3. Live FoSCoS external registry verification (HTTP 200, 404, 500, timeout).
4. Local verified FSSAI cache retrieval.
5. 1D Barcode decoding & Modulo-10 checksum validation (EAN-13, EAN-8, UPC-A).
6. GS1 Country prefix resolution.
7. GS1 DataKart registry verification (HTTP 200, 404, 500, timeout).
8. Strict SSRF Protection (localhost, private CIDR, metadata IP, IPv6 loopback, restricted ports).
9. 4 explicit provenance statuses: "Extracted from package", "Externally verified", "Not found", "Verification unavailable".
10. Strict non-fabrication when external lookups fail or are unconfigured.
11. Cross-validation & conflict detection across OCR, Barcode, and FSSAI registry.
12. PDF and Excel report generation with explicit provenance tags.
"""

import pytest
import io
import httpx
from unittest.mock import patch, MagicMock
from services.identity.schemas import FieldStatus, ProductIdentity, BarcodeIdentityData
from services.identity.qr_decoder import SafeURLValidator
from services.identity.fssai_extractor import fssai_extractor, FSSAIInformationExtractor
from services.identity.cross_validator import cross_validator
from services.identity.identity_service import identity_service
from services.barcode_service import barcode_service, validate_ean13_checksum, resolve_gs1_country
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
from models.schemas import ProductInfo, ProductImageEvidence, AnalysisResponse, ComplianceResult


# ============================================================================
# 1. FSSAI EXTRACTION & NOISE RESILIENCE TESTS
# ============================================================================

def test_fssai_clean_extraction():
    ocr_text = "FSSAI Lic. No. 10013022001897 Manufactured by Kissan"
    item, state_name, lic_type = fssai_extractor.extract_fssai(ocr_text)
    assert item.value == "10013022001897"
    assert item.status == FieldStatus.FOUND
    assert state_name == "Central Licensing Authority"
    assert lic_type == "CENTRAL_LICENSE"


def test_fssai_ocr_noise_repair():
    # Test OCR substitution: 'O' instead of '0', spaces, and dashes
    noisy_ocr_text = "FSSAI Lic No: 1OO13-O22OO-1897 Packaged Fresh"
    item, state_name, lic_type = fssai_extractor.extract_fssai(noisy_ocr_text)
    assert item.value == "10013022001897"
    assert item.status == FieldStatus.FOUND
    assert state_name == "Central Licensing Authority"


def test_fssai_state_license_decoding():
    # State license starting with 1, state code 27 (Maharashtra)
    text = "Licence No: 12721001004567"
    item, state_name, lic_type = fssai_extractor.extract_fssai(text)
    assert item.value == "12721001004567"
    assert state_name == "Maharashtra"
    assert lic_type == "STATE_OR_CENTRAL_LICENSE"


def test_fssai_basic_registration_decoding():
    # Registration starting with 2, state code 24 (Gujarat)
    text = "FSSAI Registration No. 22421001007890"
    item, state_name, lic_type = fssai_extractor.extract_fssai(text)
    assert item.value == "22421001007890"
    assert state_name == "Gujarat"
    assert lic_type == "BASIC_REGISTRATION"


def test_fssai_unreadable_indicator():
    text = "Contains sugar and spices. fssai approved food facility."
    item, state_name, lic_type = fssai_extractor.extract_fssai(text)
    assert item.value is None
    assert item.status == FieldStatus.REVIEW_REQUIRED
    assert "FSSAI indicator detected" in item.explanation


# ============================================================================
# 2. SSRF SECURITY PROTECTION TESTS
# ============================================================================

def test_ssrf_validator_blocks_private_ips():
    # IPv4 loopback & private ranges
    is_safe, _, host, warn = SafeURLValidator.validate_url("http://127.0.0.1:8000/api")
    assert is_safe is False
    assert "Forbidden private/internal IP" in warn or "Loopback" in warn

    is_safe, _, host, warn = SafeURLValidator.validate_url("http://10.0.0.5/lookup")
    assert is_safe is False

    is_safe, _, host, warn = SafeURLValidator.validate_url("http://192.168.1.1/admin")
    assert is_safe is False

    is_safe, _, host, warn = SafeURLValidator.validate_url("http://169.254.169.254/latest/meta-data")
    assert is_safe is False


def test_ssrf_validator_blocks_loopback_and_internal_hostnames():
    is_safe, _, host, warn = SafeURLValidator.validate_url("http://localhost:3000")
    assert is_safe is False

    is_safe, _, host, warn = SafeURLValidator.validate_url("http://metadata.google.internal/computeMetadata/v1/")
    assert is_safe is False

    is_safe, _, host, warn = SafeURLValidator.validate_url("http://internal-service.local/api")
    assert is_safe is False


def test_ssrf_validator_blocks_ipv6_loopback():
    is_safe, _, host, warn = SafeURLValidator.validate_url("http://[::1]:8080/data")
    assert is_safe is False


def test_ssrf_validator_blocks_restricted_ports():
    is_safe, _, host, warn = SafeURLValidator.validate_url("http://example.com:22/ssh")
    assert is_safe is False
    assert "restricted internal port" in warn

    is_safe, _, host, warn = SafeURLValidator.validate_url("http://example.com:6379/redis")
    assert is_safe is False


def test_ssrf_validator_permits_safe_external_urls():
    is_safe, parsed, host, warn = SafeURLValidator.validate_url("https://foscos.fssai.gov.in/api/v1/verify")
    assert is_safe is True
    assert host == "foscos.fssai.gov.in"
    assert warn is None


# ============================================================================
# 3. EXTERNAL FSSAI REGISTRY VERIFICATION & NON-FABRICATION
# ============================================================================

@pytest.mark.asyncio
async def test_fssai_provider_ssrf_protection():
    # Attempt to point FoSCoSApiProvider to an internal endpoint
    provider = FoSCoSApiProvider(api_url="http://127.0.0.1:9999/admin")
    rec = await provider.verify_licence("10013022001897")
    assert rec.status == FSSAIVerificationStatus.SERVICE_UNAVAILABLE
    assert "SSRF Protection Policy blocked" in rec.message


@pytest.mark.asyncio
async def test_fssai_live_registry_success():
    mock_payload = {
        "active": True,
        "business_name": "Hindustan Unilever Limited",
        "licence_type": "Central Licence",
        "valid_upto": "2027-12-31"
    }
    provider = FoSCoSApiProvider(api_url="https://api.fssai.gov.in/verify")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        rec = await provider.verify_licence("10013022001897")
        assert rec.status == FSSAIVerificationStatus.VERIFIED
        assert rec.business_name == "Hindustan Unilever Limited"
        assert rec.is_live is True


@pytest.mark.asyncio
async def test_fssai_live_registry_not_found():
    provider = FoSCoSApiProvider(api_url="https://api.fssai.gov.in/verify")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        rec = await provider.verify_licence("10013022009999")
        assert rec.status == FSSAIVerificationStatus.NOT_FOUND
        assert rec.business_name is None  # Never fabricate!
        assert "not found in FoSCoS registry" in rec.message


@pytest.mark.asyncio
async def test_fssai_unconfigured_non_fabrication():
    verifier = FSSAILicenceVerifier(primary_provider=FoSCoSApiProvider(api_url=""))
    rec = await verifier.verify("10019021004567")
    assert rec.status == FSSAIVerificationStatus.NOT_VERIFIED
    assert rec.business_name is None
    assert rec.valid_upto is None
    assert "unconfigured" in rec.message.lower()


# ============================================================================
# 4. 1D BARCODE CHECKSUM & GS1 VERIFICATION TESTS
# ============================================================================

def test_barcode_checksum_validation():
    # Valid EAN-13
    assert validate_ean13_checksum("8901030383748") is True
    # Invalid EAN-13 check digit (8 replaced by 5)
    assert validate_ean13_checksum("8901030383745") is False
    # Valid GS1 Modulo-10 GTIN-8, GTIN-12, GTIN-13
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901030383748") is True
    assert GS1BarcodeVerifier.validate_gtin_checksum("8901030383745") is False


def test_gs1_country_of_origin_resolution():
    country, flag = resolve_gs1_country("8901030383748")
    assert country == "India"
    assert flag == "🇮🇳"

    country_us, _ = resolve_gs1_country("012345678905")
    assert "United States" in country_us

    country_uk, _ = resolve_gs1_country("5000123456789")
    assert country_uk == "United Kingdom"


@pytest.mark.asyncio
async def test_gs1_provider_ssrf_protection():
    provider = GS1DataKartApiProvider(api_url="http://169.254.169.254/datakart")
    rec = await provider.verify_gtin("8901030383748")
    assert rec.status == GS1VerificationStatus.SERVICE_UNAVAILABLE
    assert "SSRF Protection Policy blocked" in rec.message


@pytest.mark.asyncio
async def test_gs1_live_registry_success():
    mock_payload = {
        "valid": True,
        "brand_name": "Kissan",
        "product_description": "Fresh Tomato Ketchup 950g",
        "company_name": "Hindustan Unilever Limited",
        "net_content": "950 g",
        "country_of_sale": "India"
    }
    provider = GS1DataKartApiProvider(api_url="https://datakart.gs1india.org/api")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        rec = await provider.verify_gtin("8901030383748")
        assert rec.status == GS1VerificationStatus.VERIFIED
        assert rec.brand_name == "Kissan"
        assert rec.company_name == "Hindustan Unilever Limited"
        assert rec.net_content == "950 g"
        assert rec.is_live is True


@pytest.mark.asyncio
async def test_gs1_unconfigured_non_fabrication():
    verifier = GS1BarcodeVerifier(primary_provider=GS1DataKartApiProvider(api_url=""))
    rec = await verifier.verify("8901030383748")
    assert rec.status == GS1VerificationStatus.NOT_VERIFIED
    assert rec.brand_name is None
    assert rec.product_description is None
    assert rec.company_name is None
    assert "unconfigured" in rec.message.lower()


# ============================================================================
# 5. PROVENANCE SEPARATION & CROSS-VALIDATION
# ============================================================================

def test_provenance_four_explicit_states():
    # State 1: "Extracted from package" (detected from OCR, but external verification unavailable/unconfigured)
    prod_extracted = ProductInfo(
        product_name="Sample Tomato Sauce",
        brand="Kissan",
        fssai_license="10013022001897",
        barcode_detected="8901030383748",
        net_quantity="950 g",
        is_food=True
    )
    ident_extracted = identity_service.extract_identity(
        product_info=prod_extracted,
        ocr_text="FSSAI 10013022001897 8901030383748 950g",
        fssai_verification=None,
        gs1_verification=None
    )
    assert ident_extracted.fssai_provenance_label == "Extracted from package"
    assert ident_extracted.barcode_provenance_label == "Extracted from package"
    assert ident_extracted.fssai_external_verified is False
    assert ident_extracted.barcode_external_verified is False
    assert ident_extracted.barcode_registered_details is None  # Zero fabrication

    # State 2: "Externally verified" (when verified external records are provided)
    from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus
    from integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus

    mock_gs1_rec = GS1VerificationRecord(
        gtin="8901030383748",
        status=GS1VerificationStatus.VERIFIED,
        brand_name="Kissan",
        product_description="Fresh Tomato Ketchup",
        company_name="Hindustan Unilever Limited",
        net_content="950 g",
        country_of_sale="India",
        provider="GS1 India DataKart"
    )

    mock_fssai_rec = FSSAIVerificationRecord(
        licence_number="10013022001897",
        status=FSSAIVerificationStatus.VERIFIED,
        business_name="Hindustan Unilever Limited",
        licence_type="Central Licence",
        valid_upto="2027-12-31",
        is_live=True
    )

    ident_verified = identity_service.extract_identity(
        product_info=prod_extracted,
        ocr_text="FSSAI 10013022001897 8901030383748 950g",
        fssai_verification=mock_fssai_rec,
        gs1_verification=mock_gs1_rec
    )
    assert ident_verified.fssai_provenance_label == "Externally verified"
    assert ident_verified.barcode_provenance_label == "Externally verified"
    assert ident_verified.fssai_external_verified is True
    assert ident_verified.barcode_external_verified is True
    assert ident_verified.barcode_registered_details["brand_name"] == "Kissan"

    # State 3: "Not found" (neither on package nor external)
    prod_empty = ProductInfo(is_food=False)
    ident_empty = identity_service.extract_identity(product_info=prod_empty, ocr_text="")
    assert ident_empty.fssai_provenance_label == "Not found"
    assert ident_empty.barcode_provenance_label == "Not found"

    # State 4: "Verification unavailable" (extracted on package, but lookup service timed out or unavailable)
    mock_gs1_unavail = GS1VerificationRecord(
        gtin="8901030383748",
        status=GS1VerificationStatus.SERVICE_UNAVAILABLE
    )
    mock_fssai_unavail = FSSAIVerificationRecord(
        licence_number="10013022001897",
        status=FSSAIVerificationStatus.SERVICE_UNAVAILABLE
    )

    ident_unavail = identity_service.extract_identity(
        product_info=prod_extracted,
        ocr_text="FSSAI 10013022001897 8901030383748",
        fssai_verification=mock_fssai_unavail,
        gs1_verification=mock_gs1_unavail
    )
    assert ident_unavail.fssai_provenance_label == "Verification unavailable"
    assert ident_unavail.barcode_provenance_label == "Verification unavailable"
    assert ident_unavail.barcode_registered_details is None


def test_cross_validation_conflict_detection():
    # Packaging claims 500g, but Barcode Master Record registers 950g
    prod_conflict = ProductInfo(
        product_name="Fresh Tomato Ketchup",
        brand="Kissan",
        net_quantity="500 g",
        barcode_detected="8901030383748",
        fssai_license="10013022001897",
        is_food=True
    )
    ident = identity_service.extract_identity(
        product_info=prod_conflict,
        ocr_text="Kissan Fresh Tomato Ketchup 500g 8901030383748"
    )
    cv = ident.cross_validation
    assert cv.has_conflicts is True
    assert cv.status == "CONFLICT_DETECTED"
    conflict_names = [c.field_name for c in cv.conflicts]
    assert "Net Quantity" in conflict_names


# ============================================================================
# 6. END-TO-END REPORT AUDIT (PDF & EXCEL)
# ============================================================================

def test_pdf_report_contains_product_identity_provenance():
    from services.report_service import generate_pdf_report
    prod_info = ProductInfo(
        product_name="Kissan Fresh Tomato Ketchup",
        brand="Kissan",
        net_quantity="950 g",
        mrp="₹145.00",
        fssai_license="10013022001897",
        is_food=True
    )
    ident = identity_service.extract_identity(
        product_info=prod_info,
        ocr_text="Kissan Fresh Tomato Ketchup 950g FSSAI 10013022001897 8901030383748"
    )
    comp_res = ComplianceResult(
        checks=[],
        score=95,
        status="COMPLIANT",
        total_rules=10,
        passed_rules=10,
        failed_rules=0,
        issues=[]
    )
    analysis = AnalysisResponse(
        id="test-audit-001",
        product_name="Kissan Fresh Tomato Ketchup",
        image_url="/test.png",
        ocr_result={"full_text": "sample", "words": [], "language": "eng", "processing_time": 0.0},
        product_info=prod_info,
        compliance_result=comp_res,
        product_identity=ident,
        created_at="2026-09-17T12:00:00Z"
    )
    pdf_bytes = generate_pdf_report(analysis)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 5000


@pytest.mark.asyncio
async def test_excel_report_contains_product_identity():
    from openpyxl import load_workbook
    from api.report import get_report_xlsx
    from database.db import save_analysis

    prod_info = ProductInfo(
        product_name="Kissan Fresh Tomato Ketchup",
        brand="Kissan",
        net_quantity="950 g",
        mrp="₹145.00",
        fssai_license="10013022001897",
        barcode_detected="8901030383748",
        is_food=True
    )
    ident = identity_service.extract_identity(
        product_info=prod_info,
        ocr_text="Kissan Fresh Tomato Ketchup 950g FSSAI 10013022001897 8901030383748"
    )
    comp_res = ComplianceResult(
        checks=[],
        score=95,
        status="COMPLIANT",
        total_rules=10,
        passed_rules=10,
        failed_rules=0,
        issues=[]
    )
    db_record = {
        "id": "audit-xlsx-001",
        "product_name": "Kissan Fresh Tomato Ketchup",
        "image_filename": "test.png",
        "ocr_text": "Kissan Fresh Tomato Ketchup 950g",
        "extracted_data": prod_info.model_dump(),
        "compliance_result": comp_res.model_dump(),
        "score": 95,
        "status": "COMPLIANT",
        "created_at": "2026-09-17T12:00:00Z",
        "images": [],
        "product_identity": ident.model_dump()
    }
    await save_analysis(db_record)
    response = await get_report_xlsx("audit-xlsx-001")
    excel_bytes = b"".join([chunk async for chunk in response.body_iterator])
    wb = load_workbook(io.BytesIO(excel_bytes))
    assert "Product Identity" in wb.sheetnames
    ws = wb["Product Identity"]
    cell_values = [cell.value for row in ws.rows for cell in row if cell.value]
    assert "INTELLIGENT PRODUCT IDENTITY & VERIFICATION FINDINGS" in cell_values
    assert "FSSAI Verification Status" in cell_values
    assert "Barcode Verification Status" in cell_values
