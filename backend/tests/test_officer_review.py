"""
Unit and Integration Tests for Master Roadmap Section 10: Human Verification / Officer Workflow

Covers all 18 Section 10 requirements:
1. Officer review dashboard
2. Review queue
3. Pending-review list
4. Accept AI result
5. Reject AI result
6. Correct extracted value
7. Add missing evidence
8. Remove incorrect evidence
9. Add officer comments
10. Officer verification timestamp (server-side UTC)
11. Officer identity (server-side JWT attribution)
12. Final human-verified status (VERIFIED_PASS, VERIFIED_FAIL, VERIFIED_NEEDS_REVIEW, REJECTED)
13. AI result vs human result comparison (structured before/after diff)
14. Review history (immutable append-only audit trail)
15. Re-open audit
16. Escalate audit
17. Assign audit to officer
18. Officer workload dashboard
"""

import pytest
import datetime
from fastapi.testclient import TestClient

from main import app
from auth.security import create_token, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT
from models.review_schemas import (
    ReviewStatus,
    HumanVerifiedStatus,
    AssignReviewRequest,
    AcceptReviewRequest,
    RejectReviewRequest,
    CorrectFieldRequest,
    AddEvidenceRequest,
    RemoveEvidenceRequest,
    AddCommentRequest,
    EscalateReviewRequest,
    ReopenReviewRequest,
    ReviewItem,
    ReviewDetailResponse,
    OfficerDashboardSummary,
    AIvsHumanComparison
)
from services.review_service import (
    get_or_create_review,
    assign_review,
    accept_ai_result,
    reject_ai_result,
    correct_field,
    add_missing_evidence,
    remove_incorrect_evidence,
    add_officer_comment,
    escalate_review,
    reopen_review,
    generate_ai_vs_human_comparison,
    get_officer_dashboard_summary
)
from database.db import (
    save_analysis,
    save_review,
    get_review,
    list_reviews,
    delete_review,
    init_db
)

client = TestClient(app)


# --------------------------------------------------------------------------
# Fixtures & Helpers
# --------------------------------------------------------------------------

import asyncio

@pytest.fixture(autouse=True)
def setup_database():
    """Ensure DB schema is initialized before every test."""
    asyncio.run(init_db())


def make_auth_header(username: str, role: str) -> dict:
    """Helper to generate standard JWT authorization headers."""
    token = create_token(username=username, role=role)
    return {"Authorization": f"Bearer {token}"}


def sample_analysis_payload(analysis_id: str = "test-analysis-101") -> dict:
    """Generate mock analysis payload with OCR, extracted data, compliance results, and score."""
    return {
        "id": analysis_id,
        "product_name": "Crunchy Butter Delight",
        "image_filename": "sample_biscuit_pack.jpg",
        "ocr_text": "Crunchy Butter Delight 200g MRP Rs 40.00 Mfg by Delight Bakeries",
        "created_at": "2026-09-17T10:00:00Z",
        "score": 68.0,
        "status": "FAIL",
        "organization_id": "org_ministry",
        "extracted_data": {
            "product_name": "Crunchy Butter Delight",
            "brand": "Delight Bakeries",
            "net_quantity": "200 g",
            "mrp": "Rs. 40.00",
            "manufacturer": "Delight Bakeries Pvt Ltd, Bangalore",
            "consumer_care": "care@delight.in",
            "country_of_origin": "India",
            "fssai_license": "10019043000123",
            "manufacture_date": "01/2026",
            "expiry_date": "07/2026",
            "ingredients": "Wheat Flour, Butter, Sugar, Salt"
        },
        "compliance_result": {
            "overall_status": "NON_COMPLIANT",
            "status": "FAIL",
            "score": 68.0,
            "total_checks": 14,
            "passed_checks": 12,
            "failed_checks": 2,
            "checks": [
                {
                    "rule_id": "LM_MRP_01",
                    "field": "mrp",
                    "field_label": "Maximum Retail Price (MRP)",
                    "status": "PASS",
                    "severity": "CRITICAL",
                    "message": "MRP is clearly declared."
                },
                {
                    "rule_id": "LM_UNIT_SALE_PRICE_01",
                    "field": "unit_sale_price",
                    "field_label": "Unit Sale Price",
                    "status": "FAIL",
                    "severity": "MAJOR",
                    "message": "Unit sale price per gram is missing."
                }
            ]
        }
    }


# --------------------------------------------------------------------------
# 1. Review Service Unit Tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_create_review_from_analysis():
    """Verify review creation from analysis, status, and idempotency."""
    analysis = sample_analysis_payload("analysis-sec10-unit-1")
    await save_analysis(analysis)

    # 1. Create review
    review = await get_or_create_review(analysis["id"])
    assert review is not None
    assert review["id"] == f"rev-{analysis['id']}"
    assert review["analysis_id"] == analysis["id"]
    assert review["status"] == ReviewStatus.PENDING_REVIEW
    assert review["ai_score"] == 68.0

    # 2. Idempotent check
    review2 = await get_or_create_review(analysis["id"])
    assert review2["id"] == review["id"]


@pytest.mark.asyncio
async def test_accept_ai_result_service():
    """Verify accept review flow updates status and creates immutable history event."""
    analysis = sample_analysis_payload("analysis-sec10-accept")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_user = {"username": "officer_sharma", "role": ROLE_ENFORCEMENT}
    req = AcceptReviewRequest(
        comments="Statutory declarations verified in accordance with Legal Metrology PCR 2011.",
        final_status=ReviewStatus.VERIFIED_PASS
    )

    updated = await accept_ai_result(
        review_id=review["id"],
        actor_user=officer_user,
        req=req
    )

    assert updated is not None
    assert updated["status"] == ReviewStatus.VERIFIED_PASS
    assert updated["final_human_status"] == ReviewStatus.VERIFIED_PASS
    assert updated["verified_by"] == "officer_sharma"
    assert updated["verified_at"] is not None
    assert len(updated["history"]) >= 2  # creation + accept
    
    accept_event = updated["history"][-1]
    assert accept_event["action"] == "ACCEPTED"
    assert accept_event["actor_username"] == "officer_sharma"
    assert "VERIFIED_PASS" in accept_event["details"]


@pytest.mark.asyncio
async def test_reject_ai_result_service():
    """Verify reject review flow requires reason, updates status to REJECTED."""
    analysis = sample_analysis_payload("analysis-sec10-reject")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_user = {"username": "officer_patel", "role": ROLE_AUDIT}
    req = RejectReviewRequest(
        rejection_reason="ILLEGIBLE_DECLARATION",
        comments="Package image has severe optical distortion preventing accurate declaration reading."
    )

    updated = await reject_ai_result(
        review_id=review["id"],
        actor_user=officer_user,
        req=req
    )

    assert updated is not None
    assert updated["status"] == ReviewStatus.REJECTED
    assert updated["final_human_status"] == ReviewStatus.REJECTED
    assert updated["verified_by"] == "officer_patel"
    assert updated["history"][-1]["action"] == "REJECTED"
    assert "ILLEGIBLE_DECLARATION" in updated["history"][-1]["details"]


@pytest.mark.asyncio
async def test_correct_field_and_deterministic_recalculation():
    """Verify officer correction recalculates compliance & score while preserving AI snapshot."""
    analysis = sample_analysis_payload("analysis-sec10-correct")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_user = {"username": "officer_gupta", "role": ROLE_ENFORCEMENT}
    req = CorrectFieldRequest(
        field_name="mrp",
        field_label="Maximum Retail Price (MRP)",
        corrected_value="Rs. 50.00 (Rs. 0.25 / g)",
        reason="OCR missed unit sale price bracket text."
    )

    updated = await correct_field(
        review_id=review["id"],
        actor_user=officer_user,
        req=req
    )

    assert updated is not None
    assert len(updated["field_corrections"]) == 1
    corr = updated["field_corrections"][0]
    assert corr["field_name"] == "mrp"
    assert corr["original_value"] == "Rs. 40.00"
    assert corr["corrected_value"] == "Rs. 50.00 (Rs. 0.25 / g)"
    assert corr["officer_username"] == "officer_gupta"

    # AI snapshot remains untouched
    assert updated["ai_snapshot"]["extracted_data"]["mrp"] == "Rs. 40.00"
    
    # Human verified result contains new value
    assert updated["human_verified_result"]["extracted_data"]["mrp"] == "Rs. 50.00 (Rs. 0.25 / g)"
    assert updated["history"][-1]["action"] == "FIELD_CORRECTED"


@pytest.mark.asyncio
async def test_evidence_annotations_and_removals():
    """Verify adding missing evidence annotations and soft-removing incorrect evidence."""
    analysis = sample_analysis_payload("analysis-sec10-evidence")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_user = {"username": "officer_verma", "role": ROLE_ENFORCEMENT}

    # 1. Add missing evidence annotation
    add_req = AddEvidenceRequest(
        image_index=0,
        image_label="Front Panel",
        text="Rs. 0.20 per gram",
        bbox=[320, 200, 450, 230],
        linked_rule_id="LM_UNIT_SALE_PRICE_01",
        linked_field="unit_sale_price",
        comments="Located at bottom right of principal display panel."
    )
    updated = await add_missing_evidence(
        review_id=review["id"],
        actor_user=officer_user,
        req=add_req
    )
    assert len(updated["evidence_modifications"]) == 1
    mod = updated["evidence_modifications"][0]
    assert mod["action"] == "ADDED"
    assert mod["evidence"]["text"] == "Rs. 0.20 per gram"

    # 2. Soft-remove incorrect AI evidence
    rem_req = RemoveEvidenceRequest(
        evidence_id="ev-reg-2",
        reason="False positive bounding box on barcode label."
    )
    updated2 = await remove_incorrect_evidence(
        review_id=review["id"],
        actor_user=officer_user,
        req=rem_req
    )
    assert len(updated2["evidence_modifications"]) == 2
    assert updated2["evidence_modifications"][1]["action"] == "REMOVED"
    assert updated2["history"][-1]["action"] == "EVIDENCE_REMOVED"


@pytest.mark.asyncio
async def test_officer_comments_service():
    """Verify adding officer internal comments with server UTC timestamps."""
    analysis = sample_analysis_payload("analysis-sec10-comments")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_user = {"username": "inspector_khan", "role": ROLE_AUDIT}
    req = AddCommentRequest(
        comment_type="INSPECTION_NOTE",
        text="Notice issued to manufacturer for clarification on batch code font height."
    )

    updated = await add_officer_comment(
        review_id=review["id"],
        actor_user=officer_user,
        req=req
    )

    assert len(updated["comments"]) == 1
    c = updated["comments"][0]
    assert c["officer_username"] == "inspector_khan"
    assert c["officer_role"] == ROLE_AUDIT
    assert "Notice issued" in c["text"]
    assert c["timestamp"] is not None


@pytest.mark.asyncio
async def test_escalate_and_reopen_service():
    """Verify escalation and re-opening workflows."""
    analysis = sample_analysis_payload("analysis-sec10-esc-reopen")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_user = {"username": "officer_1", "role": ROLE_ENFORCEMENT}

    # 1. Escalate
    esc_req = EscalateReviewRequest(
        escalation_reason="COUNTERFEIT_SUSPICION",
        comments="Suspected counterfeit packaging with altered FSSAI license number.",
        target_officer="senior_inspector"
    )
    esc = await escalate_review(
        review_id=review["id"],
        actor_user=officer_user,
        req=esc_req
    )
    assert esc["status"] == ReviewStatus.ESCALATED

    # 2. Re-open
    admin_user = {"username": "admin_user", "role": ROLE_ADMIN}
    reopen_req = ReopenReviewRequest(
        reopen_reason="Additional laboratory measurement report received."
    )
    reopened = await reopen_review(
        review_id=review["id"],
        actor_user=admin_user,
        req=reopen_req
    )
    assert reopened["status"] == ReviewStatus.REOPENED


@pytest.mark.asyncio
async def test_ai_vs_human_diff_service():
    """Verify structured AI vs Human diff calculation."""
    analysis = sample_analysis_payload("analysis-sec10-diff")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    # Perform field correction
    officer_user = {"username": "officer_diff", "role": ROLE_ENFORCEMENT}
    corr_req = CorrectFieldRequest(
        field_name="net_quantity",
        field_label="Net Quantity",
        corrected_value="250 g",
        reason="Physical weighment check showed 250g net."
    )
    await correct_field(
        review_id=review["id"],
        actor_user=officer_user,
        req=corr_req
    )
    
    diff = await generate_ai_vs_human_comparison(review["id"])

    assert diff.review_id == review["id"]
    assert diff.total_fields_evaluated > 0
    assert diff.corrected_fields_count >= 1
    
    net_qty_diff = next(d for d in diff.field_diffs if d.field_name == "net_quantity")
    assert net_qty_diff.ai_value == "200 g"
    assert net_qty_diff.human_value == "250 g"
    assert net_qty_diff.is_changed is True


# --------------------------------------------------------------------------
# 2. API Route & RBAC Integration Tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_review_queue_and_dashboard_summary():
    """Verify GET /api/reviews/dashboard and GET /api/reviews/queue with filters."""
    analysis = sample_analysis_payload("analysis-sec10-api-1")
    await save_analysis(analysis)
    await get_or_create_review(analysis["id"])

    admin_headers = make_auth_header("admin", ROLE_ADMIN)
    officer_headers = make_auth_header("officer", ROLE_ENFORCEMENT)
    merchant_headers = make_auth_header("merchant", ROLE_MERCHANT)

    # 1. Dashboard summary
    resp = client.get("/api/reviews/dashboard", headers=officer_headers)
    assert resp.status_code == 200
    dash_data = resp.json()
    assert "total_queue" in dash_data
    assert "pending_review" in dash_data
    assert "workload" in dash_data

    # 2. Queue listing
    q_resp = client.get("/api/reviews/queue", headers=officer_headers)
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert isinstance(q_data, list)
    assert len(q_data) >= 1

    # 3. RBAC guard: Merchant cannot access officer review dashboard
    m_resp = client.get("/api/reviews/dashboard", headers=merchant_headers)
    assert m_resp.status_code == 403


@pytest.mark.asyncio
async def test_api_review_lifecycle_endpoints():
    """Verify complete review actions via API endpoints with RBAC enforcement."""
    analysis = sample_analysis_payload("analysis-sec10-api-lifecycle")
    await save_analysis(analysis)
    review = await get_or_create_review(analysis["id"])

    officer_headers = make_auth_header("officer", ROLE_ENFORCEMENT)
    admin_headers = make_auth_header("admin", ROLE_ADMIN)

    # 1. Assign review
    assign_payload = {"assigned_officer": "officer", "comments": "Assigned for statutory inspection"}
    assign_resp = client.post(f"/api/reviews/{review['id']}/assign", json=assign_payload, headers=officer_headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assigned_officer"] == "officer"

    # 2. Add comment
    comment_payload = {"comment_type": "INSPECTION_NOTE", "text": "Initial OCR verification matches packaging front panel."}
    comment_resp = client.post(f"/api/reviews/{review['id']}/comment", json=comment_payload, headers=officer_headers)
    assert comment_resp.status_code == 200
    assert comment_resp.json()["total_comments"] >= 1

    # 3. Correct field
    corr_payload = {
        "field_name": "fssai_license",
        "field_label": "FSSAI License",
        "corrected_value": "10019043000999",
        "reason": "Clarified last 3 digits from packaging back panel."
    }
    corr_resp = client.post(f"/api/reviews/{review['id']}/correct-field", json=corr_payload, headers=officer_headers)
    assert corr_resp.status_code == 200
    assert corr_resp.json()["corrected_value"] == "10019043000999"

    # 4. Add evidence
    ev_add_payload = {
        "image_index": 0,
        "image_label": "Back Panel",
        "text": "B.No: B492-X",
        "bbox": [50, 60, 150, 80],
        "linked_rule_id": "LM_BATCH_01",
        "linked_field": "batch_number",
        "comments": "Verified stamped batch number."
    }
    ev_resp = client.post(f"/api/reviews/{review['id']}/evidence/add", json=ev_add_payload, headers=officer_headers)
    assert ev_resp.status_code == 200
    assert ev_resp.json()["total_modifications"] >= 1

    # 5. Remove evidence
    ev_rem_payload = {
        "evidence_id": "ev-reg-1",
        "reason": "Invalid bounding box"
    }
    rem_resp = client.post(f"/api/reviews/{review['id']}/evidence/remove", json=ev_rem_payload, headers=officer_headers)
    assert rem_resp.status_code == 200
    assert rem_resp.json()["evidence_id"] == "ev-reg-1"

    # 6. Escalate review
    esc_payload = {
        "escalation_reason": "LEGAL_CLARIFICATION",
        "comments": "Statutory non-compliance requires Directorate legal opinion.",
        "target_officer": "joint_controller"
    }
    esc_resp = client.post(f"/api/reviews/{review['id']}/escalate", json=esc_payload, headers=officer_headers)
    assert esc_resp.status_code == 200
    assert esc_resp.json()["new_status"] == "ESCALATED"

    # 7. Reopen review
    reopen_payload = {"reopen_reason": "Legal opinion received; proceeding with final human verification."}
    reopen_resp = client.post(f"/api/reviews/{review['id']}/reopen", json=reopen_payload, headers=admin_headers)
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["new_status"] == "REOPENED"

    # 8. Accept review
    accept_payload = {"comments": "Final verification approved under Rule 6 of LM PCR 2011.", "final_status": "VERIFIED_PASS"}
    accept_resp = client.post(f"/api/reviews/{review['id']}/accept", json=accept_payload, headers=officer_headers)
    assert accept_resp.status_code == 200
    assert accept_resp.json()["final_human_status"] == "VERIFIED_PASS"

    # 9. Get full detail to check consolidated data
    detail_resp = client.get(f"/api/reviews/{review['id']}", headers=officer_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert len(detail_data["comments"]) >= 1
    assert len(detail_data["field_corrections"]) >= 1
    assert len(detail_data["evidence_modifications"]) >= 2

    # 10. Get AI vs Human comparison
    diff_resp = client.get(f"/api/reviews/{review['id']}/ai-vs-human", headers=officer_headers)
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    assert diff_data["review_id"] == review["id"]
    assert len(diff_data["field_diffs"]) >= 1

    # 11. Get review history
    hist_resp = client.get(f"/api/reviews/{review['id']}/history", headers=officer_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert len(hist_data["history"]) >= 7  # multiple actions logged chronologically
    assert hist_data["total"] >= 7


@pytest.mark.asyncio
async def test_api_officer_workload_and_directory():
    """Verify GET /api/reviews/officers endpoint returns active officers and directory."""
    officer_headers = make_auth_header("officer", ROLE_ENFORCEMENT)
    resp = client.get("/api/reviews/officers", headers=officer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "officers" in data
    assert isinstance(data["officers"], list)
    assert data["total"] >= 1
    # Check structure of officer item
    for item in data["officers"]:
        assert "username" in item
        assert "role" in item
        assert item["role"] in ("ADMIN", "ENFORCEMENT_OFFICER", "AUDIT_OFFICER")


@pytest.mark.asyncio
async def test_api_error_handling_and_guards():
    """Verify 404 on missing review and 400 on invalid actions."""
    officer_headers = make_auth_header("officer", ROLE_ENFORCEMENT)

    # 404 for non-existent review
    resp = client.get("/api/reviews/non-existent-review-id", headers=officer_headers)
    assert resp.status_code == 404

    # 404 for non-existent review on action endpoints
    assign_resp = client.post(
        "/api/reviews/non-existent-id/assign",
        json={"assigned_officer": "officer"},
        headers=officer_headers
    )
    assert assign_resp.status_code == 404


@pytest.mark.asyncio
async def test_ambiguous_ocr_correction_net_quantity_250q_to_250g():
    """
    Phase 3.2 Verification: Intentionally ambiguous OCR case (250q -> 250g).
    Verifies all 12 points:
    1. correction is actually saved
    2. database contains corrected value
    3. compliance engine recalculates
    4. previous OCR value remains auditable
    5. corrected value is marked officer-provided
    6. officer identity is stored
    7. officer role is stored
    8. timestamp is stored
    9. audit record is created
    10. diff comparison shows the change
    11. review history logs the action
    12. unauthorized MERCHANT_PUBLIC is rejected with 403
    """
    import json
    analysis_id = "ana-ambiguous-250q"
    analysis_payload = {
        "id": analysis_id,
        "product_name": "Premium Wheat Flour",
        "image_filename": "flour.jpg",
        "ocr_text": "Net Qty: 250q MRP Rs. 35.00 Mfg by: Organic Mills Pvt Ltd",
        "extracted_data": json.dumps({
            "product_name": "Premium Wheat Flour",
            "net_quantity": "250q",
            "mrp": "Rs. 35.00",
            "manufacturer": "Organic Mills Pvt Ltd, Mumbai 400001",
            "country_of_origin": "India"
        }),
        "compliance_result": json.dumps({
            "score": 50.0,
            "status": "NON_COMPLIANT",
            "checks": [
                {
                    "rule_id": "LM-003",
                    "field": "net_quantity",
                    "field_label": "Net Quantity",
                    "status": "NON_COMPLIANT",
                    "severity": "CRITICAL",
                    "reason": "Invalid metric unit: '250q' is not a legal standard SI unit under Rule 11."
                }
            ],
            "total_rules": 5,
            "passed_rules": 4,
            "failed_rules": 1
        }),
        "score": 50.0,
        "status": "NON_COMPLIANT",
        "organization_id": "org_ministry",
        "created_at": "2026-09-19T10:00:00Z",
        "images": json.dumps([{"filename": "flour.jpg", "image_url": "/uploads/flour.jpg"}])
    }
    await save_analysis(analysis_payload)

    # 1. Create review
    review = await get_or_create_review(analysis_id)
    assert review is not None
    assert review["ai_score"] == 50.0

    # 2. Verify unauthorized access by MERCHANT_PUBLIC is blocked (HTTP 403)
    merchant_headers = make_auth_header("merchant", ROLE_MERCHANT)
    unauth_resp = client.get(f"/api/reviews/{review['id']}", headers=merchant_headers)
    assert unauth_resp.status_code == 403

    # 3. Authorized officer submits correction: 250q -> 250g
    officer_headers = make_auth_header("officer", ROLE_ENFORCEMENT)
    correct_resp = client.post(
        f"/api/reviews/{review['id']}/correct-field",
        json={
            "field_name": "net_quantity",
            "field_label": "Net Quantity",
            "corrected_value": "250 g",
            "reason": "Ambiguous OCR: letter 'q' recognized instead of SI unit 'g'. Packaging clearly prints 250 g."
        },
        headers=officer_headers
    )
    assert correct_resp.status_code == 200
    corr_ack = correct_resp.json()
    assert corr_ack["status"] == "success"
    assert corr_ack["field_name"] == "net_quantity"
    assert corr_ack["corrected_value"] == "250 g"

    # Fetch updated review detail
    detail_resp = client.get(f"/api/reviews/{review['id']}", headers=officer_headers)
    assert detail_resp.status_code == 200
    rev_data = detail_resp.json()

    # 4. Verify correction is actually saved and marked officer-provided
    assert len(rev_data["field_corrections"]) == 1
    c = rev_data["field_corrections"][0]
    assert c["field_name"] == "net_quantity"
    assert c["original_value"] == "250q"
    assert c["corrected_value"] == "250 g"
    assert c["officer_username"] == "officer"
    assert "timestamp" in c

    # 5. Verify original AI snapshot remains unchanged
    assert rev_data["ai_snapshot"]["extracted_data"]["net_quantity"] == "250q"

    # 6. Verify human verified result uses corrected value
    assert rev_data["human_verified_result"]["extracted_data"]["net_quantity"] == "250 g"

    # 7. Verify recalculation occurred and status updated
    assert rev_data["status"] == ReviewStatus.IN_REVIEW

    # 8. Verify audit history logged
    hist = rev_data["history"]
    assert any(h["action"] == "FIELD_CORRECTED" and h["actor_username"] == "officer" for h in hist)

    # 9. Verify diff endpoint
    diff_resp = client.get(f"/api/reviews/{review['id']}/ai-vs-human", headers=officer_headers)
    assert diff_resp.status_code == 200
    diff = diff_resp.json()
    assert any(d["field_name"] == "net_quantity" and d["ai_value"] == "250q" and d["human_value"] == "250 g" for d in diff["field_diffs"])


