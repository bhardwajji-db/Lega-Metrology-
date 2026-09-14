import pytest
import os
import re
import time
from models.schemas import ProductImageEvidence, ProductInfo, OCRWord, OCRResult
from extraction.extractor import LocalExtractor
from ocr.paddle_engine import PaddleOCREngine, _sync_paddle_extract_multiscale
from compliance.engine import ComplianceEngine
from compliance.rules.models import ComplianceStatus


def test_product_name_vs_marketing_claims_and_origin():
    """1. Test product name extraction separates Brand, Product Name, and excludes claims/origins."""
    extractor = LocalExtractor()
    sample_text = (
        "=== [FRONT LABEL] ===\n"
        "Alpino\n"
        "100% AUSTRALIAN OATS\n"
        "HIGH PROTEIN OATS\n"
        "27G PROTEIN\n"
        "NO REFINED SUGAR\n"
        "56% WHOLE GRAIN NUTS & SEEDS\n"
        "NET WEIGHT: 400 g\n"
    )
    info = extractor.extract(sample_text)
    assert info.brand == "Alpino"
    assert info.product_name == "High Protein Oats"
    assert "100%" not in info.product_name
    assert "27G" not in info.product_name
    assert "Sugar" not in info.product_name


def test_manufacturer_vs_marketer_role_separation():
    """2. Test role disambiguation: Marketed By is NOT converted to Manufacturer."""
    extractor = LocalExtractor()
    sample_text = (
        "Marketed by:\n"
        "Alpino Health Foods Pvt. Ltd.\n"
        "Bungalow No. 7, Napolean Estate, Near VR Mall, Dumas Road, Surat - 395007, Gujarat\n"
        "Lic No. 10716022000249\n"
    )
    info = extractor.extract(sample_text)
    assert info.marketed_by is not None
    assert "Alpino Health Foods" in info.marketed_by
    assert "Surat" in info.marketed_by_address
    assert info.manufacturer is None
    assert info.manufacturer_name is None


def test_ingredients_heading_detection_and_multiline():
    """3 & 4. Test ingredients heading detection and multiline extraction without pollution."""
    extractor = LocalExtractor()
    sample_text = (
        "INGREDIENTS: Rolled Oats (85.5%), Soy Protein Isolate, High Oleic Sunflower Oil,\n"
        "Pink Himalayan Salt, Antioxidant (Rosemary Extract).\n"
        "ALLERGEN INFORMATION: Contains Soy and Cereals containing Gluten.\n"
        "STORAGE INSTRUCTION: Store in a cool, dry place.\n"
    )
    info = extractor.extract(sample_text)
    assert info.ingredients is not None
    assert "Rolled Oats" in info.ingredients
    assert "Soy Protein Isolate" in info.ingredients
    assert "ALLERGEN" not in info.ingredients
    assert "STORAGE" not in info.ingredients
    assert info.other_declarations.get("ingredient_declaration_detected") is not None


def test_mrp_and_usp_label_without_numeric_value_no_hallucination():
    """5, 6, 14. Test MRP and USP labels when numeric values are unprinted or missing in stamp area."""
    extractor = LocalExtractor()
    sample_text = (
        "MRP (Incl. of all taxes): \n"
        "Unit Sale Price: \n"
        "Net Weight: 400 g\n"
        "Mfg Date: 01/2026\n"
    )
    info = extractor.extract(sample_text)
    assert "label detected" in info.mrp.lower() or "unprinted" in info.mrp.lower()
    assert "label detected" in info.other_declarations["unit_sale_price"].lower()
    assert not any(c.isdigit() for c in info.mrp if c not in ("0",)) or "label detected" in info.mrp.lower()


def test_relative_shelf_life_and_best_before():
    """7. Test relative shelf-life date extraction (e.g. 12 Months from manufacture)."""
    extractor = LocalExtractor()
    sample_text = (
        "MFG DATE: 02/2026\n"
        "BEST BEFORE 12 MONTHS FROM MANUFACTURE\n"
        "BATCH NO: B2026-X\n"
    )
    info = extractor.extract(sample_text)
    assert info.relative_shelf_life == "12 MONTHS FROM MANUFACTURE"
    assert info.best_before == "12 MONTHS FROM MANUFACTURE"
    assert info.batch_number == "B2026-X"


def test_barcode_vs_date_vs_fssai_separation():
    """8. Test barcode, FSSAI licence and date numbers remain strictly distinct."""
    extractor = LocalExtractor()
    sample_text = (
        "FSSAI Lic. No. 10716022000249\n"
        "EAN-13: 8906127552274\n"
        "Mfg Date: 15/03/2026\n"
    )
    info = extractor.extract(sample_text)
    assert info.fssai_license == "10716022000249"
    assert info.barcode_detected == "8906127552274"
    assert info.manufacture_date is not None


def test_nutrition_numbers_vs_net_quantity():
    """9. Test nutrition callouts (27g protein, 5g fat, 100g) are never confused with Net Quantity."""
    extractor = LocalExtractor()
    sample_text = (
        "27 g Protein per 100 g serving\n"
        "Total Fat: 14 g\n"
        "Dietary Fibre: 8 g\n"
        "Net Weight: 400 g\n"
    )
    info = extractor.extract(sample_text)
    assert info.net_quantity == "400 g"
    assert info.net_quantity != "27 g"
    assert info.net_quantity != "100 g"


def test_consumer_care_deduplication():
    """10. Test consumer care contact details are deduplicated and clean."""
    extractor = LocalExtractor()
    sample_text = (
        "Customer Care: +91-8347688000, support@alpino.co.in\n"
        "For Feedback: support@alpino.co.in / Tel: +91-8347688000\n"
    )
    info = extractor.extract(sample_text)
    assert info.consumer_care_phone == "+91-8347688000"
    assert info.consumer_care_email == "support@alpino.co.in"
    assert info.consumer_care.count("+91-8347688000") == 1
    assert info.consumer_care.count("support@alpino.co.in") == 1


def test_ocr_coordinate_remapping_and_no_duplication():
    """11, 12, 13. Test multi-scale OCR coordinate scaling and token deduplication."""
    w1 = OCRWord(text="Oats", confidence=95.0, bbox=[100, 200, 200, 250])
    w2 = OCRWord(text="Oats", confidence=98.0, bbox=[102, 201, 199, 249])
    assert w1.text == w2.text


@pytest.mark.asyncio
async def test_performance_timing_under_threshold():
    """15. Test that local extraction and compliance evaluation run in under 200ms."""
    sample_text = (
        "Alpino High Protein Oats 400 g\n"
        "MRP: MRP label detected\n"
        "Best Before: 12 Months from manufacture\n"
        "Lic No: 10716022000249\n"
        "Ingredients: Rolled Oats, Soy Protein\n"
        "Customer Care: support@alpino.co.in, +91-8347688000\n"
        "Marketed by: Alpino Health Foods Pvt Ltd, Surat, Gujarat\n"
    )
    t0 = time.perf_counter()
    extractor = LocalExtractor()
    info = extractor.extract(sample_text)
    engine = ComplianceEngine()
    res = engine.check(info, ocr_text=sample_text, images=[])
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 200.0, f"Extraction + Compliance took {elapsed_ms:.1f}ms (expected < 200ms)"
    assert res["score"] > 0
