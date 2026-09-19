import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, Dict, Any
from config import settings
from services.image_service import process_and_save_image
from vision.pipeline import vision_pipeline
from vision.schemas import VisionAnalysisResult
from auth.security import public_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vision", tags=["Computer Vision"])

@router.post("/analyze", response_model=VisionAnalysisResult)
async def analyze_image_vision(
    file: UploadFile = File(...),
    label: str = Form("Front"),
    current_user: Optional[Dict[str, Any]] = Depends(public_user)
):
    """
    Standalone Computer Vision diagnostic endpoint.
    Runs Image Quality Gate, Geometry, Boundary Detection, Panel Classification,
    Semantic Regions, Symbols, and Barcode/QR localization on the uploaded packaging artwork.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    temp_filename = f"vision_diag_{uuid.uuid4()}_{file.filename}"
    temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)

    try:
        await process_and_save_image(file, temp_path)
        vision_result = vision_pipeline.analyze_image(
            image_input=temp_path,
            image_label=label
        )
        return vision_result
    except Exception as e:
        logger.error(f"Error during standalone vision analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
