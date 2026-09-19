"""
API Router for Master Roadmap Section 10: Human Verification / Officer Workflow.
Enforces strict server-side RBAC for ADMIN, ENFORCEMENT_OFFICER, and AUDIT_OFFICER roles.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.security import (
    get_current_user,
    require_roles,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT
)
from database.db import (
    get_review,
    get_review_by_analysis_id,
    list_reviews,
    get_all_users
)
from models.review_schemas import (
    ReviewItem,
    ReviewDetailResponse,
    AssignReviewRequest,
    AcceptReviewRequest,
    RejectReviewRequest,
    CorrectFieldRequest,
    AddEvidenceRequest,
    RemoveEvidenceRequest,
    AddCommentRequest,
    EscalateReviewRequest,
    ReopenReviewRequest,
    AIvsHumanComparison,
    OfficerDashboardSummary,
    OfficerWorkloadItem
)
from services.review_service import (
    get_or_create_review,
    parse_review_db_record,
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

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _check_review_access(user: dict, review: dict):
    """Enforces tenant isolation and access control on officer reviews."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access reviews."
        )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if not check_tenant_access(user, review):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Cross-organization review access prohibited."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1. OFFICER DASHBOARD & QUEUE
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=OfficerDashboardSummary,
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def get_dashboard_metrics(current_user: dict = Depends(get_current_user)):
    """Summary KPI metrics and officer workload for the officer dashboard with tenant scoping."""
    user_role = current_user.get("role")
    org_id = current_user.get("organization_id")
    if user_role == ROLE_ADMIN:
        org_id = None
    return await get_officer_dashboard_summary(organization_id=org_id, user_role=user_role)


@router.get(
    "/queue",
    response_model=List[ReviewItem],
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def get_review_queue(
    status: Optional[str] = Query(None, description="Filter by status (e.g. PENDING_REVIEW, ASSIGNED, IN_REVIEW, VERIFIED, REJECTED)"),
    assigned_officer: Optional[str] = Query(None, description="Filter by assigned officer username"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (CRITICAL, HIGH, MEDIUM, LOW)"),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns filterable review queue with deterministic priority ordering
    (CRITICAL > HIGH > MEDIUM > LOW, followed by oldest age) scoped to tenant.
    """
    user_role = current_user.get("role")
    user_org = (current_user.get("organization_id") or "").strip()

    if user_role == ROLE_ADMIN:
        raw_reviews = await list_reviews(
            status=status,
            assigned_officer=assigned_officer,
            risk_level=risk_level,
            organization_id=None,
            limit=limit
        )
    else:
        if not user_org:
            return []
        raw_reviews = await list_reviews(
            status=status,
            assigned_officer=assigned_officer,
            risk_level=risk_level,
            organization_id=user_org,
            limit=limit
        )

    items: List[ReviewItem] = []
    now = datetime.now(timezone.utc)

    for r in raw_reviews:
        rev = parse_review_db_record(r)
        if not check_tenant_access(current_user, rev):
            continue
        
        # Calculate age in hours
        created_str = rev.get("created_at") or now.isoformat()
        try:
            c_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            age_hrs = round(max(0.0, (now - c_dt).total_seconds() / 3600.0), 1)
        except Exception:
            age_hrs = 0.0

        ai_snap = rev.get("ai_snapshot") or {}
        comp_res = ai_snap.get("compliance_result") or {}
        checks = comp_res.get("checks", [])
        crit_count = sum(1 for c in checks if c.get("status") == "FAIL" and c.get("severity") == "critical")
        
        reasons = []
        for c in checks:
            if c.get("status") in ("FAIL", "WARNING", "NEEDS_REVIEW"):
                reasons.append(f"{c.get('rule_id')}: {c.get('field_label') or c.get('field')}")

        items.append(ReviewItem(
            review_id=rev["id"],
            analysis_id=rev["analysis_id"],
            target_type=rev.get("target_type", "ANALYSIS"),
            product_name=rev.get("product_name", "Unknown Product"),
            status=rev.get("status", "PENDING_REVIEW"),
            assigned_officer=rev.get("assigned_officer") or None,
            assigned_by=rev.get("assigned_by") or None,
            assigned_at=rev.get("assigned_at"),
            created_at=rev.get("created_at", ""),
            updated_at=rev.get("updated_at", ""),
            verified_by=rev.get("verified_by") or None,
            verified_at=rev.get("verified_at"),
            final_human_status=rev.get("final_human_status") or None,
            ai_score=float(rev.get("ai_score", 0.0)),
            ai_risk_level=rev.get("ai_risk_level", "LOW"),
            ai_status=rev.get("ai_status", "PASS"),
            critical_issues_count=crit_count,
            review_reasons=reasons,
            age_hours=age_hrs
        ))

    # Priority sorting: CRITICAL (4) > HIGH (3) > MEDIUM (2) > LOW (1), then oldest first
    risk_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    items.sort(key=lambda x: (risk_weights.get(x.ai_risk_level.upper(), 0), x.age_hours), reverse=True)
    return items


@router.get(
    "/officers",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def list_available_officers(current_user: dict = Depends(get_current_user)):
    """List of all registered officers available for assignment scoped to tenant."""
    all_users = await get_all_users()
    user_role = current_user.get("role")
    org_id = current_user.get("organization_id")
    officers = [
        {
            "username": u["username"],
            "full_name": u.get("full_name") or u["username"],
            "role": u.get("role", "OFFICER"),
            "status": u.get("status", "ACTIVE")
        }
        for u in all_users
        if u.get("role") in (ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT)
        and (user_role == ROLE_ADMIN or not org_id or u.get("organization_id") == org_id or not u.get("organization_id"))
    ]
    return {"officers": officers, "total": len(officers)}


# ─────────────────────────────────────────────────────────────────────────────
# 2. REVIEW DETAILS & WORKSPACE
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{review_id}",
    response_model=ReviewDetailResponse,
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def get_review_details(
    review_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve full review detail workspace payload."""
    raw = await get_review(review_id)
    if not raw:
        # Check if review_id is an analysis_id and create if needed
        raw = await get_or_create_review(review_id)
        if not raw:
            raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")

    _check_review_access(current_user, raw)

    rev = parse_review_db_record(raw)
    ai_snap = rev.get("ai_snapshot") or {}
    comp_res = ai_snap.get("compliance_result") or {}
    checks = comp_res.get("checks", [])
    crit_count = sum(1 for c in checks if c.get("status") == "FAIL" and c.get("severity") == "critical")
    
    reasons = []
    for c in checks:
        if c.get("status") in ("FAIL", "WARNING", "NEEDS_REVIEW"):
            reasons.append(f"{c.get('rule_id')}: {c.get('field_label') or c.get('field')}")

    human_res = rev.get("human_verified_result") or {}

    return ReviewDetailResponse(
        review_id=rev["id"],
        analysis_id=rev["analysis_id"],
        target_type=rev.get("target_type", "ANALYSIS"),
        product_name=rev.get("product_name", "Unknown Product"),
        status=rev.get("status", "PENDING_REVIEW"),
        assigned_officer=rev.get("assigned_officer") or None,
        assigned_by=rev.get("assigned_by") or None,
        assigned_at=rev.get("assigned_at"),
        created_at=rev.get("created_at", ""),
        updated_at=rev.get("updated_at", ""),
        verified_by=rev.get("verified_by") or None,
        verified_at=rev.get("verified_at"),
        final_human_status=rev.get("final_human_status") or None,
        ai_score=float(rev.get("ai_score", 0.0)),
        ai_risk_level=rev.get("ai_risk_level", "LOW"),
        ai_status=rev.get("ai_status", "PASS"),
        human_score=float(human_res.get("score")) if human_res.get("score") is not None else None,
        human_risk_level=human_res.get("risk_level"),
        critical_issues_count=crit_count,
        review_reasons=reasons,
        ai_snapshot=ai_snap,
        human_verified_result=human_res,
        field_corrections=rev.get("field_corrections", []),
        evidence_modifications=rev.get("evidence_modifications", []),
        comments=rev.get("comments", []),
        history=rev.get("history", [])
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. WORKFLOW ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{review_id}/assign",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def assign_audit_review(
    review_id: str,
    req: AssignReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Assign audit review to designated officer."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await assign_review(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "new_status": updated["status"], "assigned_officer": updated["assigned_officer"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/accept",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def accept_ai_review(
    review_id: str,
    req: AcceptReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Accept AI outcome and set final human-verified status."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await accept_ai_result(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "new_status": updated["status"], "final_human_status": updated["final_human_status"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/reject",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def reject_ai_review(
    review_id: str,
    req: RejectReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Reject AI outcome with mandatory reason."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await reject_ai_result(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "new_status": updated["status"], "final_human_status": updated["final_human_status"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/correct-field",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def correct_extracted_field(
    review_id: str,
    req: CorrectFieldRequest,
    current_user: dict = Depends(get_current_user)
):
    """Correct extracted statutory declaration value with deterministic recalculation."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await correct_field(review_id, current_user, req)
        human_res = updated.get("human_verified_result") or {}
        return {
            "status": "success",
            "review_id": review_id,
            "field_name": req.field_name,
            "corrected_value": req.corrected_value,
            "human_score": human_res.get("score"),
            "human_risk_level": human_res.get("risk_level")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/evidence/add",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def add_review_evidence(
    review_id: str,
    req: AddEvidenceRequest,
    current_user: dict = Depends(get_current_user)
):
    """Annotate and link missing evidence from package image."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await add_missing_evidence(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "total_modifications": len(updated.get("evidence_modifications", []))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/evidence/remove",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def remove_review_evidence(
    review_id: str,
    req: RemoveEvidenceRequest,
    current_user: dict = Depends(get_current_user)
):
    """Soft-remove incorrect automated evidence."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await remove_incorrect_evidence(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "evidence_id": req.evidence_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/comment",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def add_comment(
    review_id: str,
    req: AddCommentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add structured comment to review."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await add_officer_comment(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "total_comments": len(updated.get("comments", []))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/escalate",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def escalate_audit_review(
    review_id: str,
    req: EscalateReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Escalate review to senior officers or administrators."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await escalate_review(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "new_status": updated["status"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{review_id}/reopen",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def reopen_audit_review(
    review_id: str,
    req: ReopenReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Reopen a completed or verified review."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        updated = await reopen_review(review_id, current_user, req)
        return {"status": "success", "review_id": review_id, "new_status": updated["status"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{review_id}/ai-vs-human",
    response_model=AIvsHumanComparison,
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def get_ai_vs_human_diff(
    review_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Side-by-side comparison between automated AI output and human verified output."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    try:
        return await generate_ai_vs_human_comparison(review_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{review_id}/history",
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT))]
)
async def get_review_history_timeline(
    review_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Chronological review history audit trail."""
    raw = await get_review(review_id)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    _check_review_access(current_user, raw)
    rev = parse_review_db_record(raw)
    return {"review_id": review_id, "history": rev.get("history", []), "total": len(rev.get("history", []))}
