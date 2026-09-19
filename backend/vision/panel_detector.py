import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from vision.schemas import PanelCandidate, PanelClassificationResult
from vision.classifiers import panel_classifier
from vision.config import vision_config
from vision.utils import normalize_bbox

class PackagePanelDetector:
    """
    Identifies distinct packaging facets/panels (e.g. Front, Back, Side 1, Side 2)
    and classifies them with confidence tiers and supporting signals.
    """

    @classmethod
    def detect_and_classify(
        cls,
        img_bgr: np.ndarray,
        ocr_text: str = "",
        words: List[Dict[str, Any]] = None,
        has_nutrition_table: bool = False,
        has_barcode: bool = False
    ) -> PanelClassificationResult:
        if img_bgr is None or img_bgr.size == 0:
            return PanelClassificationResult()

        h, w = img_bgr.shape[:2]
        words = words or []

        # 1. Primary Full-Frame / Facet Classification
        primary_type, primary_conf, signals = panel_classifier.classify(
            text=ocr_text,
            words=words,
            img_width=w,
            img_height=h,
            has_nutrition_table=has_nutrition_table,
            has_barcode=has_barcode
        )

        norm_full_bbox = [0.0, 0.0, 1.0, 1.0]
        full_panel = PanelCandidate(
            id="panel_primary",
            panel_type=primary_type,
            confidence=primary_conf,
            confidence_tier=vision_config.get_confidence_tier(primary_conf),
            bbox=[0, 0, w, h],
            normalized_bbox=norm_full_bbox,
            polygon=[[0, 0], [w, 0], [w, h], [0, h]],
            supporting_signals=signals,
            estimated_aspect_ratio=round(w / float(h), 2)
        )

        panels = [full_panel]

        # 2. Check for multi-facet split (e.g. photo showing front + side together)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=int(h * 0.45), maxLineGap=20)

        if lines is not None:
            v_lines = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Check near vertical line (angle > 75 deg)
                if abs(x2 - x1) < 20 and abs(y2 - y1) > h * 0.45:
                    v_lines.append((x1 + x2) // 2)

            if v_lines:
                median_split_x = int(np.median(v_lines))
                # Only split if line divides package nicely (between 25% and 75% width)
                if int(w * 0.25) < median_split_x < int(w * 0.75):
                    # Left facet
                    left_words = [wd for wd in words if wd.get('bbox', [0,0,0,0])[2] <= median_split_x]
                    left_text = " ".join(wd.get('text', '') for wd in left_words)
                    left_type, left_conf, left_sig = panel_classifier.classify(
                        text=left_text,
                        words=left_words,
                        img_width=median_split_x,
                        img_height=h
                    )

                    # Right facet
                    right_words = [wd for wd in words if wd.get('bbox', [0,0,0,0])[0] >= median_split_x]
                    right_text = " ".join(wd.get('text', '') for wd in right_words)
                    right_type, right_conf, right_sig = panel_classifier.classify(
                        text=right_text,
                        words=right_words,
                        img_width=w - median_split_x,
                        img_height=h
                    )

                    left_panel = PanelCandidate(
                        id="facet_left",
                        panel_type=left_type,
                        confidence=left_conf,
                        confidence_tier=vision_config.get_confidence_tier(left_conf),
                        bbox=[0, 0, median_split_x, h],
                        normalized_bbox=normalize_bbox([0, 0, median_split_x, h], w, h),
                        supporting_signals=left_sig,
                        estimated_aspect_ratio=round(median_split_x / float(h), 2)
                    )
                    right_panel = PanelCandidate(
                        id="facet_right",
                        panel_type=right_type,
                        confidence=right_conf,
                        confidence_tier=vision_config.get_confidence_tier(right_conf),
                        bbox=[median_split_x, 0, w, h],
                        normalized_bbox=normalize_bbox([median_split_x, 0, w, h], w, h),
                        supporting_signals=right_sig,
                        estimated_aspect_ratio=round((w - median_split_x) / float(h), 2)
                    )
                    panels.extend([left_panel, right_panel])

        return PanelClassificationResult(
            primary_panel=primary_type,
            confidence=primary_conf,
            confidence_tier=vision_config.get_confidence_tier(primary_conf),
            panels=panels,
            classification_signals=signals
        )

panel_detector = PackagePanelDetector()
