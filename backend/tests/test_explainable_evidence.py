"""
Comprehensive test suite for Master Roadmap Section 5: Explainable AI / Evidence System.
Tests traceability metadata, deterministic explanations, reliability scoring,
spatial heatmaps, officer correction/review actions, and immutable audit logs.
"""

import pytest
import asyncio
from compliance.engine import ComplianceEngine
from compliance.evidence_locator import (
    locate_evidence_for_rule,
    compute_evidence_heatmap,
    get_panel_compliance_summary,
    _compute_reliability,
)
from models.schemas import (
    ProductInfo,
    OCRResult,
    OCRWord,
    ComplianceCheck,
    EvidenceItem,
    ProductImageEvidence,
    EvidenceCorrectionRequest,
    EvidenceReviewActionRequest,
)
from database.db import (
    init_db,
    save_evidence_audit_log,
    get_evidence_audit_logs,
    save_analysis,
    get_analysis,
    update_analysis_compliance_evidence,
)


@pytest.mark.asyncio
async def test_traceability_and_grounded_explanations():
    """Verify that compliance checks produce grounded, deterministic pass/fail/review explanations with traceability."""
    engine = ComplianceEngine()
    
    # Test Passing Product
    prod = ProductInfo(
        product_name="Atta Whole Wheat",
        manufacturer="ITC Limited, Kolkata, West Bengal",
        net_quantity="5 kg",
        mrp="Rs. 250.00",
        consumer_care="1800-123-4567, care@itc.in",
        country_of_origin="India",
        date_of_manufacture="01/2025",
        field_status={"product_name": "PRESENT", "net_quantity": "PRESENT", "mrp": "PRESENT"},
    )
    res = engine.check(prod, ocr_text="ITC Limited, Kolkata, West Bengal\nAtta Whole Wheat\n5 kg\nRs. 250.00")
    checks = res["checks"]

    # Verify LM-001 has grounded pass explanation and regulation reference
    lm001 = next(c for c in checks if c.rule_id == "LM-001")
    assert lm001.status == "PASS"
    assert lm001.pass_reason is not None
    assert "ITC Limited" in lm001.pass_reason
    assert "Rule 6(1)(a)" in lm001.regulation_reference
    assert lm001.linked_field in ["manufacturer", "manufacturer_name_and_address"]

    # Verify LM-002 has grounded pass explanation
    lm002 = next(c for c in checks if c.rule_id == "LM-002")
    assert lm002.status == "PASS"
    assert lm002.pass_reason is not None
    assert "Atta Whole Wheat" in lm002.pass_reason

    # Verify LM-003 has grounded net quantity explanation
    lm003 = next(c for c in checks if c.rule_id == "LM-003")
    assert lm003.status == "PASS"
    assert "5 kg" in (lm003.pass_reason or "")

    # Test Failing Product (Missing declarations)
    failing_prod = ProductInfo(
        product_name=None,
        manufacturer=None,
        net_quantity=None,
        mrp=None,
        country_of_origin=None,
    )
    fail_res = engine.check(failing_prod, ocr_text="")
    fail_checks = fail_res["checks"]

    lm003_fail = next(c for c in fail_checks if c.rule_id == "LM-003")
    assert lm003_fail.status == "FAIL"
    assert lm003_fail.fail_reason is not None
    assert "Non-Compliance" in lm003_fail.fail_reason
    assert "Net quantity declaration was not detected" in lm003_fail.fail_reason

    lm001_check = next(c for c in fail_checks if c.rule_id == "LM-001")
    assert lm001_check.status in ["FAIL", "NEEDS_REVIEW"]
    assert (lm001_check.review_reason or lm001_check.fail_reason) is not None


def test_reliability_scoring_tiers():
    """Verify reliability tier classification and score calculation."""
    # Direct high-confidence OCR match
    rel_high, tier_high = _compute_reliability(
        match_method="DIRECT_OCR",
        confidence=95.0,
        evidence_status="VERIFIED",
    )
    assert rel_high >= 80.0
    assert tier_high == "HIGH"

    # Contextual regex match with lower confidence
    rel_med, tier_med = _compute_reliability(
        match_method="CONTEXTUAL_OCR",
        confidence=70.0,
        evidence_status="CONTEXTUAL",
    )
    assert tier_med in ["HIGH", "MEDIUM", "LOW"]

    # Uncertain / Ambiguous
    rel_low, tier_low = _compute_reliability(
        match_method="SEMANTIC_PANEL",
        confidence=40.0,
        evidence_status="NEEDS_REVIEW",
    )
    assert rel_low <= 65.0
    assert tier_low in ["LOW", "NEEDS_VERIFICATION", "MEDIUM"]


def test_spatial_heatmap_generation():
    """Verify compute_evidence_heatmap outputs structured coordinate data."""
    images = [
        ProductImageEvidence(
            label="Front",
            image_index=0,
            filename="front.jpg",
            image_url="http://localhost/front.jpg",
            words=[
                OCRWord(text="Flour", confidence=95.0, bbox=[50, 50, 200, 90])
            ]
        )
    ]
    compliance_checks = [
        ComplianceCheck(
            rule_id="LM-002",
            field="product_name",
            field_label="Common / Generic Name",
            required=True,
            detected=True,
            detected_value="Wheat Flour",
            severity="HIGH",
            status="PASS",
            description="Generic Name",
            source="Rule 6(1)(b)",
            explanation="Verified",
            recommendation=None,
            evidence=[
                EvidenceItem(
                    id="LM-002-ev-1",
                    image_index=0,
                    image_label="Front",
                    text="Wheat Flour",
                    bbox=[50, 50, 200, 90],
                    confidence=95.0,
                    evidence_status="VERIFIED",
                )
            ]
        )
    ]

    heatmaps = compute_evidence_heatmap(images, compliance_checks, analysis_id="test-123")
    assert len(heatmaps) == 1
    assert heatmaps[0]["image_label"] == "Front"
    assert heatmaps[0]["total_tokens"] > 0
    assert len(heatmaps[0]["points"]) > 0


def test_panel_compliance_summary():
    """Verify get_panel_compliance_summary properly partitions front and back panel compliance."""
    checks = [
        ComplianceCheck(
            rule_id="LM-002",
            field="product_name",
            field_label="Common Name",
            required=True,
            detected=True,
            detected_value="Flour",
            severity="HIGH",
            status="PASS",
            description="Common Name",
            source="Rule 6(1)(b)",
            explanation=None,
            recommendation=None,
        ),
        ComplianceCheck(
            rule_id="LM-001",
            field="manufacturer",
            field_label="Manufacturer",
            required=True,
            detected=False,
            detected_value=None,
            severity="HIGH",
            status="FAIL",
            description="Manufacturer",
            source="Rule 6(1)(a)",
            explanation=None,
            recommendation=None,
        ),
    ]

    summary = get_panel_compliance_summary(checks, analysis_id="test-123")
    assert "panels" in summary
    assert len(summary["panels"]) == 2
    assert summary["overall_status"] == "FAIL"


@pytest.mark.asyncio
async def test_evidence_audit_logs_and_review_workflow():
    """Verify database audit logs record immutable timestamps, roles, reasons, and actions."""
    await init_db()
    test_id = "test_analysis_explainable_001"

    mock_analysis_data = {
        "id": test_id,
        "product_name": "Sample Tea",
        "image_filename": "tea.jpg",
        "ocr_text": "Sample Tea Co\n250 g",
        "extracted_data": {
            "product_name": "Sample Tea",
            "manufacturer": "Sample Tea Co",
            "net_quantity": "250 g",
        },
        "compliance_result": {
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "manufacturer",
                    "status": "PASS",
                    "description": "Manufacturer declaration",
                    "required": True,
                    "detected": True,
                }
            ],
            "score": 100.0,
            "status": "COMPLIANT",
        },
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-17T12:00:00",
        "images": [],
        "owner_user_id": "officer_042",
    }
    await save_analysis(mock_analysis_data)

    # 1. Record Audit Log for Officer Correction
    await save_evidence_audit_log(
        analysis_id=test_id,
        evidence_id="LM-001-ev-1",
        rule_id="LM-001",
        actor_username="officer_042",
        action_type="CORRECTION",
        previous_value="Sample Tea Co",
        new_value="Sample Tea Co Ltd, Assam",
        comments="Address clarification from secondary packaging",
    )

    # 2. Record Review Action Log
    await save_evidence_audit_log(
        analysis_id=test_id,
        evidence_id="LM-001-ev-1",
        rule_id="LM-001",
        actor_username="supervisor_007",
        action_type="APPROVE",
        previous_value="REVIEW",
        new_value="PASS",
        comments="Verified physical stamp",
    )

    # 3. Retrieve and Validate Audit Logs
    logs = await get_evidence_audit_logs(test_id)
    assert len(logs) >= 2

    correction_log = next(l for l in logs if l["action_type"] == "CORRECTION")
    assert correction_log["actor_username"] == "officer_042"
    assert correction_log["previous_value"] == "Sample Tea Co"
    assert correction_log["new_value"] == "Sample Tea Co Ltd, Assam"
    assert "Address clarification" in correction_log["comments"]
    assert "created_at" in correction_log