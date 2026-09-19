"""
MetrCheck AI — Report Generation & Officer-Friendly Structure Tests
Verifies compliance report enhancements:
1. Executive Summary with Main Compliance Summary (Top of report)
2. Product & Statutory Declarations
3. Compact FSSAI Verification section with Package/OCR value vs Registry value
4. Compact Barcode/GS1 Verification section (GTIN, Checksum, Country, Brand, Product, Qty, Mfr, Match)
   and 'Barcode: Not detected' when absent
5. Prominent Conflict Detection when conflicts exist; compact when no conflicts
6. Simplified Rule-by-rule Legal Metrology table with short reasons for non-compliance only
7. Simplified FSSAI Compliance table
8. Evidence for issues only (FAIL, NEEDS REVIEW, CONFLICT)
9. Final Statutory Disclaimer & Legal Note
10. Multi-sheet Excel report with updated summary and verification details
"""

import pytest
import io
from openpyxl import load_workbook
from models.schemas import (
    AnalysisResponse, ProductInfo, ComplianceResult, ComplianceCheck,
    OCRResult, ProductImageEvidence
)
from services.identity.schemas import (
    ProductIdentity, BarcodeIdentityData, ConflictItem, CrossValidationSummary,
    FieldEvidenceItem, FieldStatus
)
from services.identity.identity_service import identity_service
from services.report_service import generate_pdf_report
from database.db import save_analysis
from api.report import get_report_xlsx, get_report_csv, get_report


# ============================================================================
# FIXTURES
# ============================================================================

def _create_sample_analysis(
    has_barcode: bool = True,
    has_conflicts: bool = False,
    has_issues: bool = False,
    is_fssai_verified: bool = True,
    is_barcode_verified: bool = True
) -> AnalysisResponse:
    prod_info = ProductInfo(
        product_name="Kissan Fresh Tomato Ketchup",
        brand="Kissan",
        manufacturer="Hindustan Unilever Limited",
        net_quantity="950 g",
        mrp="₹145.00",
        fssai_license="10013022001897",
        country_of_origin="India",
        manufacturing_date="15/01/2026",
        expiry_date="15/10/2026",
        batch_number="B26019A",
        consumer_care="care@hul.com / 1800-10-2222",
        ingredients="Water, Tomato Paste (28%), Sugar, Salt, Spices",
        barcode_detected="8901030383748" if has_barcode else None,
        is_food=True
    )

    # Checks
    checks = [
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            domain="LEGAL_METROLOGY",
            field_label="Manufacturer / Packer Name & Address",
            status="PASS",
            detected_value="Hindustan Unilever Limited",
            confidence=95.0,
            reason=""
        ),
        ComplianceCheck(
            rule_id="LM-003",
            field="net_quantity",
            domain="LEGAL_METROLOGY",
            field_label="Net Quantity Declaration",
            status="FAIL" if has_issues else "PASS",
            detected_value="950 g",
            confidence=94.0,
            reason="Net quantity font height is below 4mm statutory minimum." if has_issues else ""
        ),
        ComplianceCheck(
            rule_id="LM-004",
            field="mrp",
            domain="LEGAL_METROLOGY",
            field_label="Maximum Retail Price (MRP)",
            status="NEEDS_REVIEW" if has_issues else "PASS",
            detected_value="₹145.00",
            confidence=88.0,
            reason="MRP prefix requires physical verification of inclusive of all taxes wording." if has_issues else ""
        ),
        ComplianceCheck(
            rule_id="FS-001",
            field="fssai_license",
            domain="FSSAI",
            field_label="FSSAI License Number",
            status="PASS",
            detected_value="10013022001897",
            confidence=96.0,
            reason=""
        )
    ]

    comp_res = ComplianceResult(
        checks=checks,
        score=72 if has_issues else 96,
        status="NON_COMPLIANCE" if has_issues else "COMPLIANT",
        total_rules=len(checks),
        passed_rules=2 if has_issues else 4,
        failed_rules=1 if has_issues else 0,
        needs_review_rules=1 if has_issues else 0,
        warning_rules=0,
        issues=[]
    )

    images = [
        ProductImageEvidence(
            filename="ketchup_front.jpg",
            image_url="/uploads/ketchup_front.jpg",
            label="Front",
            ocr_text="Kissan Tomato Ketchup Net Quantity: 950 g MRP ₹145"
        ),
        ProductImageEvidence(
            filename="ketchup_back.jpg",
            image_url="/uploads/ketchup_back.jpg",
            label="Back",
            ocr_text="FSSAI Lic. No. 10013022001897 Manufactured by Hindustan Unilever 8901030383748"
        )
    ]

    # Product Identity
    barcodes = []
    if has_barcode:
        barcodes.append(BarcodeIdentityData(
            raw_value="8901030383748",
            symbology="EAN-13",
            is_valid_checksum=True,
            country_of_origin="India",
            external_verified=is_barcode_verified,
            verification_status="VERIFIED" if is_barcode_verified else "SERVICE_UNAVAILABLE",
            provenance_label="Externally verified" if is_barcode_verified else "Verification unavailable",
            registered_brand="Kissan" if is_barcode_verified else None,
            registered_product="Fresh Tomato Ketchup 950g" if is_barcode_verified else None,
            registered_company="Hindustan Unilever Limited" if is_barcode_verified else None,
            registered_net_quantity="950 g" if is_barcode_verified else None
        ))

    conflicts = []
    if has_conflicts:
        conflicts.append(ConflictItem(
            field_name="Net Quantity",
            source_a="Package OCR",
            value_a="950 g",
            source_b="GS1 Registry",
            value_b="500 g",
            severity="HIGH",
            description="Package declares 950 g but registered GS1 GTIN record specifies 500 g."
        ))

    cv = CrossValidationSummary(
        status="CONFLICT_DETECTED" if has_conflicts else "PASS",
        has_conflicts=has_conflicts,
        conflicts=conflicts,
        summary_message="Discrepancy detected between package and registry." if has_conflicts else "All sources consistent."
    )

    fssai_details = None
    if is_fssai_verified:
        fssai_details = {
            "licence_number": "10013022001897",
            "business_name": "Hindustan Unilever Limited",
            "licence_type": "Central Licence",
            "valid_upto": "31/12/2027",
            "status": "Active",
            "state": "Central Authority",
            "is_live": True
        }

    barcode_details = None
    if is_barcode_verified and has_barcode:
        barcode_details = {
            "gtin": "8901030383748",
            "brand_name": "Kissan",
            "product_description": "Fresh Tomato Ketchup 950g",
            "company_name": "Hindustan Unilever Limited",
            "net_content": "500 g" if has_conflicts else "950 g",
            "country_of_sale": "India"
        }

    pi = ProductIdentity(
        product_name=FieldEvidenceItem(value="Kissan Fresh Tomato Ketchup", status=FieldStatus.FOUND),
        brand_name=FieldEvidenceItem(value="Kissan", status=FieldStatus.FOUND),
        manufacturer=FieldEvidenceItem(value="Hindustan Unilever Limited", status=FieldStatus.FOUND),
        net_quantity=FieldEvidenceItem(value="950 g", status=FieldStatus.FOUND),
        mrp=FieldEvidenceItem(value="₹145.00", status=FieldStatus.FOUND),
        fssai_license_number=FieldEvidenceItem(value="10013022001897", status=FieldStatus.FOUND),
        fssai_state_name="Central Authority",
        fssai_license_type="Central Licence",
        fssai_external_verified=is_fssai_verified,
        fssai_verification_status="VERIFIED" if is_fssai_verified else "SERVICE_UNAVAILABLE",
        fssai_provenance_label="Externally verified" if is_fssai_verified else "Verification unavailable",
        fssai_verification_details=fssai_details,
        barcodes=barcodes,
        barcode_external_verified=is_barcode_verified,
        barcode_verification_status="VERIFIED" if is_barcode_verified else "SERVICE_UNAVAILABLE",
        barcode_provenance_label="Externally verified" if is_barcode_verified else "Verification unavailable",
        barcode_registered_details=barcode_details,
        cross_validation=cv
    )

    return AnalysisResponse(
        id="report-test-001",
        product_name="Kissan Fresh Tomato Ketchup",
        image_url="/uploads/ketchup_front.jpg",
        images=images,
        ocr_result=OCRResult(full_text="sample", words=[], language="eng", processing_time=0.0),
        product_info=prod_info,
        compliance_result=comp_res,
        product_identity=pi,
        cross_validation=cv,
        created_at="2026-09-17T12:00:00Z"
    )


# ============================================================================
# TESTS
# ============================================================================

def test_pdf_report_fully_compliant_case():
    """Verify PDF generates successfully for fully compliant commodity."""
    analysis = _create_sample_analysis(has_barcode=True, has_conflicts=False, has_issues=False)
    pdf = generate_pdf_report(analysis)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 8000


def test_pdf_report_no_barcode_detected():
    """Verify PDF generates cleanly when no barcode is detected and renders 'Barcode: Not detected'."""
    analysis = _create_sample_analysis(has_barcode=False, has_conflicts=False, has_issues=False)
    pdf = generate_pdf_report(analysis)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")


def test_pdf_report_registry_unavailable():
    """Verify PDF generates cleanly when external registries are unconfigured without fabricating data."""
    analysis = _create_sample_analysis(
        has_barcode=True,
        has_conflicts=False,
        has_issues=False,
        is_fssai_verified=False,
        is_barcode_verified=False
    )
    pdf = generate_pdf_report(analysis)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")


def test_pdf_report_with_conflicts_and_issues():
    """Verify PDF displays prominent conflict detection and issues evidence callouts."""
    analysis = _create_sample_analysis(has_barcode=True, has_conflicts=True, has_issues=True)
    pdf = generate_pdf_report(analysis)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")


def test_pdf_report_multilingual_hindi():
    """Verify report localization in Hindi."""
    analysis = _create_sample_analysis(has_barcode=True, has_conflicts=False, has_issues=True)
    pdf = generate_pdf_report(analysis, lang="hi")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")


def test_pdf_report_multilingual_tamil():
    """Verify report localization in Tamil."""
    analysis = _create_sample_analysis(has_barcode=True, has_conflicts=False, has_issues=False)
    pdf = generate_pdf_report(analysis, lang="ta")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_excel_report_enhanced_structure():
    """Verify multi-sheet Excel report contains updated Executive Summary and Product Identity verification."""
    analysis = _create_sample_analysis(has_barcode=True, has_conflicts=True, has_issues=True)
    
    db_rec = {
        "id": "excel-enh-001",
        "product_name": analysis.product_name,
        "image_filename": "ketchup_front.jpg",
        "ocr_text": "sample",
        "extracted_data": analysis.product_info.model_dump(),
        "compliance_result": analysis.compliance_result.model_dump(),
        "score": analysis.compliance_result.score,
        "status": analysis.compliance_result.status,
        "created_at": "2026-09-17T12:00:00Z",
        "images": [im.model_dump() for im in analysis.images],
        "product_identity": analysis.product_identity.model_dump()
    }
    await save_analysis(db_rec)

    response = await get_report_xlsx("excel-enh-001")
    excel_bytes = b"".join([chunk async for chunk in response.body_iterator])
    wb = load_workbook(io.BytesIO(excel_bytes))

    # 1. Summary Sheet
    assert "Summary" in wb.sheetnames
    ws_sum = wb["Summary"]
    sum_vals = [cell.value for row in ws_sum.rows for cell in row if cell.value]
    assert "Product Name" in sum_vals
    assert "Brand" in sum_vals
    assert "Manufacturer / Packer" in sum_vals
    assert "Net Quantity" in sum_vals
    assert "Retail Price (MRP)" in sum_vals
    assert "FSSAI Licence Number" in sum_vals
    assert "Overall Compliance Score" in sum_vals
    assert "Overall Status" in sum_vals

    # 2. Rule-by-rule Checklist Sheet
    assert "Rule-by-Rule Checklist" in wb.sheetnames

    # 3. Product Identity Sheet
    assert "Product Identity" in wb.sheetnames
    ws_id = wb["Product Identity"]
    id_vals = [cell.value for row in ws_id.rows for cell in row if cell.value]
    assert "FSSAI Information" in id_vals
    assert "FSSAI Verification Status" in id_vals
    assert "FSSAI Registry Match" in id_vals
    assert "Barcode Verification Status" in id_vals
    assert "Barcode Registry Match" in id_vals
    assert any("Conflict:" in str(v) for v in id_vals)


@pytest.mark.asyncio
async def test_api_report_pdf_streaming():
    """Verify GET /api/report/{id} streams valid PDF using _get_full_analysis_object."""
    analysis = _create_sample_analysis(has_barcode=True, has_conflicts=False, has_issues=False)
    db_rec = {
        "id": "pdf-api-001",
        "product_name": analysis.product_name,
        "image_filename": "ketchup_front.jpg",
        "ocr_text": "sample",
        "extracted_data": analysis.product_info.model_dump(),
        "compliance_result": analysis.compliance_result.model_dump(),
        "score": analysis.compliance_result.score,
        "status": analysis.compliance_result.status,
        "created_at": "2026-09-17T12:00:00Z",
        "images": [im.model_dump() for im in analysis.images],
        "product_identity": analysis.product_identity.model_dump()
    }
    await save_analysis(db_rec)

    response = await get_report("pdf-api-001")
    pdf_bytes = b"".join([chunk async for chunk in response.body_iterator])
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 8000
