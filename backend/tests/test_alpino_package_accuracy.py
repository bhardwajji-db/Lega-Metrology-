import pytest
import os
from ocr.paddle_engine import PaddleOCREngine
from extraction.extractor import LocalExtractor
from compliance.engine import ComplianceEngine
from compliance.rules.models import ComplianceStatus
from models.schemas import ProductImageEvidence


@pytest.mark.asyncio
async def test_alpino_real_package_extraction_and_evidence():
    base_dir = os.path.dirname(__file__)
    front_path = os.path.join(base_dir, "..", "fixtures", "alpino_front.png")
    back_path = os.path.join(base_dir, "..", "fixtures", "alpino_back.png")
    if not os.path.exists(front_path):
        front_path = os.path.join("backend", "fixtures", "alpino_front.png")
        back_path = os.path.join("backend", "fixtures", "alpino_back.png")

    if not os.path.exists(front_path) or not os.path.exists(back_path):
        pytest.skip("Alpino fixtures not found")

    ocr_engine = PaddleOCREngine()
    res_f = await ocr_engine.extract(front_path)
    res_b = await ocr_engine.extract(back_path)

    ev_f = ProductImageEvidence(
        filename="alpino_front.png",
        image_url="/alpino_front.png",
        label="Front",
        ocr_text=res_f.full_text,
        words=res_f.words
    )
    ev_b = ProductImageEvidence(
        filename="alpino_back.png",
        image_url="/alpino_back.png",
        label="Back",
        ocr_text=res_b.full_text,
        words=res_b.words
    )

    combined_text = f"=== [FRONT LABEL] ===\n{res_f.full_text}\n\n=== [BACK LABEL] ===\n{res_b.full_text}"
    extractor = LocalExtractor()
    info = extractor.extract(combined_text, images=[ev_f, ev_b])

    # 1. Product Name & Brand
    assert info.brand == "Alpino"
    assert info.product_name == "High Protein Oats"

    # 2. Net Quantity
    assert info.net_quantity == "400 g"

    # 3. FSSAI License Number
    assert info.fssai_license == "10716022000249"

    # 4. Consumer Care (No duplicate occurrences)
    assert info.consumer_care_phone == "+91-8347688000"
    assert info.consumer_care_email == "support@alpino.co.in"
    assert info.consumer_care.count("+91-8347688000") == 1
    assert info.consumer_care.count("support@alpino.co.in") == 1

    # 5. Role Disambiguation: Marketed By identified, NOT falsely as manufacturer
    assert info.marketed_by is not None
    assert "alpino" in info.marketed_by.lower()
    assert info.manufacturer is None

    # 6. MRP: Label detected, numeric price unprinted/missing (no hallucination)
    assert info.mrp is not None
    assert "label detected" in info.mrp.lower() or "unprinted" in info.mrp.lower() or "missing" in info.mrp.lower()
    assert not any(c.isdigit() for c in info.mrp if c not in ("0",)) or "label detected" in info.mrp.lower()

    # 7. Unit Sale Price: Label detected, no hallucinated rate
    assert info.other_declarations.get("unit_sale_price") is not None
    assert "label detected" in info.other_declarations["unit_sale_price"].lower() or "unprinted" in info.other_declarations["unit_sale_price"].lower()

    # 8. Date Marking / Relative Shelf-Life
    assert info.relative_shelf_life == "12 MONTHS FROM MANUFACTURE"
    assert info.best_before == "12 MONTHS FROM MANUFACTURE"

    # 9. Ingredients: List detected from multi-scale OCR
    assert info.ingredients is not None
    assert len(info.ingredients) >= 10
    assert "OATS" in info.ingredients.upper()

    # 10. Compliance Engine Checks & Evidence Localization
    engine = ComplianceEngine()
    result = engine.check(info, ocr_text=combined_text, images=[ev_f, ev_b], analysis_id="test-alpino")
    checks = {c.rule_id: c for c in result["checks"]}

    # LM-001 (Marketed By): PASS with verified evidence
    assert checks["LM-001"].status == ComplianceStatus.PASS.value
    assert len(checks["LM-001"].evidence) >= 1
    assert checks["LM-001"].evidence[0].bbox is not None

    # LM-002 (Product Name): PASS with Front evidence
    assert checks["LM-002"].status == ComplianceStatus.PASS.value
    assert checks["LM-002"].evidence[0].image_label == "Front"
    assert checks["LM-002"].evidence[0].bbox is not None

    # LM-003 (Net Quantity): PASS
    assert checks["LM-003"].status == ComplianceStatus.PASS.value
    assert checks["LM-003"].detected_value == "400 g"
    assert checks["LM-003"].evidence[0].bbox is not None

    # LM-004 (MRP): NEEDS_REVIEW (stamp unprinted, not fake PASS)
    assert checks["LM-004"].status == ComplianceStatus.NEEDS_REVIEW.value
    assert checks["LM-004"].evidence[0].bbox is not None

    # LM-005 (Consumer Care): PASS without duplicate items
    assert checks["LM-005"].status == ComplianceStatus.PASS.value
    assert checks["LM-005"].detected_value == "+91-8347688000, support@alpino.co.in"

    # LM-007 (Unit Sale Price): NEEDS_REVIEW (label present, rate unprinted)
    assert checks["LM-007"].status == ComplianceStatus.NEEDS_REVIEW.value
    assert checks["LM-007"].evidence[0].bbox is not None

    # FS-001 (FSSAI): PASS with Back evidence
    assert checks["FS-001"].status == ComplianceStatus.PASS.value
    assert checks["FS-001"].detected_value == "10716022000249"

    # FS-003 (Ingredients): PASS with Back evidence
    assert checks["FS-003"].status == ComplianceStatus.PASS.value
    assert checks["FS-003"].evidence[0].image_label == "Back"
    assert checks["FS-003"].evidence[0].bbox is not None
    assert checks["FS-003"].evidence[0].evidence_status == "VERIFIED"

    # FS-005 (Date Marking): NEEDS_REVIEW (relative shelf life present, reference mfg date stamp unprinted)
    assert checks["FS-005"].status == ComplianceStatus.NEEDS_REVIEW.value
    assert checks["FS-005"].evidence[0].bbox is not None
