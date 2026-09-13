import os
import json
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from collections import Counter
from config import settings, PROD_UPLOAD_DIR
from database.db import (
    get_analyses, get_analysis, get_stats, delete_analysis,
    delete_all_user_analyses, search_analyses, get_trend_stats,
)
from models.schemas import AnalysisResponse, HistoryItem, DashboardStats, ComplianceResult, ProductInfo, OCRResult, ProductImageEvidence
from compliance.rules.legal_metrology import compute_font_size_and_readability
from integrations.fssai.verifier import fssai_verifier
from integrations.gs1.verifier import gs1_verifier
from api.demo import build_demo_response
from auth.security import get_current_user, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_MERCHANT

router = APIRouter()


def _is_demo_id(analysis_id: str) -> bool:
    if not analysis_id:
        return False
    aid = str(analysis_id).strip().lower()
    return aid.startswith("demo-") or aid in ("1", "2", "3")


def _cleanup_analysis_files(data: dict, analysis_id: str):
    """Safely remove uploaded image files associated with an analysis."""
    import sys
    is_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    if settings.TEST_MODE or os.environ.get("TEST_MODE") == "1" or is_pytest:
        if os.path.abspath(settings.UPLOAD_DIR) == PROD_UPLOAD_DIR:
            raise RuntimeError(
                f"SAFETY ERROR: Automated tests cannot clean files from the production/development uploads directory ({PROD_UPLOAD_DIR})!\n"
                f"Please ensure tests use isolated_test_env() or conftest with a dedicated temporary uploads directory."
            )
    upload_dir_abs = os.path.abspath(settings.UPLOAD_DIR)
    files_to_remove = set()

    # 1. Main image_filename
    if data and data.get('image_filename'):
        fname = data['image_filename']
        if fname and not fname.startswith('demo_') and not fname.startswith('http'):
            files_to_remove.add(os.path.basename(fname))

    # 2. Images array
    if data and data.get('images'):
        try:
            imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
            for img in imgs:
                if isinstance(img, dict) and img.get('filename'):
                    fname = img['filename']
                    if fname and not fname.startswith('demo_') and not fname.startswith('http'):
                        files_to_remove.add(os.path.basename(fname))
        except Exception:
            pass

    # 3. Any files in uploads directory prefixed with {analysis_id}_
    if os.path.exists(upload_dir_abs):
        try:
            for item in os.listdir(upload_dir_abs):
                if item.startswith(f"{analysis_id}_"):
                    files_to_remove.add(item)
        except Exception:
            pass

    # Delete the files with path traversal protection
    for fname in files_to_remove:
        clean_fname = os.path.basename(fname)
        target_path = os.path.abspath(os.path.join(upload_dir_abs, clean_fname))
        if target_path.startswith(upload_dir_abs) and os.path.isfile(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass


@router.get("/history", response_model=List[HistoryItem])
async def list_history(user: dict = Depends(get_current_user)):
    """Return list of genuine user screening analyses. Demo benchmarks are excluded."""
    analyses = await get_analyses()
    history = []
    for a in analyses:
        if _is_demo_id(a.get('id', '')):
            continue
        img_fn = a.get('image_filename') or ''
        image_url = f"/uploads/{img_fn}" if img_fn else "/placeholder.png"
        history.append(HistoryItem(
            id=a['id'],
            product_name=a['product_name'],
            score=a['score'],
            status=a['status'],
            created_at=a['created_at'],
            image_url=image_url,
            owner_user_id=a.get('owner_user_id')
        ))
    return history


@router.get("/history/search")
async def search_history(
    q: str = Query(default="", description="Search query (product name, ID, OCR text)"),
    status: str = Query(default="ALL", description="Filter: ALL|COMPLIANT|VIOLATIONS|NEEDS_REVIEW"),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Search & filter analysed products — requires authentication."""
    rows = await search_analyses(query=q, status=status, limit=limit)
    res = []
    for a in rows:
        img_fn = a.get('image_filename') or ''
        image_url = f"/uploads/{img_fn}" if img_fn else "/placeholder.png"
        res.append(HistoryItem(
            id=a['id'],
            product_name=a['product_name'],
            score=a['score'],
            status=a['status'],
            created_at=a['created_at'],
            image_url=image_url,
            owner_user_id=a.get('owner_user_id')
        ).model_dump())
    return res


@router.get("/history/{id}", response_model=AnalysisResponse)
async def get_history_item(id: str):
    """Retrieve an analysis record by ID. Serves demo benchmarks directly from in-memory fixtures."""
    if _is_demo_id(id):
        return build_demo_response(id)

    data = await get_analysis(id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

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
            image_url=f"/uploads/{data['image_filename']}",
            label="Front",
            ocr_text=data.get('ocr_text', ''),
            word_count=len(data['ocr_text'].split()) if data.get('ocr_text') else 0
        )]

    comp_dict = json.loads(data['compliance_result']) if isinstance(data['compliance_result'], str) else (data['compliance_result'] or {})
    if 'score' not in comp_dict:
        comp_dict['score'] = float(comp_dict.get('compliance_score', data.get('score', 0.0)))
    if 'status' not in comp_dict:
        comp_dict['status'] = data.get('status', 'UNKNOWN')
    checks_raw = comp_dict.get('checks', [])
    if 'total_rules' not in comp_dict:
        comp_dict['total_rules'] = len(checks_raw)
    if 'passed_rules' not in comp_dict:
        comp_dict['passed_rules'] = sum(1 for c in checks_raw if isinstance(c, dict) and c.get('status') in ['PASS', 'COMPLIANT'])
    if 'failed_rules' not in comp_dict:
        comp_dict['failed_rules'] = sum(1 for c in checks_raw if isinstance(c, dict) and c.get('status') in ['FAIL', 'NON_COMPLIANT'])

    if 'recommendations' not in comp_dict or not comp_dict['recommendations']:
        from compliance.recommendations import generate_recommendations
        from models.schemas import ComplianceCheck
        checks = [ComplianceCheck(**c) if isinstance(c, dict) else c for c in checks_raw]
        comp_dict['recommendations'] = [r.model_dump() for r in generate_recommendations(checks)]

    compliance_res = ComplianceResult(**comp_dict)
    raw_extracted = json.loads(data['extracted_data']) if isinstance(data['extracted_data'], str) else data['extracted_data']
    prod_info = ProductInfo(**raw_extracted)

    aggregated_words = [w for img in images_list for w in (img.words or [])]

    font_size_analysis = compute_font_size_and_readability(
        product_info=prod_info,
        ocr_result=OCRResult(full_text=data['ocr_text'], words=aggregated_words, language="eng", processing_time=0.0),
        images=images_list,
        checks=compliance_res.checks
    )

    fssai_verification = await fssai_verifier.verify(prod_info.fssai_license)
    barcode_val = prod_info.barcode_detected or getattr(prod_info, 'barcode', None) or (prod_info.other_declarations.get('barcode') if prod_info.other_declarations else None)
    gs1_verification = await gs1_verifier.verify(barcode_val)

    primary_image_filename = data.get('image_filename') or (images_list[0].filename if images_list else '')
    primary_image_url = f"/uploads/{primary_image_filename}" if primary_image_filename else "/placeholder.png"

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
        owner_user_id=data.get('owner_user_id')
    )


@router.delete("/history/{id}")
async def delete_history_item(id: str, user: dict = Depends(get_current_user)):
    if _is_demo_id(id):
        raise HTTPException(status_code=403, detail="Demonstration benchmark cases are protected and cannot be deleted.")

    data = await get_analysis(id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID '{id}' not found.")

    user_role = user.get("role")
    if user_role in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        # Privileged roles can delete screening records
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
            image_url=f"/uploads/{a['image_filename']}" if a.get('image_filename') else "/placeholder.png",
            owner_user_id=a.get('owner_user_id')
        ) for a in stats['recent']]
    )


@router.get("/stats/trends")
async def get_trends(days: int = Query(default=14, ge=7, le=90),
                     user: dict = Depends(get_current_user)):
    """Daily screening trend stats for the dashboard (last N days)."""
    return await get_trend_stats(days=days)


@router.get("/stats/by-status")
async def get_stats_by_status(user: dict = Depends(get_current_user)):
    """Status breakdown for dashboard pie chart."""
    analyses = await get_analyses()
    counts = Counter(a.get("status", "UNKNOWN") for a in analyses)
    return {"labels": list(counts.keys()), "values": list(counts.values())}