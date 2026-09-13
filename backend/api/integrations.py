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
