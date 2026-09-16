import logging
from typing import Optional
from config import settings
from ocr.base import OCREngine

logger = logging.getLogger(__name__)

_GLOBAL_OCR_ENGINE: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """
    Returns the configured OCR engine singleton.
    Reads settings.OCR_ENGINE:
      - "paddleocr" (default) → PaddleOCREngine (PP-OCRv4, heavy, ~2GB+ RAM)
      - "tesseract"            → TesseractOCREngine (light, ~200MB, cloud-friendly)
    Falls back to Paddle if the requested engine fails to import.
    """
    global _GLOBAL_OCR_ENGINE
    if _GLOBAL_OCR_ENGINE is not None:
        return _GLOBAL_OCR_ENGINE

    engine_name = (settings.OCR_ENGINE or "paddleocr").lower().strip()
    logger.info("Initializing OCR engine: %s", engine_name)

    if engine_name == "tesseract":
        try:
            from ocr.tesseract_engine import TesseractOCREngine
            _GLOBAL_OCR_ENGINE = TesseractOCREngine()
            logger.info("Tesseract OCR engine initialized successfully")
            return _GLOBAL_OCR_ENGINE
        except Exception as exc:
            logger.warning("Tesseract init failed (%s), falling back to PaddleOCR", exc)

    # Default / fallback path: PaddleOCR
    try:
        from ocr.paddle_engine import PaddleOCREngine
        _GLOBAL_OCR_ENGINE = PaddleOCREngine()
        logger.info("PaddleOCR engine initialized successfully")
    except Exception as exc:
        logger.error("PaddleOCR init failed: %s", exc)
        raise

    return _GLOBAL_OCR_ENGINE


def reset_ocr_engine() -> None:
    """Clears the cached OCR engine singleton, forcing re-initialization on next get_ocr_engine()."""
    global _GLOBAL_OCR_ENGINE
    _GLOBAL_OCR_ENGINE = None
