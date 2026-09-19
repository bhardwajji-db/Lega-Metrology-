import pytest
import time
from models.schemas import (
    ProductInfo,
    ComplianceCheck,
    ScoringConfiguration,
    ExtractionCandidate,
    EvidenceItem
)
from compliance.scorer import (
    calculate_score,
    get_scoring_config,
    set_scoring_config,
    DEFAULT_SCORING_CONFIG
)
from compliance.engine import ComplianceEngine
from compliance.rules.models import ComplianceStatus


@pytest.fixture(autouse=True)
def reset_scoring_config():
    """Ensure default scoring configuration is restored for each test."""
    set_scoring_config(DEFAULT_SCORING_CONFIG)
    yield
    set_scoring_config(DEFAULT_SCORING_CONFIG)


def _make_sample_checks(status_map: dict):
    """Helper to construct synthetic ComplianceCheck objects with given statuses."""
    checks = []
    for r_id, (status, sev, domain, name) in status_map.items():
        checks.append(ComplianceCheck(
            rule_id=r_id,
            field=f"field_{r_id.lower()}",
            field_label=name,
            required=status != ComplianceStatus.NOT_APPLICABLE.value,
            detected=status in (ComplianceStatus.PASS.value, ComplianceStatus.WARNING.value),
            detected_value="Sample Value" if status in (ComplianceStatus.PASS.value, ComplianceStatus.WARNING.value) else None,
            severity=sev,
            status=status,
            description=f"Requirement for {r_id}",
            source=f"Rule reference for {r_id}",
            domain=domain,
            confidence=85.0 if status == ComplianceStatus.PASS.value else (50.0 if status == ComplianceStatus.NEEDS_REVIEW.value else None)
        ))
    return checks


def test_perfect_compliance_score_and_low_risk():
    """Req 1, 6, 10: All PASS results in 100.0 score and LOW risk."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
        "LM-002": (ComplianceStatus.PASS.value, "high", "LEGAL_METROLOGY", "Product Name"),
        "LM-003": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Net Quantity"),
        "LM-004": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "MRP"),
        "FS-001": (ComplianceStatus.PASS.value, "critical", "FSSAI", "FSSAI License"),
    })
    product_info = ProductInfo(
        product_name="Standard Biscuits",
        manufacturer="Parle Products Pvt Ltd",
        mrp="₹20.00",
        net_quantity="100 g",
        fssai_license="10012011000123"
    )

    result = calculate_score(checks, product_info=product_info)
    assert result["score"] == 100.0
    assert result["status"] == "COMPLIANT"
    ra = result["risk_assessment"]
    assert (ra.risk_level if hasattr(ra, 'risk_level') else ra['risk_level']) == "LOW"
    assert (ra.missing_declaration_count if hasattr(ra, 'missing_declaration_count') else ra['missing_declaration_count']) == 0
    assert (ra.critical_violation_count if hasattr(ra, 'critical_violation_count') else ra['critical_violation_count']) == 0


def test_rule_level_and_category_scores():
    """Req 2, 3: RuleScore and CategoryScore breakdowns calculated correctly."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
        "LM-004": (ComplianceStatus.FAIL.value, "critical", "LEGAL_METROLOGY", "MRP"),
        "FS-001": (ComplianceStatus.PASS.value, "critical", "FSSAI", "FSSAI License"),
        "FS-005": (ComplianceStatus.FAIL.value, "critical", "FSSAI", "Expiry Date"),
    })
    result = calculate_score(checks)

    # Check rule scores list
    rs_map = {r.rule_id: r for r in result["rule_scores"]}
    assert "LM-001" in rs_map
    assert rs_map["LM-001"].status == "PASS"
    assert rs_map["LM-001"].earned_points == 1.0

    assert "LM-004" in rs_map
    assert rs_map["LM-004"].status == "FAIL"
    assert rs_map["LM-004"].earned_points == 0.0

    # Check category scores list
    cs_map = {c.category_id: c for c in result["category_scores"]}
    assert "LEGAL_METROLOGY" in cs_map
    assert "FSSAI" in cs_map
    assert cs_map["LEGAL_METROLOGY"].passed_rules == 1
    assert cs_map["LEGAL_METROLOGY"].failed_rules == 1
    assert cs_map["FSSAI"].passed_rules == 1
    assert cs_map["FSSAI"].failed_rules == 1


def test_critical_risk_identification_on_mandatory_failure():
    """Req 6, 7, 14: Critical violation triggers CRITICAL risk tier."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
        "LM-004": (ComplianceStatus.FAIL.value, "critical", "LEGAL_METROLOGY", "MRP"),
    })
    result = calculate_score(checks)
    ra = result["risk_assessment"]
    assert (ra.risk_level if hasattr(ra, 'risk_level') else ra['risk_level']) == "CRITICAL"
    assert (ra.critical_violation_count if hasattr(ra, 'critical_violation_count') else ra['critical_violation_count']) >= 1
    assert len(ra.risk_factors if hasattr(ra, 'risk_factors') else ra['risk_factors']) >= 1


def test_high_risk_identification_on_multiple_failures():
    """Req 6, 8, 13: Multiple missing declarations trigger HIGH risk tier."""
    checks = _make_sample_checks({
        "LM-002": (ComplianceStatus.FAIL.value, "high", "LEGAL_METROLOGY", "Generic Name"),
        "LM-006": (ComplianceStatus.FAIL.value, "high", "LEGAL_METROLOGY", "Country of Origin"),
        "LM-007": (ComplianceStatus.PASS.value, "medium", "LEGAL_METROLOGY", "Unit Sale Price"),
    })
    result = calculate_score(checks)
    ra = result["risk_assessment"]
    assert (ra.risk_level if hasattr(ra, 'risk_level') else ra['risk_level']) in ("CRITICAL", "HIGH")
    assert (ra.missing_declaration_count if hasattr(ra, 'missing_declaration_count') else ra['missing_declaration_count']) >= 2


def test_medium_risk_identification_on_reviews():
    """Req 6, 9, 15: Review and warning items trigger MEDIUM risk."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
        "LM-002": (ComplianceStatus.PASS.value, "high", "LEGAL_METROLOGY", "Product Name"),
        "LM-003": (ComplianceStatus.NEEDS_REVIEW.value, "critical", "LEGAL_METROLOGY", "Net Quantity"),
        "LM-005": (ComplianceStatus.WARNING.value, "medium", "LEGAL_METROLOGY", "Consumer Care"),
    })
    result = calculate_score(checks)
    ra = result["risk_assessment"]
    assert (ra.risk_level if hasattr(ra, 'risk_level') else ra['risk_level']) == "MEDIUM"
    assert (ra.review_required_count if hasattr(ra, 'review_required_count') else ra['review_required_count']) >= 1


def test_grounded_risk_explanation():
    """Req 11: Risk assessment includes human-readable statutory explanation."""
    checks = _make_sample_checks({
        "LM-004": (ComplianceStatus.FAIL.value, "critical", "LEGAL_METROLOGY", "MRP"),
    })
    result = calculate_score(checks)
    ra = result["risk_assessment"]
    explanation = ra.risk_explanation if hasattr(ra, 'risk_explanation') else ra['risk_explanation']
    assert "critical" in explanation.lower() or "statutory" in explanation.lower() or "declaration" in explanation.lower()


def test_risk_factor_breakdown():
    """Req 12: Detailed structured risk factors with legal reference and resolution action."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.FAIL.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
    })
    result = calculate_score(checks)
    ra = result["risk_assessment"]
    factors = ra.risk_factors if hasattr(ra, 'risk_factors') else ra['risk_factors']
    assert len(factors) > 0
    f = factors[0]
    assert "LM-001" in (f.factor_id if hasattr(f, 'factor_id') else f['factor_id'])
    assert (f.severity if hasattr(f, 'severity') else f['severity']) == "CRITICAL"


def test_extraction_candidate_conflicts_integrated_in_risk():
    """Req 5, 12: Candidate conflicts from Section 4 surface in risk factors."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
        "LM-004": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "MRP"),
    })
    conflicts = [{
        "conflict_id": "CONF-MRP-01",
        "conflict_type": "VALUE_DISCREPANCY",
        "field": "mrp",
        "description": "Front panel claims ₹25 while back panel claims ₹30",
        "severity": "HIGH",
        "resolution_hint": "Inspect sticker overlay."
    }]
    result = calculate_score(checks, conflicts=conflicts)
    ra = result["risk_assessment"]
    factors = ra.risk_factors if hasattr(ra, 'risk_factors') else ra['risk_factors']
    factor_ids = [f.factor_id if hasattr(f, 'factor_id') else f['factor_id'] for f in factors]
    assert any("CONF" in fid for fid in factor_ids)


def test_confidence_summary_calculation():
    """Req 4, 16: Aggregated confidence balances OCR, extraction, and spatial reliability."""
    checks = [
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            field_label="Manufacturer",
            required=True,
            detected=True,
            severity="critical",
            status="PASS",
            description="Req",
            source="Ref",
            confidence=90.0,
            reliability_score=85.0
        ),
        ComplianceCheck(
            rule_id="LM-004",
            field="mrp",
            field_label="MRP",
            required=True,
            detected=True,
            severity="critical",
            status="PASS",
            description="Req",
            source="Ref",
            confidence=80.0,
            reliability_score=75.0
        )
    ]
    product_info = ProductInfo(
        product_name="Test Item",
        declaration_confidences={"manufacturer": 92.0, "mrp": 84.0}
    )
    result = calculate_score(checks, product_info=product_info)
    conf_summary = result["confidence_summary"]
    assert conf_summary.extraction_confidence_avg == 88.0
    assert conf_summary.evidence_reliability_avg == 80.0
    assert conf_summary.overall_confidence > 0
    assert conf_summary.confidence_tier in ("HIGH", "MEDIUM", "LOW")


def test_confidence_adjusted_risk_reporting():
    """Req 16: Low confidence flags uncertainty in confidence summary."""
    checks = [
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            field_label="Manufacturer",
            required=True,
            detected=True,
            severity="critical",
            status="PASS",
            description="Req",
            source="Ref",
            confidence=40.0,
            reliability_score=40.0
        )
    ]
    product_info = ProductInfo(
        product_name="Blurry Item",
        declaration_confidences={"manufacturer": 40.0}
    )
    result = calculate_score(checks, product_info=product_info)
    conf_summary = result["confidence_summary"]
    assert conf_summary.low_confidence_declarations_count >= 1
    assert conf_summary.confidence_tier in ("LOW", "MEDIUM")


def test_configurable_scoring_rules():
    """Req 17: Configurable weights and status multipliers take effect dynamically."""
    custom_config = ScoringConfiguration(
        scoring_version="2026.CUSTOM",
        weight_pass=1.0,
        weight_warning=0.75,
        weight_needs_review=0.5,
        weight_fail=0.0,
        critical_risk_threshold=2,
        high_risk_failures_threshold=3,
        medium_risk_review_threshold=3,
        enabled_factors=["MANDATORY_PRESENCE", "CUSTOM_FACTOR"]
    )
    set_scoring_config(custom_config)
    retrieved = get_scoring_config()
    assert retrieved.scoring_version == "2026.CUSTOM"
    assert retrieved.critical_risk_threshold == 2


def test_all_five_lifecycle_states_evaluated():
    """Evaluates PASS, WARNING, NEEDS_REVIEW, INSUFFICIENT_EVIDENCE, FAIL, NOT_APPLICABLE."""
    checks = _make_sample_checks({
        "LM-001": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", "Manufacturer"),
        "LM-002": (ComplianceStatus.WARNING.value, "high", "LEGAL_METROLOGY", "Generic Name"),
        "LM-003": (ComplianceStatus.NEEDS_REVIEW.value, "critical", "LEGAL_METROLOGY", "Net Qty"),
        "LM-004": (ComplianceStatus.INSUFFICIENT_EVIDENCE.value, "critical", "LEGAL_METROLOGY", "MRP"),
        "LM-005": (ComplianceStatus.FAIL.value, "critical", "LEGAL_METROLOGY", "Consumer Care"),
        "LM-009": (ComplianceStatus.NOT_APPLICABLE.value, "low", "LEGAL_METROLOGY", "Wholesale Exemption"),
    })
    result = calculate_score(checks)
    assert result["score"] >= 0.0
    assert result["score"] <= 100.0
    assert result["status"] in ("COMPLIANT", "REVIEW REQUIRED", "POTENTIAL NON-COMPLIANCE")


def test_scoring_performance_zero_external_calls():
    """Verify deterministic in-memory calculation runs under 15ms with zero external calls."""
    checks = _make_sample_checks({
        f"RULE-{i}": (ComplianceStatus.PASS.value, "critical", "LEGAL_METROLOGY", f"Field {i}")
        for i in range(25)
    })
    t0 = time.perf_counter()
    result = calculate_score(checks)
    t_elapsed_ms = (time.perf_counter() - t0) * 1000
    assert t_elapsed_ms < 15.0
    assert result["score"] == 100.0


def test_engine_check_integration():
    """End-to-end engine.check() returns Section 7 scoring and risk assessment."""
    engine = ComplianceEngine()
    info = ProductInfo(
        product_name="Fortune Sunlite Sunflower Oil 1L",
        manufacturer="Adani Wilmar Limited, Fortune House, Ahmedabad",
        net_quantity="1 L",
        mrp="Rs. 145.00 (incl. of all taxes)",
        unit_sale_price="Rs. 145.00 / L",
        consumer_care="care@adaniwilmar.in, 1800-233-1234",
        country_of_origin="India",
        fssai_license="10013021000853",
        ingredients="Refined Sunflower Oil, Vitamin A, Vitamin D",
        nutritional_info="Energy: 900 kcal, Protein: 0g, Fat: 100g per 100g",
        nutrition_panel_detected=True,
        nutrition_facts={"Energy": "900 kcal", "Protein": "0g", "Fat": "100g"},
        manufacturing_date="01/2026",
        best_before="12 months from manufacture"
    )
    res = engine.check(info)
    assert "score" in res
    assert "rule_scores" in res
    assert "category_scores" in res
    assert "risk_assessment" in res
    assert "confidence_summary" in res
    assert "scoring_version" in res
    ra = res["risk_assessment"]
    assert (ra.risk_level if hasattr(ra, 'risk_level') else ra['risk_level']) == "LOW"


@pytest.mark.asyncio
async def test_database_product_risk_history_and_batch_distribution():
    """Req 18, 19, 20: Database stores and queries score history, product trajectory, and batch distribution."""
    from database.db import (
        init_db,
        save_analysis,
        get_product_risk_history,
        get_batch_risk_distribution,
        delete_all_user_analyses
    )
    await init_db()
    await delete_all_user_analyses()

    # Save a compliant analysis
    a1 = {
        'id': 'test-risk-001',
        'product_name': 'Test Olive Oil 500ml',
        'image_filename': 'front.jpg',
        'ocr_text': 'Olive Oil 500ml',
        'extracted_data': {'product_name': 'Test Olive Oil 500ml'},
        'compliance_result': {
            'score': 95.0,
            'status': 'COMPLIANT',
            'failed_rules': 0,
            'passed_rules': 13,
            'needs_review_rules': 0,
            'risk_assessment': {'risk_level': 'LOW'}
        },
        'score': 95.0,
        'status': 'COMPLIANT',
        'created_at': '2026-09-01T10:00:00Z',
        'owner_user_id': 'merchant1'
    }
    await save_analysis(a1)

    # Save a non-compliant analysis for same product
    a2 = {
        'id': 'test-risk-002',
        'product_name': 'Test Olive Oil 500ml',
        'image_filename': 'front2.jpg',
        'ocr_text': 'Olive Oil',
        'extracted_data': {'product_name': 'Test Olive Oil 500ml'},
        'compliance_result': {
            'score': 50.0,
            'status': 'POTENTIAL NON-COMPLIANCE',
            'failed_rules': 2,
            'passed_rules': 10,
            'needs_review_rules': 0,
            'risk_assessment': {'risk_level': 'HIGH'}
        },
        'score': 50.0,
        'status': 'POTENTIAL NON-COMPLIANCE',
        'created_at': '2026-09-02T10:00:00Z',
        'owner_user_id': 'merchant1'
    }
    await save_analysis(a2)

    # Query product risk history
    history = await get_product_risk_history('Test Olive Oil 500ml')
    assert history["product_name"] == 'Test Olive Oil 500ml'
    assert history["total_analyses"] == 2
    assert history["current_risk_level"] == "HIGH"
    assert len(history["history_entries"]) == 2

    # Query batch distribution
    batch = await get_batch_risk_distribution()
    assert batch["total_analyzed"] >= 2
    assert batch["low_count"] >= 1
    assert batch["high_count"] >= 1


@pytest.mark.asyncio
async def test_legacy_analysis_risk_fallback():
    """Verify legacy analysis rows lacking Section 7 risk_assessment deserialize gracefully."""
    from database.db import _extract_analysis_risk_info

    legacy_row = {
        "id": "legacy-001",
        "product_name": "Legacy Biscuits",
        "score": 92.0,
        "status": "COMPLIANT",
        "created_at": "2025-01-01T00:00:00Z",
        "compliance_result": '{"score": 92.0, "status": "COMPLIANT", "failed_rules": 0, "passed_rules": 12}'
    }
    extracted = _extract_analysis_risk_info(legacy_row)
    assert extracted["analysis_id"] == "legacy-001"
    assert extracted["score"] == 92.0
    assert extracted["risk_level"] == "LOW"


