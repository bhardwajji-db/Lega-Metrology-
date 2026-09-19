"""
MetrCheck AI — Test Suite for Intelligent Product Identity & Multi-Source Verification
Covers all 17 key scenarios specified in SIH Problem Statement 26034:
1. Standard packaged food identity extraction
2. QR Code GS1 Digital Link parsing (GTIN, lot, expiry)
3. QR safe URL parsing & SSRF prevention
4. Barcode EAN-13 checksum & GS1 country prefix
5. Barcode invalid checksum detection
6. FSSAI 14-digit format & state jurisdiction decoding
7. FSSAI invalid length/syntax validation
8. FSSAI Extracted from package vs Externally verified distinction
9. Cross-validation: OCR net quantity consistent with registry
10. Cross-validation: OCR net quantity conflict detected
11. Cross-validation: OCR FSSAI conflicts with QR code FSSAI
12. Cross-validation: OCR Country of Origin conflicts with GS1 prefix
13. Low quality image diagnostics & Review Required status
14. Non-food product handling (NOT_APPLICABLE statuses)
15. Multi-image panel aggregation
16. End-to-end analysis service & SQLite persistence
17. Backward compatibility & PDF / Excel report exports
"""

import os
import pytest
import numpy as np
import cv2
from models.schemas import ProductInfo, ProductImageEvidence, OCRWord, AnalysisResponse
from services.identity.schemas import (
    ProductIdentity,
    FieldEvidenceItem,
    FieldStatus,
    QRContentData,
    BarcodeIdentityData,
    ConflictItem
)
from services.identity.qr_decoder import qr_decoder_service, SafeURLValidator
from services.identity.fssai_extractor import fssai_extractor, FSSAI_STATE_CODES
from services.identity.cross_validator import cross_validator
from services.identity.identity_service import identity_service
from services.barcode_service import barcode_service, validate_ean13_checksum, resolve_gs1_country
from services.analysis_service import analyze_text
from database.db import get_analysis, save_analysis
from services.report_service import generate_pdf_report


# =============================================================================
# SCENARIO 1: Standard Packaged Food Identity Extraction
# =============================================================================
def test_01_standard_packaged_food_identity():
    ocr_text = """
    Kissan Fresh Tomato Ketchup
    Net Quantity: 950 g
    MRP: Rs. 145.00 (Incl. of all taxes)
    Batch No: B10293
    Mfg Date: 15/01/2026
    Best Before: 12 months from manufacture
    FSSAI Lic. No. 10013022001897
    Country of Origin: India
    Manufactured by: Hindustan Unilever Limited
    Address: B.D. Sawant Marg, Chakala, Andheri (E), Mumbai 400099
    Ingredients: Tomato paste, Water, Sugar, Salt, Spices
    Customer Care: 1800-10-22-221, feedback@hul.com
    """

    info = ProductInfo(
        product_name="Fresh Tomato Ketchup",
        brand="Kissan",
        category="Sauces & Condiments",
        is_food=True,
        net_quantity="950 g",
        mrp="145.00",
        batch_number="B10293",
        manufacturing_date="15/01/2026",
        best_before="12 months",
        fssai_license="10013022001897",
        country_of_origin="India",
        manufacturer_name="Hindustan Unilever Limited",
        manufacturer_address="Mumbai 400099",
        ingredients="Tomato paste, Water, Sugar, Salt, Spices",
        consumer_care_phone="1800-10-22-221",
        consumer_care_email="feedback@hul.com"
    )

    identity = identity_service.extract_identity(
        product_info=info,
        ocr_text=ocr_text
    )

    assert isinstance(identity, ProductIdentity)
    assert identity.product_name.value == "Fresh Tomato Ketchup"
    assert identity.brand_name.value == "Kissan"
    assert identity.net_quantity.value == "950 g"
    assert identity.fssai_license_number.value == "10013022001897"
    assert identity.fssai_license_number.status in (FieldStatus.FOUND, FieldStatus.VERIFIED)
    assert identity.fssai_state_name == "Central Licensing Authority"
    assert identity.food_declarations.is_food is True
    assert len(identity.food_declarations.ingredients) >= 4


# =============================================================================
# SCENARIO 2: QR Code GS1 Digital Link Parsing (GTIN, lot, expiry)
# =============================================================================
def test_02_qr_code_gs1_digital_link_extraction():
    digital_link_url = "https://id.gs1.org/01/08901030383748/10/BATCH2026/17/261231"
    content_type, ai_data = qr_decoder_service.classify_content(digital_link_url)

    assert content_type == "GS1_DIGITAL_LINK"
    assert ai_data is not None
    assert ai_data.get("gtin") == "08901030383748"
    assert ai_data.get("lot") == "BATCH2026"
    assert ai_data.get("expiry") == "261231"


# =============================================================================
# SCENARIO 3: QR Safe URL Parsing & SSRF Prevention
# =============================================================================
def test_03_qr_url_safe_parsing_and_ssrf_blocking():
    # Public trusted domains
    safe_urls = [
        "https://fssai.gov.in/verify?lic=10013022001897",
        "https://www.hul.co.in/kissan-ketchup",
        "http://brands.gs1india.org/products/8901030383748"
    ]
    for u in safe_urls:
        is_safe, parsed, host, warn = SafeURLValidator.validate_url(u)
        assert is_safe is True, f"Expected {u} to be safe, got warning: {warn}"
        assert warn is None

    # SSRF / internal / loopback attacks that must be blocked
    malicious_urls = [
        "http://127.0.0.1:8000/admin/secrets",
        "http://localhost:5000/config",
        "http://10.0.0.1/internal/metadata",
        "http://192.168.1.1/router",
        "http://172.16.0.5/api",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "javascript:alert(1)"
    ]
    for bad in malicious_urls:
        is_safe, _, _, warn = SafeURLValidator.validate_url(bad)
        assert is_safe is False, f"Expected {bad} to be flagged as unsafe"
        assert warn is not None


# =============================================================================
# SCENARIO 4: Barcode EAN-13 Checksum & GS1 Country Prefix
# =============================================================================
def test_04_barcode_ean13_valid_checksum_and_gs1_country():
    gtin_india = "8901030383748"
    assert validate_ean13_checksum(gtin_india) is True

    country, flag = resolve_gs1_country(gtin_india)
    assert country == "India"
    assert flag == "🇮🇳"

    gtin_france = "3017620422003"  # Nutella France
    assert validate_ean13_checksum(gtin_france) is True
    country_fr, flag_fr = resolve_gs1_country(gtin_france)
    assert country_fr == "France"
    assert flag_fr == "🇫🇷"


# =============================================================================
# SCENARIO 5: Barcode Invalid Checksum Detection
# =============================================================================
def test_05_barcode_invalid_checksum_flagged():
    bad_gtin = "8901030383749"  # Check digit 9 is invalid for this code (valid is 8)
    assert validate_ean13_checksum(bad_gtin) is False

    from services.barcode_service import BarcodeItem
    fake_item = BarcodeItem(
        raw_value=bad_gtin,
        symbology="EAN-13",
        is_valid_checksum=False,
        confidence=95.0
    )

    ident = identity_service.extract_identity(
        product_info=ProductInfo(),
        barcode_items=[fake_item]
    )

    assert len(ident.barcodes) == 1
    assert ident.barcodes[0].is_valid_checksum is False
    assert ident.barcodes[0].status == FieldStatus.REVIEW_REQUIRED


# =============================================================================
# SCENARIO 6: FSSAI 14-Digit Format & State Jurisdiction Decoding
# =============================================================================
def test_06_fssai_valid_format_and_state_decoding():
    # Central License (starts with 1, state code 00)
    is_v, st_name, l_type = fssai_extractor.validate_structure("10013022001897")
    assert is_v is True
    assert st_name == "Central Licensing Authority"
    assert l_type == "CENTRAL_LICENSE"

    # Maharashtra (state code 27)
    is_v, st_name, l_type = fssai_extractor.validate_structure("12721011000123")
    assert is_v is True
    assert st_name == "Maharashtra"
    assert l_type == "STATE_OR_CENTRAL_LICENSE"

    # Delhi (state code 07)
    is_v, st_name, l_type = fssai_extractor.validate_structure("10718001000456")
    assert is_v is True
    assert st_name == "Delhi"

    # Basic Registration (starts with 2)
    is_v, st_name, l_type = fssai_extractor.validate_structure("22419001000789")
    assert is_v is True
    assert st_name == "Gujarat"
    assert l_type == "BASIC_REGISTRATION"


# =============================================================================
# SCENARIO 7: FSSAI Invalid Length or Syntax Validation
# =============================================================================
def test_07_fssai_invalid_format_or_missing_digits():
    # 13 digits (missing one)
    is_v, _, _ = fssai_extractor.validate_structure("1001302200189")
    assert is_v is False

    # Non-numeric
    is_v, _, _ = fssai_extractor.validate_structure("1001302200189X")
    assert is_v is False

    # Text declaring FSSAI without a readable 14-digit number
    unreadable_fssai_text = "FSSAI Lic. No: [SMUDGED INK UNREADABLE]"
    item, _, _ = fssai_extractor.extract_fssai(unreadable_fssai_text)
    assert item.status == FieldStatus.REVIEW_REQUIRED


# =============================================================================
# SCENARIO 8: FSSAI Extracted from Package vs Externally Verified Distinction
# =============================================================================
def test_08_fssai_package_extraction_vs_external_verification():
    ocr_text = "FSSAI Lic. No. 10013022001897"
    
    # 1. Extracted only (no external API verification called yet)
    ident_extracted = identity_service.extract_identity(
        product_info=ProductInfo(fssai_license="10013022001897"),
        ocr_text=ocr_text,
        fssai_verification=None
    )
    assert ident_extracted.fssai_license_number.value == "10013022001897"
    assert ident_extracted.fssai_external_verified is False
    assert ident_extracted.fssai_license_number.status == FieldStatus.FOUND

    # 2. Externally verified against registry
    from integrations.fssai.schemas import FSSAIVerificationRecord
    verified_record = FSSAIVerificationRecord(
        licence_number="10013022001897",
        status="VERIFIED",
        business_name="Hindustan Unilever Ltd",
        licence_type="Central License",
        message="Active in FoSCoS database",
        is_live=True
    )
    ident_verified = identity_service.extract_identity(
        product_info=ProductInfo(fssai_license="10013022001897"),
        ocr_text=ocr_text,
        fssai_verification=verified_record
    )
    assert ident_verified.fssai_license_number.value == "10013022001897"
    assert ident_verified.fssai_external_verified is True
    assert ident_verified.fssai_license_number.status == FieldStatus.VERIFIED


# =============================================================================
# SCENARIO 9: Cross-Validation: OCR Net Quantity Consistent with Registry
# =============================================================================
def test_09_cross_validation_net_quantity_consistent_with_master():
    # 8901030383748 has registered master net quantity "950 g"
    from services.barcode_service import BarcodeItem
    bc = BarcodeItem(raw_value="8901030383748", symbology="EAN-13")

    ident = identity_service.extract_identity(
        product_info=ProductInfo(
            net_quantity="950 g",
            brand="Kissan",
            barcode_detected="8901030383748"
        ),
        barcode_items=[bc]
    )

    summary = ident.cross_validation
    assert summary.status == "PASS"
    assert summary.has_conflicts is False
    assert len(summary.conflicts) == 0


# =============================================================================
# SCENARIO 10: Cross-Validation: OCR Net Quantity Conflict Detected
# =============================================================================
def test_10_cross_validation_net_quantity_conflict_detected():
    # OCR says 500 g, but barcode 8901030383748 master registry is 950 g
    from services.barcode_service import BarcodeItem
    bc = BarcodeItem(raw_value="8901030383748", symbology="EAN-13")

    ident = identity_service.extract_identity(
        product_info=ProductInfo(
            net_quantity="500 g",
            brand="Kissan",
            barcode_detected="8901030383748"
        ),
        barcode_items=[bc]
    )

    summary = ident.cross_validation
    assert summary.status == "CONFLICT_DETECTED"
    assert summary.has_conflicts is True
    net_conflict = next((c for c in summary.conflicts if c.field_name == "Net Quantity"), None)
    assert net_conflict is not None
    assert net_conflict.severity == "HIGH"
    assert "500 g" in net_conflict.value_a
    assert "950 g" in net_conflict.value_b


# =============================================================================
# SCENARIO 11: Cross-Validation: OCR FSSAI Conflicts with QR Code FSSAI
# =============================================================================
def test_11_cross_validation_fssai_ocr_vs_qr_conflict():
    # OCR claims 10013022001897, but QR code claims 10019999999999
    from services.barcode_service import BarcodeItem
    qr_item = BarcodeItem(
        raw_value="https://fssai.gov.in/lic/10019999999999",
        symbology="QR_CODE"
    )

    ident = identity_service.extract_identity(
        product_info=ProductInfo(fssai_license="10013022001897"),
        ocr_text="FSSAI Lic No. 10013022001897",
        barcode_items=[qr_item]
    )

    summary = ident.cross_validation
    assert summary.status == "CONFLICT_DETECTED"
    fssai_conflict = next((c for c in summary.conflicts if c.field_name == "FSSAI License Number"), None)
    assert fssai_conflict is not None
    assert fssai_conflict.severity == "HIGH"
    assert fssai_conflict.value_a == "10013022001897"
    assert fssai_conflict.value_b == "10019999999999"
    assert ident.fssai_license_number.status == FieldStatus.REVIEW_REQUIRED


# =============================================================================
# SCENARIO 12: Cross-Validation: OCR Country of Origin Conflicts with GS1 Prefix
# =============================================================================
def test_12_cross_validation_country_of_origin_vs_gs1_prefix_conflict():
    # Label claims Country of Origin: Germany, but Barcode prefix 890 is India
    from services.barcode_service import BarcodeItem
    bc = BarcodeItem(raw_value="8901030383748", symbology="EAN-13")

    ident = identity_service.extract_identity(
        product_info=ProductInfo(
            country_of_origin="Germany",
            barcode_detected="8901030383748"
        ),
        barcode_items=[bc]
    )

    summary = ident.cross_validation
    coo_conflict = next((c for c in summary.conflicts if c.field_name == "Country of Origin"), None)
    assert coo_conflict is not None
    assert coo_conflict.severity == "MEDIUM"
    assert "Germany" in coo_conflict.value_a
    assert "India" in coo_conflict.value_b


# =============================================================================
# SCENARIO 13: Low Quality Image Diagnostics & Review Required Status
# =============================================================================
def test_13_low_quality_image_quality_gate():
    low_res_evidence = ProductImageEvidence(
        filename="blurry_low_res.jpg",
        image_url="/uploads/blurry_low_res.jpg",
        label="Front",
        ocr_text="Some faint text",
        image_quality={
            "is_good": False,
            "resolution": "240x240",
            "blur_score": 35.0,
            "issues": ["Low resolution (under 300px min dimension)", "Camera blur detected"]
        }
    )

    ident = identity_service.extract_identity(
        product_info=ProductInfo(),
        images=[low_res_evidence]
    )

    assert ident.image_quality_status == "REVIEW_REQUIRED"
    assert len(ident.quality_reasons) > 0
    assert any("blur" in r.lower() or "resolution" in r.lower() for r in ident.quality_reasons)


# =============================================================================
# SCENARIO 14: Non-Food Product Handling (NOT_APPLICABLE Statuses)
# =============================================================================
def test_14_non_food_product_handling():
    non_food_info = ProductInfo(
        product_name="UltraClean Detergent Bar",
        brand="SuperWash",
        category="Household Cleaning / Detergents",
        is_food=False,
        net_quantity="200 g",
        mrp="35.00"
    )

    ident = identity_service.extract_identity(
        product_info=non_food_info,
        ocr_text="UltraClean Detergent Bar Net Wt 200g MRP 35.00"
    )

    assert ident.food_declarations.is_food is False
    assert ident.food_declarations.ingredients_evidence.status == FieldStatus.NOT_APPLICABLE
    assert ident.food_declarations.nutrition_evidence.status == FieldStatus.NOT_APPLICABLE
    assert ident.fssai_license_number.status == FieldStatus.NOT_APPLICABLE


# =============================================================================
# SCENARIO 15: Multi-Image Panel Aggregation
# =============================================================================
def test_15_multi_image_panel_aggregation():
    front_img = ProductImageEvidence(
        filename="ketchup_front.jpg",
        image_url="/uploads/ketchup_front.jpg",
        label="Front",
        ocr_text="Kissan Fresh Tomato Ketchup Net Quantity: 950 g",
        words=[
            OCRWord(text="Kissan", confidence=96.0, bbox=[100, 100, 300, 150]),
            OCRWord(text="950 g", confidence=94.0, bbox=[200, 500, 400, 550])
        ]
    )
    back_img = ProductImageEvidence(
        filename="ketchup_back.jpg",
        image_url="/uploads/ketchup_back.jpg",
        label="Back",
        ocr_text="FSSAI Lic. No. 10013022001897 Manufactured by Hindustan Unilever",
        words=[
            OCRWord(text="10013022001897", confidence=95.0, bbox=[50, 200, 400, 250]),
            OCRWord(text="Hindustan Unilever", confidence=92.0, bbox=[50, 400, 500, 450])
        ]
    )

    info = ProductInfo(
        product_name="Fresh Tomato Ketchup",
        brand="Kissan",
        net_quantity="950 g",
        fssai_license="10013022001897",
        manufacturer_name="Hindustan Unilever"
    )

    ident = identity_service.extract_identity(
        product_info=info,
        ocr_text=f"{front_img.ocr_text}\n{back_img.ocr_text}",
        images=[front_img, back_img]
    )

    # Front field provenance
    assert ident.product_name.value == "Fresh Tomato Ketchup"
    assert ident.net_quantity.value == "950 g"
    assert ident.net_quantity.bounding_box == [200, 500, 400, 550]
    assert ident.net_quantity.image_id == "Front"

    # Back field provenance
    assert ident.fssai_license_number.value == "10013022001897"
    assert ident.fssai_license_number.bounding_box == [50, 200, 400, 250]
    assert ident.fssai_license_number.image_id == "Back"


# =============================================================================
# SCENARIO 16: End-to-End Analysis Service & SQLite Persistence
# =============================================================================
@pytest.mark.asyncio
async def test_16_analysis_service_e2e_integration():
    sample_text = """
    Alpino High Protein Super Oats
    Net Weight: 400 g
    MRP: Rs. 199
    FSSAI Lic No: 10716022000249
    Country of Origin: India
    """

    res = await analyze_text(sample_text)

    # 1. Verify AnalysisResponse contains product_identity
    assert isinstance(res, AnalysisResponse)
    assert res.product_identity is not None
    assert res.product_identity.product_name.value is not None
    assert "400" in (res.product_identity.net_quantity.normalized_value or res.product_identity.net_quantity.value or "")
    assert res.product_identity.fssai_license_number.value == "10716022000249"
    assert res.cross_validation is not None

    # 2. Verify SQLite DB row stores serialized product_identity
    db_row = await get_analysis(res.id)
    assert db_row is not None
    assert 'product_identity' in db_row
    assert "10716022000249" in db_row['product_identity']


# =============================================================================
# SCENARIO 17: Backward Compatibility & Report Generation
# =============================================================================
@pytest.mark.asyncio
async def test_17_backward_compatibility_and_report_generation():
    sample_text = "Kissan Tomato Ketchup Net Quantity: 950 g MRP: 145 FSSAI: 10013022001897"
    res = await analyze_text(sample_text)

    # Ensure all original legacy API fields are intact
    assert res.id is not None
    assert res.product_name is not None
    assert res.compliance_result is not None
    assert res.ocr_result is not None
    assert isinstance(res.recommendations, list)

    # Ensure ReportLab PDF generation executes cleanly with product_identity
    pdf_bytes = generate_pdf_report(res, lang="en")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
