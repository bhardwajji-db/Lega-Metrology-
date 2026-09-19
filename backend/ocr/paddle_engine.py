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
from models.schemas import OCRResult, OCRWord, MultilingualMetadata, MultilingualLanguageInfo
from multilingual.detector import detect_token_script_and_language, detect_document_languages

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

# Image-level content hash cache & model load stats
_OCR_RESULT_CACHE: Dict[str, Tuple[List[str], List[OCRWord], List[float], int]] = {}
_OCR_CACHE_LOCK = threading.Lock()
_MODEL_LOAD_STATS = {
    "model_load_count": 0,
    "total_load_time_ms": 0.0,
    "languages_loaded": []
}


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
    alias_map = {
        "hi": "hi", "hindi": "hi", "devanagari": "hi", "hin": "hi",
        "mr": "mr", "marathi": "mr", "mar": "mr",
        "bn": "bn", "bengali": "bn", "ben": "bn", "bangla": "bn",
        "gu": "gu", "gujarati": "gu", "guj": "gu",
        "pa": "pa", "punjabi": "pa", "pan": "pa", "gurmukhi": "pa",
        "ta": "ta", "tamil": "ta", "tam": "ta",
        "te": "te", "telugu": "te", "tel": "te",
        "kn": "ka", "kannada": "ka", "kan": "ka", "ka": "ka",
        "ml": "ml", "malayalam": "ml", "mal": "ml",
        "en": "en", "english": "en", "eng": "en", "latin": "en"
    }
    return alias_map.get(l, "en")


def _init_paddle_ocr(lang: str = "en", use_angle_cls: bool = True):
    """
    Initialize PaddleOCR instance with resilient parameter handling.
    PaddleOCR downloads PP-OCR models automatically on first run.
    Thread-safe per-language singleton pattern.
    Enforces text_recognition_batch_size=1 on CPU to avoid expensive max-width sequence padding.
    """
    global _PADDLE_OCR_INSTANCES, _MODEL_LOAD_STATS
    norm_lang = _normalize_lang_code(lang)
    if norm_lang in _PADDLE_OCR_INSTANCES:
        return _PADDLE_OCR_INSTANCES[norm_lang]

    with _PADDLE_OCR_LOCK:
        if norm_lang in _PADDLE_OCR_INSTANCES:
            return _PADDLE_OCR_INSTANCES[norm_lang]

        t_load0 = time.perf_counter()

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

        # Attempt initialization with high-performance parameters (batch_size=1 avoids massive padding overhead)
        try:
            instance = PaddleOCR(
                lang=norm_lang,
                ocr_version="PP-OCRv4",
                use_doc_unwarping=False,
                use_doc_orientation_classify=False,
                use_textline_orientation=False,
                text_recognition_batch_size=1
            )
        except Exception:
            try:
                instance = PaddleOCR(
                    lang=norm_lang,
                    use_doc_unwarping=False,
                    use_doc_orientation_classify=False,
                    use_textline_orientation=False,
                    text_recognition_batch_size=1
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

        # Configure C++ Paddle Inference Predictors for DBNet and SVTR with optimal oneDNN and threading
        try:
            if hasattr(instance, "paddlex_pipeline") and hasattr(instance.paddlex_pipeline, "_pipeline"):
                pipe = instance.paddlex_pipeline._pipeline
                import multiprocessing
                import paddle.inference as paddle_infer

                optimal_threads = min(max(multiprocessing.cpu_count() // 2, 4), 6)

                # 1. DBNet Text Detection: CPU threads = 6, MKLDNN disabled (DBNet PIR limitation)
                if hasattr(pipe, "text_det_model") and hasattr(pipe.text_det_model, "runner"):
                    runner_det = pipe.text_det_model.runner
                    m_file_d = runner_det.model_dir / f"{runner_det.model_file_prefix}.json"
                    p_file_d = runner_det.model_dir / f"{runner_det.model_file_prefix}.pdiparams"
                    if m_file_d.exists() and p_file_d.exists():
                        cfg_det = paddle_infer.Config(str(m_file_d), str(p_file_d))
                        cfg_det.disable_gpu()
                        cfg_det.disable_mkldnn()
                        cfg_det.set_cpu_math_library_num_threads(optimal_threads)
                        cfg_det.disable_glog_info()
                        runner_det.predictor = paddle_infer.create_predictor(cfg_det)
                        runner_det.infer = type(runner_det.infer)(runner_det.predictor)

                # 2. SVTR Text Recognition: oneDNN enabled, CPU threads = 6, batch_size = 1
                if hasattr(pipe, "text_rec_model"):
                    if hasattr(pipe.text_rec_model, "batch_sampler"):
                        pipe.text_rec_model.batch_sampler.batch_size = 1
                    if hasattr(pipe.text_rec_model, "runner"):
                        runner_rec = pipe.text_rec_model.runner
                        m_file_r = runner_rec.model_dir / f"{runner_rec.model_file_prefix}.json"
                        p_file_r = runner_rec.model_dir / f"{runner_rec.model_file_prefix}.pdiparams"
                        if m_file_r.exists() and p_file_r.exists():
                            cfg_rec = paddle_infer.Config(str(m_file_r), str(p_file_r))
                            cfg_rec.disable_gpu()
                            cfg_rec.enable_mkldnn()
                            cfg_rec.set_mkldnn_cache_capacity(10)
                            cfg_rec.set_cpu_math_library_num_threads(optimal_threads)
                            cfg_rec.disable_glog_info()
                            runner_rec.predictor = paddle_infer.create_predictor(cfg_rec)
                            runner_rec.infer = type(runner_rec.infer)(runner_rec.predictor)

                # 3. Minimal 1-crop startup warmup so oneDNN graph compiles ahead of user requests
                try:
                    dummy_crop = np.zeros((48, 160, 3), dtype=np.uint8)
                    _ = list(pipe.text_rec_model([dummy_crop]))
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[OCR] Predictor optimization fallback: {e}")

        t_load = (time.perf_counter() - t_load0) * 1000
        _MODEL_LOAD_STATS["model_load_count"] += 1
        _MODEL_LOAD_STATS["total_load_time_ms"] += t_load
        _MODEL_LOAD_STATS["languages_loaded"].append(norm_lang)
        logger.info(f"[OCR] Loaded PP-OCR model for lang '{norm_lang}' in {t_load:.1f}ms (Total loads: {_MODEL_LOAD_STATS['model_load_count']})")

        _PADDLE_OCR_INSTANCES[norm_lang] = instance
        return instance



def _sync_paddle_extract(image_path: str, lang: str = "en") -> Tuple[List[str], List[OCRWord], List[float]]:
    """
    Synchronous execution of PaddleOCR inference on image_path with pre-recognition deduplication & text-line grouping.
    1. Detects text polygons via DBNet.
    2. Filters zero-area/noise boxes and removes duplicate detection boxes.
    3. Groups horizontally adjacent word/character fragments on the same visual line into unified line crops.
    4. Evaluates SVTR recognition on grouped crops with batch_size=1 (unpadded).
    5. Reconstructs OCRWord tokens with precise proportional bounding boxes in original image space.
    """
    import cv2

    ocr_inst = _init_paddle_ocr(lang=lang)
    lines: List[str] = []
    words: List[OCRWord] = []
    confs: List[float] = []

    pipe = getattr(ocr_inst, "paddlex_pipeline", None)
    inner_pipe = getattr(pipe, "_pipeline", None) if pipe else None

    # Optimized direct pipeline path with Line Grouping & Deduplication
    img = cv2.imread(image_path) if (isinstance(image_path, str) and os.path.exists(image_path)) else None
    if img is not None and inner_pipe is not None and hasattr(inner_pipe, "text_det_model") and hasattr(inner_pipe, "text_rec_model"):
        with _PADDLE_INFERENCE_LOCK:
            img_h, img_w = img.shape[:2]

            try:
                # 1. DBNet Text Detection
                det_res = list(inner_pipe.text_det_model.predict(img))
                if not det_res or "dt_polys" not in det_res[0]:
                    return lines, words, confs
                dt_polys = det_res[0]["dt_polys"]
                if dt_polys is None or len(dt_polys) == 0:
                    return lines, words, confs

                # 2. Convert polygons to [x1, y1, x2, y2] & validate
                raw_boxes = []
                for poly in dt_polys:
                    xs = [pt[0] for pt in poly]
                    ys = [pt[1] for pt in poly]
                    x1 = max(0, int(round(min(xs))))
                    y1 = max(0, int(round(min(ys))))
                    x2 = min(img_w, int(round(max(xs))))
                    y2 = min(img_h, int(round(max(ys))))
                    if (x2 - x1) >= 5 and (y2 - y1) >= 4 and ((x2 - x1) * (y2 - y1)) >= 25:
                        raw_boxes.append([x1, y1, x2, y2])

                # Deduplicate high-overlap detection boxes (IoU >= 0.85)
                valid_boxes = []
                for b in raw_boxes:
                    dup = False
                    for vb in valid_boxes:
                        x_left = max(b[0], vb[0])
                        y_top = max(b[1], vb[1])
                        x_right = min(b[2], vb[2])
                        y_bottom = min(b[3], vb[3])
                        if x_right > x_left and y_bottom > y_top:
                            inter = (x_right - x_left) * (y_bottom - y_top)
                            a1 = (b[2] - b[0]) * (b[3] - b[1])
                            a2 = (vb[2] - vb[0]) * (vb[3] - vb[1])
                            if inter / float(a1 + a2 - inter) >= 0.85:
                                dup = True
                                break
                    if not dup:
                        valid_boxes.append(b)

                # 3. Horizontal Text-Line Grouping
                boxes_sorted = sorted(valid_boxes, key=lambda b: (b[1], b[0]))
                grouped_boxes = []
                used = [False] * len(boxes_sorted)

                for i in range(len(boxes_sorted)):
                    if used[i]:
                        continue
                    curr_box = list(boxes_sorted[i])
                    used[i] = True

                    merged_any = True
                    while merged_any:
                        merged_any = False
                        curr_h = curr_box[3] - curr_box[1]
                        curr_yc = (curr_box[1] + curr_box[3]) / 2.0

                        for j in range(len(boxes_sorted)):
                            if used[j]:
                                continue
                            cand_box = boxes_sorted[j]
                            cand_h = cand_box[3] - cand_box[1]
                            cand_yc = (cand_box[1] + cand_box[3]) / 2.0

                            href = min(curr_h, cand_h)
                            if abs(curr_yc - cand_yc) <= max(href * 0.45, 6) and (max(curr_h, cand_h) / max(href, 1) <= 1.8):
                                gap = max(0, max(curr_box[0], cand_box[0]) - min(curr_box[2], cand_box[2]))
                                overlap_x = max(0, min(curr_box[2], cand_box[2]) - max(curr_box[0], cand_box[0]))

                                if (gap <= href * 1.5 or overlap_x > 0) and ((max(curr_box[2], cand_box[2]) - min(curr_box[0], cand_box[0])) <= 460):
                                    curr_box[0] = min(curr_box[0], cand_box[0])
                                    curr_box[1] = min(curr_box[1], cand_box[1])
                                    curr_box[2] = max(curr_box[2], cand_box[2])
                                    curr_box[3] = max(curr_box[3], cand_box[3])
                                    used[j] = True
                                    merged_any = True
                                    break

                    grouped_boxes.append(curr_box)

                # 4. Crop sub-images from grouped bounding boxes
                crops = [img[b[1]:b[3], b[0]:b[2]] for b in grouped_boxes if (b[2] - b[0]) > 0 and (b[3] - b[1]) > 0]
                if not crops:
                    return lines, words, confs

                # 5. SVTR Text Recognition with batch_size=1
                inner_pipe.text_rec_model.batch_sampler.batch_size = 1
                rec_res = list(inner_pipe.text_rec_model(crops))

                # 6. Parse recognized texts and generate OCRWords with proportional sub-boxes
                for b, r in zip(grouped_boxes, rec_res):
                    raw_text = str(r["rec_text"]).strip()
                    if not raw_text:
                        continue
                    raw_conf = float(r["rec_score"])
                    conf = round(raw_conf * 100.0 if raw_conf <= 1.0 else raw_conf, 1)
                    lines.append(raw_text)
                    confs.append(conf)

                    tokens = raw_text.split()
                    if len(tokens) <= 1:
                        t_meta = detect_token_script_and_language(raw_text)
                        words.append(OCRWord(text=raw_text, confidence=conf, bbox=b, language=t_meta.get("language"), script=t_meta.get("script")))
                    else:
                        x1, y1, x2, y2 = b
                        line_w = max(x2 - x1, 1)
                        total_chars = sum(len(t) for t in tokens)
                        curr_x = x1
                        for t in tokens:
                            char_ratio = len(t) / max(total_chars, 1)
                            t_w = max(int(round(line_w * char_ratio)), 1)
                            t_bbox = [curr_x, y1, min(curr_x + t_w, x2), y2]
                            t_meta = detect_token_script_and_language(t)
                            words.append(OCRWord(text=t, confidence=conf, bbox=t_bbox, language=t_meta.get("language"), script=t_meta.get("script")))
                            curr_x += t_w

                return lines, words, confs

            except Exception as e:
                logger.warning(f"[OCR] Direct grouped recognition failed: {e}; falling back to standard pipeline")

    # Fallback path if direct pipeline is unavailable
    results = None
    with _PADDLE_INFERENCE_LOCK:
        if hasattr(ocr_inst, "predict"):
            try:
                res_gen = ocr_inst.predict(image_path)
                results = list(res_gen) if not isinstance(res_gen, (list, tuple)) else res_gen
            except Exception as e:
                logger.debug(f"ocr_inst.predict failed: {e}; falling back to ocr_inst.ocr")

        if results is None:
            try:
                results = ocr_inst.ocr(image_path)
            except Exception as e:
                logger.error(f"ocr_inst.ocr failed: {e}")

    if not results:
        return lines, words, confs

    page_data = results[0] if isinstance(results, (list, tuple)) else results
    if not page_data:
        return lines, words, confs

    # PaddleOCR 3.x dict format fallback
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

            tokens = raw_text.split()
            if len(tokens) <= 1:
                t_meta = detect_token_script_and_language(raw_text)
                words.append(OCRWord(text=raw_text, confidence=conf, bbox=line_bbox, language=t_meta.get("language"), script=t_meta.get("script")))
            else:
                x1, y1, x2, y2 = line_bbox
                line_w = max(x2 - x1, 1)
                total_chars = sum(len(t) for t in tokens)
                curr_x = x1
                for t in tokens:
                    char_ratio = len(t) / max(total_chars, 1)
                    t_w = max(int(round(line_w * char_ratio)), 1)
                    t_bbox = [curr_x, y1, min(curr_x + t_w, x2), y2]
                    t_meta = detect_token_script_and_language(t)
                    words.append(OCRWord(text=t, confidence=conf, bbox=t_bbox, language=t_meta.get("language"), script=t_meta.get("script")))
                    curr_x += t_w

        return lines, words, confs

    # Legacy PaddleOCR 2.x list format fallback
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
                t_meta = detect_token_script_and_language(raw_text)
                words.append(OCRWord(text=raw_text, confidence=conf, bbox=line_bbox, language=t_meta.get("language"), script=t_meta.get("script")))
            else:
                x1, y1, x2, y2 = line_bbox
                line_w = max(x2 - x1, 1)
                total_chars = sum(len(t) for t in tokens)
                curr_x = x1
                for t in tokens:
                    char_ratio = len(t) / max(total_chars, 1)
                    t_w = max(int(round(line_w * char_ratio)), 1)
                    t_bbox = [curr_x, y1, min(curr_x + t_w, x2), y2]
                    t_meta = detect_token_script_and_language(t)
                    words.append(OCRWord(text=t, confidence=conf, bbox=t_bbox, language=t_meta.get("language"), script=t_meta.get("script")))
                    curr_x += t_w

        return lines, words, confs

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


def _identify_statutory_candidate_regions(
    words: List[OCRWord],
    img_w: int,
    img_h: int,
    max_regions: int = 2,
    max_area_ratio: float = 0.45
) -> List[Tuple[int, int, int, int]]:
    """
    Identify targeted candidate bounding boxes for statutory fine-print declarations.
    Focuses on ingredients, nutrition, allergens, licensing, and small/low-confidence text clusters.
    Enforces max_regions <= 2 and region area ratio <= max_area_ratio (45%).
    """
    if not words:
        return []

    statutory_keywords = {
        "ingredient", "ingredients", "inored", "nored", "composition", "contains",
        "allergen", "allergens", "nutrition", "nutritional", "manufactured", "marketed",
        "mfd", "mfg", "packed", "batch", "expiry", "exp", "use by", "best before",
        "mrp", "lic", "fssai", "veg", "consumer", "feedback"
    }

    target_words: List[OCRWord] = []
    for wd in words:
        txt_norm = re.sub(r'[^a-z0-9]', '', wd.text.lower())
        h_box = wd.bbox[3] - wd.bbox[1]
        is_statutory = any(k in txt_norm for k in statutory_keywords)
        is_fine_print = h_box <= 12 and wd.confidence < 65.0
        if is_statutory or is_fine_print:
            target_words.append(wd)

    if not target_words:
        return []

    # Enclose high-priority statutory / fine-print words
    pad_x = 16
    pad_y = 16
    min_x = max(0, min(w.bbox[0] for w in target_words) - pad_x)
    min_y = max(0, min(w.bbox[1] for w in target_words) - pad_y)
    max_x = min(img_w, max(w.bbox[2] for w in target_words) + pad_x)
    max_y = min(img_h, max(w.bbox[3] for w in target_words) + pad_y)

    total_area = max(img_w * img_h, 1)
    cand_area = (max_x - min_x) * (max_y - min_y)

    # If the candidate region exceeds max_area_ratio, clamp vertically to fine-print core
    if cand_area / total_area > max_area_ratio:
        # Sort target words by Y and select the densest statutory window
        y_centers = sorted([(w.bbox[1] + w.bbox[3]) / 2.0 for w in target_words])
        mid_idx = len(y_centers) // 2
        core_y_center = y_centers[mid_idx]
        allowed_h = int(img_h * max_area_ratio)
        min_y = max(0, int(core_y_center - allowed_h // 2))
        max_y = min(img_h, min_y + allowed_h)

    return [(min_x, min_y, max_x, max_y)]


def _sync_paddle_extract_multiscale(image_path: str, lang: str = "en") -> Tuple[List[str], List[OCRWord], List[float], int]:
    """
    Targeted Secondary OCR (Region-Based OCR) inference pipeline with coordinate remapping and spatial deduplication.
    1. Checks deterministic image-level hash cache.
    2. Runs Base Pass 1 on original image with batch_size=1.
    3. Evaluates if primary packaging text is already sufficient (>= 25 words with ingredients or front panel prominence).
       If sufficient, returns immediately in 1 pass.
    4. If fine-print statutory declarations require recovery, identifies candidate regions and crops ONLY
       the statutory candidate region(s), upscales by 1.35x, remaps coordinates, and merges tokens.
    5. Controlled Fallback: If Pass 1 is severely degraded (< 8 words on non-empty image), runs full-image fallback.
    """
    import cv2
    import tempfile
    import hashlib

    # 0. Deterministic Image-Level Hash Cache Check
    cache_key = None
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as f_img:
                img_bytes = f_img.read()
                img_hash = hashlib.sha256(img_bytes).hexdigest()
                cache_key = f"{img_hash}_{lang}"
                with _OCR_CACHE_LOCK:
                    if cache_key in _OCR_RESULT_CACHE:
                        c_lines, c_words, c_confs, c_passes = _OCR_RESULT_CACHE[cache_key]
                        logger.info(f"[OCR] Cache HIT for {os.path.basename(image_path)} (hash: {img_hash[:8]}): returning {len(c_words)} words (1 pass)")
                        return list(c_lines), [w.model_copy() if hasattr(w, "model_copy") else w for w in c_words], list(c_confs), c_passes
    except Exception as err:
        logger.debug(f"[OCR] Cache check error: {err}")

    t0 = time.perf_counter()
    # 1. Base pass on original image
    lines1, words1, confs1 = _sync_paddle_extract(image_path, lang=lang)
    t_pass1 = (time.perf_counter() - t0) * 1000

    raw_text = " ".join(lines1).upper()
    has_ingr = any(k in raw_text for k in ["INGRED", "INORED", "NOREDIENT", "COMPOSITION", "CONTAINS", "SAMAGRI"])
    has_mrp = any(k in raw_text for k in ["MRP", "M.R.P.", "MAXIMUM RETAIL", "UNIT SALE"])
    has_back_panel_indicators = any(k in raw_text for k in ["NUTRITION", "MARKETED BY", "MANUFACTURED", "FEEDBACK", "ALLERGEN", "FSSAI", "LIC NO"])
    has_front_prominence = any((w.bbox[3] - w.bbox[1]) >= 28 for w in words1) and len(words1) >= 8 and not has_back_panel_indicators

    # If front panel image or all statutory declarations already found in Pass 1, avoid 2nd pass
    if (has_ingr and has_mrp) or has_front_prominence or (has_ingr and len(words1) >= 25):
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
        if cache_key:
            with _OCR_CACHE_LOCK:
                _OCR_RESULT_CACHE[cache_key] = (merged_lines, words1, confs1, 1)
        return merged_lines, words1, confs1, 1

    img = cv2.imread(image_path)
    if img is None:
        return lines1, words1, confs1, 1

    h, w = img.shape[:2]
    scale = 1.35

    # 2. Controlled Fallback: If Pass 1 is severely degraded (< 8 words on non-empty image)
    if len(words1) < 8 and (w * h) > 10000:
        logger.warning(f"[OCR] Degraded Pass 1 ({len(words1)} words) for {os.path.basename(image_path)}. Running full-image fallback.")
        img_up = cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_CUBIC)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix="_fallback.png")
        os.close(tmp_fd)
        try:
            cv2.imwrite(tmp_path, img_up)
            fb_lines, fb_words, fb_confs = _sync_paddle_extract(tmp_path, lang=lang)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        scaled_fb_words = [
            OCRWord(
                text=wd.text,
                confidence=wd.confidence,
                bbox=[
                    max(0, min(w, int(round(wd.bbox[0] / scale)))),
                    max(0, min(h, int(round(wd.bbox[1] / scale)))),
                    max(0, min(w, int(round(wd.bbox[2] / scale)))),
                    max(0, min(h, int(round(wd.bbox[3] / scale)))),
                ]
            )
            for wd in fb_words
        ]
        return fb_lines, scaled_fb_words, fb_confs, 2

    # 3. Targeted Secondary OCR: Identify candidate statutory / fine-print regions with hard time budget
    candidate_regions = _identify_statutory_candidate_regions(words1, w, h, max_regions=2, max_area_ratio=0.45)
    if not candidate_regions:
        logger.info(f"[PERF] {os.path.basename(image_path)} No secondary regions identified: returning Pass 1 ({t_pass1:.1f}ms, 1 pass)")
        return lines1, words1, confs1, 1

    t_pass2_0 = time.perf_counter()
    secondary_words: List[OCRWord] = []
    secondary_lines: List[str] = []
    MAX_SECONDARY_TIME_MS = 6000.0  # 6.0s hard time budget

    for rx1, ry1, rx2, ry2 in candidate_regions:
        elapsed = (time.perf_counter() - t_pass2_0) * 1000
        if elapsed >= MAX_SECONDARY_TIME_MS:
            logger.info(f"[OCR] Secondary OCR time budget reached ({elapsed:.1f}ms >= {MAX_SECONDARY_TIME_MS:.1f}ms), stopping gracefully")
            break

        crop = img[ry1:ry2, rx1:rx2]
        if crop.size == 0:
            continue
        scale_sec = 1.25
        crop_up = cv2.resize(crop, (0, 0), fx=scale_sec, fy=scale_sec, interpolation=cv2.INTER_CUBIC)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix="_target_crop.png")
        os.close(tmp_fd)
        try:
            cv2.imwrite(tmp_path, crop_up)
            c_lines, c_words, _ = _sync_paddle_extract(tmp_path, lang=lang)
            secondary_lines.extend(c_lines)
            for wd in c_words:
                orig_bbox = [
                    max(0, min(w, rx1 + int(round(wd.bbox[0] / scale_sec)))),
                    max(0, min(h, ry1 + int(round(wd.bbox[1] / scale_sec)))),
                    max(0, min(w, rx1 + int(round(wd.bbox[2] / scale_sec)))),
                    max(0, min(h, ry1 + int(round(wd.bbox[3] / scale_sec)))),
                ]
                secondary_words.append(OCRWord(text=wd.text, confidence=wd.confidence, bbox=orig_bbox))
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    t_pass2 = (time.perf_counter() - t_pass2_0) * 1000
    logger.info(f"[PERF] {os.path.basename(image_path)} Pass 1: {t_pass1:.1f}ms + Targeted Secondary OCR: {t_pass2:.1f}ms (Total: {t_pass1+t_pass2:.1f}ms)")

    # Spatial and text deduplication: combine word tokens from Pass 1 and Targeted Secondary Pass
    all_words = list(words1) + list(secondary_words)
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

    # Reconstruct reading-order geometric lines from accepted words with column separation
    words_sorted = sorted(accepted_words, key=lambda w: (w.bbox[1], w.bbox[0]))
    reconstructed_lines = []
    curr_line: List[OCRWord] = []
    curr_y = None
    last_x2 = None

    for w in words_sorted:
        y_mid = (w.bbox[1] + w.bbox[3]) / 2.0
        h_box = max(w.bbox[3] - w.bbox[1], 10)
        same_line = (curr_y is not None) and (abs(y_mid - curr_y) < max(h_box * 0.45, 12))
        same_col = (last_x2 is None) or (w.bbox[0] - last_x2 < max(h_box * 3.5, 45))

        if same_line and same_col:
            curr_line.append(w)
            curr_y = curr_y * 0.7 + y_mid * 0.3
            last_x2 = max(last_x2 or w.bbox[2], w.bbox[2])
        else:
            if curr_line:
                curr_line.sort(key=lambda x: x.bbox[0])
                reconstructed_lines.append(" ".join(x.text for x in curr_line))
            curr_line = [w]
            curr_y = y_mid
            last_x2 = w.bbox[2]

    if curr_line:
        curr_line.sort(key=lambda x: x.bbox[0])
        reconstructed_lines.append(" ".join(x.text for x in curr_line))

    # Merge native detection lines first (preserving native box reading order), then supplementary reconstructed lines
    seen_line_keys = set()
    merged_lines = []
    for l in lines1 + secondary_lines + reconstructed_lines:
        l_clean = l.strip()
        l_norm = _norm_token(l_clean)
        if not l_norm or l_norm in seen_line_keys:
            continue
        seen_line_keys.add(l_norm)
        merged_lines.append(l_clean)

    merged_confs = [wd.confidence for wd in accepted_words] if accepted_words else confs1
    if cache_key:
        with _OCR_CACHE_LOCK:
            _OCR_RESULT_CACHE[cache_key] = (merged_lines, accepted_words, merged_confs, 2)
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

            doc_meta = detect_document_languages(final_text)
            multi_meta = MultilingualMetadata(**doc_meta) if doc_meta else None

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
                ocr_passes=passes,
                multilingual=multi_meta
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

