import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status

from auth.security import get_current_user_optional
from models.listing_schemas import ListingCheckRequest, ListingCheckResponse
from services.listing_service import check_listing_compliance
from database.db import get_analyses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/listing", tags=["listing"])


@router.post("/check", response_model=ListingCheckResponse)
async def check_ecommerce_listing(
    request: ListingCheckRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Check e-commerce listing compliance across Legal Metrology and FSSAI statutory rules.
    Supports 3 modes:
    - URL: SSRF-protected link scraping.
    - RAW_TEXT: Direct copy-paste of listing description.
    - STRUCTURED: Form-based field declarations.
    Optionally cross-compares with a physical package screening (Package vs Listing).
    """
    try:
        response = await check_listing_compliance(request)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[LISTING] Error processing listing compliance check: {e}")
        raise HTTPException(status_code=500, detail=f"Listing analysis failed: {str(e)}")


@router.get("/package-targets")
async def list_package_targets(
    limit: int = Query(30, ge=1, le=100),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Lists recent physical package analyses available for cross-comparison.
    """
    owner_id = current_user.get("user_id") if current_user else None
    analyses = await get_analyses(owner_user_id=owner_id, limit=limit)
    
    targets = []
    for a in analyses:
        targets.append({
            "analysis_id": a["id"],
            "product_name": a.get("product_name", "Unknown Product"),
            "created_at": a.get("created_at", ""),
            "score": a.get("score", 0.0),
            "status": a.get("status", "PASS")
        })
    return {"targets": targets, "total": len(targets)}
