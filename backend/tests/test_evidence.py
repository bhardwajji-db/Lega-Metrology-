import pytest
from models.schemas import OCRWord, ProductImageEvidence, ProductInfo, ComplianceCheck
from compliance.rules.models import ComplianceStatus, RuleDomain
from compliance.rules.registry import registry
from compliance.evidence_locator import (
    locate_evidence_for_rule,
    _compute_bbox,
    _determine_geometry,
    _aggregate_confidence,
    _find_exact_or_contiguous_sequence,
    _find_line_tokens
)


def test_tight_single_and_multi_token_boxes():
    """Verify tight bounding boxes for single tokens and multi-token lines."""
    w1 = OCRWord(text="Weight:", confidence=100.0, bbox=[476, 724, 529, 739])
    w2 = OCRWord(text="400", confidence=98.5, bbox=[529, 724, 552, 739])
    
    bbox = _compute_bbox([w1, w2])
    assert bbox == [476, 724, 552, 739]
    assert (bbox[3] - bbox[1]) == 15  # Exactly 15px height, tight line!
    assert _determine_geometry([w1, w2]) == "LINE"
    assert _aggregate_confidence([w1, w2]) == 98.5  # Conservative minimum


def test_reject_distant_tokens():
    """Verify that tokens from distant parts of the image (e.g. y=10 vs y=700) are never merged."""
    words = [
        OCRWord(text="Alpino", confidence=99.0, bbox=[50, 10, 150, 35]),    # Header at y=10
        OCRWord(text="MADEININDIA", confidence=98.0, bbox=[413, 675, 459, 685]),  # Origin at y=675
        OCRWord(text="Alpino", confidence=98.0, bbox=[403, 388, 431, 398]),   # Mfg at y=388
        OCRWord(text="HEALTH", confidence=98.0, bbox=[431, 388, 459, 398]),   # Mfg at y=388
        OCRWord(text="SURAT", confidence=86.0, bbox=[527, 406, 551, 417]),    # Address at y=406
    ]
    img = ProductImageEvidence(
        filename="back.png",
        image_url="/back.png",
        label="Back",
        ocr_text="Alpino MADEININDIA Alpino HEALTH SURAT",
        words=words
    )
    pinfo = ProductInfo(
        manufacturer_name="Alpino Health Foods",
        manufacturer_address="Surat, Gujarat",
        is_food=True
    )
    lm_001_rule = registry.get_rule("LM-001")

    items, lbl, bbox, bx, by, bw, bh = locate_evidence_for_rule(
        rule_def=lm_001_rule,
        product_info=pinfo,
        status=ComplianceStatus.PASS,
        reason="Manufacturer verified",
        detected_value="Alpino Health Foods",
        images=[img]
    )

    # Must NOT merge the header at y=10 with mfg at y=388!
    assert items[0].bbox[1] >= 350
    assert items[0].bbox[3] <= 430
    assert (items[0].bbox[3] - items[0].bbox[1]) < 60  # Tight mfg region!


def test_country_of_origin_explicit_declaration():
    """Verify LM-006 specifically matches MADE IN INDIA and rejects 'India's' from address or marketing text."""
    words = [
        OCRWord(text="India's", confidence=98.6, bbox=[92, 207, 120, 217]),  # Marketing slogan at y=207
        OCRWord(text="MADEININDIA", confidence=98.3, bbox=[413, 675, 459, 685]),  # Origin at y=675
    ]
    img = ProductImageEvidence(
        filename="back.png",
        image_url="/back.png",
        label="Back",
        ocr_text="India's MADEININDIA",
        words=words
    )
    pinfo = ProductInfo(country_of_origin="India", is_food=True)
    lm_006_rule = registry.get_rule("LM-006")

    items, lbl, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=lm_006_rule,
        product_info=pinfo,
        status=ComplianceStatus.PASS,
        reason="Country of origin verified",
        detected_value="India",
        images=[img]
    )

    assert len(items) == 1
    assert items[0].bbox == [413, 675, 459, 685]
    assert items[0].text == "MADEININDIA"
    assert items[0].bbox[1] == 675  # Exactly the MADE IN INDIA line!


def test_fssai_vs_gtin_disambiguation_precision():
    """Verify FS-001 produces a tight bounding box around the 14-digit licence and rejects GTIN."""
    words = [
        OCRWord(text="81906127552274", confidence=99.0, bbox=[50, 530, 200, 550]),  # GTIN barcode
        OCRWord(text="LICNO.:10716022000249", confidence=100.0, bbox=[416, 453, 550, 469]),  # FSSAI
    ]
    img = ProductImageEvidence(
        filename="back.png",
        image_url="/back.png",
        label="Back",
        ocr_text="81906127552274 LICNO.:10716022000249",
        words=words
    )
    pinfo = ProductInfo(fssai_license="10716022000249", is_food=True)
    fs_001_rule = registry.get_rule("FS-001")

    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=fs_001_rule,
        product_info=pinfo,
        status=ComplianceStatus.PASS,
        reason="14-digit FSSAI licence verified",
        detected_value="10716022000249",
        images=[img]
    )

    assert len(items) == 1
    assert items[0].bbox == [416, 453, 550, 469]
    assert (items[0].bbox[3] - items[0].bbox[1]) == 16  # Tight 16px height!
    assert "81906127" not in items[0].text


def test_consumer_care_multiple_evidence_items():
    """Verify LM-005 separates phone and email into distinct, tight EvidenceItems."""
    words = [
        OCRWord(text="+91-8347688000", confidence=99.9, bbox=[415, 294, 512, 308]),
        OCRWord(text="support@alpino.co.in", confidence=100.0, bbox=[418, 326, 535, 341]),
    ]
    img = ProductImageEvidence(
        filename="back.png",
        image_url="/back.png",
        label="Back",
        ocr_text="+91-8347688000 support@alpino.co.in",
        words=words
    )
    pinfo = ProductInfo(
        consumer_care_phone="+91-8347688000",
        consumer_care_email="support@alpino.co.in",
        is_food=True
    )
    lm_005_rule = registry.get_rule("LM-005")

    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=lm_005_rule,
        product_info=pinfo,
        status=ComplianceStatus.PASS,
        reason="Consumer care verified",
        detected_value="+91-8347688000, support@alpino.co.in",
        images=[img]
    )

    # Must produce 2 separate granular EvidenceItems rather than 1 merged box
    assert len(items) == 2
    assert items[0].bbox == [415, 294, 512, 308]
    assert items[1].bbox == [418, 326, 535, 341]
    assert items[0].evidence_status == "VERIFIED"
    assert items[1].evidence_status == "VERIFIED"


def test_not_applicable_proviso_delegation():
    """Verify LM-008 for food commodity returns NOT_APPLICABLE and PROVISO_DELEGATION with bbox=None."""
    pinfo = ProductInfo(is_food=True)
    lm_008_rule = registry.get_rule("LM-008")

    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=lm_008_rule,
        product_info=pinfo,
        status=ComplianceStatus.NOT_APPLICABLE,
        reason="Food commodity date marking governed under FSSAI",
        detected_value=None,
        images=[ProductImageEvidence(filename="back.png", image_url="/back.png", label="Back", ocr_text="OATS", words=[])]
    )

    assert len(items) == 1
    assert items[0].evidence_status == "NOT_APPLICABLE"
    assert items[0].evidence_type == "PROVISO_DELEGATION"
    assert items[0].bbox is None
    assert bbox is None
    assert "FSSAI" in items[0].explanation


def test_derived_field_lm_009():
    """Verify LM-009 returns DERIVED_FIELD with geometry_type=NONE, bbox=None, and confidence=0."""
    pinfo = ProductInfo(is_food=True)
    lm_009_rule = registry.get_rule("LM-009")

    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=lm_009_rule,
        product_info=pinfo,
        status=ComplianceStatus.PASS,
        reason="Pricing and declaration integrity verified",
        detected_value=None,
        images=[ProductImageEvidence(filename="front.png", image_url="/front.png", label="Front", ocr_text="OATS", words=[])]
    )

    assert len(items) == 1
    assert items[0].evidence_type == "DERIVED_FIELD"
    assert items[0].geometry_type == "NONE"
    assert items[0].match_method == "NONE"
    assert items[0].confidence == 0.0
    assert items[0].bbox is None
    assert "Derived" in items[0].explanation


def test_mrp_faint_stamp_tight_label_highlight():
    """Verify LM-004 faint stamp highlights only the MRP label line, not the entire stamp box."""
    words = [
        OCRWord(text="MRP:", confidence=95.6, bbox=[182, 756, 218, 766]),
    ]
    img = ProductImageEvidence(
        filename="back.png",
        image_url="/back.png",
        label="Back",
        ocr_text="MRP:",
        words=words
    )
    pinfo = ProductInfo(is_food=True)
    lm_004_rule = registry.get_rule("LM-004")

    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=lm_004_rule,
        product_info=pinfo,
        status=ComplianceStatus.NEEDS_REVIEW,
        reason="MRP label detected; numeric rate requires visual verification",
        detected_value="MRP detected in stamp area",
        images=[img]
    )

    assert len(items) == 1
    assert items[0].evidence_status == "CONTEXTUAL"
    assert items[0].bbox == [182, 756, 218, 766]
    assert (items[0].bbox[3] - items[0].bbox[1]) == 10  # Tight 10px height!
