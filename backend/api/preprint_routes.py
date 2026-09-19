import os
import uuid
import shutil
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends

from config import settings
from models.preprint_schemas import (
    PreprintUploadResponse,
    PreprintAnalysisResponse,
    PreprintApprovalRequest,
    ArtworkDocument,
    ArtworkPageInfo,
)
from services.preprint_service import (
    validate_artwork_file,
    render_artwork_pages,
    analyze_artwork,
)
from database.db import (
    save_artwork,
    get_artwork,
    list_artworks,
    update_artwork_analysis,
    update_artwork_approval,
    delete_artwork,
)
from auth.security import (
    get_current_user,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)

router = APIRouter(prefix="/api/preprint", tags=["preprint"])


def _user_owns_artwork(user: dict, owner_user_id: Optional[str]) -> bool:
    """Check if authenticated user owns the artwork record."""
    if not owner_user_id:
        return True
    username = user.get("username") or ""
    uid = str(user.get("id", "")) if user.get("id") is not None else ""
    return (owner_user_id == username) or (bool(uid) and owner_user_id == uid)


def _check_artwork_access(user: dict, artwork: dict, require_delete: bool = False):
    """Strict IDOR, RBAC, and Tenant Isolation access control for pre-print packaging artworks."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access pre-print artworks."
        )
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found")

    user_role = user.get("role")

    if require_delete:
        if user_role in (ROLE_ADMIN, ROLE_ENFORCEMENT):
            if not check_tenant_access(user, artwork):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Cross-organization deletion prohibited."
                )
            return
        if user_role == ROLE_MERCHANT:
            if not check_tenant_access(user, artwork):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Merchants can only delete their own artworks within their organization."
                )
            return
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to delete pre-print artworks."
        )

    # Read / Analyze / Approve access
    if not check_tenant_access(user, artwork):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Organization or ownership boundary violation."
        )


def _cleanup_artwork_files(artwork: dict):
    """Safely remove uploaded artwork PDF and rendered page previews."""
    import json
    upload_dir_abs = os.path.abspath(settings.UPLOAD_DIR)
    paths_to_delete = []

    if artwork.get("file_path"):
        paths_to_delete.append(artwork["file_path"])

    if artwork.get("pages_data"):
        pages = artwork["pages_data"]
        if isinstance(pages, str):
            try:
                pages = json.loads(pages)
            except Exception:
                pages = []
        if isinstance(pages, list):
            for p in pages:
                if isinstance(p, dict):
                    if p.get("image_path"):
                        paths_to_delete.append(p["image_path"])
                    if p.get("image_url") and str(p["image_url"]).startswith("/api/images/"):
                        fn = str(p["image_url"]).replace("/api/images/", "")
                        paths_to_delete.append(os.path.join(upload_dir_abs, fn))

    for p in set(paths_to_delete):
        if not p:
            continue
        target_path = os.path.abspath(p)
        if target_path.startswith(upload_dir_abs) and os.path.isfile(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass


@router.post("/upload", response_model=PreprintUploadResponse)
async def upload_artwork(
    file: UploadFile = File(...),
    parent_artwork_id: Optional[str] = Form(None),
    iteration_number: int = Form(1),
    owner_user_id: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    """
    Upload a pre-print packaging artwork (PDF, PNG, JPG, WEBP).
    Validates file format, magic bytes, dimensions, and creates an artwork record.
    """
    content = await file.read()
    filename = file.filename or "artwork.pdf"
    file_type, error_msg = validate_artwork_file(filename, content)
    if error_msg or not file_type:
        raise HTTPException(status_code=400, detail=error_msg or "Invalid artwork file format.")

    artwork_id = f"art-{uuid.uuid4().hex[:12]}"
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = f".{file_type.lower()}"
    saved_filename = f"{artwork_id}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

    with open(saved_path, "wb") as f:
        f.write(content)

    pages = render_artwork_pages(saved_path, file_type, settings.UPLOAD_DIR)
    page_count = len(pages)
    first_page_dims = {"width": pages[0].width, "height": pages[0].height} if pages else {"width": 800, "height": 600}
    first_page_dpi = pages[0].dpi if pages else 72.0

    effective_owner = user.get("username", "")
    if user.get("role") in (ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT) and owner_user_id:
        effective_owner = owner_user_id
    elif user.get("role") == ROLE_MERCHANT:
        effective_owner = user.get("username", "") or owner_user_id or ""

    now_iso = datetime.now(timezone.utc).isoformat()
    org_id = user.get("organization_id", "")
    artwork_doc = {
        "id": artwork_id,
        "filename": filename,
        "file_path": saved_path,
        "file_type": file_type,
        "file_size": len(content),
        "page_count": page_count,
        "dimensions": first_page_dims,
        "dpi": first_page_dpi,
        "source_identity": "PRE-PRINT ARTWORK",
        "compliance_ruleset": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "parent_artwork_id": parent_artwork_id,
        "iteration_number": iteration_number,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "approval_record": None,
        "analysis_result": None,
        "pages_data": [p.model_dump() for p in pages],
        "owner_user_id": effective_owner,
        "organization_id": org_id,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await save_artwork(artwork_doc)

    return PreprintUploadResponse(
        success=True,
        artwork_id=artwork_id,
        filename=filename,
        file_type=file_type,
        file_size=len(content),
        page_count=page_count,
        dimensions=first_page_dims,
        dpi=first_page_dpi,
        pages=pages,
        message="Artwork uploaded successfully and pages prepared for pre-print analysis.",
    )


@router.post("/{artwork_id}/analyze", response_model=PreprintAnalysisResponse)
async def analyze_preprint_artwork(
    artwork_id: str,
    product_name: Optional[str] = Query(None, description="Optional product name hint"),
    category: Optional[str] = Query(None, description="Optional commodity category"),
    user: dict = Depends(get_current_user),
):
    """
    Run the comprehensive pre-print compliance engine on an uploaded artwork.
    Executes layout zoning, placement checks, font-size assistance, missing-declaration checks,
    compliance scoring, and designer checklist generation.
    """
    artwork = await get_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found.")

    _check_artwork_access(user, artwork)

    analysis_res = analyze_artwork(
        artwork_dict=artwork,
        product_name_hint=product_name,
        category=category,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    await update_artwork_analysis(
        artwork_id=artwork_id,
        analysis_result=analysis_res.model_dump(),
        workflow_status=analysis_res.workflow_status,
        updated_at=now_iso,
    )

    return analysis_res


@router.get("")
@router.get("/artworks")
async def list_preprint_artworks(
    owner_user_id: Optional[str] = Query(None, description="Optional filter by user ID"),
    user: dict = Depends(get_current_user),
):
    """List all pre-print artworks with tenant and IDOR filtering."""
    user_role = user.get("role")
    user_org = (user.get("organization_id") or "").strip()

    if user_role == ROLE_ADMIN:
        artworks = await list_artworks(owner_user_id=owner_user_id, organization_id=None)
    else:
        if not user_org:
            return {"artworks": [], "total": 0}
        effective_owner = user.get("username") if user_role == ROLE_MERCHANT else owner_user_id
        raw_artworks = await list_artworks(owner_user_id=effective_owner, organization_id=user_org)
        artworks = [a for a in raw_artworks if check_tenant_access(user, a)]

    return {"artworks": artworks, "total": len(artworks)}


@router.get("/{artwork_id}")
async def get_preprint_artwork_details(
    artwork_id: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve details and analysis report for a pre-print artwork with ownership authorization."""
    artwork = await get_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found.")

    _check_artwork_access(user, artwork)
    return artwork


@router.post("/{artwork_id}/correction-upload", response_model=PreprintAnalysisResponse)
async def upload_corrected_artwork(
    artwork_id: str,
    file: UploadFile = File(...),
    owner_user_id: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    """
    Re-upload corrected packaging artwork as a new iteration linked to the parent artwork.
    Performs immediate validation and full analysis pipeline.
    """
    parent = await get_artwork(artwork_id)
    if not parent:
        raise HTTPException(status_code=404, detail=f"Parent artwork '{artwork_id}' not found.")

    _check_artwork_access(user, parent)

    new_iteration = parent.get("iteration_number", 1) + 1
    content = await file.read()
    filename = file.filename or f"corrected_artwork_v{new_iteration}.pdf"
    file_type, error_msg = validate_artwork_file(filename, content)
    if error_msg or not file_type:
        raise HTTPException(status_code=400, detail=error_msg or "Invalid artwork file format.")

    new_artwork_id = f"art-{uuid.uuid4().hex[:12]}"
    ext = os.path.splitext(filename)[1].lower() or f".{file_type.lower()}"
    saved_filename = f"{new_artwork_id}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

    with open(saved_path, "wb") as f:
        f.write(content)

    pages = render_artwork_pages(saved_path, file_type, settings.UPLOAD_DIR)
    page_count = len(pages)
    first_page_dims = {"width": pages[0].width, "height": pages[0].height} if pages else {"width": 800, "height": 600}
    first_page_dpi = pages[0].dpi if pages else 72.0

    effective_owner = parent.get("owner_user_id", "") or user.get("username", "")
    if user.get("role") in (ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT) and owner_user_id:
        effective_owner = owner_user_id

    now_iso = datetime.now(timezone.utc).isoformat()
    org_id = parent.get("organization_id") or user.get("organization_id", "")
    new_artwork_doc = {
        "id": new_artwork_id,
        "filename": filename,
        "file_path": saved_path,
        "file_type": file_type,
        "file_size": len(content),
        "page_count": page_count,
        "dimensions": first_page_dims,
        "dpi": first_page_dpi,
        "source_identity": "PRE-PRINT ARTWORK",
        "compliance_ruleset": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "parent_artwork_id": artwork_id,
        "iteration_number": new_iteration,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "approval_record": None,
        "analysis_result": None,
        "pages_data": [p.model_dump() for p in pages],
        "owner_user_id": effective_owner,
        "organization_id": org_id,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await save_artwork(new_artwork_doc)

    # Run analysis
    analysis_res = analyze_artwork(artwork_dict=new_artwork_doc)
    await update_artwork_analysis(
        artwork_id=new_artwork_id,
        analysis_result=analysis_res.model_dump(),
        workflow_status=analysis_res.workflow_status,
        updated_at=now_iso,
    )

    return analysis_res


@router.post("/{artwork_id}/approval")
async def submit_artwork_approval(
    artwork_id: str,
    approval_req: PreprintApprovalRequest,
    user: dict = Depends(get_current_user),
):
    """
    Compliance approval workflow (Approve / Reject / Request Changes).
    Guards the 'READY_FOR_PRINT' transition:
    - 'READY_FOR_PRINT' is a verified workflow status, NOT an absolute legal certification.
    - Cannot approve if critical non-compliances exist without explicit acknowledgment.
    """
    artwork = await get_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found.")

    _check_artwork_access(user, artwork)

    if not approval_req.legal_disclaimer_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="Legal disclaimer must be acknowledged before submitting pre-print approval decisions."
        )

    analysis = artwork.get("analysis_result")
    if approval_req.decision == "APPROVED":
        if analysis and analysis.get("overall_status") == "NON_COMPLIANT":
            raise HTTPException(
                status_code=400,
                detail="Cannot approve artwork with NON_COMPLIANT status. All critical violations must be resolved first."
            )
        new_workflow_status = "READY_FOR_PRINT"
        approval_status = "APPROVED"
    elif approval_req.decision == "REJECTED":
        new_workflow_status = "REJECTED"
        approval_status = "REJECTED"
    else:  # REQUEST_CHANGES
        new_workflow_status = "CHANGES_REQUESTED"
        approval_status = "CHANGES_REQUESTED"

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "approval_id": f"appr-{uuid.uuid4().hex[:8]}",
        "artwork_id": artwork_id,
        "reviewer_id": approval_req.reviewer_id or user.get("username", "usr-current"),
        "reviewer_name": approval_req.reviewer_name or user.get("full_name", user.get("username", "")),
        "reviewer_role": approval_req.reviewer_role or user.get("role", ROLE_MERCHANT),
        "decision": approval_req.decision,
        "comments": approval_req.comments,
        "timestamp": now_iso,
        "conditions": approval_req.conditions,
        "legal_disclaimer_acknowledged": approval_req.legal_disclaimer_acknowledged,
    }

    await update_artwork_approval(
        artwork_id=artwork_id,
        approval_status=approval_status,
        approval_record=record,
        workflow_status=new_workflow_status,
        updated_at=now_iso,
    )

    updated_artwork = await get_artwork(artwork_id)
    return {
        "success": True,
        "artwork_id": artwork_id,
        "workflow_status": new_workflow_status,
        "approval_status": approval_status,
        "approval_record": record,
        "artwork": updated_artwork,
    }




@router.delete("/{artwork_id}")
async def delete_preprint_artwork(
    artwork_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a pre-print artwork record with ownership verification."""
    artwork = await get_artwork(artwork_id)
    if not artwork:
        raise HTTPException(status_code=404, detail=f"Artwork '{artwork_id}' not found.")

    _check_artwork_access(user, artwork, require_delete=True)

    _cleanup_artwork_files(artwork)
    await delete_artwork(artwork_id)
    return {"success": True, "message": f"Artwork '{artwork_id}' deleted successfully."}
