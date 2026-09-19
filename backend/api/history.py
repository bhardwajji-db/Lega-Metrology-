import os
import json
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from collections import Counter
from config import settings, PROD_UPLOAD_DIR
from database.db import (
    get_analyses, get_analysis, get_stats, delete_analysis,
    delete_all_user_analyses, search_analyses, get_trend_stats,
)
from models.schemas import AnalysisResponse, HistoryItem, DashboardStats, ComplianceResult, ProductInfo, OCRResult, ProductImageEvidence, ComplianceCheck
from compliance.rules.legal_metrology import compute_font_size_and_readability
from integrations.fssai.verifier import fssai_verifier
from integrations.gs1.verifier import gs1_verifier
from api.demo import build_demo_response
from auth.security import get_current_user, check_tenant_access, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT
from services.integrity_service import verify_analysis_integrity
from claims.models import ClaimAnalysisResult

router = APIRouter()


def _is_demo_id(analysis_id: str) -> bool:
    if not analysis_id:
        return False
    aid = str(analysis_id).strip().lower()
    return aid.startswith("demo-") or aid in ("1", "2", "3")


def _check_history_access(user: dict, data: dict):
    """Strict tenant isolation, IDOR, and RBAC access control protection for history items."""
    if not check_tenant_access(user, data):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to access or modify this record. Merchants can only delete their own records."
        )


def _cleanup_analysis_files(data: dict, analysis_id: str):
    """Safely remove uploaded image files associated with an analysis."""
    import sys
    is_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    if settings.TEST_MODE or os.environ.get("TEST_MODE") == "1" or is_pytest:
        if os.path.abspath(settings.UPLOAD_DIR) == PROD_UPLOAD_DIR:
            raise RuntimeError(
                f"SAFETY ERROR: Automated tests cannot clean files from the production/development uploads directory ({PROD_UPLOAD_DIR})!\n"
                f"Ensure tests set settings.UPLOAD_DIR to a temporary directory."
            )

    upload_dir_abs = os.path.abspath(settings.UPLOAD_DIR)
    filenames = []

    if data.get('image_filename'):
        filenames.append(data['image_filename'])

    if data.get('images'):
        try:
            imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
            for im in imgs:
                if isinstance(im, dict) and im.get('filename'):
                    filenames.append(im['filename'])
        except Exception:
            pass

    for fname in set(filenames):
        if not fname:
            continue
        clean_fname = os.path.basename(fname)
        target_path = os.path.abspath(os.path.join(upload_dir_abs, clean_fname))
        if target_path.startswith(upload_dir_abs) and os.path.isfile(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass


def _user_owns_record(user: Optional[dict], owner_user_id: Optional[str]) -> bool:
    if not user:
        return True
    if user.get("role") in (ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT):
        return True
    if not owner_user_id:
        return True
    username = user.get("username") or ""
    uid = str(user.get("id", "")) if user.get("id") is not None else ""
    return owner_user_id == username or (bool(uid) and owner_user_id == uid)


@router.get("/history", response_model=List[HistoryItem])
async def list_history(user: dict = Depends(get_current_user)):
    """Return list of screening analyses with tenant and IDOR protection."""
    user_role = user.get("role")
    user_org = (user.get("organization_id") or "").strip()

    if user_role == ROLE_ADMIN:
        analyses = await get_analyses()
    else:
        if not user_org:
            return []
        analyses = await get_analyses(organization_id=user_org)

    history = []
    for a in analyses:
        if _is_demo_id(a.get('id', '')):
            continue
        
        # Verify tenant boundary via fail-closed guard
        if not check_tenant_access(user, a):
            continue

        img_fn = a.get('image_filename') or ''
        image_url = f"/api/images/{img_fn}" if img_fn else "/placeholder.png"
        history.append(HistoryItem(
            id=a['id'],
            product_name=a['product_name'],
            score=a['score'],
            status=a['status'],
            created_at=a['created_at'],
            image_url=image_url,
            owner_user_id=a.get('owner_user_id'),
            organization_id=a.get('organization_id'),
            integrity_hash=a.get('integrity_hash')
        ))
    return history


@router.get("/history/search")
async def search_history(
    q: str = Query(default="", description="Search query (product name, ID, OCR text)"),
    status: str = Query(default="ALL", description="Filter: ALL|COMPLIANT|VIOLATIONS|NEEDS_REVIEW"),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Search & filter analysed products — requires authentication with tenant and IDOR protection."""
    user_role = user.get("role")
    user_org = (user.get("organization_id") or "").strip()

    if user_role != ROLE_ADMIN and not user_org:
        return []

    org_filter = user_org if (user_role != ROLE_ADMIN and user_org) else None

    rows = await search_analyses(query=q, status=status, organization_id=org_filter, limit=limit)
    res = []
    for a in rows:
        if not check_tenant_access(user, a):
            continue

        img_fn = a.get('image_filename') or ''
        image_url = f"/api/images/{img_fn}" if img_fn else "/placeholder.png"
        res.append(HistoryItem(
            id=a['id'],
            product_name=a['product_name'],
            score=a['score'],
            status=a['status'],
            created_at=a['created_at'],
            image_url=image_url,
            owner_user_id=a.get('owner_user_id'),
            organization_id=a.get('organization_id'),
            integrity_hash=a.get('integrity_hash')
        ).model_dump())
    return res


@router.get("/history/{id}/integrity")
async def check_analysis_integrity_endpoint(id: str):
    """
    Verify the tamper-evident cryptographic hash of a stored screening analysis.
    Recalculates SHA-256 canonical hash across all static fields and compares with stored digest.
    """
    if _is_demo_id(id):
        return {
            "analysis_id": id,
            "verified": True,
            "is_demo_fixture": True,
            "message": "Demo benchmark fixtures are static immutable references."
        }

    data = await get_analysis(id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stored_hash = data.get("integrity_hash") or ""
    extracted_data = json.loads(data['extracted_data']) if isinstance(data['extracted_data'], str) else (data['extracted_data'] or {})
    compliance_result = json.loads(data['compliance_result']) if isinstance(data['compliance_result'], str) else (data['compliance_result'] or {})

    verification_result = verify_analysis_integrity(
        stored_hash=stored_hash,
        analysis_id=data['id'],
        created_at=data['created_at'],
        product_name=data['product_name'],
        score=data['score'],
        status=data['status'],
        extracted_data=extracted_data,
        compliance_result=compliance_result
    )
    verification_result["system_version"] = data.get("system_version")
    verification_result["ruleset_version"] = data.get("ruleset_version")
    verification_result["ocr_engine_version"] = data.get("ocr_engine_version")
    return verification_result


@router.get("/history/{id}", response_model=AnalysisResponse)
async def get_history_item(id: str, user: dict = Depends(get_current_user)):
    """Retrieve an analysis record by ID. Serves demo benchmarks directly from in-memory fixtures."""
    if _is_demo_id(id):
        return build_demo_response(id)

    data = await get_analysis(id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    _check_history_access(user, data)

    images_list = []
    if 'images' in data and data['images']:
        try:
            raw_imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
            for img in raw_imgs:
                if isinstance(img, dict) and img.get('filename'):
                    images_list.append(ProductImageEvidence(**img))
                elif isinstance(img, ProductImageEvidence) and img.filename:
                    images_list.append(img)
        except Exception:
            images_list = []

    if not images_list and data.get('image_filename'):
        images_list = [ProductImageEvidence(
            filename=data['image_filename'],
            image_url=f"/api/images/{data['image_filename']}",
            label="Front"
        )]

    extracted_dict = json.loads(data['extracted_data']) if isinstance(data['extracted_data'], str) else data['extracted_data']
    prod_info = ProductInfo(**extracted_dict)

    compliance_dict = json.loads(data['compliance_result']) if isinstance(data['compliance_result'], str) else (data['compliance_result'] or {})
    if 'score' not in compliance_dict:
        compliance_dict['score'] = float(data.get('score', 0.0) or 0.0)
    if 'status' not in compliance_dict:
        compliance_dict['status'] = data.get('status', 'UNKNOWN') or 'UNKNOWN'
    checks_list = compliance_dict.get('checks', [])
    if 'total_rules' not in compliance_dict:
        compliance_dict['total_rules'] = len(checks_list)
    if 'passed_rules' not in compliance_dict:
        compliance_dict['passed_rules'] = sum(1 for c in checks_list if (isinstance(c, dict) and c.get('status') in ('PASS', 'COMPLIANT')) or getattr(c, 'status', '') in ('PASS', 'COMPLIANT'))
    if 'failed_rules' not in compliance_dict:
        compliance_dict['failed_rules'] = sum(1 for c in checks_list if (isinstance(c, dict) and c.get('status') in ('FAIL', 'NON_COMPLIANT')) or getattr(c, 'status', '') in ('FAIL', 'NON_COMPLIANT'))

    if 'recommendations' not in compliance_dict or not compliance_dict['recommendations']:
        from compliance.recommendations import generate_recommendations
        checks = [ComplianceCheck(**c) if isinstance(c, dict) else c for c in checks_list]
        compliance_dict['recommendations'] = [r.model_dump() for r in generate_recommendations(checks)]

    compliance_res = ComplianceResult(**compliance_dict)

    aggregated_words = []
    for ev in images_list:
        if ev.words:
            aggregated_words.extend(ev.words)

    mock_ocr = OCRResult(
        full_text=data['ocr_text'],
        words=aggregated_words,
        language="eng",
        processing_time=0.0
    )

    font_size_analysis = compute_font_size_and_readability(
        product_info=prod_info,
        ocr_result=mock_ocr,
        images=images_list,
        checks=compliance_res.checks
    )

    fssai_verification = await fssai_verifier.verify(prod_info.fssai_license)
    barcode_val = prod_info.barcode_detected or getattr(prod_info, 'barcode', None) or (prod_info.other_declarations.get('barcode') if prod_info.other_declarations else None)
    gs1_verification = await gs1_verifier.verify(barcode_val)

    primary_image_filename = data.get('image_filename') or (images_list[0].filename if images_list else '')
    primary_image_url = f"/api/images/{primary_image_filename}" if primary_image_filename else "/placeholder.png"

    claims_analysis_obj = None
    if 'claims_analysis' in data and data['claims_analysis']:
        try:
            raw_claims = json.loads(data['claims_analysis']) if isinstance(data['claims_analysis'], str) else data['claims_analysis']
            claims_analysis_obj = ClaimAnalysisResult(**raw_claims)
        except Exception:
            claims_analysis_obj = None
    if not claims_analysis_obj:
        from claims.engine import claim_engine
        claims_analysis_obj = claim_engine.analyze(product_info=prod_info, ocr_text=data.get('ocr_text', ''), images=images_list)

    return AnalysisResponse(
        id=data['id'],
        product_name=data['product_name'],
        image_url=primary_image_url,
        images=images_list,
        ocr_result={"full_text": data['ocr_text'], "words": aggregated_words, "language": "eng", "processing_time": 0.0},
        product_info=prod_info,
        compliance_result=compliance_res,
        recommendations=compliance_res.recommendations,
        created_at=data['created_at'],
        font_size_analysis=font_size_analysis,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification,
        calibration_result=None,
        owner_user_id=data.get('owner_user_id'),
        organization_id=data.get('organization_id'),
        integrity_hash=data.get('integrity_hash'),
        system_version=data.get('system_version'),
        ocr_engine_version=data.get('ocr_engine_version'),
        ruleset_version=data.get('ruleset_version'),
        claims_analysis=claims_analysis_obj
    )


@router.delete("/history/{id}")
async def delete_history_item(id: str, user: dict = Depends(get_current_user)):
    if _is_demo_id(id):
        raise HTTPException(status_code=403, detail="Demonstration benchmark cases are protected and cannot be deleted.")

    data = await get_analysis(id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID '{id}' not found.")

    _check_history_access(user, data)

    user_role = user.get("role")
    if user_role in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        # Privileged roles can delete screening records within their jurisdiction/tenant
        pass
    elif user_role == ROLE_MERCHANT:
        owner = data.get("owner_user_id") or ""
        username = user.get("username") or ""
        user_id_str = str(user.get("id", "")) if user.get("id") is not None else ""
        
        is_owner = bool(owner) and (owner == username or (user_id_str and owner == user_id_str))
        if not is_owner:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to delete this screening record. Merchants can only delete their own records."
            )
    else:
        raise HTTPException(
            status_code=403,
            detail="Insufficient privileges to delete screening records."
        )

    _cleanup_analysis_files(data, id)
    success = await delete_analysis(id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Failed to delete analysis '{id}'.")

    return {"message": f"Analysis '{id}' deleted successfully", "id": id}


@router.delete("/history")
async def clear_all_history(user: dict = Depends(get_current_user)):
    if user["role"] not in (ROLE_ADMIN,):
        raise HTTPException(status_code=403, detail="Admin role required to clear all history.")
    analyses = await get_analyses()
    user_analyses = [a for a in analyses if not _is_demo_id(a.get('id', ''))]

    for a in user_analyses:
        _cleanup_analysis_files(a, a['id'])

    deleted_count = await delete_all_user_analyses()
    return {
        "message": f"Successfully deleted {deleted_count} analyses.",
        "deleted_count": deleted_count
    }


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """Return dashboard statistics reflecting only real user screenings with workspace filtering."""
    stats = await get_stats(user=user)
    return DashboardStats(
        total_analyzed=stats['total_analyzed'],
        compliant=stats['compliant'],
        needs_review=stats.get('needs_review', 0),
        failures=stats.get('failures', 0),
        violations=stats.get('violations', 0),
        average_score=stats['average_score'],
        packages_screened=stats.get('packages_screened', stats['total_analyzed']),
        compliant_packages=stats.get('compliant_packages', stats['compliant']),
        review_findings=stats.get('review_findings', stats.get('needs_review', 0)),
        failed_findings=stats.get('failed_findings', stats.get('failures', 0)),
        recent=[HistoryItem(
            id=a['id'],
            product_name=a['product_name'],
            score=a['score'],
            status=a['status'],
            created_at=a['created_at'],
            image_url=f"/api/images/{a['image_filename']}" if a.get('image_filename') else "/placeholder.png",
            owner_user_id=a.get('owner_user_id'),
            organization_id=a.get('organization_id')
        ) for a in stats['recent']]
    )


@router.get("/stats/trends")
async def get_trends(days: int = Query(default=14, ge=7, le=90),
                     user: dict = Depends(get_current_user)):
    """Daily screening trend stats for the dashboard (last N days) scoped to tenant/user."""
    return await get_trend_stats(
        days=days,
        organization_id=user.get("organization_id"),
        owner_user_id=user.get("username"),
        user_role=user.get("role")
    )


@router.get("/stats/by-status")
async def get_stats_by_status(user: dict = Depends(get_current_user)):
    """Status breakdown for dashboard pie chart scoped to tenant/user."""
    role = user.get("role")
    org_id = user.get("organization_id")

    if role == "ADMIN":
        analyses = await get_analyses()
    elif role in ("ENFORCEMENT_OFFICER", "AUDIT_OFFICER"):
        analyses = await get_analyses(organization_id=org_id)
    elif role == "MERCHANT_PUBLIC":
        analyses = await get_analyses(organization_id=org_id)
        username = (user.get("username") or "").lower()
        user_id_str = str(user.get("id", "")) if user.get("id") is not None else ""
        analyses = [
            a for a in analyses
            if a.get("owner_user_id") and (
                a.get("owner_user_id", "").lower() == username or
                (user_id_str and str(a.get("owner_user_id", "")) == user_id_str)
            )
        ]
    elif org_id:
        analyses = await get_analyses(organization_id=org_id)
    else:
        analyses = await get_analyses()

    counts = Counter(a.get("status", "UNKNOWN") for a in analyses)
    return {"labels": list(counts.keys()), "values": list(counts.values())}