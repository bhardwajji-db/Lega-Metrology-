from fastapi import APIRouter
from ocr.factory import get_ocr_engine

router = APIRouter()

@router.get("/health")
async def health_check():
    ocr_engine = get_ocr_engine()
    return {
        "status": "healthy",
        "ocr_available": ocr_engine.is_available(),
        "ocr_engine": ocr_engine.__class__.__name__,
        "database": "connected",
        "version": "1.0.0"
    }
