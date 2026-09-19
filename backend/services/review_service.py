"""
MetrCheck AI — Master Roadmap Section 10: Human Verification / Officer Workflow Service

Business logic, review state machine, deterministic AI vs Human comparison,
statutory field corrections, evidence management, and workload tracking.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from models.schemas import (
    ProductInfo,
    ComplianceResult,
    ComplianceCheck,
    ComplianceIssue,
    EvidenceItem
)
from models.review_schemas import (
    ReviewStatus,
    HumanVerifiedStatus,
    FieldCorrectionItem,
    OfficerCommentItem,
    ReviewHistoryEvent,
    AssignReviewRequest,
    AcceptReviewRequest,
    RejectReviewRequest,
    CorrectFieldRequest,
    AddEvidenceRequest,
    RemoveEvidenceRequest,
    AddCommentRequest,
    EscalateReviewRequest,
    ReopenReviewRequest,
    AIvsHumanDiffItem,
    AIvsHumanComparison,
    ReviewItem,
    ReviewDetailResponse,
    OfficerWorkloadItem,
    OfficerDashboardSummary
)
from compliance.engine import ComplianceEngine
from compliance.scorer import calculate_score
from database.db import (
    save_review,
    get_review,
    get_review_by_analysis_id,
    list_reviews,
    get_analysis,
    get_all_users,
    save_evidence_audit_log
)


# ════════════════════════════════════════════════════════════════════════════
# 1. STATE MACHINE & TRANSITION VALIDATION
# ════════════════════════════════════════════════════════════════════════════

ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    ReviewStatus.PENDING_REVIEW: [
        ReviewStatus.ASSIGNED,
        ReviewStatus.IN_REVIEW,
        ReviewStatus.VERIFIED_PASS,
        ReviewStatus.VERIFIED_FAIL,
        ReviewStatus.VERIFIED_NEEDS_REVIEW,
        ReviewStatus.REJECTED,
        ReviewStatus.ESCALATED
    ],
    ReviewStatus.ASSIGNED: [
        ReviewStatus.ASSIGNED,  # Reassign
        ReviewStatus.IN_REVIEW,
        ReviewStatus.VERIFIED_PASS,
        ReviewStatus.VERIFIED_FAIL,
        ReviewStatus.VERIFIED_NEEDS_REVIEW,
        ReviewStatus.REJECTED,
        ReviewStatus.ESCALATED
    ],
    ReviewStatus.IN_REVIEW: [
        ReviewStatus.CORRECTION_REQUIRED,
        ReviewStatus.VERIFIED_PASS,
        ReviewStatus.VERIFIED_FAIL,
        ReviewStatus.VERIFIED_NEEDS_REVIEW,
        ReviewStatus.REJECTED,
        ReviewStatus.ESCALATED,
        ReviewStatus.ASSIGNED
    ],
    ReviewStatus.CORRECTION_REQUIRED: [
        ReviewStatus.IN_REVIEW,
        ReviewStatus.VERIFIED_PASS,
        ReviewStatus.VERIFIED_FAIL,
        ReviewStatus.VERIFIED_NEEDS_REVIEW,
        ReviewStatus.REJECTED,
        ReviewStatus.ESCALATED
    ],
    ReviewStatus.VERIFIED_PASS: [
        ReviewStatus.REOPENED,
        ReviewStatus.CLOSED
    ],
    ReviewStatus.VERIFIED_FAIL: [
        ReviewStatus.REOPENED,
        ReviewStatus.CLOSED
    ],
    ReviewStatus.VERIFIED_NEEDS_REVIEW: [
        ReviewStatus.REOPENED,
        ReviewStatus.CLOSED
    ],
    ReviewStatus.REJECTED: [
        ReviewStatus.REOPENED,
        ReviewStatus.CLOSED
    ],
    ReviewStatus.ESCALATED: [
        ReviewStatus.IN_REVIEW,
        ReviewStatus.ASSIGNED,
        ReviewStatus.VERIFIED_PASS,
        ReviewStatus.VERIFIED_FAIL,
        ReviewStatus.VERIFIED_NEEDS_REVIEW,
        ReviewStatus.REJECTED,
        ReviewStatus.REOPENED
    ],
    ReviewStatus.REOPENED: [
        ReviewStatus.IN_REVIEW,
        ReviewStatus.ASSIGNED,
        ReviewStatus.VERIFIED_PASS,
        ReviewStatus.VERIFIED_FAIL,
        ReviewStatus.VERIFIED_NEEDS_REVIEW,
        ReviewStatus.REJECTED,
        ReviewStatus.ESCALATED
    ],
    ReviewStatus.CLOSED: [
        ReviewStatus.REOPENED
    ]
}


def validate_transition(current_status: str, next_status: str) -> bool:
    """Validates if current status can transition to next status."""
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    return next_status in allowed


def now_utc_iso() -> str:
    """Returns standard UTC ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════════════════
# 2. REVIEW INITIALIZATION & SNAPSHOT BUILDER
# ════════════════════════════════════════════════════════════════════════════

def create_initial_review_record(analysis_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs an initial officer review record from an analysis database dict.
    The original AI output is immutably snapshotted in `ai_snapshot`.
    """
    now = now_utc_iso()
    ana_id = analysis_dict["id"]
    
    # Parse extracted_data and compliance_result if stringified
    ext_data = analysis_dict.get("extracted_data")
    if isinstance(ext_data, str):
        try: ext_data = json.loads(ext_data)
        except Exception: ext_data = {}
    elif not ext_data:
        ext_data = {}

    comp_res = analysis_dict.get("compliance_result")
    if isinstance(comp_res, str):
        try: comp_res = json.loads(comp_res)
        except Exception: comp_res = {}
    elif not comp_res:
        comp_res = {}

    images = analysis_dict.get("images")
    if isinstance(images, str):
        try: images = json.loads(images)
        except Exception: images = []
    elif not images:
        images = []

    score = float(analysis_dict.get("score") or comp_res.get("score") or 0.0)
    ai_status = str(analysis_dict.get("status") or comp_res.get("status") or "PASS")
    
    # Risk calculation
    risk_level = "LOW"
    if score < 60: risk_level = "CRITICAL"
    elif score < 80: risk_level = "HIGH"
    elif score < 90: risk_level = "MEDIUM"

    checks = comp_res.get("checks", [])
    crit_count = sum(1 for c in checks if c.get("status") == "FAIL" and c.get("severity") == "critical")
    review_reasons = []
    for c in checks:
        if c.get("status") in ("FAIL", "WARNING", "NEEDS_REVIEW"):
            review_reasons.append(f"{c.get('rule_id')}: {c.get('field_label') or c.get('field')}")

    ai_snapshot = {
        "analysis_id": ana_id,
        "product_name": analysis_dict.get("product_name", "Unknown"),
        "image_filename": analysis_dict.get("image_filename"),
        "ocr_text": analysis_dict.get("ocr_text", ""),
        "extracted_data": ext_data,
        "compliance_result": comp_res,
        "images": images,
        "score": score,
        "risk_level": risk_level,
        "status": ai_status,
        "snapshotted_at": now
    }

    # Working human verified result initialized as clone of AI snapshot
    human_verified_result = {
        "extracted_data": dict(ext_data),
        "compliance_result": dict(comp_res),
        "score": score,
        "risk_level": risk_level,
        "status": ai_status,
        "last_recalculated_at": now
    }

    review_id = f"rev-{ana_id}"
    history_item = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "CREATED",
        "actor_username": "SYSTEM",
        "actor_role": "SYSTEM",
        "details": f"Review queue item initialized with AI score {score:.1f} ({risk_level} risk).",
        "previous_state": None,
        "new_state": ReviewStatus.PENDING_REVIEW,
        "timestamp": now,
        "metadata": {"critical_issues": crit_count, "reasons_count": len(review_reasons)}
    }

    return {
        "id": review_id,
        "analysis_id": ana_id,
        "organization_id": analysis_dict.get("organization_id", ""),
        "target_type": "ANALYSIS",
        "product_name": analysis_dict.get("product_name", "Unknown Product"),
        "status": ReviewStatus.PENDING_REVIEW,
        "assigned_officer": "",
        "assigned_by": "",
        "assigned_at": None,
        "verified_by": "",
        "verified_at": None,
        "final_human_status": "",
        "ai_score": score,
        "ai_risk_level": risk_level,
        "ai_status": ai_status,
        "ai_snapshot": json.dumps(ai_snapshot),
        "human_verified_result": json.dumps(human_verified_result),
        "field_corrections": json.dumps([]),
        "evidence_modifications": json.dumps([]),
        "comments": json.dumps([]),
        "history": json.dumps([history_item]),
        "created_at": analysis_dict.get("created_at") or now,
        "updated_at": now
    }


# ════════════════════════════════════════════════════════════════════════════
# 3. WORKFLOW ACTIONS & STATE MUTATIONS
# ════════════════════════════════════════════════════════════════════════════

async def get_or_create_review(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves review record for analysis or creates it if it doesn't exist yet."""
    review = await get_review_by_analysis_id(analysis_id)
    if review:
        return review

    analysis = await get_analysis(analysis_id)
    if not analysis:
        return None

    init_data = create_initial_review_record(analysis)
    await save_review(init_data)
    return await get_review(init_data["id"])


def parse_review_db_record(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to parse JSON fields of a database review record."""
    d = dict(row_dict)
    for k in ("ai_snapshot", "human_verified_result", "field_corrections", "evidence_modifications", "comments", "history"):
        val = d.get(k)
        if isinstance(val, str):
            try: d[k] = json.loads(val)
            except Exception: d[k] = {} if k in ("ai_snapshot", "human_verified_result") else []
        elif val is None:
            d[k] = {} if k in ("ai_snapshot", "human_verified_result") else []
    return d


async def assign_review(
    review_id: str,
    actor_user: Dict[str, Any],
    req: AssignReviewRequest
) -> Dict[str, Any]:
    """Assigns an audit review to a specific officer."""
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()
    prev_status = rev["status"]
    new_status = ReviewStatus.ASSIGNED

    if not validate_transition(prev_status, new_status):
        raise ValueError(f"Cannot transition review from '{prev_status}' to '{new_status}'.")

    rev["assigned_officer"] = req.assigned_officer.strip()
    rev["assigned_by"] = actor_user.get("username", "")
    rev["assigned_at"] = now
    rev["status"] = new_status
    rev["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "ASSIGNED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Assigned to officer '{req.assigned_officer}'." + (f" Note: {req.comments}" if req.comments else ""),
        "previous_state": prev_status,
        "new_state": new_status,
        "timestamp": now,
        "metadata": {"assigned_officer": req.assigned_officer}
    }
    rev["history"].append(event)

    if req.comments:
        comment_item = {
            "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
            "comment_type": "GENERAL",
            "text": req.comments,
            "officer_username": actor_user.get("username", "officer"),
            "officer_role": actor_user.get("role", "OFFICER"),
            "timestamp": now
        }
        rev["comments"].append(comment_item)

    await save_review(rev)
    return rev


async def accept_ai_result(
    review_id: str,
    actor_user: Dict[str, Any],
    req: AcceptReviewRequest
) -> Dict[str, Any]:
    """
    Accepts AI result as authoritative human verification.
    Preserves original AI output; sets final human verified status.
    """
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()
    prev_status = rev["status"]

    # Determine final status
    ai_status = rev.get("ai_status", "PASS").upper()
    if req.final_status:
        final_stat = req.final_status
    elif ai_status == "PASS":
        final_stat = ReviewStatus.VERIFIED_PASS
    elif ai_status == "FAIL":
        final_stat = ReviewStatus.VERIFIED_FAIL
    else:
        final_stat = ReviewStatus.VERIFIED_NEEDS_REVIEW

    if not validate_transition(prev_status, final_stat):
        raise ValueError(f"Cannot transition review from '{prev_status}' to '{final_stat}'.")

    rev["status"] = final_stat
    rev["final_human_status"] = final_stat
    rev["verified_by"] = actor_user.get("username", "")
    rev["verified_at"] = now
    rev["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "ACCEPTED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"AI result accepted and confirmed as {final_stat}." + (f" Comments: {req.comments}" if req.comments else ""),
        "previous_state": prev_status,
        "new_state": final_stat,
        "timestamp": now,
        "metadata": {"final_status": final_stat}
    }
    rev["history"].append(event)

    if req.comments:
        comment_item = {
            "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
            "comment_type": "SIGN_OFF",
            "text": req.comments,
            "officer_username": actor_user.get("username", "officer"),
            "officer_role": actor_user.get("role", "OFFICER"),
            "timestamp": now
        }
        rev["comments"].append(comment_item)

    await save_review(rev)
    return rev


async def reject_ai_result(
    review_id: str,
    actor_user: Dict[str, Any],
    req: RejectReviewRequest
) -> Dict[str, Any]:
    """
    Rejects AI outcome with mandatory reason.
    Preserves original AI output; sets status to REJECTED.
    """
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()
    prev_status = rev["status"]
    new_status = ReviewStatus.REJECTED

    if not validate_transition(prev_status, new_status):
        raise ValueError(f"Cannot transition review from '{prev_status}' to '{new_status}'.")

    rev["status"] = new_status
    rev["final_human_status"] = new_status
    rev["verified_by"] = actor_user.get("username", "")
    rev["verified_at"] = now
    rev["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "REJECTED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"AI result rejected. Reason: {req.rejection_reason}. Comments: {req.comments}",
        "previous_state": prev_status,
        "new_state": new_status,
        "timestamp": now,
        "metadata": {"rejection_reason": req.rejection_reason}
    }
    rev["history"].append(event)

    comment_item = {
        "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
        "comment_type": "REJECTION",
        "text": f"[{req.rejection_reason}] {req.comments}",
        "officer_username": actor_user.get("username", "officer"),
        "officer_role": actor_user.get("role", "OFFICER"),
        "timestamp": now
    }
    rev["comments"].append(comment_item)

    await save_review(rev)
    return rev


async def correct_field(
    review_id: str,
    actor_user: Dict[str, Any],
    req: CorrectFieldRequest
) -> Dict[str, Any]:
    """
    Corrects an extracted statutory declaration value.
    Updates the working human-verified result, triggers deterministic score recalculation,
    and appends to field_corrections without touching immutable ai_snapshot.
    """
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()

    # Get working human-verified result
    human_res = rev.get("human_verified_result") or {}
    ext_data = human_res.get("extracted_data") or {}

    old_val = ext_data.get(req.field_name)
    ext_data[req.field_name] = req.corrected_value.strip()
    human_res["extracted_data"] = ext_data

    # Re-run deterministic compliance & scoring on corrected values
    try:
        p_info = ProductInfo(**ext_data)
        engine = ComplianceEngine()
        comp_dict = engine.check(product_info=p_info, ocr_text="")
        score_breakdown = calculate_score(
            checks=comp_dict.get("checks", []),
            product_info=p_info,
            conflicts=comp_dict.get("conflicts", [])
        )

        final_score = float(score_breakdown.get("final_score", comp_dict.get("score", 0.0)))
        comp_res = ComplianceResult(
            checks=comp_dict.get("checks", []),
            score=final_score,
            status=comp_dict.get("status", "COMPLIANT"),
            total_rules=comp_dict.get("total_rules", 0),
            passed_rules=comp_dict.get("passed_rules", 0),
            failed_rules=comp_dict.get("failed_rules", 0),
            warning_rules=comp_dict.get("warning_rules", 0),
            needs_review_rules=comp_dict.get("needs_review_rules", 0),
            not_applicable_rules=comp_dict.get("not_applicable_rules", 0),
            issues=comp_dict.get("issues", []),
            recommendations=comp_dict.get("recommendations", [])
        )

        human_res["compliance_result"] = comp_res.model_dump()
        human_res["score"] = final_score
        human_res["status"] = comp_res.status
        risk_level = None
        if isinstance(score_breakdown.get("risk_assessment"), dict):
            risk_level = score_breakdown["risk_assessment"].get("risk_level")
        elif hasattr(score_breakdown.get("risk_assessment"), "risk_level"):
            risk_level = score_breakdown["risk_assessment"].risk_level

        if not risk_level:
            risk_level = "LOW" if final_score >= 90 else ("CRITICAL" if final_score < 60 else "MEDIUM")
        human_res["risk_level"] = risk_level
    except Exception as e:
        logger.error(f"[REVIEW] Field correction recalculation error: {e}")

    human_res["last_recalculated_at"] = now
    rev["human_verified_result"] = human_res

    # Transition to IN_REVIEW if PENDING or ASSIGNED
    if rev["status"] in (ReviewStatus.PENDING_REVIEW, ReviewStatus.ASSIGNED):
        rev["status"] = ReviewStatus.IN_REVIEW
    rev["updated_at"] = now

    correction_item = {
        "field_name": req.field_name,
        "field_label": req.field_label,
        "original_value": str(old_val) if old_val is not None else None,
        "corrected_value": req.corrected_value.strip(),
        "reason": req.reason or "Officer manual statutory correction",
        "officer_username": actor_user.get("username", "officer"),
        "officer_role": actor_user.get("role", "OFFICER"),
        "timestamp": now,
        "evidence_id": req.evidence_id
    }
    rev["field_corrections"].append(correction_item)

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "FIELD_CORRECTED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Corrected '{req.field_label}' from '{old_val}' to '{req.corrected_value}'." + (f" Reason: {req.reason}" if req.reason else ""),
        "previous_state": rev["status"],
        "new_state": rev["status"],
        "timestamp": now,
        "metadata": {
            "field_name": req.field_name,
            "old_value": old_val,
            "new_value": req.corrected_value
        }
    }
    rev["history"].append(event)

    # Save to evidence audit logs as well
    await save_evidence_audit_log(
        analysis_id=rev["analysis_id"],
        evidence_id=req.evidence_id or f"corr-{req.field_name}",
        rule_id=req.field_name,
        actor_username=actor_user.get("username", "officer"),
        action_type="CORRECTION",
        previous_value=str(old_val) if old_val is not None else "None",
        new_value=req.corrected_value,
        comments=req.reason or "Officer field correction"
    )

    await save_review(rev)
    return rev


async def add_missing_evidence(
    review_id: str,
    actor_user: Dict[str, Any],
    req: AddEvidenceRequest
) -> Dict[str, Any]:
    """Allows an officer to annotate and link missing evidence from package images."""
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()

    ev_id = f"ev-officer-{uuid.uuid4().hex[:8]}"
    ev_item = {
        "id": ev_id,
        "image_index": req.image_index,
        "image_label": req.image_label,
        "text": req.text.strip(),
        "bbox": req.bbox,
        "linked_rule_id": req.linked_rule_id,
        "linked_field": req.linked_field,
        "evidence_type": "OFFICER_CREATED",
        "evidence_status": "VERIFIED",
        "reliability_tier": "HIGH",
        "reliability_score": 100.0,
        "created_by": actor_user.get("username", "officer"),
        "created_at": now,
        "comments": req.comments
    }

    rev["evidence_modifications"].append({
        "action": "ADDED",
        "evidence": ev_item,
        "officer_username": actor_user.get("username", "officer"),
        "timestamp": now
    })

    if rev["status"] in (ReviewStatus.PENDING_REVIEW, ReviewStatus.ASSIGNED):
        rev["status"] = ReviewStatus.IN_REVIEW
    rev["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "EVIDENCE_ADDED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Added missing evidence for rule '{req.linked_rule_id}': '{req.text}'.",
        "previous_state": rev["status"],
        "new_state": rev["status"],
        "timestamp": now,
        "metadata": {"evidence_id": ev_id, "rule_id": req.linked_rule_id}
    }
    rev["history"].append(event)

    await save_evidence_audit_log(
        analysis_id=rev["analysis_id"],
        evidence_id=ev_id,
        rule_id=req.linked_rule_id,
        actor_username=actor_user.get("username", "officer"),
        action_type="EVIDENCE_ADDED",
        previous_value=None,
        new_value=req.text,
        comments=req.comments or "Officer added missing evidence annotation"
    )

    await save_review(rev)
    return rev


async def remove_incorrect_evidence(
    review_id: str,
    actor_user: Dict[str, Any],
    req: RemoveEvidenceRequest
) -> Dict[str, Any]:
    """Soft-removes incorrect automated evidence, marking it REMOVED without destroying history."""
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()

    rev["evidence_modifications"].append({
        "action": "REMOVED",
        "evidence_id": req.evidence_id,
        "reason": req.reason,
        "officer_username": actor_user.get("username", "officer"),
        "timestamp": now
    })

    rev["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "EVIDENCE_REMOVED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Soft-removed evidence '{req.evidence_id}'. Reason: {req.reason}",
        "previous_state": rev["status"],
        "new_state": rev["status"],
        "timestamp": now,
        "metadata": {"evidence_id": req.evidence_id, "reason": req.reason}
    }
    rev["history"].append(event)

    await save_evidence_audit_log(
        analysis_id=rev["analysis_id"],
        evidence_id=req.evidence_id,
        rule_id="EVIDENCE_REMOVAL",
        actor_username=actor_user.get("username", "officer"),
        action_type="EVIDENCE_REMOVED",
        previous_value="ACTIVE",
        new_value="REMOVED",
        comments=req.reason
    )

    await save_review(rev)
    return rev


async def add_officer_comment(
    review_id: str,
    actor_user: Dict[str, Any],
    req: AddCommentRequest
) -> Dict[str, Any]:
    """Adds a structured comment or note to the review record."""
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()

    comment_item = {
        "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
        "comment_type": req.comment_type,
        "text": req.text.strip(),
        "officer_username": actor_user.get("username", "officer"),
        "officer_role": actor_user.get("role", "OFFICER"),
        "timestamp": now
    }
    rev["comments"].append(comment_item)
    rev["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "COMMENT_ADDED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Added comment ({req.comment_type}): {req.text[:80]}...",
        "previous_state": rev["status"],
        "new_state": rev["status"],
        "timestamp": now,
        "metadata": {"comment_type": req.comment_type}
    }
    rev["history"].append(event)

    await save_review(rev)
    return rev


async def escalate_review(
    review_id: str,
    actor_user: Dict[str, Any],
    req: EscalateReviewRequest
) -> Dict[str, Any]:
    """Escalates an audit review to a senior officer or administrator."""
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()
    prev_status = rev["status"]
    new_status = ReviewStatus.ESCALATED

    if not validate_transition(prev_status, new_status):
        raise ValueError(f"Cannot escalate review from '{prev_status}' to '{new_status}'.")

    target = req.escalation_target or "ADMIN"
    rev["status"] = new_status
    rev["updated_at"] = now

    comment_item = {
        "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
        "comment_type": "ESCALATION",
        "text": f"[Escalated to {target}] Reason: {req.escalation_reason}." + (f" Comments: {req.comments}" if req.comments else ""),
        "officer_username": actor_user.get("username", "officer"),
        "officer_role": actor_user.get("role", "OFFICER"),
        "timestamp": now
    }
    rev["comments"].append(comment_item)

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "ESCALATED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Audit escalated to {target}. Reason: {req.escalation_reason}.",
        "previous_state": prev_status,
        "new_state": new_status,
        "timestamp": now,
        "metadata": {"escalation_target": target, "reason": req.escalation_reason}
    }
    rev["history"].append(event)

    await save_review(rev)
    return rev


async def reopen_review(
    review_id: str,
    actor_user: Dict[str, Any],
    req: ReopenReviewRequest
) -> Dict[str, Any]:
    """Reopens a completed, verified, or closed review while preserving past history."""
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    now = now_utc_iso()
    prev_status = rev["status"]
    new_status = ReviewStatus.REOPENED

    if not validate_transition(prev_status, new_status):
        raise ValueError(f"Cannot reopen review from '{prev_status}'. Must be verified, rejected, or closed.")

    rev["status"] = new_status
    rev["updated_at"] = now

    comment_item = {
        "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
        "comment_type": "REOPEN",
        "text": f"[Audit Reopened] Reason: {req.reopen_reason}." + (f" Comments: {req.comments}" if req.comments else ""),
        "officer_username": actor_user.get("username", "officer"),
        "officer_role": actor_user.get("role", "OFFICER"),
        "timestamp": now
    }
    rev["comments"].append(comment_item)

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "REOPENED",
        "actor_username": actor_user.get("username", "officer"),
        "actor_role": actor_user.get("role", "OFFICER"),
        "details": f"Audit reopened from '{prev_status}'. Reason: {req.reopen_reason}.",
        "previous_state": prev_status,
        "new_state": new_status,
        "timestamp": now,
        "metadata": {"reopen_reason": req.reopen_reason}
    }
    rev["history"].append(event)

    await save_review(rev)
    return rev


# ════════════════════════════════════════════════════════════════════════════
# 4. AI VS HUMAN COMPARISON ENGINE
# ════════════════════════════════════════════════════════════════════════════

async def generate_ai_vs_human_comparison(review_id: str) -> AIvsHumanComparison:
    """
    Generates a structured side-by-side comparison between the original AI snapshot
    and the human-verified working/final result.
    """
    raw = await get_review(review_id)
    if not raw:
        raise ValueError(f"Review '{review_id}' not found.")

    rev = parse_review_db_record(raw)
    ai_snap = rev.get("ai_snapshot") or {}
    human_res = rev.get("human_verified_result") or {}

    ai_data = ai_snap.get("extracted_data") or {}
    human_data = human_res.get("extracted_data") or {}

    ai_score = float(ai_snap.get("score") or rev.get("ai_score") or 0.0)
    human_score = float(human_res.get("score") or rev.get("ai_score") or 0.0)
    score_delta = round(human_score - ai_score, 1)

    ai_risk = rev.get("ai_risk_level", "LOW")
    human_risk = human_res.get("risk_level", ai_risk)

    ai_status = rev.get("ai_status", "PASS")
    human_status = rev.get("final_human_status") or human_res.get("status", ai_status)

    target_fields = [
        ("product_name", "Product Name"),
        ("brand", "Brand"),
        ("mrp", "Maximum Retail Price (MRP)"),
        ("net_quantity", "Net Quantity"),
        ("manufacturer", "Manufacturer"),
        ("marketed_by", "Marketed By"),
        ("fssai_license", "FSSAI License"),
        ("consumer_care", "Consumer Care"),
        ("country_of_origin", "Country of Origin"),
        ("manufacture_date", "Date of Manufacture"),
        ("expiry_date", "Expiry / Best Before"),
        ("batch_number", "Batch Number"),
        ("ingredients", "Ingredients"),
        ("nutritional_info", "Nutritional Info")
    ]

    corrections_map = {c["field_name"]: c for c in rev.get("field_corrections", [])}
    diff_items: List[AIvsHumanDiffItem] = []
    corrected_count = 0

    for f_name, f_label in target_fields:
        ai_val = ai_data.get(f_name)
        human_val = human_data.get(f_name)
        
        corr = corrections_map.get(f_name)
        if corr:
            is_changed = True
            change_type = "CORRECTED"
            corrected_count += 1
            officer = corr.get("officer_username")
            ts = corr.get("timestamp")
            reason = corr.get("reason")
        elif str(ai_val or "").strip() != str(human_val or "").strip():
            is_changed = True
            change_type = "CORRECTED" if (ai_val and human_val) else ("ADDED" if human_val else "REMOVED")
            corrected_count += 1
            officer = rev.get("verified_by")
            ts = rev.get("verified_at")
            reason = "Human verification adjustment"
        else:
            is_changed = False
            change_type = "UNCHANGED"
            officer = None
            ts = None
            reason = None

        diff_items.append(AIvsHumanDiffItem(
            field_name=f_name,
            field_label=f_label,
            ai_value=str(ai_val) if ai_val is not None else None,
            human_value=str(human_val) if human_val is not None else None,
            is_changed=is_changed,
            change_type=change_type,
            officer_username=officer,
            timestamp=ts,
            reason=reason
        ))

    summary = (
        f"Human verification: {corrected_count} field(s) corrected. "
        f"Score shifted by {score_delta:+0.1f} pts ({ai_score} -> {human_score}). "
        f"Final Status: {human_status}."
    )

    return AIvsHumanComparison(
        analysis_id=rev["analysis_id"],
        review_id=rev["id"],
        ai_score=ai_score,
        human_score=human_score,
        score_delta=score_delta,
        ai_risk_level=ai_risk,
        human_risk_level=human_risk,
        ai_status=ai_status,
        human_status=human_status,
        total_fields_evaluated=len(target_fields),
        corrected_fields_count=corrected_count,
        field_diffs=diff_items,
        summary=summary
    )


# ════════════════════════════════════════════════════════════════════════════
# 5. DASHBOARD & WORKLOAD AGGREGATION
# ════════════════════════════════════════════════════════════════════════════

async def get_officer_dashboard_summary(
    organization_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> OfficerDashboardSummary:
    """Computes aggregated review queue metrics and workload by officer with tenant scoping."""
    if user_role == "ADMIN":
        reviews = await list_reviews(limit=500)
    elif organization_id:
        reviews = await list_reviews(organization_id=organization_id, limit=500)
    else:
        reviews = []

    users = await get_all_users()
    
    if user_role != "ADMIN" and organization_id:
        officer_users = [
            u for u in users 
            if u.get("role") in ("ADMIN", "ENFORCEMENT_OFFICER", "AUDIT_OFFICER")
            and u.get("organization_id") == organization_id
        ]
    elif user_role == "ADMIN":
        officer_users = [
            u for u in users 
            if u.get("role") in ("ADMIN", "ENFORCEMENT_OFFICER", "AUDIT_OFFICER")
        ]
    else:
        officer_users = []

    total_q = len(reviews)
    pending_cnt = sum(1 for r in reviews if r.get("status") == ReviewStatus.PENDING_REVIEW)
    assigned_cnt = sum(1 for r in reviews if r.get("status") == ReviewStatus.ASSIGNED)
    in_review_cnt = sum(1 for r in reviews if r.get("status") in (ReviewStatus.IN_REVIEW, ReviewStatus.CORRECTION_REQUIRED))
    verified_cnt = sum(1 for r in reviews if str(r.get("status", "")).startswith("VERIFIED"))
    rejected_cnt = sum(1 for r in reviews if r.get("status") == ReviewStatus.REJECTED)
    escalated_cnt = sum(1 for r in reviews if r.get("status") == ReviewStatus.ESCALATED)
    reopened_cnt = sum(1 for r in reviews if r.get("status") == ReviewStatus.REOPENED)

    workload_items: List[OfficerWorkloadItem] = []
    for u in officer_users:
        uname = u.get("username", "")
        u_reviews = [r for r in reviews if r.get("assigned_officer", "").lower() == uname.lower()]
        
        tot_assigned = len(u_reviews)
        u_pending = sum(1 for r in u_reviews if r.get("status") in (ReviewStatus.PENDING_REVIEW, ReviewStatus.ASSIGNED))
        u_in_rev = sum(1 for r in u_reviews if r.get("status") in (ReviewStatus.IN_REVIEW, ReviewStatus.CORRECTION_REQUIRED))
        u_comp = sum(1 for r in u_reviews if str(r.get("status", "")).startswith("VERIFIED") or r.get("status") == ReviewStatus.REJECTED)
        u_esc = sum(1 for r in u_reviews if r.get("status") == ReviewStatus.ESCALATED)

        workload_items.append(OfficerWorkloadItem(
            officer_username=uname,
            officer_name=u.get("full_name") or uname,
            officer_role=u.get("role", "OFFICER"),
            total_assigned=tot_assigned,
            pending_count=u_pending,
            in_review_count=u_in_rev,
            completed_count=u_comp,
            escalated_count=u_esc
        ))

    return OfficerDashboardSummary(
        total_queue=total_q,
        pending_review=pending_cnt,
        assigned=assigned_cnt,
        in_review=in_review_cnt,
        verified=verified_cnt,
        rejected=rejected_cnt,
        escalated=escalated_cnt,
        reopened=reopened_cnt,
        workload=workload_items
    )
