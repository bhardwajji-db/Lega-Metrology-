import logging
from typing import Optional
from config import settings
from ocr.base import OCREngine
from ocr.paddle_engine import PaddleOCREngine

logger = logging.getLogger(__name__)

_GLOBAL_OCR_ENGINE: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """
    Returns the configured OCR engine singleton.
    PaddleOCR (PP-OCRv4) is the sole OCR engine for the application.
    """
    global _GLOBAL_OCR_ENGINE
    if _GLOBAL_OCR_ENGINE is not None:
        return _GLOBAL_OCR_ENGINE

    logger.info("Initializing PaddleOCR engine (PP-OCRv4)")
    _GLOBAL_OCR_ENGINE = PaddleOCREngine()
    return _GLOBAL_OCR_ENGINE


def reset_ocr_engine() -> None:
    """Clears the cached OCR engine singleton, forcing re-initialization on next get_ocr_engine()."""
    global _GLOBAL_OCR_ENGINE
    _GLOBAL_OCR_ENGINE = None


