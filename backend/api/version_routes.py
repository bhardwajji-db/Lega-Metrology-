import json
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
import io
import csv

from models.schemas import ProductInfo, ComplianceResult
from models.version_schemas import (
    VersionSnapshot,
    VersionComparisonRequest,
    VersionComparisonResult,
    VersionTimelineEvent
)
from services.version_comparison_service import compare_versions
from database.db import (
    get_analysis,
    get_analyses,
    get_artwork,
    list_artworks,
    save_version_comparison,
    get_version_comparison,
    list_version_comparisons,
    delete_version_comparison,
    get_version_timeline,
    _extract_analysis_risk_info
)
from auth.security import (
    get_current_user,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)

router = APIRouter(prefix="/api/versions", tags=["versions"])


async def _resolve_snapshot(version_id: str, version_type: str = "ANALYSIS", user: Optional[dict] = None) -> VersionSnapshot:
    """Helper to resolve a VersionSnapshot from either analyses or artworks table with tenant check."""
    v_type = version_type.upper()

    if v_type == "ARTWORK" or version_id.startswith("art-"):
        art = await get_artwork(version_id)
        if not art:
            raise HTTPException(status_code=404, detail=f"Artwork version '{version_id}' not found.")
        if user and not check_tenant_access(user, art):
            raise HTTPException(status_code=403, detail="Access denied. Cross-tenant artwork comparison prohibited.")
        
        ana_res = art.get("analysis_result") or {}
        p_info_dict = ana_res.get("product_info") or {}
        p_info = ProductInfo(**p_info_dict) if p_info_dict else ProductInfo(product_name=art.get("filename"))
        
        comp_dict = ana_res.get("compliance_result") or {}
        comp_res = ComplianceResult(**comp_dict) if comp_dict else None

        score = float(ana_res.get("overall_score", 0.0))
        risk_level = "LOW" if score >= 90 else ("MEDIUM" if score >= 70 else "CRITICAL")

        return VersionSnapshot(
            version_id=art["id"],
            version_label=f"{art['filename']} (v{art.get('iteration_number', 1)})",
            version_type="ARTWORK",
            product_name=art["filename"],
            timestamp=art.get("created_at", ""),
            score=score,
            risk_level=risk_level,
            image_url=f"/api/images/{art['filename']}",
            owner_user_id=art.get("owner_user_id", ""),
            organization_id=art.get("organization_id"),
            product_info=p_info,
            compliance_result=comp_res
        )

    else:
        # Default: ANALYSIS
        analysis = await get_analysis(version_id)
        if not analysis and (version_id.startswith("demo-") or version_id in ("1", "2", "3")):
            from api.demo import get_demo_case
            clean_id = version_id.replace("demo-", "") if version_id.startswith("demo-") else version_id
            demo_resp = await get_demo_case(clean_id)
            if demo_resp:
                return VersionSnapshot(
                    version_id=version_id,
                    version_label=f"Demo Benchmark: {demo_resp.product_info.product_name}",
                    version_type="ANALYSIS",
                    product_name=demo_resp.product_info.product_name,
                    timestamp="2026-01-01T00:00:00Z",
                    score=float(demo_resp.score),
                    risk_level=demo_resp.risk_level,
                    image_url=f"/api/images/{demo_resp.images[0].filename}" if demo_resp.images else "",
                    owner_user_id="",
                    organization_id=None,
                    product_info=demo_resp.product_info,
                    compliance_result=demo_resp.compliance_result
                )

        if not analysis:
            raise HTTPException(status_code=404, detail=f"Analysis version '{version_id}' not found.")
        
        if user and not check_tenant_access(user, analysis):
            raise HTTPException(status_code=403, detail="Access denied. Cross-tenant analysis comparison prohibited.")

        raw_p_info = analysis.get("extracted_data")
        if isinstance(raw_p_info, str):
            try: raw_p_info = json.loads(raw_p_info)
            except Exception: raw_p_info = {}
        p_info = ProductInfo(**raw_p_info) if raw_p_info else ProductInfo(product_name=analysis.get("product_name"))

        cr_data = analysis.get("compliance_result")
        if isinstance(cr_data, str):
            try: cr_data = json.loads(cr_data)
            except Exception: cr_data = {}
        comp_res = ComplianceResult(**cr_data) if cr_data else None

        info = _extract_analysis_risk_info(analysis)
        images = analysis.get("images")
        if isinstance(images, str):
            try: images = json.loads(images)
            except Exception: images = []
        image_url = images[0].get("image_url") if images and len(images) > 0 else f"/api/images/{analysis.get('image_filename')}"

        return VersionSnapshot(
            version_id=analysis["id"],
            version_label=f"{analysis.get('product_name', 'Product')} ({analysis['id'][:8]})",
            version_type="ANALYSIS",
            product_name=analysis.get("product_name", "Unknown Product"),
            timestamp=analysis.get("created_at", ""),
            score=float(info["score"]),
            risk_level=info["risk_level"],
            image_url=image_url,
            owner_user_id=analysis.get("owner_user_id", ""),
            organization_id=analysis.get("organization_id"),
            product_info=p_info,
            compliance_result=comp_res
        )


@router.post("/compare", response_model=VersionComparisonResult)
async def compare_two_versions(
    req: VersionComparisonRequest,
    user: dict = Depends(get_current_user),
):
    """
    Compares Version A (Base) vs Version B (Target/Revised).
    Computes field changes, MRP shifts, quantity deltas, ingredient diffs,
    nutrition tables, score deltas, rule state transitions, and issue resolution matrix.
    Enforces dual-sided authorization and blocks mixed cross-tenant comparisons.
    """
    snap_a = await _resolve_snapshot(req.version_a_id, req.version_type_a, user=user)
    snap_b = await _resolve_snapshot(req.version_b_id, req.version_type_b, user=user)

    # Check for mixed cross-tenant comparison
    user_role = user.get("role")
    if user_role != ROLE_ADMIN:
        org_a = snap_a.organization_id
        org_b = snap_b.organization_id
        if org_a and org_b and org_a != org_b:
            raise HTTPException(status_code=403, detail="Access denied. Cross-tenant mixed version comparison prohibited.")

    result = compare_versions(snap_a, snap_b)
    res_dict = result.model_dump()
    res_dict["owner_user_id"] = user.get("username", "")
    res_dict["organization_id"] = user.get("organization_id", "")
    await save_version_comparison(res_dict)
    return result


@router.get("/comparisons")
async def list_recent_comparisons(
    owner_user_id: Optional[str] = Query(None, description="Optional filter by user ID"),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """List saved version comparisons scoped to tenant."""
    user_role = user.get("role")
    user_org = (user.get("organization_id") or "").strip()

    if user_role == ROLE_ADMIN:
        comps = await list_version_comparisons(owner_user_id=owner_user_id, organization_id=None, limit=limit)
    else:
        if not user_org:
            return {"comparisons": [], "total": 0}
        effective_owner = user.get("username") if user_role == ROLE_MERCHANT else owner_user_id
        raw_comps = await list_version_comparisons(owner_user_id=effective_owner, organization_id=user_org, limit=limit)
        comps = [c for c in raw_comps if check_tenant_access(user, c)]

    return {"comparisons": comps, "total": len(comps)}


@router.get("/comparisons/{comparison_id}", response_model=VersionComparisonResult)
async def get_comparison_details(
    comparison_id: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve details for a specific version comparison with tenant authorization."""
    comp = await get_version_comparison(comparison_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")
    if not check_tenant_access(user, comp):
        raise HTTPException(status_code=403, detail="Access denied to this comparison.")
    return comp


@router.delete("/comparisons/{comparison_id}")
async def delete_comparison(
    comparison_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a saved version comparison with tenant authorization."""
    comp = await get_version_comparison(comparison_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")
    if not check_tenant_access(user, comp):
        raise HTTPException(status_code=403, detail="Access denied to delete this comparison.")
    
    deleted = await delete_version_comparison(comparison_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")
    return {"status": "deleted", "comparison_id": comparison_id}


@router.get("/comparisons/{comparison_id}/json")
async def export_comparison_json(
    comparison_id: str,
    user: dict = Depends(get_current_user),
):
    """Export the version comparison result as formatted JSON."""
    comp = await get_version_comparison(comparison_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")
    if not check_tenant_access(user, comp):
        raise HTTPException(status_code=403, detail="Access denied to this comparison.")
    
    json_bytes = json.dumps(comp, indent=2).encode('utf-8')
    filename = f"metrcheck-version-comparison-{comparison_id}.json"
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/comparisons/{comparison_id}/csv")
async def export_comparison_csv(
    comparison_id: str,
    user: dict = Depends(get_current_user),
):
    """Export the version comparison deltas as a CSV report with formula sanitization."""
    comp = await get_version_comparison(comparison_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")
    if not check_tenant_access(user, comp):
        raise HTTPException(status_code=403, detail="Access denied to this comparison.")
    
    from api.report import sanitize_spreadsheet_value

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([sanitize_spreadsheet_value("METRCHECK AI — VERSION COMPARISON AUDIT REPORT")])
    writer.writerow([sanitize_spreadsheet_value("Comparison ID"), sanitize_spreadsheet_value(comp.get("id", comparison_id))])
    writer.writerow([sanitize_spreadsheet_value("Product"), sanitize_spreadsheet_value(comp.get("product_name", ""))])
    writer.writerow([sanitize_spreadsheet_value("Timestamp"), sanitize_spreadsheet_value(comp.get("created_at", ""))])
    writer.writerow([sanitize_spreadsheet_value("Version A Score"), sanitize_spreadsheet_value(comp.get("version_a_score", 0))])
    writer.writerow([sanitize_spreadsheet_value("Version B Score"), sanitize_spreadsheet_value(comp.get("version_b_score", 0))])
    writer.writerow([sanitize_spreadsheet_value("Score Delta"), sanitize_spreadsheet_value(comp.get("score_delta", 0))])
    writer.writerow([sanitize_spreadsheet_value("Overall Verdict"), sanitize_spreadsheet_value(comp.get("overall_verdict", ""))])
    writer.writerow([])

    # Field Diffs
    diffs = comp.get("field_diffs", [])
    if diffs:
        writer.writerow([sanitize_spreadsheet_value("FIELD-BY-FIELD DECLARATION COMPARISON")])
        writer.writerow([
            sanitize_spreadsheet_value("Field Name"),
            sanitize_spreadsheet_value("Change Type"),
            sanitize_spreadsheet_value("Version A Value"),
            sanitize_spreadsheet_value("Version B Value"),
            sanitize_spreadsheet_value("Compliance Impact"),
            sanitize_spreadsheet_value("Explanation")
        ])
        for d in diffs:
            writer.writerow([
                sanitize_spreadsheet_value(d.get("field_name", "")),
                sanitize_spreadsheet_value(d.get("change_type", "")),
                sanitize_spreadsheet_value(d.get("value_a", "")),
                sanitize_spreadsheet_value(d.get("value_b", "")),
                sanitize_spreadsheet_value(d.get("compliance_impact", "")),
                sanitize_spreadsheet_value(d.get("explanation", ""))
            ])
        writer.writerow([])

    # Rule Transitions
    r_trans = comp.get("rule_transitions", [])
    if r_trans:
        writer.writerow([sanitize_spreadsheet_value("RULE STATE TRANSITIONS")])
        writer.writerow([
            sanitize_spreadsheet_value("Rule ID"),
            sanitize_spreadsheet_value("Field"),
            sanitize_spreadsheet_value("Status A"),
            sanitize_spreadsheet_value("Status B"),
            sanitize_spreadsheet_value("Transition Type"),
            sanitize_spreadsheet_value("Detail")
        ])
        for rt in r_trans:
            writer.writerow([
                sanitize_spreadsheet_value(rt.get("rule_id", "")),
                sanitize_spreadsheet_value(rt.get("field", "")),
                sanitize_spreadsheet_value(rt.get("status_a", "")),
                sanitize_spreadsheet_value(rt.get("status_b", "")),
                sanitize_spreadsheet_value(rt.get("transition_type", "")),
                sanitize_spreadsheet_value(rt.get("detail", ""))
            ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    filename = f"metrcheck-version-comparison-{comparison_id}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/timeline/{entity_id}")
async def get_entity_version_timeline(
    entity_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Retrieve chronological version timeline events for a product name or artwork chain scoped to tenant.
    """
    events = await get_version_timeline(
        entity_id=entity_id,
        organization_id=user.get("organization_id"),
        owner_user_id=user.get("username"),
        user_role=user.get("role")
    )
    return {"entity_id": entity_id, "events": events, "total": len(events)}


@router.get("/targets")
async def list_comparable_version_targets(
    owner_user_id: Optional[str] = Query(None, description="Optional filter by user ID"),
    user: dict = Depends(get_current_user),
):
    """
    Returns available version snapshots (both physical screenings and artwork iterations)
    for Version A and Version B selection, strictly scoped to tenant.
    """
    user_role = user.get("role")
    effective_org = user.get("organization_id")
    effective_owner = owner_user_id

    if user_role == ROLE_ADMIN:
        effective_org = None
    elif user_role == ROLE_MERCHANT:
        effective_owner = user.get("username")
        effective_org = user.get("organization_id")

    analyses = await get_analyses(organization_id=effective_org)
    artworks = await list_artworks(owner_user_id=effective_owner, organization_id=effective_org)

    targets: List[Dict[str, Any]] = []

    # Add Analyses
    for a in analyses:
        if effective_owner and a.get("owner_user_id") and a.get("owner_user_id", "").lower() != effective_owner.lower():
            continue
        info = _extract_analysis_risk_info(a)
        targets.append({
            "version_id": a["id"],
            "version_label": f"Screening: {a.get('product_name', 'Unknown')} ({a['id'][:8]})",
            "version_type": "ANALYSIS",
            "product_name": a.get("product_name", "Unknown Product"),
            "timestamp": a.get("created_at", ""),
            "score": float(info["score"]),
            "risk_level": info["risk_level"]
        })

    # Add Artworks
    for art in artworks:
        ana_res = art.get("analysis_result") or {}
        score = float(ana_res.get("overall_score", 0.0))
        targets.append({
            "version_id": art["id"],
            "version_label": f"Artwork: {art['filename']} (v{art.get('iteration_number', 1)})",
            "version_type": "ARTWORK",
            "product_name": art.get("filename", ""),
            "timestamp": art.get("created_at", ""),
            "score": score,
            "risk_level": "LOW" if score >= 90 else "MEDIUM",
            "iteration_number": art.get("iteration_number", 1),
            "parent_artwork_id": art.get("parent_artwork_id")
        })

    # Sort newest first
    targets.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"targets": targets, "total": len(targets)}


