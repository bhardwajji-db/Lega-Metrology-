import logging
from typing import Optional
from config import settings
from ocr.base import OCREngine

logger = logging.getLogger(__name__)

_GLOBAL_OCR_ENGINE: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """
    Returns the configured OCR engine singleton.
    Supports PaddleOCR (local/production) and Tesseract (cloud/lightweight).
    """
    global _GLOBAL_OCR_ENGINE
    if _GLOBAL_OCR_ENGINE is not None:
        return _GLOBAL_OCR_ENGINE

    engine_type = (getattr(settings, "OCR_ENGINE", "") or "paddleocr").lower()

    if engine_type == "tesseract":
        try:
            from ocr.tesseract_engine import TesseractOCREngine
            logger.info("Initializing Tesseract OCR engine (cloud/lightweight)")
            _GLOBAL_OCR_ENGINE = TesseractOCREngine()
            return _GLOBAL_OCR_ENGINE
        except Exception as exc:
            logger.warning("Failed to initialize Tesseract engine: %s", exc)

    try:
        from ocr.paddle_engine import PaddleOCREngine
        logger.info("Initializing PaddleOCR engine (PP-OCRv4)")
        _GLOBAL_OCR_ENGINE = PaddleOCREngine()
        return _GLOBAL_OCR_ENGINE
    except (ImportError, Exception) as exc:
        logger.warning("PaddleOCR unavailable (%s), falling back to Tesseract OCR", exc)
        from ocr.tesseract_engine import TesseractOCREngine
        _GLOBAL_OCR_ENGINE = TesseractOCREngine()
        return _GLOBAL_OCR_ENGINE


def reset_ocr_engine() -> None:
    """Clears the cached OCR engine singleton, forcing re-initialization on next get_ocr_engine()."""
    global _GLOBAL_OCR_ENGINE
    _GLOBAL_OCR_ENGINE = None


