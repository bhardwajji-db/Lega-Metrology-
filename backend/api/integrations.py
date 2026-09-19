from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import tempfile
import uuid

from models.schemas import FSSAIVerificationResult, GS1VerificationResult, CalibrationResult
from integrations.fssai.verifier import fssai_verifier
from integrations.gs1.verifier import gs1_verifier
from services.calibration_service import calibration_service
from config import settings

router = APIRouter(prefix="/integrations", tags=["Integrations & Metrology"])

class FSSAIRequest(BaseModel):
    licence_number: str

class GS1Request(BaseModel):
    gtin: str

@router.post("/fssai/verify", response_model=FSSAIVerificationResult)
async def verify_fssai_licence(req: FSSAIRequest):
    if not req.licence_number or not req.licence_number.strip():
        raise HTTPException(status_code=400, detail="FSSAI licence number is required.")
    
    rec = await fssai_verifier.verify(req.licence_number.strip())
    return FSSAIVerificationResult(
        licence_number=rec.licence_number,
        status=rec.status.value,
        provider=rec.provider,
        business_name=rec.business_name,
        licence_type=rec.licence_type,
        valid_upto=rec.valid_upto,
        verification_timestamp=rec.verification_timestamp,
        message=rec.message,
        is_live=rec.is_live,
        error_details=rec.error_details
    )

@router.post("/gs1/verify", response_model=GS1VerificationResult)
async def verify_gs1_barcode(req: GS1Request):
    if not req.gtin or not req.gtin.strip():
        raise HTTPException(status_code=400, detail="GTIN barcode is required.")
    
    rec = await gs1_verifier.verify(req.gtin.strip())
    return GS1VerificationResult(
        gtin=rec.gtin,
        status=rec.status.value,
        provider=rec.provider,
        brand_name=rec.brand_name,
        product_description=rec.product_description,
        company_name=rec.company_name,
        verification_timestamp=rec.verification_timestamp,
        message=rec.message,
        is_live=rec.is_live,
        error_details=rec.error_details
    )

@router.post("/calibrate", response_model=CalibrationResult)
async def calibrate_image_target(file: UploadFile = File(...)):
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            contents = await file.read()
            tmp.write(contents)
        
        result = calibration_service.detect_aruco_marker(tmp_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibration analysis failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ── Section 13: External Cross-Checking & Integration Status Routes ──

from models.verification_schemas import (
    CrossCheckRequest,
    ExternalVerificationSummary,
    CacheSeedItem,
    ApiAvailabilityStatus,
    ApiAvailabilityState
)
from integrations.cross_checker import cross_check_engine
from database.db import (
    get_verification_cache_stats,
    save_cached_verification,
    clear_expired_verification_cache,
    list_cached_verifications
)
from utils.datetime_utils import get_current_utc_iso


@router.post("/cross-check", response_model=ExternalVerificationSummary)
async def run_external_cross_check(req: CrossCheckRequest):
    """
    On-demand statutory cross-checking between extracted package declarations
    and external registries (FoSCoS, GS1 DataKart, QR payload).
    """
    # 1. Run FSSAI verification
    fssai_rec = None
    if req.fssai_license:
        fssai_rec = await fssai_verifier.verify(req.fssai_license)

    # 2. Run GS1 verification
    gs1_rec = None
    if req.gtin_barcode:
        gs1_rec = await gs1_verifier.verify(req.gtin_barcode)

    # 3. Build extracted data dict
    extracted_data = {
        "product_name": req.product_name,
        "brand_name": req.brand_name,
        "manufacturer": req.manufacturer_name,
        "manufacturer_address": req.manufacturer_address,
        "fssai_license": req.fssai_license,
        "net_quantity": req.net_quantity,
        "mrp": req.mrp
    }

    # 4. Evaluate cross checks
    summary = cross_check_engine.evaluate_all(
        extracted_data=extracted_data,
        fssai_record=fssai_rec,
        gs1_record=gs1_rec,
        qr_payload=req.qr_payload,
        barcode_detected=req.gtin_barcode,
        offline_mode=req.offline_mode
    )
    return summary


@router.get("/status")
async def get_integrations_status():
    """
    Returns live connectivity status, configuration, and offline readiness for external registries.
    """
    now_ts = get_current_utc_iso()
    cache_stats = await get_verification_cache_stats()

    foscos_configured = bool(settings.FSSAI_API_URL)
    gs1_configured = bool(settings.GS1_API_URL)

    return {
        "status": "OPERATIONAL",
        "timestamp": now_ts,
        "offline_mode_ready": True,
        "registries": {
            "foscos": {
                "name": "Food Safety and Standards Authority of India (FoSCoS)",
                "state": ApiAvailabilityState.ONLINE if foscos_configured else ApiAvailabilityState.UNCONFIGURED,
                "endpoint": settings.FSSAI_API_URL or "UNCONFIGURED",
                "fallback_mode": "SQLite persistent cache + Local 14-digit validator"
            },
            "gs1_datakart": {
                "name": "GS1 India DataKart & Verified by GS1",
                "state": ApiAvailabilityState.ONLINE if gs1_configured else ApiAvailabilityState.UNCONFIGURED,
                "endpoint": settings.GS1_API_URL or "UNCONFIGURED",
                "fallback_mode": "SQLite persistent cache + Modulo-10 checksum engine"
            }
        },
        "cache": cache_stats
    }


from auth.security import require_roles, ROLE_ADMIN
from database.db import log_security_event
from fastapi import Depends


@router.get("/cache/stats")
async def get_cache_statistics():
    """
    Returns persistent SQLite verification cache statistics.
    """
    return await get_verification_cache_stats()


@router.post("/cache/seed")
async def seed_verification_cache(
    items: list[CacheSeedItem],
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """
    Seeds authoritative records into the persistent SQLite cache for offline verification.
    Requires ADMIN privileges (governance control).
    """
    seeded_count = 0
    for item in items:
        await save_cached_verification(
            identifier_type=item.identifier_type,
            identifier_value=item.identifier_value,
            record_data=item.record_data,
            source=item.source,
            ttl_seconds=item.ttl_seconds
        )
        seeded_count += 1

    await log_security_event(
        event_type="CACHE_SEED",
        actor_username=user.get("username", "admin"),
        resource_id="verification_cache",
        details=f"Admin seeded {seeded_count} records into verification cache."
    )
    return {"status": "SUCCESS", "seeded_count": seeded_count}


@router.delete("/cache/expired")
async def purge_expired_cache(
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """
    Purges all expired records from the persistent cache.
    Requires ADMIN privileges (governance control).
    """
    purged = await clear_expired_verification_cache()
    await log_security_event(
        event_type="CACHE_PURGE_EXPIRED",
        actor_username=user.get("username", "admin"),
        resource_id="verification_cache",
        details=f"Admin purged {purged} expired records from verification cache."
    )
    return {"status": "SUCCESS", "purged_count": purged}

