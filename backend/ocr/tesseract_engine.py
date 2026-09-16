"""
Tesseract OCR engine for MetrCheck AI (cloud / low-memory deployments).

Lightweight drop-in replacement for PaddleOCREngine (which needs ~2GB+ RAM
and is unsuitable for free-tier cloud instances like Render's 512MB).
Implements the same OCREngine interface (async extract + is_available).

Dependencies: pytesseract + the tesseract-ocr system binary (apt package
`tesseract-ocr` in the cloud Dockerfile). Pillow is used for image loading.
"""
import asyncio
import logging
import os
import time
from typing import List, Tuple

from ocr.base import OCREngine
from ocr.cleaner import clean_ocr_text
from ocr.repair import repair_fssai_license, repair_net_quantity, repair_mrp, repair_date
from models.schemas import OCRResult, OCRWord

logger = logging.getLogger(__name__)

_TESSERACT_AVAILABLE: bool | None = None


def _is_tesseract_available() -> bool:
    """Check if pytesseract module + the tesseract binary are usable."""
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
    try:
        import pytesseract
        # Probe the binary with a version call (fast, no image needed)
        pytesseract.get_tesseract_version()
        _TESSERACT_AVAILABLE = True
    except Exception as exc:  # pragma: no cover - env-dependent
        logger.warning("Tesseract not available: %s", exc)
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def _sync_tesseract_extract(image_path: str, lang: str = "eng") -> Tuple[List[str], List[OCRWord], List[float]]:
    """Synchronous Tesseract extraction: lines, words (bbox + confidence), confs."""
    import pytesseract
    from PIL import Image, ImageOps

    lines: List[str] = []
    words: List[OCRWord] = []
    confs: List[float] = []

    img = Image.open(image_path)
    # Convert to grayscale for more reliable tesseract results
    img = ImageOps.grayscale(img)

    # TSV gives word-level data: text, confidence, bounding box
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

    n = len(data.get("text", []))
    # Bundle words into lines: tesseract gives block_num/par_num/line_num per word.
    # A word is only kept if it has visible text and a meaningful confidence.
    for i in range(n):
        text = str(data.get("text", [""] * n)[i]).strip()
        if not text:
            continue
        try:
            conf = float(data.get("conf", [0] * n)[i] or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < 1.0:  # skip "empty/partial" entries tesseract emits
            continue
        left = int(data.get("left", [0] * n)[i] or 0)
        top = int(data.get("top", [0] * n)[i] or 0)
        w = int(data.get("width", [0] * n)[i] or 0)
        h = int(data.get("height", [0] * n)[i] or 0)
        bbox = [left, top, left + w, top + h]
        words.append(OCRWord(text=text, confidence=round(min(conf, 100.0), 1), bbox=bbox))
        confs.append(min(conf, 100.0))

    # Reconstruct line-level text so the downstream cleaners/repairers work.
    # Group words by (block, par, line) preserving reading order.
    groups: dict[tuple, list[str]] = {}
    order: List[tuple] = []
    for i in range(n):
        text = str(data.get("text", [""] * n)[i]).strip()
        if not text:
            continue
        key = (
            int(data.get("block_num", [0] * n)[i] or 0),
            int(data.get("par_num", [0] * n)[i] or 0),
            int(data.get("line_num", [0] * n)[i] or 0),
        )
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(text)

    for key in order:
        lines.append(" ".join(groups[key]))

    return lines, words, confs


class TesseractOCREngine(OCREngine):
    """Tesseract-based OCR engine — the low-memory cloud engine."""

    def __init__(self, lang: str = "eng"):
        self.lang = lang

    def is_available(self) -> bool:
        return _is_tesseract_available()

    async def extract(self, image_path: str) -> OCRResult:
        start_time = time.time()

        if not self.is_available():
            logger.error("Tesseract is not available (pytesseract / tesseract binary missing).")
            return OCRResult(
                full_text="Tesseract is unavailable or dependencies are not installed in the environment.",
                words=[],
                language=self.lang,
                processing_time=round(time.time() - start_time, 2),
                average_confidence=0.0,
                word_count=0,
                engine="Tesseract OCR",
                preprocessing_variant="LSTM word-level (pytesseract)",
                regions_processed=0,
                ocr_passes=1,
            )

        try:
            lines, words, confs = await asyncio.to_thread(_sync_tesseract_extract, image_path, self.lang)

            raw_combined = "\n".join(lines)
            cleaned = clean_ocr_text(raw_combined)

            # Same repair pass as Paddle engine: FSSAI license, net quantity, MRP, dates
            repaired_lines: List[str] = []
            for line in cleaned.splitlines():
                line = repair_fssai_license(line) or line
                line = repair_net_quantity(line)
                line = repair_mrp(line)
                line = repair_date(line)
                repaired_lines.append(line)
            final_text = "\n".join(repaired_lines)

            avg_conf = round(sum(confs) / len(confs), 1) if confs else 0.0
            word_count = len(words) or len(final_text.split())

            return OCRResult(
                full_text=final_text,
                words=words,
                language=self.lang,
                processing_time=round(time.time() - start_time, 2),
                average_confidence=avg_conf,
                word_count=word_count,
                engine="Tesseract OCR",
                preprocessing_variant="LSTM word-level (pytesseract)",
                regions_processed=len(lines),
                ocr_passes=1,
            )
        except Exception as exc:
            logger.exception("Tesseract extraction failed for %s: %s", image_path, exc)
            return OCRResult(
                full_text=f"Tesseract extraction error: {exc}",
                words=[],
                language=self.lang,
                processing_time=round(time.time() - start_time, 2),
                average_confidence=0.0,
                word_count=0,
                engine="Tesseract OCR",
                preprocessing_variant="LSTM word-level (pytesseract)",
                regions_processed=0,
                ocr_passes=1,
            )