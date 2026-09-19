"""
Comprehensive Semantic Precision and Negative False-Positive Tests for Evidence Locator.
Verifies Bugs 1 through 5 as required by MetrCheck AI Acceptance Audit:
- Bug 1: Short keyword substring safety (/g does not match MAKING)
- Bug 2: LM-007 Unit Sale Price precision (no tagline false matches)
- Bug 3: FS-003 Ingredients detection (header variations and allergen context)
- Bug 4: LM-001 Manufacturer handle decomposition and multi-token matching
- Bug 5: LM-005 Consumer care non-nutrition filtering
"""
import sys, os
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import pytest
from models.schemas import OCRWord, ProductImageEvidence, ProductInfo
from compliance.rules.models import ComplianceStatus
from compliance.rules.registry import registry
from compliance.evidence_locator import (
    locate_evidence_for_rule,
    _token_matches,
    _find_exact_or_contiguous_sequence,
    _find_line_tokens,
    _is_nutrition_or_table_line,
    _split_handle_to_words,
)


def _make_word(text: str, bbox: list, conf: float = 90.0) -> OCRWord:
    return OCRWord(text=text, bbox=bbox, confidence=conf)


def _make_image(label: str = "Back", words: list = None) -> ProductImageEvidence:
    return ProductImageEvidence(
        image_index=0,
        filename=f"{label.lower()}.png",
        image_url=f"/api/images/{label.lower()}.png",
        label=label,
        width=500,
        height=500,
        words=words or []
    )


# ── BUG 1: SHORT KEYWORD SUBSTRING SAFETY ──────────────────────────────────────

def test_bug1_token_matches_short_keyword_safety():
    """Verify /g, g, kg, mrp, usp do NOT match unrelated words containing those characters."""
    assert not _token_matches("MAKING", "/g")
    assert not _token_matches("MAKING", "g")
    assert not _token_matches("PACKAGING", "g")
    assert not _token_matches("INGREDIENT", "g")
    assert not _token_matches("SUSPENDED", "usp")
    assert not _token_matches("CONSUMER", "usp")
    assert not _token_matches("SERVICES", "rs")
    
    # Positive exact matches must still work
    assert _token_matches("g", "g")
    assert _token_matches("/g", "/g")
    assert _token_matches("400g", "400g")
    assert _token_matches("MRP", "mrp")
    assert _token_matches("USP", "usp")
    assert _token_matches("kg", "kg")


def test_bug1_find_line_tokens_no_false_substring_match():
    """Verify _find_line_tokens with /g does not pick a line containing 'MAKING HEALTH FUN'."""
    words = [
        _make_word("MAKING", [10, 10, 50, 20]),
        _make_word("HEALTH", [60, 10, 100, 20]),
        _make_word("FUN!", [110, 10, 140, 20]),
        _make_word("Net", [10, 40, 30, 50]),
        _make_word("400", [35, 40, 55, 50]),
        _make_word("g", [60, 40, 70, 50]),
    ]
    res_g = _find_line_tokens(words, "g")
    assert res_g is not None
    matched_texts = [w.text for w in res_g]
    assert "MAKING" not in matched_texts
    assert "g" in matched_texts


# ── BUG 2: LM-007 UNIT SALE PRICE PRECISION ────────────────────────────────────

def test_bug2_lm007_rejects_tagline_and_nutrition():
    """Verify LM-007 does NOT select tagline 'MAKING HEALTH FUN!' or consumer service headers."""
    rule_def = registry.get_rule("LM-007")
    prod_info = ProductInfo(
        product_name="High Protein Oats",
        brand="Alpino",
        net_quantity="400 g"
    )
    words = [
        _make_word("MAKING", [10, 10, 50, 20]),
        _make_word("HEALTH", [60, 10, 100, 20]),
        _make_word("FUN!", [110, 10, 140, 20]),
        _make_word("THE", [10, 40, 30, 50]),
        _make_word("CONSUMER", [35, 40, 80, 50]),
        _make_word("SERVICES", [85, 40, 130, 50]),
        _make_word("MANAGER", [135, 40, 180, 50]),
    ]
    img = _make_image("Back", words)
    
    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=rule_def,
        product_info=prod_info,
        status=ComplianceStatus.NEEDS_REVIEW,
        reason="Unit sale price not detected",
        detected_value=None,
        images=[img]
    )
    assert items[0].text != "MAKING HEALTH FUN!"
    assert "MAKING" not in items[0].text
    assert "SERVICES" not in items[0].text


def test_bug2_lm007_positive_unit_sale_price_detection():
    """Verify LM-007 correctly locates genuine Unit Sale Price declaration."""
    rule_def = registry.get_rule("LM-007")
    prod_info = ProductInfo(
        product_name="Chips",
        brand="Lay's",
        net_quantity="143 g"
    )
    words = [
        _make_word("UNIT", [10, 100, 40, 115]),
        _make_word("SALE", [45, 100, 75, 115]),
        _make_word("PRICE:", [80, 100, 120, 115]),
        _make_word("Rs", [125, 100, 140, 115]),
        _make_word("0.35/g", [145, 100, 180, 115]),
    ]
    img = _make_image("Back", words)
    
    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(
        rule_def=rule_def,
        product_info=prod_info,
        status=ComplianceStatus.PASS,
        reason="Unit sale price verified",
        detected_value="Rs 0.35/g",
        images=[img]
    )
    assert bbox is not None
    assert "UNIT" in items[0].text
    assert items[0].evidence_status == "VERIFIED"


# ── BUG 3: FS-003 INGREDIENTS DETECTION ────────────────────────────────────────

def test_bug3_fs003_ingredients_variations():
    """Verify FS-003 detects various ingredients header formats."""
    rule_def = registry.get_rule("FS-003")
    prod_info = ProductInfo(product_name="Oats", category="Packaged Food")

    # Case A: "LIST OF INGREDIENTS"
    words_a = [
        _make_word("LIST", [10, 50, 35, 65]),
        _make_word("OF", [40, 50, 55, 65]),
        _make_word("INGREDIENTS:", [60, 50, 140, 65]),
        _make_word("Rolled", [10, 70, 50, 85]),
        _make_word("Oats", [55, 70, 80, 85]),
    ]
    img_a = _make_image("Back", words_a)
    items_a, _, bbox_a, _, _, _, _ = locate_evidence_for_rule(rule_def, prod_info, ComplianceStatus.PASS, None, "Rolled Oats", [img_a])
    assert bbox_a is not None
    assert "INGREDIENTS" in items_a[0].text

    # Case B: "INGREDIENTS"
    words_b = [
        _make_word("INGREDIENTS:", [10, 50, 100, 65]),
        _make_word("Wheat", [10, 70, 45, 85]),
        _make_word("Flour", [50, 70, 80, 85]),
    ]
    img_b = _make_image("Back", words_b)
    items_b, _, bbox_b, _, _, _, _ = locate_evidence_for_rule(rule_def, prod_info, ComplianceStatus.PASS, None, "Wheat Flour", [img_b])
    assert bbox_b is not None
    assert "INGREDIENTS" in items_b[0].text


# ── BUG 4: LM-001 MANUFACTURER HANDLE DECOMPOSITION ────────────────────────────

def test_bug4_handle_decomposition():
    """Verify handle splitting decomposes concatenated website/handles."""
    parts = _split_handle_to_words("alpinohealthfoods")
    assert "alpino" in parts
    assert "health" in parts


def test_bug4_lm001_locates_decomposed_manufacturer():
    """Verify LM-001 matches visual tokens when extracted manufacturer is a concatenated handle."""
    rule_def = registry.get_rule("LM-001")
    prod_info = ProductInfo(
        product_name="High Protein Oats",
        manufacturer_name="alpinohealthfoods"
    )
    words = [
        _make_word("ALPINO", [10, 50, 50, 65]),
        _make_word("HEALTH", [55, 50, 95, 65]),
        _make_word("FOODS", [100, 50, 140, 65]),
        _make_word("PVT", [145, 50, 170, 65]),
        _make_word("LTD", [175, 50, 195, 65]),
    ]
    img = _make_image("Back", words)
    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(rule_def, prod_info, ComplianceStatus.PASS, None, "Alpino Health Foods", [img])
    assert bbox is not None
    assert "HEALTH" in items[0].text


# ── BUG 5: LM-005 CONSUMER CARE NON-NUTRITION FILTERING ────────────────────────

def test_bug5_consumer_care_rejects_nutrition_numbers():
    """Verify LM-005 selects actual consumer-care section and rejects nutrition table rows."""
    rule_def = registry.get_rule("LM-005")
    prod_info = ProductInfo(
        product_name="Snacks",
        consumer_care_phone="01202400286"
    )
    # Image containing both a nutrition row with numbers and a consumer care section
    words = [
        # Nutrition row (should be rejected)
        _make_word("Total", [10, 100, 35, 115]),
        _make_word("Carbohydrates", [40, 100, 110, 115]),
        _make_word("50.0", [115, 100, 140, 115]),
        _make_word("Energy", [10, 120, 45, 135]),
        _make_word("450", [50, 120, 70, 135]),
        _make_word("kcal", [75, 120, 95, 135]),
        # Consumer care section (should be selected)
        _make_word("CUSTOMER", [10, 200, 60, 215]),
        _make_word("CARE:", [65, 200, 95, 215]),
        _make_word("0120-2400286", [100, 200, 170, 215]),
    ]
    img = _make_image("Back", words)
    items, _, bbox, _, _, _, _ = locate_evidence_for_rule(rule_def, prod_info, ComplianceStatus.PASS, None, "01202400286", [img])
    assert bbox is not None
    assert bbox[1] >= 200  # Must be in the consumer care region, NOT the nutrition table at y=100-135
    assert "0120-2400286" in items[0].text
    assert "Carbohydrates" not in items[0].text
    assert "Energy" not in items[0].text


def test_multi_token_bbox_union_integrity():
    """Verify _compute_bbox calculates the union bbox [min_x, min_y, max_x, max_y] across all tokens."""
    words = [
        _make_word("HIGH", [100, 200, 150, 230]),
        _make_word("PROTEIN", [155, 195, 220, 235]),
        _make_word("OATS", [225, 205, 280, 232]),
    ]
    from compliance.evidence_locator import _compute_bbox
    bbox = _compute_bbox(words)
    assert bbox == [100, 195, 280, 235]
