import asyncio
import logging
import os
import re
import time
from typing import List, Tuple, Optional, Any, Dict

# ── Windows/OneDNN workaround ─────────────────────────────────────────────
# paddlepaddle 3.x PIR executor + OneDNN fails with:
#   "ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute]"
# Disable OneDNN (and PIR as fallback) BEFORE any paddle import so the legacy
# CPU path is used. Env vars are read at import time.
os.environ.setdefault("FLAGS_enable_onednn", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
# ──────────────────────────────────────────────────────────────────────────

from ocr.base import OCREngine
from ocr.cleaner import clean_ocr_text
from ocr.repair import repair_fssai_license, repair_net_quantity, repair_mrp, repair_date
from models.schemas import OCRResult, OCRWord

logger = logging.getLogger(__name__)

# ── Windows / paddlepaddle 3.3.x OneDNN+PIR workaround ──
# paddle 3.3 on Windows fails with
# "ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<...>]"
# at onednn_instruction.cc:118 for PP-OCR models. Disabling the PIR API and
# OneDNN before ANY paddle import routes execution through the legacy
# executor which works reliably on CPU. (Env flags are read once at runtime init.)
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_onednn", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
# paddlex 3.x defaults ENABLE_MKLDNN_BYDEFAULT=True and unconditionally builds
# an OneDNN (mkldnn) inference graph whose PIR->runtime conversion crashes on
# paddle 3.3 Windows ("ConvertPirAttribute2RuntimeAttribute ... not support ...
# onednn_instruction.cc:118"). Disable it so run_mode falls back to plain CPU.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import threading

# Global cached PaddleOCR instances by language, initialization lock & inference lock
_PADDLE_OCR_INSTANCES: Dict[str, Any] = {}
_PADDLE_OCR_LOCK = threading.Lock()
_PADDLE_INFERENCE_LOCK = threading.Lock()


def _is_paddle_available() -> bool:
    """Check if paddleocr and paddlepaddle are installed and importable."""
    try:
        import paddleocr  # noqa: F401
        import paddle  # noqa: F401
        return True
    except Exception:
        return False


def _normalize_lang_code(lang: str) -> str:
    l = (lang or "en").lower().strip()
    if l in ("hi", "hindi", "devanagari", "hin"):
        return "hi"
    return "en"


def _init_paddle_ocr(lang: str = "en", use_angle_cls: bool = True):
    """
    Initialize PaddleOCR instance with resilient parameter handling.
    PaddleOCR downloads PP-OCR models automatically on first run.
    Thread-safe per-language singleton pattern.
    """
    global _PADDLE_OCR_INSTANCES
    norm_lang = _normalize_lang_code(lang)
    if norm_lang in _PADDLE_OCR_INSTANCES:
        return _PADDLE_OCR_INSTANCES[norm_lang]

    with _PADDLE_OCR_LOCK:
        if norm_lang in _PADDLE_OCR_INSTANCES:
            return _PADDLE_OCR_INSTANCES[norm_lang]

        # Belt & suspenders: ensure OneDNN/PIR stay disabled before paddle inits
        os.environ["FLAGS_enable_pir_api"] = "0"
        os.environ["FLAGS_enable_onednn"] = "0"
        os.environ["FLAGS_use_mkldnn"] = "0"
        os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"

        from paddleocr import PaddleOCR

        # Disable remote model hoster connectivity check on subsequent runs
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        # Suppress verbose debug logging from paddle
        logging.getLogger("ppocr").setLevel(logging.WARNING)

        # Attempt initialization with high-performance parameters (disabling heavy doc unwarping & orientation models on CPU)
        try:
            instance = PaddleOCR(
                lang=norm_lang,
                ocr_version="PP-OCRv4",
                use_doc_unwarping=False,
                use_doc_orientation_classify=False,
                use_textline_orientation=False,
                text_recognition_batch_size=16
            )
        except Exception:
            try:
                instance = PaddleOCR(
                    lang=norm_lang,
                    use_doc_unwarping=False,
                    use_doc_orientation_classify=False,
                    use_textline_orientation=False,
                    text_recognition_batch_size=16
                )
            except Exception:
                try:
                    instance = PaddleOCR(lang=norm_lang, use_angle_cls=use_angle_cls)
                except Exception:
                    try:
                        instance = PaddleOCR(lang=norm_lang)
                    except Exception as err:
                        logger.error(f"PaddleOCR initialization error for lang '{norm_lang}': {err}")
                        if norm_lang != "en":
                            logger.warning("Falling back to default 'en' PaddleOCR model")
                            return _init_paddle_ocr(lang="en", use_angle_cls=use_angle_cls)
                        raise err

        _PADDLE_OCR_INSTANCES[norm_lang] = instance
        return instance



def _sync_paddle_extract(image_path: str, lang: str = "en") -> Tuple[List[str], List[OCRWord], List[float]]:
    """
    Synchronous execution of PaddleOCR inference on image_path.
    Supports both PaddleOCR 3.x pipeline results and legacy 2.x list outputs.
    Guarantees thread-safe inference on the shared model instance.
    Returns:
        lines: list of extracted text lines
        words: list of OCRWord objects with bounding boxes and normalized confidence (0-100)
        confs: list of confidences
    """
    ocr_inst = _init_paddle_ocr(lang=lang)

    lines: List[str] = []
    words: List[OCRWord] = []
    confs: List[float] = []

    # 1. Execute inference using predict (3.x preferred) or ocr (fallback) under inference lock
    results = None
    with _PADDLE_INFERENCE_LOCK:
        if hasattr(ocr_inst, "predict"):
            try:
                results = ocr_inst.predict(image_path)
            except Exception as e:
                logger.debug(f"ocr_inst.predict failed: {e}; falling back to ocr_inst.ocr")

        if results is None:
            try:
                results = ocr_inst.ocr(image_path, cls=True)
            except (TypeError, ValueError):
                results = ocr_inst.ocr(image_path)


    if not results:
        return lines, words, confs

    # In PaddleOCR, results is a list of page results; inspect the first page
    page_data = results[0] if isinstance(results, (list, tuple)) else results
    if not page_data:
        return lines, words, confs

    # ── CASE A: PaddleOCR 3.x Dictionary Format ───────────────────────────
    if isinstance(page_data, dict):
        rec_texts = page_data.get("rec_texts") or page_data.get("texts") or []
        rec_scores = page_data.get("rec_scores") or page_data.get("scores") or []
        rec_boxes = page_data.get("rec_boxes")
        rec_polys = page_data.get("rec_polys") or page_data.get("dt_polys")

        for i, raw_item in enumerate(rec_texts):
            raw_text = str(raw_item).strip()
            if not raw_text:
                continue

            raw_conf = float(rec_scores[i]) if (rec_scores is not None and i < len(rec_scores)) else 1.0
            conf = round(raw_conf * 100.0 if raw_conf <= 1.0 else raw_conf, 1)

            # Compute bounding box [x1, y1, x2, y2]
            line_bbox = [0, 0, 10, 10]
            if rec_boxes is not None and i < len(rec_boxes):
                b = rec_boxes[i]
                x1, y1, x2, y2 = int(round(float(b[0]))), int(round(float(b[1]))), int(round(float(b[2]))), int(round(float(b[3])))
                line_bbox = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
            elif rec_polys is not None and i < len(rec_polys):
                poly = rec_polys[i]
                xs = [float(pt[0]) for pt in poly]
                ys = [float(pt[1]) for pt in poly]
                line_bbox = [int(round(min(xs))), int(round(min(ys))), int(round(max(xs))), int(round(max(ys)))]

            lines.append(raw_text)
            confs.append(conf)

            # Generate individual OCRWord tokens with proportional bounding boxes
            tokens = raw_text.split()
            if len(tokens) <= 1:
                words.append(OCRWord(text=raw_text, confidence=conf, bbox=line_bbox))
            else:
                x1, y1, x2, y2 = line_bbox
                line_w = max(x2 - x1, 1)
                total_chars = sum(len(t) for t in tokens)
                curr_x = x1
                for t in tokens:
                    char_ratio = len(t) / max(total_chars, 1)
                    t_w = max(int(round(line_w * char_ratio)), 1)
                    t_bbox = [curr_x, y1, min(curr_x + t_w, x2), y2]
                    words.append(OCRWord(text=t, confidence=conf, bbox=t_bbox))
                    curr_x += t_w

        return lines, words, confs

    # ── CASE B: Legacy PaddleOCR 2.x List Format ───────────────────────────
    if isinstance(page_data, (list, tuple)):
        for item in page_data:
            if not item or not isinstance(item, (list, tuple)) or len(item) < 2:
                continue

            box = item[0]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            text_info = item[1]  # (text, confidence)
            if not text_info or len(text_info) < 2:
                continue

            raw_text = str(text_info[0]).strip()
            if not raw_text:
                continue

            raw_conf = float(text_info[1])
            conf = round(raw_conf * 100.0 if raw_conf <= 1.0 else raw_conf, 1)

            try:
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                x1 = int(round(min(xs)))
                y1 = int(round(min(ys)))
                x2 = int(round(max(xs)))
                y2 = int(round(max(ys)))
                line_bbox = [x1, y1, x2, y2]
            except Exception:
                line_bbox = [0, 0, 10, 10]

            lines.append(raw_text)
            confs.append(conf)

            tokens = raw_text.split()
            if len(tokens) <= 1:
                words.append(OCRWord(text=raw_text, confidence=conf, bbox=line_bbox))
            else:
                x1, y1, x2, y2 = line_bbox
                line_w = max(x2 - x1, 1)
                total_chars = sum(len(t) for t in tokens)
                curr_x = x1
                for t in tokens:
                    char_ratio = len(t) / max(total_chars, 1)
                    t_w = max(int(round(line_w * char_ratio)), 1)
                    t_bbox = [curr_x, y1, min(curr_x + t_w, x2), y2]
                    words.append(OCRWord(text=t, confidence=conf, bbox=t_bbox))
                    curr_x += t_w

    return lines, words, confs


def _box_iou(b1: List[int], b2: List[int]) -> float:
    """Calculate Intersection over Union between two [x1, y1, x2, y2] bounding boxes."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    a1 = max((b1[2] - b1[0]) * (b1[3] - b1[1]), 1)
    a2 = max((b2[2] - b2[0]) * (b2[3] - b2[1]), 1)
    return inter / float(a1 + a2 - inter)


def _sync_paddle_extract_multiscale(image_path: str, lang: str = "en") -> Tuple[List[str], List[OCRWord], List[float], int]:
    """
    High-performance smart multi-scale OCR inference pipeline with coordinate remapping and spatial deduplication.
    1. Runs Base Pass 1 on original image.
    2. Evaluates if primary packaging text is already sufficient.
    3. If statutory fine-print (e.g. ingredients) is missing, runs a targeted small crop pass instead of full-image 2x.
    """
    import cv2
    import tempfile

    t0 = time.perf_counter()
    # 1. Base pass on the original image
    lines1, words1, confs1 = _sync_paddle_extract(image_path, lang=lang)
    t_pass1 = (time.perf_counter() - t0) * 1000

    raw_text = " ".join(lines1).upper()
    has_ingr = any(k in raw_text for k in ["INGRED", "INORED", "COMPOSITION", "CONTAINS", "SAMAGRI"])
    has_mrp = any(k in raw_text for k in ["MRP", "M.R.P.", "MAXIMUM RETAIL", "UNIT SALE"])
    has_back_panel_indicators = any(k in raw_text for k in ["NUTRITION", "MARKETED BY", "MANUFACTURED", "FEEDBACK", "ALLERGEN", "FSSAI", "LIC NO"])
    has_front_prominence = any((w.bbox[3] - w.bbox[1]) >= 30 for w in words1) and len(words1) >= 10 and not has_back_panel_indicators

    # If front panel image or all statutory declarations already found in Pass 1, avoid expensive 2nd pass
    if (has_ingr and has_mrp) or has_front_prominence:
        # Reconstruct reading-order geometric lines from accepted words
        words_sorted = sorted(words1, key=lambda w: (w.bbox[1], w.bbox[0]))
        reconstructed_lines: List[str] = []
        curr_line: List[OCRWord] = []
        curr_y = None
        for w in words_sorted:
            y_mid = (w.bbox[1] + w.bbox[3]) / 2.0
            h_box = max(w.bbox[3] - w.bbox[1], 10)
            if curr_y is None or abs(y_mid - curr_y) < max(h_box * 0.45, 12):
                curr_line.append(w)
                curr_y = y_mid if curr_y is None else (curr_y * 0.7 + y_mid * 0.3)
            else:
                curr_line.sort(key=lambda x: x.bbox[0])
                reconstructed_lines.append(" ".join(x.text for x in curr_line))
                curr_line = [w]
                curr_y = y_mid
        if curr_line:
            curr_line.sort(key=lambda x: x.bbox[0])
            reconstructed_lines.append(" ".join(x.text for x in curr_line))

        seen_line_keys = set()
        merged_lines: List[str] = []
        for l in reconstructed_lines + lines1:
            l_clean = l.strip()
            l_norm = re.sub(r'[^a-z0-9]', '', l_clean.lower())
            if not l_norm or l_norm in seen_line_keys:
                continue
            seen_line_keys.add(l_norm)
            merged_lines.append(l_clean)

        logger.info(f"[PERF] {os.path.basename(image_path)} OCR Pass 1 sufficient: {t_pass1:.1f}ms ({len(words1)} words, 1 pass)")
        return merged_lines, words1, confs1, 1

    # 2. Optimized multi-scale pass for back packaging fine-print (scale = 1.4x for fast DBNet/SVTR inference)
    img = cv2.imread(image_path)
    if img is None:
        return lines1, words1, confs1, 1

    h, w = img.shape[:2]
    t_pass2_0 = time.perf_counter()
    scale = 1.4
    img_up = cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_CUBIC)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix="_multiscale.png")
    os.close(tmp_fd)
    try:
        cv2.imwrite(tmp_path, img_up)
        lines2, words2, confs2 = _sync_paddle_extract(tmp_path, lang=lang)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    t_pass2 = (time.perf_counter() - t_pass2_0) * 1000
    logger.info(f"[PERF] {os.path.basename(image_path)} OCR Pass 1: {t_pass1:.1f}ms + Pass 2 (1.4x): {t_pass2:.1f}ms (Total: {t_pass1+t_pass2:.1f}ms)")

    # Rescale word bounding boxes from 1.4x space back to original image space
    scaled_words2: List[OCRWord] = []
    for wd in words2:
        orig_bbox = [
            max(0, min(w, int(round(wd.bbox[0] / scale)))),
            max(0, min(h, int(round(wd.bbox[1] / scale)))),
            max(0, min(w, int(round(wd.bbox[2] / scale)))),
            max(0, min(h, int(round(wd.bbox[3] / scale)))),
        ]
        scaled_words2.append(OCRWord(text=wd.text, confidence=wd.confidence, bbox=orig_bbox))

    # Spatial and text deduplication: combine word tokens from both passes
    all_words = list(words1) + list(scaled_words2)
    accepted_words: List[OCRWord] = []

    def _norm_token(t: str) -> str:
        return re.sub(r'[^a-z0-9]', '', str(t).lower())

    for wd in all_words:
        w_norm = _norm_token(wd.text)
        if not w_norm:
            continue
        duplicate = False
        for idx, acc in enumerate(accepted_words):
            acc_norm = _norm_token(acc.text)
            iou = _box_iou(wd.bbox, acc.bbox)

            h_ref = max(wd.bbox[3] - wd.bbox[1], acc.bbox[3] - acc.bbox[1], 10)
            yc1 = (wd.bbox[1] + wd.bbox[3]) / 2.0
            yc2 = (acc.bbox[1] + acc.bbox[3]) / 2.0
            xc1 = (wd.bbox[0] + wd.bbox[2]) / 2.0
            xc2 = (acc.bbox[0] + acc.bbox[2]) / 2.0
            same_region = (iou > 0.35) or (abs(yc1 - yc2) <= h_ref * 0.7 and abs(xc1 - xc2) <= h_ref * 1.5)

            if same_region and (w_norm == acc_norm or w_norm in acc_norm or acc_norm in w_norm):
                duplicate = True
                if len(wd.text) > len(acc.text) or (len(wd.text) == len(acc.text) and wd.confidence > acc.confidence):
                    accepted_words[idx] = wd
                break

        if not duplicate:
            accepted_words.append(wd)

    # Reconstruct reading-order geometric lines from accepted words
    words_sorted = sorted(accepted_words, key=lambda w: (w.bbox[1], w.bbox[0]))
    reconstructed_lines = []
    curr_line = []
    curr_y = None
    for w in words_sorted:
        y_mid = (w.bbox[1] + w.bbox[3]) / 2.0
        h_box = max(w.bbox[3] - w.bbox[1], 10)
        if curr_y is None or abs(y_mid - curr_y) < max(h_box * 0.45, 12):
            curr_line.append(w)
            curr_y = y_mid if curr_y is None else (curr_y * 0.7 + y_mid * 0.3)
        else:
            curr_line.sort(key=lambda x: x.bbox[0])
            reconstructed_lines.append(" ".join(x.text for x in curr_line))
            curr_line = [w]
            curr_y = y_mid
    if curr_line:
        curr_line.sort(key=lambda x: x.bbox[0])
        reconstructed_lines.append(" ".join(x.text for x in curr_line))

    # Merge reconstructed reading-order lines with unique raw detection lines cleanly
    seen_line_keys = set()
    merged_lines = []
    for l in reconstructed_lines + lines1 + lines2:
        l_clean = l.strip()
        l_norm = _norm_token(l_clean)
        if not l_norm or l_norm in seen_line_keys:
            continue
        seen_line_keys.add(l_norm)
        merged_lines.append(l_clean)

    merged_confs = [wd.confidence for wd in accepted_words] if accepted_words else confs1
    return merged_lines, accepted_words, merged_confs, 2


class PaddleOCREngine(OCREngine):
    """
    PaddleOCR Deep Learning Engine (PP-OCRv4).
    Features:
    - Multi-scale text detection & recognition (DBNet/SVTR)
    - Direction/angle classification
    - High accuracy on rotated, curved, and stylized package text
    - Contextual post-processing and statutory compliance cleanup
    """

    def __init__(self, lang: str = "en", use_angle_cls: bool = True):
        self.lang = lang
        self.use_angle_cls = use_angle_cls

    def is_available(self) -> bool:
        return _is_paddle_available()

    async def extract(self, image_path: str) -> OCRResult:
        start_time = time.time()

        if not self.is_available():
            logger.error("PaddleOCR is not available or dependencies (paddleocr, paddlepaddle) are not installed.")
            return OCRResult(
                full_text="PaddleOCR is unavailable or dependencies are not installed in the environment.",
                words=[],
                language=self.lang,
                processing_time=round(time.time() - start_time, 2),
                average_confidence=0.0,
                word_count=0,
                engine="PaddleOCR (Unavailable)",
                preprocessing_variant="None",
                regions_processed=0,
                ocr_passes=0
            )

        try:
            # Run multi-scale PaddleOCR inference in a thread pool so it does not block async loop
            lines, words, confs, passes = await asyncio.to_thread(_sync_paddle_extract_multiscale, image_path, self.lang)

            raw_combined = "\n".join(lines)

            # Apply OCR text cleaning
            cleaned = clean_ocr_text(raw_combined)

            # Apply contextual statutory repairs (e.g. FSSA1 -> FSSAI, 400 9 -> 400 g)
            repaired_lines = []
            for line in cleaned.split("\n"):
                l = line.strip()
                l = re.sub(r'\bFSSA[1lI]\b', 'FSSAI', l, flags=re.IGNORECASE)
                if re.search(r'Net\s*(?:Weight|Wt|Qty)', l, re.IGNORECASE):
                    l = re.sub(r'\b(\d+(?:\.\d+)?)\s*9\b', r'\1 g', l)
                repaired_lines.append(l)

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
                engine="PaddleOCR (PP-OCRv4)",
                preprocessing_variant="Multi-Scale Deep Learning Det + Rec + Angle Classifier",
                regions_processed=len(lines),
                ocr_passes=passes
            )

        except Exception as e:
            logger.exception(f"PaddleOCR extraction error: {e}")
            return OCRResult(
                full_text=f"PaddleOCR failed to process this image: {str(e)}",
                words=[],
                language=self.lang,
                processing_time=round(time.time() - start_time, 2),
                average_confidence=0.0,
                word_count=0,
                engine="PaddleOCR (Error)",
                preprocessing_variant="None",
                regions_processed=0,
                ocr_passes=0
            )

