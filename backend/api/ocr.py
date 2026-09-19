import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, status
from models.schemas import OCRResult
from ocr.factory import get_ocr_engine
from utils.validators import validate_image_file
from config import settings
from services.image_service import process_and_save_image
from auth.ratelimit import get_client_ip, check_ocr_rate_limit

router = APIRouter()

@router.post("/ocr", response_model=OCRResult)
async def ocr_endpoint(request: Request, file: UploadFile = File(...)):
    client_ip = get_client_ip(request)
    allowed, rate_msg = check_ocr_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    validate_image_file(file)
    temp_id = str(uuid.uuid4())
    image_path = os.path.join(settings.UPLOAD_DIR, f"temp_{temp_id}_{file.filename}")
    
    try:
        await process_and_save_image(file, image_path)
        engine = get_ocr_engine()
        result = await engine.extract(image_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)
