"""
API router for Explainable AI / Evidence System endpoints.
Provides evidence correction, review actions, audit history, spatial heatmaps, and panel compliance summaries.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from models.schemas import (
    EvidenceCorrectionRequest,
    EvidenceReviewActionRequest,
    EvidenceAuditLogItem,
    EvidenceHistoryResponse,
    EvidenceHeatmapResponse,
    PanelComplianceHeatmapResponse,
    AnalysisResponse,
)
from compliance.evidence_locator import compute_evidence_heatmap, get_panel_compliance_summary
from database.db import (
    get_analysis,
    save_evidence_audit_log,
    get_evidence_audit_logs,
    update_analysis_compliance_evidence,
)
from auth.security import get_current_user, require_roles, check_tenant_access, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.post("/{analysis_id}/correct", response_model=AnalysisResponse)
async def correct_evidence(
    analysis_id: str,
    req: EvidenceCorrectionRequest,
    current_user: dict = Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT)),
):
    analysis_data = await get_analysis(analysis_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID {analysis_id} not found")

    if not check_tenant_access(current_user, analysis_data):
        raise HTTPException(status_code=403, detail="Access denied. Cross-organization evidence correction prohibited.")

    analysis_res = analysis_data.get("result")
    if not analysis_res:
        raise HTTPException(status_code=400, detail="Analysis result data is missing")

    evidence_list = analysis_res.get("evidence", [])
    matched_ev = None
    for ev in evidence_list:
        if ev.get("id") == req.evidence_id or ev.get("linked_rule_id") == req.rule_id:
            matched_ev = ev
            break

    old_val = str(matched_ev.get("text") or matched_ev.get("extracted_text")) if matched_ev else "None"
    new_val = req.corrected_value

    if matched_ev:
        matched_ev["text"] = req.corrected_value
        matched_ev["confidence"] = 100.0
        matched_ev["reliability_score"] = 100.0
        matched_ev["reliability_tier"] = "HIGH"
        matched_ev["match_method"] = "DIRECT_OCR"
        matched_ev["evidence_status"] = "VERIFIED"
        if req.corrected_bbox:
            matched_ev["bbox"] = req.corrected_bbox
    else:
        new_ev = {
            "id": req.evidence_id or f"{req.rule_id}-ev-corrected",
            "image_index": 0,
            "image_label": "Front",
            "text": req.corrected_value,
            "confidence": 100.0,
            "reliability_score": 100.0,
            "reliability_tier": "HIGH",
            "match_method": "DIRECT_OCR",
            "evidence_status": "VERIFIED",
            "bbox": req.corrected_bbox,
            "linked_rule_id": req.rule_id,
        }
        evidence_list.append(new_ev)

    compliance_checks = analysis_res.get("compliance_checks", [])
    for check in compliance_checks:
        if check.get("rule_id") == req.rule_id:
            check["field_status"] = "PRESENT"
            check["reliability_score"] = 100.0
            check["reliability_tier"] = "HIGH"
            check["detected_value"] = req.corrected_value
            check["pass_reason"] = f"Verified by officer manual correction: {req.comments or 'Officer correction'}"
            check["status"] = "PASS"

    analysis_res["evidence"] = evidence_list
    analysis_res["compliance_checks"] = compliance_checks
    await update_analysis_compliance_evidence(analysis_id, analysis_res)

    user_name = str(current_user.get("username") or current_user.get("sub") or "officer")
    org_id = analysis_data.get("organization_id", "") or current_user.get("organization_id", "")
    await save_evidence_audit_log(
        analysis_id=analysis_id,
        evidence_id=req.evidence_id or f"{req.rule_id}-ev-1",
        rule_id=req.rule_id,
        actor_username=user_name,
        action_type="CORRECTION",
        previous_value=old_val,
        new_value=new_val,
        comments=req.comments or "Officer manual evidence correction",
        organization_id=org_id,
    )

    return AnalysisResponse(**analysis_res)


@router.post("/{analysis_id}/review-action")
async def review_action(
    analysis_id: str,
    req: EvidenceReviewActionRequest,
    current_user: dict = Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT)),
):
    analysis_data = await get_analysis(analysis_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID {analysis_id} not found")

    if not check_tenant_access(current_user, analysis_data):
        raise HTTPException(status_code=403, detail="Access denied. Cross-organization evidence review prohibited.")

    analysis_res = analysis_data.get("result")
    if not analysis_res:
        raise HTTPException(status_code=400, detail="Analysis result data is missing")

    compliance_checks = analysis_res.get("compliance_checks", [])
    matched_check = None
    for check in compliance_checks:
        if check.get("rule_id") == req.rule_id:
            matched_check = check
            break

    if not matched_check:
        raise HTTPException(status_code=404, detail=f"Rule {req.rule_id} not found in analysis")

    old_status = matched_check.get("status")
    user_name = str(current_user.get("username") or current_user.get("sub") or "officer")

    if req.action == "APPROVE":
        matched_check["status"] = "PASS"
        matched_check["pass_reason"] = f"Approved by officer ({user_name}): {req.comments or 'No comments provided'}"
        matched_check["reliability_tier"] = "HIGH"
        matched_check["reliability_score"] = 100.0
    elif req.action == "REJECT":
        matched_check["status"] = "FAIL"
        matched_check["fail_reason"] = f"Rejected by officer ({user_name}): {req.comments or 'No comments provided'}"
    elif req.action == "REQUEST_RESCAN":
        matched_check["status"] = "NEEDS_REVIEW"
        matched_check["review_reason"] = f"Rescan requested by officer ({user_name}): {req.comments or 'No comments provided'}"

    analysis_res["compliance_checks"] = compliance_checks
    await update_analysis_compliance_evidence(analysis_id, analysis_res)

    org_id = analysis_data.get("organization_id", "") or current_user.get("organization_id", "")
    await save_evidence_audit_log(
        analysis_id=analysis_id,
        evidence_id=req.evidence_id or f"{req.rule_id}-ev-1",
        rule_id=req.rule_id,
        actor_username=user_name,
        action_type=req.action,
        previous_value=old_status,
        new_value=matched_check.get("status"),
        comments=req.comments or f"Officer review action: {req.action}",
        organization_id=org_id,
    )

    return {
        "status": "success",
        "analysis_id": analysis_id,
        "rule_id": req.rule_id,
        "action": req.action,
        "new_status": matched_check.get("status"),
    }


@router.get("/{analysis_id}/history", response_model=EvidenceHistoryResponse)
async def get_evidence_history(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
):
    analysis_data = await get_analysis(analysis_id)
    if analysis_data and not check_tenant_access(current_user, analysis_data):
        raise HTTPException(status_code=403, detail="Access denied. Cross-organization evidence history prohibited.")

    logs = await get_evidence_audit_logs(analysis_id)
    return EvidenceHistoryResponse(
        analysis_id=analysis_id,
        logs=[EvidenceAuditLogItem(**log) for log in logs],
        total_records=len(logs),
    )


@router.get("/{analysis_id}/heatmap", response_model=List[EvidenceHeatmapResponse])
async def get_heatmap(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
):
    analysis_data = await get_analysis(analysis_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID {analysis_id} not found")

    if not check_tenant_access(current_user, analysis_data):
        raise HTTPException(status_code=403, detail="Access denied. Cross-organization heatmap prohibited.")

    analysis_res = analysis_data.get("result", {})
    images = analysis_res.get("images", [])
    compliance_checks = analysis_res.get("compliance_checks", [])

    return compute_evidence_heatmap(images, compliance_checks, analysis_id=analysis_id)


@router.get("/{analysis_id}/panel-summary", response_model=PanelComplianceHeatmapResponse)
async def get_panel_summary(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
):
    analysis_data = await get_analysis(analysis_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID {analysis_id} not found")

    if not check_tenant_access(current_user, analysis_data):
        raise HTTPException(status_code=403, detail="Access denied. Cross-organization panel summary prohibited.")

    analysis_res = analysis_data.get("result", {})
    images = analysis_res.get("images", [])
    compliance_checks = analysis_res.get("compliance_checks", [])

    return get_panel_compliance_summary(compliance_checks, images, analysis_id=analysis_id)