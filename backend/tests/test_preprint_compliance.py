import os
import io
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from main import app
from config import settings
from models.preprint_schemas import (
    ArtworkDocument,
    ArtworkPageInfo,
    PreprintApprovalRequest,
    FontSizeEstimateResult,
    PlacementCheckResult,
    DesignerCorrectionItem
)
from services.preprint_service import (
    validate_artwork_file,
    render_artwork_pages,
    detect_layout_regions,
    evaluate_placement_checks,
    evaluate_font_size_estimates,
    generate_designer_corrections,
    analyze_artwork
)
from database.db import (
    save_artwork,
    get_artwork,
    list_artworks,
    update_artwork_analysis,
    update_artwork_approval,
    delete_artwork
)
from auth.security import create_token, ROLE_ADMIN


client = TestClient(app)


def _create_sample_png_bytes(text_items=None) -> bytes:
    """Helper to create synthetic packaging artwork PNG in memory."""
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw simple background shapes and simulated text
    draw.rectangle([20, 20, 780, 120], outline=(50, 50, 200), width=3)
    draw.text((40, 40), "BRITANNIA GOOD DAY BUTTER COOKIES", fill=(0, 0, 0))
    draw.text((40, 150), "Mfg by: Britannia Industries Ltd, Bangalore, Karnataka 560001", fill=(0, 0, 0))
    draw.text((40, 200), "Net Quantity: 200 g", fill=(0, 0, 0))
    draw.text((40, 250), "MRP Rs. 40.00 (incl. of all taxes)", fill=(0, 0, 0))
    draw.text((40, 300), "Mfg Date: 01/2025", fill=(0, 0, 0))
    draw.text((40, 350), "Best Before: 6 months from packaging", fill=(0, 0, 0))
    draw.text((40, 400), "FSSAI Lic No: 10014011000123", fill=(0, 0, 0))
    draw.text((40, 450), "Consumer Care: feedback@britannia.com, 1800-425-4449", fill=(0, 0, 0))
    draw.text((40, 500), "Country of Origin: India", fill=(0, 0, 0))
    draw.text((40, 550), "Ingredients: Refined Wheat Flour, Sugar, Butter, Salt", fill=(0, 0, 0))
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════════
# 1. FILE VALIDATION TESTS (Req 1, 2)
# ════════════════════════════════════════════════════════════════════════════

def test_artwork_file_validation_valid_formats():
    """Test validation accepts supported artwork file formats."""
    png_bytes = _create_sample_png_bytes()
    ftype, err = validate_artwork_file("artwork.png", png_bytes)
    assert ftype == "PNG"
    assert err is None

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    ftype_pdf, err_pdf = validate_artwork_file("packaging.pdf", pdf_bytes)
    assert ftype_pdf == "PDF"
    assert err_pdf is None


def test_artwork_file_validation_size_limit():
    """Test artwork file validation rejects files exceeding 30MB."""
    oversized_bytes = b"0" * (31 * 1024 * 1024)
    ftype, err = validate_artwork_file("large_artwork.pdf", oversized_bytes)
    assert ftype is None
    assert "exceeds maximum allowed limit of 30MB" in err


def test_artwork_file_validation_magic_bytes():
    """Test artwork file validation catches mismatched extensions and corrupted headers."""
    fake_pdf = b"NOT_A_PDF_HEADER_JUST_RANDOM_DATA"
    ftype, err = validate_artwork_file("fake.pdf", fake_pdf)
    assert ftype is None
    assert "Corrupted or invalid PDF header" in err

    fake_png = b"NOT_PNG_BYTES"
    ftype_png, err_png = validate_artwork_file("fake.png", fake_png)
    assert ftype_png is None
    assert "Corrupted or invalid PNG image" in err_png


def test_artwork_file_validation_path_traversal():
    """Test protection against directory traversal in filenames."""
    png_bytes = _create_sample_png_bytes()
    ftype, err = validate_artwork_file("../../../etc/passwd.png", png_bytes)
    assert ftype is None
    assert "Path traversal" in err


# ════════════════════════════════════════════════════════════════════════════
# 2. PAGE PARSING & RENDERING TESTS (Req 2, 5)
# ════════════════════════════════════════════════════════════════════════════

def test_raster_image_page_parsing(tmp_path):
    """Test parsing raster image artwork into ArtworkPageInfo."""
    png_bytes = _create_sample_png_bytes()
    img_path = str(tmp_path / "test_artwork.png")
    with open(img_path, "wb") as f:
        f.write(png_bytes)

    pages = render_artwork_pages(img_path, "PNG", str(tmp_path))
    assert len(pages) == 1
    page = pages[0]
    assert page.page_number == 1
    assert page.width == 800
    assert page.height == 1000
    assert page.text_source in ("OCR", "PDF_VECTOR", "HYBRID")


def test_pdf_page_rendering_fallback(tmp_path):
    """Test PDF rendering handles synthetic/vector PDFs gracefully."""
    # Write a minimal valid PDF
    pdf_path = str(tmp_path / "sample.pdf")
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)

    pages = render_artwork_pages(pdf_path, "PDF", str(tmp_path))
    assert len(pages) >= 1
    assert pages[0].width > 0
    assert pages[0].height > 0


# ════════════════════════════════════════════════════════════════════════════
# 3. SEMANTIC LAYOUT & ZONING TESTS (Req 6)
# ════════════════════════════════════════════════════════════════════════════

def test_layout_zoning_detection():
    """Test semantic layout zoning identifies key packaging panels and blocks."""
    words = [
        {"text": "BRITANNIA", "bbox": [50, 40, 200, 80]},
        {"text": "BISCUITS", "bbox": [210, 40, 350, 80]},
        {"text": "MRP", "bbox": [50, 800, 100, 830]},
        {"text": "Rs. 40.00", "bbox": [110, 800, 200, 830]},
        {"text": "Net", "bbox": [50, 850, 90, 880]},
        {"text": "Quantity:", "bbox": [95, 850, 170, 880]},
        {"text": "200 g", "bbox": [175, 850, 230, 880]},
        {"text": "Manufactured", "bbox": [50, 400, 150, 420]},
        {"text": "by", "bbox": [155, 400, 170, 420]},
        {"text": "Britannia", "bbox": [175, 400, 240, 420]},
        {"text": "Nutrition", "bbox": [500, 300, 580, 320]},
        {"text": "Facts", "bbox": [585, 300, 630, 320]},
        {"text": "Energy", "bbox": [500, 330, 550, 350]},
        {"text": "Consumer", "bbox": [50, 600, 120, 620]},
        {"text": "Care", "bbox": [125, 600, 160, 620]},
        {"text": "1800-425-4449", "bbox": [165, 600, 260, 620]},
    ]
    regions = detect_layout_regions(words, 800, 1000)
    region_types = [r.region_type for r in regions]

    assert "BRAND_HEADER" in region_types
    assert "MRP_STAMP" in region_types
    assert "NET_QTY_AREA" in region_types
    assert "MANUFACTURER_BLOCK" in region_types
    assert "NUTRITION_PANEL" in region_types
    assert "CONSUMER_CARE" in region_types


# ════════════════════════════════════════════════════════════════════════════
# 4. PLACEMENT & PROXIMITY TESTS (Req 8, 9)
# ════════════════════════════════════════════════════════════════════════════

def test_mrp_and_net_qty_placement_checks_pass():
    """Test MRP & Net Quantity placement checks evaluate correctly."""
    words = [
        {"text": "MRP", "bbox": [50, 800, 100, 830]},
        {"text": "Rs.", "bbox": [110, 800, 140, 830]},
        {"text": "50.00", "bbox": [150, 800, 200, 830]},
        {"text": "Net", "bbox": [50, 850, 90, 880]},
        {"text": "Quantity", "bbox": [95, 850, 170, 880]},
        {"text": "250g", "bbox": [175, 850, 220, 880]},
    ]
    regions = detect_layout_regions(words, 800, 1000)
    checks = evaluate_placement_checks(regions, words, 800, 1000)

    assert len(checks) == 2
    mrp_check = next(c for c in checks if c.field_name == "mrp")
    net_qty_check = next(c for c in checks if c.field_name == "net_quantity")

    assert mrp_check.passed is True
    assert mrp_check.status == "PASS"
    assert "Rule 8(1)" in mrp_check.legal_citation

    assert net_qty_check.passed is True
    assert net_qty_check.status == "PASS"
    assert "Rule 7" in net_qty_check.legal_citation


# ════════════════════════════════════════════════════════════════════════════
# 5. FONT-SIZE ASSISTANCE TESTS (Req 7)
# ════════════════════════════════════════════════════════════════════════════

def test_font_size_assistance_calculations():
    """Test font-size assistance converts optical height to mm and pt with disclaimers."""
    words = [
        {"text": "Net", "bbox": [50, 500, 90, 540]},
        {"text": "Quantity:", "bbox": [95, 500, 180, 540]},
        {"text": "200g", "bbox": [185, 500, 240, 540]},
        {"text": "MRP", "bbox": [50, 600, 100, 630]},
        {"text": "Rs. 40.00", "bbox": [105, 600, 200, 630]},
    ]
    results = evaluate_font_size_estimates(words, 800, 1000, 72.0)
    assert len(results) >= 1

    net_res = next((r for r in results if r.field_name == "net_quantity"), None)
    assert net_res is not None
    assert net_res.estimated_height_mm > 0
    assert net_res.estimated_pt_size > 0
    assert net_res.mandated_minimum_mm >= 2.0
    assert "ESTIMATED" in net_res.disclaimer
    assert "Physical proof verification recommended" in net_res.disclaimer


# ════════════════════════════════════════════════════════════════════════════
# 6. DESIGNER CORRECTIONS TESTS (Req 10, 12)
# ════════════════════════════════════════════════════════════════════════════

def test_designer_corrections_generation():
    """Test generating actionable designer checklist items for missing fields."""
    missing = ["fssai_license", "consumer_care"]
    from models.schemas import ComplianceCheck
    checks = [
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            field_label="Manufacturer",
            required=True,
            detected=True,
            severity="critical",
            status="PASS",
            description="Manufacturer must be declared",
            source="Rule 6(1)(a)"
        ),
        ComplianceCheck(
            rule_id="FS-001",
            field="fssai_license",
            field_label="FSSAI License",
            required=True,
            detected=False,
            severity="critical",
            status="FAIL",
            description="FSSAI license missing",
            source="FSSAI FSS (Labelling) 2020",
            recommendation="Add 14-digit FSSAI license number"
        )
    ]
    placement = [
        PlacementCheckResult(
            check_name="MRP Placement Check",
            field_name="mrp",
            passed=False,
            status="REVIEW",
            finding="MRP not detected in prominent area",
            recommended_zone="Principal Display Panel",
            legal_citation="Rule 8(1)"
        )
    ]
    font_estimates = []

    corrections = generate_designer_corrections(missing, checks, placement, font_estimates)
    assert len(corrections) >= 2
    
    # Verify critical blocking issue
    critical_corr = next((c for c in corrections if c.severity == "CRITICAL"), None)
    assert critical_corr is not None
    assert critical_corr.is_blocking_for_print is True
    assert critical_corr.suggested_action != ""


# ════════════════════════════════════════════════════════════════════════════
# 7. FULL PRE-PRINT PIPELINE ORCHESTRATION (Req 3, 4, 11, 15, 16)
# ════════════════════════════════════════════════════════════════════════════

def test_full_artwork_analysis_pipeline(tmp_path):
    """Test end-to-end analyze_artwork service with compliance scoring and checklist."""
    png_bytes = _create_sample_png_bytes()
    img_path = str(tmp_path / "artwork_sample.png")
    with open(img_path, "wb") as f:
        f.write(png_bytes)

    pages = render_artwork_pages(img_path, "PNG", str(tmp_path))
    artwork_doc = {
        "id": "art-test001",
        "filename": "artwork_sample.png",
        "file_path": img_path,
        "file_type": "PNG",
        "file_size": len(png_bytes),
        "page_count": 1,
        "dimensions": {"width": 800, "height": 1000},
        "dpi": 72.0,
        "source_identity": "PRE-PRINT ARTWORK",
        "compliance_ruleset": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "parent_artwork_id": None,
        "iteration_number": 1,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "approval_record": None,
        "analysis_result": None,
        "pages_data": [p.model_dump() for p in pages],
        "created_at": "2026-09-17T12:00:00Z",
        "updated_at": "2026-09-17T12:00:00Z"
    }

    resp = analyze_artwork(artwork_doc)
    assert resp.artwork_id == "art-test001"
    assert resp.source_identity == "PRE-PRINT ARTWORK"
    assert resp.compliance_ruleset == "Legal Metrology (Packaged Commodities) Rules, 2011"
    assert resp.iteration_number == 1
    assert len(resp.mandatory_checklist) > 0
    assert len(resp.placement_checks) >= 2
    assert resp.workflow_status in ("ACTION_REQUIRED", "CHANGES_REQUESTED", "DRAFT", "READY_FOR_PRINT")


# ════════════════════════════════════════════════════════════════════════════
# 8. API ENDPOINT & WORKFLOW APPROVAL TESTS (Req 13, 14, 15, 16)
# ════════════════════════════════════════════════════════════════════════════

def test_api_upload_and_analyze_artwork():
    """Test POST /api/preprint/upload and POST /api/preprint/{artwork_id}/analyze."""
    token = create_token("admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    png_bytes = _create_sample_png_bytes()
    files = {"file": ("cookie_box.png", png_bytes, "image/png")}
    
    upload_res = client.post("/api/preprint/upload", files=files, headers=headers)
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["success"] is True
    artwork_id = upload_data["artwork_id"]
    assert artwork_id.startswith("art-")

    # Analyze
    analyze_res = client.post(f"/api/preprint/{artwork_id}/analyze", headers=headers)
    assert analyze_res.status_code == 200
    ana_data = analyze_res.json()
    assert ana_data["artwork_id"] == artwork_id
    assert "mandatory_checklist" in ana_data
    assert "designer_corrections" in ana_data


def test_api_get_artwork_details():
    """Test GET /api/preprint/{artwork_id}."""
    token = create_token("admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    png_bytes = _create_sample_png_bytes()
    files = {"file": ("detail_test.png", png_bytes, "image/png")}
    up = client.post("/api/preprint/upload", files=files, headers=headers).json()
    art_id = up["artwork_id"]

    get_res = client.get(f"/api/preprint/{art_id}", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == art_id
    assert data["source_identity"] == "PRE-PRINT ARTWORK"


def test_api_correction_upload_iteration():
    """Test POST /api/preprint/{artwork_id}/correction-upload increments iteration."""
    token = create_token("admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    png_bytes = _create_sample_png_bytes()
    files = {"file": ("v1.png", png_bytes, "image/png")}
    up = client.post("/api/preprint/upload", files=files, headers=headers).json()
    art_id_v1 = up["artwork_id"]

    # Upload corrected v2
    corr_files = {"file": ("v2_fixed.png", png_bytes, "image/png")}
    corr_res = client.post(f"/api/preprint/{art_id_v1}/correction-upload", files=corr_files, headers=headers)
    assert corr_res.status_code == 200
    corr_data = corr_res.json()
    assert corr_data["iteration_number"] == 2
    assert corr_data["parent_artwork_id"] == art_id_v1


def test_api_approval_workflow_requires_disclaimer():
    """Test submitting approval without legal disclaimer is rejected with 400."""
    token = create_token("admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    png_bytes = _create_sample_png_bytes()
    files = {"file": ("appr_test.png", png_bytes, "image/png")}
    up = client.post("/api/preprint/upload", files=files, headers=headers).json()
    art_id = up["artwork_id"]

    body = {
        "reviewer_name": "Compliance Lead",
        "reviewer_role": "MERCHANT_PUBLIC",
        "decision": "APPROVED",
        "comments": "Looks ready",
        "legal_disclaimer_acknowledged": False  # Missing acknowledgment
    }
    res = client.post(f"/api/preprint/{art_id}/approval", json=body, headers=headers)
    assert res.status_code == 400
    assert "Legal disclaimer must be acknowledged" in res.json()["detail"]


def test_api_approval_workflow_request_changes():
    """Test submitting REQUEST_CHANGES transitions status to CHANGES_REQUESTED."""
    token = create_token("admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    png_bytes = _create_sample_png_bytes()
    files = {"file": ("req_change.png", png_bytes, "image/png")}
    up = client.post("/api/preprint/upload", files=files, headers=headers).json()
    art_id = up["artwork_id"]

    body = {
        "reviewer_name": "Lead Designer",
        "reviewer_role": "MERCHANT_PUBLIC",
        "decision": "REQUEST_CHANGES",
        "comments": "Please reposition MRP to PDP.",
        "legal_disclaimer_acknowledged": True
    }
    res = client.post(f"/api/preprint/{art_id}/approval", json=body, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["workflow_status"] == "CHANGES_REQUESTED"
    assert data["approval_status"] == "CHANGES_REQUESTED"


def test_api_list_and_delete_artworks():
    """Test listing and deleting artworks."""
    token = create_token("admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    png_bytes = _create_sample_png_bytes()
    files = {"file": ("del_test.png", png_bytes, "image/png")}
    up = client.post("/api/preprint/upload", files=files, headers=headers).json()
    art_id = up["artwork_id"]

    # List
    list_res = client.get("/api/preprint", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # Delete
    del_res = client.delete(f"/api/preprint/{art_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Check 404 after delete
    get_res = client.get(f"/api/preprint/{art_id}", headers=headers)
    assert get_res.status_code == 404
