import time
import logging
import cv2
import numpy as np
from typing import Optional, List, Dict, Any, Union
from vision.schemas import (
    VisionAnalysisResult,
    ImageQualityResult,
    PerspectiveCorrectionResult,
    PackageBoundaryResult,
    PanelClassificationResult,
    SemanticRegionResult,
    SymbolDetectionResult,
    LogoDetectionResult,
    BarcodeDetectionResult,
    QRDetectionResult,
    TextRegionInfo,
    VisionTimingMetrics
)
from vision.quality import quality_gate
from vision.geometry import geometric_analyzer
from vision.package_detector import package_boundary_detector
from vision.panel_detector import panel_detector
from vision.text_regions import text_region_segmenter
from vision.region_detector import semantic_region_detector
from vision.symbol_detector import symbol_detector
from vision.logo_detector import logo_detector
from vision.barcode_detector import barcode_detector
from vision.qr_detector import qr_detector
from vision.evidence import vision_evidence_adapter
from vision.config import vision_config

logger = logging.getLogger(__name__)

class VisionPipeline:
    """
    Central Coordinator for the Computer Vision Intelligence Layer.
    Executes:
    1. Image Quality Gate
    2. Geometry & Perspective Analysis
    3. Packaging Boundary Detection
    4. Text-Region Segmentation & Small-Text Flagging
    5. Semantic Region Detection (MRP, Net Qty, Dates, Nutrition, etc.)
    6. Symbol & Logo Detection (Veg/Non-Veg, FSSAI)
    7. Barcode & QR Code Localization
    8. Panel Classification (Front / Back / Side)
    Collects execution timing and ensures 100% fail-safe fault isolation.
    """

    @classmethod
    def analyze_image(
        cls,
        image_input: Optional[Union[str, np.ndarray]] = None,
        image_path: Optional[Union[str, np.ndarray]] = None,
        ocr_text: str = "",
        words: Optional[List[Dict[str, Any]]] = None,
        ocr_words: Optional[List[Dict[str, Any]]] = None,
        image_index: int = 0,
        image_label: str = "Front"
    ) -> VisionAnalysisResult:
        t_start_total = time.perf_counter()
        img_target = image_input if image_input is not None else image_path
        words = words if words is not None else (ocr_words or [])

        source_name = "memory_array"
        if isinstance(img_target, str):
            source_name = img_target.split('/')[-1].split('\\')[-1]

        res = VisionAnalysisResult(
            image_index=image_index,
            image_label=image_label,
            source_filename=source_name
        )
        timing = VisionTimingMetrics()

        try:
            if isinstance(img_target, str):
                img_bgr = cv2.imread(img_target)
                if img_bgr is None:
                    res.status = "FAILED"
                    res.error_message = f"Failed to load image at {img_target}"
                    return res
            elif isinstance(img_target, np.ndarray):
                img_bgr = img_target
            else:
                res.status = "FAILED"
                res.error_message = "Invalid image input type"
                return res
        except Exception as e:
            res.status = "FAILED"
            res.error_message = str(e)
            return res

        # ── 1. Image Quality Gate ──
        t0 = time.perf_counter()
        try:
            res.quality = quality_gate.analyze(img_bgr)
        except Exception as e:
            logger.warning(f"[VISION] Quality gate error: {e}")
        timing.quality_gate_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 2. Geometric & Perspective Analysis ──
        t0 = time.perf_counter()
        try:
            res.geometry, _ = geometric_analyzer.analyze_perspective(img_bgr)
        except Exception as e:
            logger.warning(f"[VISION] Geometry analysis error: {e}")
        timing.geometry_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 3. Packaging Boundary Detection ──
        t0 = time.perf_counter()
        try:
            res.package_boundary = package_boundary_detector.detect(img_bgr)
        except Exception as e:
            logger.warning(f"[VISION] Package boundary error: {e}")
        timing.package_boundary_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 4. Text-Region Segmentation ──
        t0 = time.perf_counter()
        try:
            h, w = img_bgr.shape[:2]
            res.text_regions = text_region_segmenter.segment(words, w, h)
        except Exception as e:
            logger.warning(f"[VISION] Text regions error: {e}")
        timing.text_regions_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 5. Semantic Region Detection ──
        t0 = time.perf_counter()
        try:
            res.semantic_regions = semantic_region_detector.detect_all_regions(img_bgr, words)
        except Exception as e:
            logger.warning(f"[VISION] Semantic regions error: {e}")
        timing.semantic_regions_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 6. Visual Symbol & Logo Detection ──
        t0 = time.perf_counter()
        try:
            res.symbols = symbol_detector.detect_symbols(img_bgr, words)
            res.logos = logo_detector.detect_logos(img_bgr, words)
        except Exception as e:
            logger.warning(f"[VISION] Symbol/Logo error: {e}")
        timing.symbols_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 7. Barcode & QR Detection ──
        t0 = time.perf_counter()
        try:
            res.barcode = barcode_detector.detect(img_bgr)
            res.qr_code = qr_detector.detect_and_decode(img_bgr)
        except Exception as e:
            logger.warning(f"[VISION] Barcode/QR error: {e}")
        timing.barcodes_ms = round((time.perf_counter() - t0) * 1000, 2)

        # ── 8. Panel Classification ──
        t0 = time.perf_counter()
        try:
            has_nutrition = any(r.region_type == "nutrition_table" for r in res.semantic_regions)
            res.panel_classification = panel_detector.detect_and_classify(
                img_bgr=img_bgr,
                ocr_text=ocr_text,
                words=words,
                has_nutrition_table=has_nutrition,
                has_barcode=res.barcode.detected
            )
        except Exception as e:
            logger.warning(f"[VISION] Panel classification error: {e}")
        timing.panel_classification_ms = round((time.perf_counter() - t0) * 1000, 2)

        timing.total_vision_ms = round((time.perf_counter() - t_start_total) * 1000, 2)
        res.timing = timing

        # Overall vision confidence
        conf_scores = [
            res.quality.overall_score / 100.0,
            res.package_boundary.confidence if res.package_boundary.detected else 0.5,
            res.panel_classification.confidence
        ]
        avg_conf = round(sum(conf_scores) / len(conf_scores), 2)
        res.overall_confidence = avg_conf
        res.overall_confidence_tier = vision_config.get_confidence_tier(avg_conf)
        # Generate standard EvidenceItems for viewer integration
        try:
            res.evidence_items = vision_evidence_adapter.generate_evidence_items(res, image_index, image_label)
        except Exception as e:
            logger.warning(f"[VISION] Evidence adapter error: {e}")

        logger.info(f"[PERF] Vision Pipeline ({image_label}): {timing.total_vision_ms:.1f} ms")
        return res

vision_pipeline = VisionPipeline()
