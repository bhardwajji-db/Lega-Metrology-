"""
Unit and Integration Tests for Master Roadmap Section 9: Version Comparison

Covers all 14 requirements:
1. Product versioning
2. Packaging versioning
3. Version A vs Version B
4. Added declaration detection
5. Removed declaration detection
6. Changed MRP detection
7. Changed quantity detection
8. Changed manufacturer detection
9. Changed FSSAI number detection
10. Changed ingredients detection
11. Changed nutrition information detection
12. Compliance score comparison
13. Issue-resolution tracking
14. Version timeline
"""

import time
import pytest
from fastapi.testclient import TestClient

from main import app
from models.schemas import (
    ProductInfo,
    ComplianceResult,
    ComplianceCheck,
    ComplianceIssue,
    VersionSnapshot,
    VersionComparisonRequest,
    VersionComparisonResult
)
from services.version_comparison_service import (
    normalize_text_for_comparison,
    parse_and_normalize_mrp,
    parse_and_normalize_quantity,
    normalize_fssai,
    compare_ingredients,
    compare_nutrition,
    compare_single_field,
    compare_compliance_rules,
    track_issue_resolutions,
    compare_versions
)
from database.db import (
    save_analysis,
    save_artwork,
    save_version_comparison,
    get_version_comparison,
    list_version_comparisons,
    get_version_timeline
)

from auth.security import create_token, hash_password, ROLE_ADMIN
from database.db import create_user, init_db

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {create_token('admin_user', ROLE_ADMIN)}"}


async def _ensure_test_user():
    """Ensure test admin user exists in test DB."""
    salt, pwh = hash_password("TestPass123!")
    try:
        await create_user(
            username="admin_user",
            password_hash=pwh,
            salt=salt,
            role=ROLE_ADMIN,
            full_name="Admin User",
            organization_id="org_admin"
        )
    except Exception:
        pass


# --------------------------------------------------------------------------
# Fixtures and Helpers
# --------------------------------------------------------------------------

def _make_snapshot(
    version_id: str = "snap_1",
    version_type: str = "ANALYSIS",
    version_label: str = "v1.0",
    product_name: str = "Britannia Good Day Butter",
    mrp: str = "₹40.00",
    net_quantity: str = "200 g",
    manufacturer: str = "Britannia Industries Ltd, Bangalore 560001",
    fssai_no: str = "10014011000123",
    consumer_care: str = "feedback@britannia.com",
    country_of_origin: str = "India",
    ingredients: str = "Refined Wheat Flour, Sugar, Butter (5%), Salt",
    nutrition_facts: dict = None,
    score: float = 75.0,
    risk_level: str = "MEDIUM",
    checks: list = None
) -> VersionSnapshot:
    pinfo = ProductInfo(
        product_name=product_name,
        mrp=mrp,
        net_quantity=net_quantity,
        manufacturer=manufacturer,
        fssai_license=fssai_no,
        consumer_care=consumer_care,
        country_of_origin=country_of_origin,
        ingredients=ingredients,
        nutrition_facts=nutrition_facts or {"Energy": "480 kcal", "Protein": "6 g", "Carbohydrates": "70 g", "Fat": "20 g"}
    )
    if checks is None:
        checks = [
            ComplianceCheck(
                rule_id="LM-001",
                field="manufacturer",
                field_label="Manufacturer Details",
                required=True,
                detected=True,
                status="PASS",
                severity="critical"
            ),
            ComplianceCheck(
                rule_id="LM-004",
                field="mrp",
                field_label="MRP Declaration",
                required=True,
                detected=True,
                status="PASS",
                severity="critical"
            ),
            ComplianceCheck(
                rule_id="FS-001",
                field="fssai_license",
                field_label="FSSAI License",
                required=True,
                detected=True,
                status="PASS",
                severity="critical"
            ),
            ComplianceCheck(
                rule_id="LM-005",
                field="consumer_care",
                field_label="Consumer Care",
                required=True,
                detected=False,
                status="FAIL",
                severity="medium"
            )
        ]
    
    passed_cnt = sum(1 for c in checks if c.status == "PASS")
    failed_cnt = sum(1 for c in checks if c.status == "FAIL")
    comp_res = ComplianceResult(
        score=score,
        status="PASS" if score >= 80 else "FAIL",
        total_rules=len(checks),
        passed_rules=passed_cnt,
        failed_rules=failed_cnt,
        checks=checks,
        issues=[ComplianceIssue(
            what=f"Issue on {c.field_label}",
            expected=f"Valid {c.field_label}",
            why="Statutory requirement",
            action=f"Correct {c.field_label}",
            severity=c.severity,
            field=c.field,
            domain=getattr(c, "domain", "LEGAL_METROLOGY")
        ) for c in checks if c.status in ("FAIL", "WARNING")]
    )

    return VersionSnapshot(
        version_id=version_id,
        version_label=version_label,
        version_type=version_type,
        product_name=product_name,
        timestamp="2026-01-01T10:00:00Z",
        score=score,
        risk_level=risk_level,
        product_info=pinfo,
        compliance_result=comp_res
    )


# --------------------------------------------------------------------------
# Unit Tests: Normalization & Field Differencing
# --------------------------------------------------------------------------

def test_normalization_helpers():
    """Test text, MRP, quantity and FSSAI normalization helpers."""
    # Text normalization
    norm = normalize_text_for_comparison("  ₹ 50.00 (Incl. Taxes) ")
    assert "50.00" in norm
    assert "taxes" in norm
    
    # MRP normalization
    amt, fmt = parse_and_normalize_mrp("Rs. 45.50 (incl of taxes)")
    assert amt == 45.50
    assert "45.50" in fmt
    
    amt2, fmt2 = parse_and_normalize_mrp("120.00/-")
    assert amt2 == 120.00

    # Quantity normalization
    amt_q, unit_q, fmt_q = parse_and_normalize_quantity("Net Wt. 500 g")
    assert amt_q == 500.0
    assert unit_q == "g"

    amt_l, unit_l, fmt_l = parse_and_normalize_quantity("1.5 Litres")
    assert amt_l == 1.5
    assert unit_l == "l"

    # FSSAI normalization
    assert normalize_fssai("Lic. No. 10014011000123 / FSSAI") == "10014011000123"


def test_changed_mrp_detection():
    """Req 6: Changed MRP detection (delta amount, delta percent, direction UP/DOWN)."""
    # Price increase
    diff_up = compare_single_field("mrp", "Maximum Retail Price", "₹ 40.00", "₹ 50.00")
    assert diff_up.change_type == "CHANGED"
    assert diff_up.delta_info is not None
    assert diff_up.delta_info["amount_delta"] == 10.0
    assert diff_up.delta_info["percent_delta"] == 25.0

    # Price decrease
    diff_down = compare_single_field("mrp", "Maximum Retail Price", "Rs. 100.00", "Rs. 80.00")
    assert diff_down.change_type == "CHANGED"
    assert diff_down.delta_info is not None
    assert diff_down.delta_info["amount_delta"] == -20.0
    assert diff_down.delta_info["percent_delta"] == -20.0


def test_changed_quantity_detection():
    """Req 7: Changed quantity detection with unit and amount deltas."""
    diff = compare_single_field("net_quantity", "Net Quantity", "200 g", "250 g")
    assert diff.change_type == "CHANGED"
    assert diff.delta_info is not None
    assert diff.delta_info["amount_delta"] == 50.0
    assert diff.delta_info["unit"] == "g"


def test_changed_manufacturer_detection():
    """Req 8: Changed manufacturer entity detection."""
    diff_same = compare_single_field(
        "manufacturer",
        "Manufacturer Name & Address",
        "Britannia Industries Ltd, Bangalore",
        "Britannia Industries Ltd, Bangalore"
    )
    assert diff_same.change_type == "UNCHANGED"

    diff_changed = compare_single_field(
        "manufacturer",
        "Manufacturer Name & Address",
        "Britannia Industries Ltd, Bangalore",
        "ITC Limited, Kolkata, West Bengal"
    )
    assert diff_changed.change_type == "CHANGED"
    assert diff_changed.old_value == "Britannia Industries Ltd, Bangalore"
    assert diff_changed.new_value == "ITC Limited, Kolkata, West Bengal"


def test_changed_fssai_detection():
    """Req 9: Changed FSSAI number detection."""
    diff_same = compare_single_field("fssai_license", "FSSAI License", "Lic No 10014011000123", "10014011000123")
    assert diff_same.change_type == "UNCHANGED"

    diff_changed = compare_single_field("fssai_license", "FSSAI License", "10014011000123", "10019043000555")
    assert diff_changed.change_type == "CHANGED"
    assert diff_changed.old_normalized_value == "10014011000123"
    assert diff_changed.new_normalized_value == "10019043000555"


def test_added_and_removed_declaration_detection():
    """Req 4 & 5: Added and removed statutory declarations."""
    # Added declaration (None -> Present)
    diff_added = compare_single_field("consumer_care", "Consumer Care", None, "care@brand.com, 1800-111-222")
    assert diff_added.change_type == "ADDED"
    assert diff_added.new_value == "care@brand.com, 1800-111-222"

    # Removed declaration (Present -> None)
    diff_removed = compare_single_field("expiry_date", "Best Before / Expiry", "Use within 12 months", None)
    assert diff_removed.change_type == "REMOVED"
    assert diff_removed.old_value == "Use within 12 months"


def test_changed_ingredients_detection():
    """Req 10: Changed ingredients detection (added, removed, common, reordered)."""
    ing_a = "Refined Wheat Flour, Sugar, Palm Oil, Salt, Artificial Vanilla Flavor"
    ing_b = "Refined Wheat Flour, Sugar, Butter, Salt, Natural Vanilla Extract"

    diff = compare_ingredients(ing_a, ing_b)
    assert diff.status == "CHANGED"
    
    # Check added ingredients
    added_names = [i.lower() for i in diff.added_ingredients]
    assert any("butter" in n for n in added_names)
    assert any("natural vanilla extract" in n for n in added_names)

    # Check removed ingredients
    removed_names = [i.lower() for i in diff.removed_ingredients]
    assert any("palm oil" in n for n in removed_names)
    assert any("artificial vanilla flavor" in n for n in removed_names)

    # Check common ingredients
    common_names = [i.lower() for i in diff.common_ingredients]
    assert any("sugar" in n for n in common_names)
    assert any("salt" in n for n in common_names)


def test_changed_nutrition_detection():
    """Req 11: Changed nutrition information detection table diff."""
    nut_a = {"Energy": "450 kcal", "Protein": "5 g", "Carbohydrates": "65 g", "Added Sugar": "25 g", "Fat": "18 g"}
    nut_b = {"Energy": "420 kcal", "Protein": "7 g", "Carbohydrates": "60 g", "Added Sugar": "15 g", "Fat": "16 g"}

    diff = compare_nutrition(nut_a, nut_b)
    assert diff.status == "CHANGED"
    assert len(diff.nutrients) >= 4

    # Check energy delta
    energy_item = next((d for d in diff.nutrients if "energy" in d.nutrient_name.lower()), None)
    assert energy_item is not None
    assert energy_item.old_amount == 450.0
    assert energy_item.new_amount == 420.0
    assert energy_item.amount_delta == -30.0

    # Check protein delta
    protein_item = next((d for d in diff.nutrients if "protein" in d.nutrient_name.lower()), None)
    assert protein_item is not None
    assert protein_item.old_amount == 5.0
    assert protein_item.new_amount == 7.0
    assert protein_item.amount_delta == 2.0


# --------------------------------------------------------------------------
# Integration Tests: Engine Pipeline & Timeline
# --------------------------------------------------------------------------

def test_compliance_score_and_rule_comparison():
    """Req 12 & 13: Compliance score comparison & issue resolution tracking."""
    v1_checks = [
        ComplianceCheck(rule_id="LM-001", field="manufacturer", field_label="Manufacturer", required=True, detected=True, status="PASS", severity="critical"),
        ComplianceCheck(rule_id="LM-004", field="mrp", field_label="MRP", required=True, detected=False, status="FAIL", severity="critical"), # Failed in v1
        ComplianceCheck(rule_id="FS-001", field="fssai_license", field_label="FSSAI", required=True, detected=True, status="PASS", severity="critical"),
    ]
    v2_checks = [
        ComplianceCheck(rule_id="LM-001", field="manufacturer", field_label="Manufacturer", required=True, detected=True, status="PASS", severity="critical"),
        ComplianceCheck(rule_id="LM-004", field="mrp", field_label="MRP", required=True, detected=True, status="PASS", severity="critical"), # Fixed in v2
        ComplianceCheck(rule_id="FS-001", field="fssai_license", field_label="FSSAI", required=True, detected=False, status="FAIL", severity="critical"), # Regressed in v2
    ]

    snap_a = _make_snapshot(version_id="s1", version_label="v1", score=65.0, risk_level="HIGH", checks=v1_checks)
    snap_b = _make_snapshot(version_id="s2", version_label="v2", score=90.0, risk_level="LOW", checks=v2_checks)

    res = compare_versions(snap_a, snap_b)

    # Score comparison
    assert res.score_a == 65.0
    assert res.score_b == 90.0
    assert res.score_delta == 25.0
    assert res.risk_level_a == "HIGH"
    assert res.risk_level_b == "LOW"
    assert res.risk_shift == "IMPROVED"

    # Rule transitions
    mrp_rule = next(r for r in res.rule_diffs if r.rule_id == "LM-004")
    assert mrp_rule.transition_type == "FIXED"

    fssai_rule = next(r for r in res.rule_diffs if r.rule_id == "FS-001")
    assert fssai_rule.transition_type == "REGRESSED"

    # Issue resolutions
    resolved_issue = next((i for i in res.issue_resolutions if i.rule_id == "LM-004"), None)
    assert resolved_issue is not None
    assert resolved_issue.resolution_status == "RESOLVED"

    new_issue = next((i for i in res.issue_resolutions if i.rule_id == "FS-001"), None)
    assert new_issue is not None
    assert new_issue.resolution_status == "NEW_ISSUE"


@pytest.mark.asyncio
async def test_version_timeline_generation():
    """Req 14: Version timeline retrieval."""
    entity_id = "test_product_timeline_123"

    # Save multiple comparisons
    await save_version_comparison({
        "comparison_id": "cmp_1",
        "entity_id": entity_id,
        "entity_type": "PRODUCT",
        "version_a_id": "v1.0",
        "version_b_id": "v1.1",
        "version_a_label": "v1.0",
        "version_b_label": "v1.1",
        "score_a": 60.0,
        "score_b": 80.0,
        "delta_score": 20.0,
        "risk_a": "HIGH",
        "risk_b": "MEDIUM",
        "total_changes": 3,
        "resolved_issues_count": 2,
        "new_issues_count": 0,
        "summary": "Updated MRP and fixed consumer care declaration",
        "details": {}
    })

    await save_version_comparison({
        "comparison_id": "cmp_2",
        "entity_id": entity_id,
        "entity_type": "PRODUCT",
        "version_a_id": "v1.1",
        "version_b_id": "v2.0",
        "version_a_label": "v1.1",
        "version_b_label": "v2.0",
        "score_a": 80.0,
        "score_b": 98.0,
        "delta_score": 18.0,
        "risk_a": "MEDIUM",
        "risk_b": "LOW",
        "total_changes": 2,
        "resolved_issues_count": 1,
        "new_issues_count": 0,
        "summary": "Added FSSAI logo and corrected font size",
        "details": {}
    })

    timeline = await get_version_timeline(entity_id)
    assert len(timeline) >= 2
    assert any("v1.0" in event["version_id"] or "v2.0" in event["version_id"] or "v1.1" in event["version_id"] for event in timeline)


def test_deterministic_speed_under_20ms():
    """Non-functional Req: Deterministic comparison must execute under 20ms."""
    snap_a = _make_snapshot(version_id="perf_a", version_label="v1")
    snap_b = _make_snapshot(version_id="perf_b", version_label="v2", mrp="₹ 50.00", net_quantity="250 g")

    start_t = time.perf_counter()
    res = compare_versions(snap_a, snap_b)
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    assert res is not None
    assert elapsed_ms < 20.0  # Must be well under 20ms


# --------------------------------------------------------------------------
# API Endpoints Integration Tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_version_targets_and_compare_saved():
    """Test /api/versions/targets and /api/versions/compare with saved analysis."""
    await _ensure_test_user()
    # 1. Save two sample analyses in DB
    await save_analysis({
        "id": "ana_test_v1",
        "product_name": "Test Snack Pack",
        "image_filename": "snack_v1.jpg",
        "ocr_text": "Test Snack Pack MRP Rs 30 Net Wt 100g",
        "score": 70.0,
        "status": "PASS",
        "created_at": "2026-01-01T10:00:00Z",
        "extracted_data": {
            "product_name": "Test Snack Pack",
            "mrp": "₹30.00",
            "net_quantity": "100 g",
            "manufacturer": "Snack Co, Delhi",
            "fssai_license": "10014011000123"
        },
        "compliance_result": {
            "score": 70.0,
            "status": "FAIL",
            "total_rules": 2,
            "passed_rules": 1,
            "failed_rules": 1,
            "checks": [
                {"rule_id": "LM-001", "field": "manufacturer", "field_label": "Manufacturer", "required": True, "detected": True, "status": "PASS", "severity": "critical"},
                {"rule_id": "LM-004", "field": "mrp", "field_label": "MRP", "required": True, "detected": False, "status": "FAIL", "severity": "critical"}
            ]
        }
    })

    await save_analysis({
        "id": "ana_test_v2",
        "product_name": "Test Snack Pack",
        "image_filename": "snack_v2.jpg",
        "ocr_text": "Test Snack Pack MRP Rs 35 Net Wt 100g",
        "score": 95.0,
        "status": "PASS",
        "created_at": "2026-01-02T10:00:00Z",
        "extracted_data": {
            "product_name": "Test Snack Pack",
            "mrp": "₹35.00",
            "net_quantity": "100 g",
            "manufacturer": "Snack Co, Delhi",
            "fssai_license": "10014011000123"
        },
        "compliance_result": {
            "score": 95.0,
            "status": "PASS",
            "total_rules": 2,
            "passed_rules": 2,
            "failed_rules": 0,
            "checks": [
                {"rule_id": "LM-001", "field": "manufacturer", "field_label": "Manufacturer", "required": True, "detected": True, "status": "PASS", "severity": "critical"},
                {"rule_id": "LM-004", "field": "mrp", "field_label": "MRP", "required": True, "detected": True, "status": "PASS", "severity": "critical"}
            ]
        }
    })

    # 2. Get targets
    r_targets = client.get("/api/versions/targets", headers=AUTH_HEADERS)
    assert r_targets.status_code == 200
    targets_data = r_targets.json()
    assert "targets" in targets_data
    assert len(targets_data["targets"]) >= 2

    # 3. Compare them via API
    payload = {
        "version_a_id": "ana_test_v1",
        "version_b_id": "ana_test_v2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }

    r_compare = client.post("/api/versions/compare", json=payload, headers=AUTH_HEADERS)
    assert r_compare.status_code == 200
    res = r_compare.json()
    assert res["version_a"]["version_id"] == "ana_test_v1"
    assert res["version_b"]["version_id"] == "ana_test_v2"
    assert res["mrp_diff"] is not None
    assert res["mrp_diff"]["change_type"] == "CHANGED"
    assert res["comparison_id"] is not None

    # 4. Retrieve saved comparison
    cmp_id = res["comparison_id"]
    r_get = client.get(f"/api/versions/comparisons/{cmp_id}", headers=AUTH_HEADERS)
    assert r_get.status_code == 200
    assert r_get.json()["comparison_id"] == cmp_id

    # 5. List comparisons
    r_list = client.get("/api/versions/comparisons", headers=AUTH_HEADERS)
    assert r_list.status_code == 200
    assert len(r_list.json()["comparisons"]) >= 1


@pytest.mark.asyncio
async def test_api_timeline_endpoint():
    """Test /api/versions/timeline/{entity_id} endpoint."""
    await _ensure_test_user()
    entity_id = "test_timeline_entity_api"
    
    # Save a comparison
    await save_version_comparison({
        "comparison_id": "cmp_api_1",
        "entity_id": entity_id,
        "entity_type": "PRODUCT",
        "version_a_id": "v1.0",
        "version_b_id": "v2.0",
        "version_a_label": "v1.0",
        "version_b_label": "v2.0",
        "score_a": 50.0,
        "score_b": 90.0,
        "delta_score": 40.0,
        "risk_a": "CRITICAL",
        "risk_b": "LOW",
        "total_changes": 4,
        "resolved_issues_count": 3,
        "new_issues_count": 0,
        "summary": "Major statutory packaging overhaul",
        "details": {}
    })

    r_timeline = client.get(f"/api/versions/timeline/{entity_id}", headers=AUTH_HEADERS)
    assert r_timeline.status_code == 200
    timeline_res = r_timeline.json()
    assert "events" in timeline_res
    events = timeline_res["events"]
    assert len(events) >= 1
    assert any(e["event_type"] == "COMPARISON" for e in events)


def test_identical_versions_no_changes():
    """Req 3: Identical versions produce UNCHANGED with 0 delta and no diffs."""
    snap_a = _make_snapshot(version_id="id_a", version_label="v1.0")
    snap_b = _make_snapshot(version_id="id_b", version_label="v1.0")

    res = compare_versions(snap_a, snap_b)
    assert res.score_delta == 0.0
    assert res.risk_shift == "UNCHANGED"
    assert len(res.added_declarations) == 0
    assert len(res.removed_declarations) == 0
    assert len(res.changed_declarations) == 0
    assert res.ingredients_diff.status == "UNCHANGED"
    assert res.nutrition_diff.status == "UNCHANGED"


def test_ingredients_reordered_only():
    """Req 10: Ingredients reordering detection."""
    ing_a = "Sugar, Wheat Flour, Palm Oil, Salt"
    ing_b = "Wheat Flour, Sugar, Palm Oil, Salt"

    diff = compare_ingredients(ing_a, ing_b)
    assert diff.is_order_changed is True
    assert len(diff.added_ingredients) == 0
    assert len(diff.removed_ingredients) == 0


@pytest.mark.asyncio
async def test_artwork_iterations_and_cross_comparison():
    """Req 2 & 3: Compare artwork v1 vs v2 and artwork vs physical screening."""
    await _ensure_test_user()
    # 1. Save Artwork v1 and v2
    await save_artwork({
        "id": "art_test_v1",
        "filename": "butter_cookies_artwork_v1.pdf",
        "file_path": "/api/images/art_test_v1.pdf",
        "file_type": "PDF",
        "file_size": 10240,
        "page_count": 1,
        "workflow_status": "DRAFT",
        "iteration_number": 1,
        "parent_artwork_id": None,
        "owner_user_id": "designer_1",
        "created_at": "2026-01-01T10:00:00Z",
        "analysis_result": {
            "overall_score": 68.0,
            "product_info": {
                "product_name": "Butter Cookies",
                "mrp": "₹40.00",
                "net_quantity": "150 g",
                "manufacturer": "Cookie Corp, Mumbai",
                "fssai_license": "10014011000123"
            },
            "compliance_result": {
                "score": 68.0,
                "status": "FAIL",
                "total_rules": 2,
                "passed_rules": 1,
                "failed_rules": 1,
                "checks": [
                    {"rule_id": "LM-001", "field": "manufacturer", "field_label": "Manufacturer", "required": True, "detected": True, "status": "PASS", "severity": "critical"},
                    {"rule_id": "LM-004", "field": "mrp", "field_label": "MRP", "required": True, "detected": False, "status": "FAIL", "severity": "critical"}
                ]
            }
        }
    })

    await save_artwork({
        "id": "art_test_v2",
        "filename": "butter_cookies_artwork_v2.pdf",
        "file_path": "/api/images/art_test_v2.pdf",
        "file_type": "PDF",
        "file_size": 10240,
        "page_count": 1,
        "workflow_status": "APPROVED",
        "iteration_number": 2,
        "parent_artwork_id": "art_test_v1",
        "owner_user_id": "designer_1",
        "created_at": "2026-01-02T10:00:00Z",
        "analysis_result": {
            "overall_score": 96.0,
            "product_info": {
                "product_name": "Butter Cookies",
                "mrp": "₹45.00",
                "net_quantity": "150 g",
                "manufacturer": "Cookie Corp, Mumbai",
                "fssai_license": "10014011000123"
            },
            "compliance_result": {
                "score": 96.0,
                "status": "PASS",
                "total_rules": 2,
                "passed_rules": 2,
                "failed_rules": 0,
                "checks": [
                    {"rule_id": "LM-001", "field": "manufacturer", "field_label": "Manufacturer", "required": True, "detected": True, "status": "PASS", "severity": "critical"},
                    {"rule_id": "LM-004", "field": "mrp", "field_label": "MRP", "required": True, "detected": True, "status": "PASS", "severity": "critical"}
                ]
            }
        }
    })

    # Compare Artwork v1 vs v2
    r_art_comp = client.post("/api/versions/compare", json={
        "version_a_id": "art_test_v1",
        "version_b_id": "art_test_v2",
        "version_type_a": "ARTWORK",
        "version_type_b": "ARTWORK"
    }, headers=AUTH_HEADERS)
    assert r_art_comp.status_code == 200
    res_art = r_art_comp.json()
    assert res_art["score_delta"] == 28.0
    assert res_art["risk_shift"] == "IMPROVED"
    assert res_art["mrp_diff"]["change_type"] == "CHANGED"

    # Cross compare Artwork v2 vs Physical Screening ana_test_v1
    r_cross = client.post("/api/versions/compare", json={
        "version_a_id": "ana_test_v1",
        "version_b_id": "art_test_v2",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ARTWORK"
    }, headers=AUTH_HEADERS)
    assert r_cross.status_code == 200
    res_cross = r_cross.json()
    assert res_cross["version_a"]["version_type"] == "ANALYSIS"
    assert res_cross["version_b"]["version_type"] == "ARTWORK"


@pytest.mark.asyncio
async def test_error_handling_nonexistent_version():
    """Verify 404 is returned when comparing non-existent version IDs."""
    await _ensure_test_user()
    r = client.post("/api/versions/compare", json={
        "version_a_id": "non_existent_123",
        "version_b_id": "non_existent_456",
        "version_type_a": "ANALYSIS",
        "version_type_b": "ANALYSIS"
    }, headers=AUTH_HEADERS)
    assert r.status_code == 404

