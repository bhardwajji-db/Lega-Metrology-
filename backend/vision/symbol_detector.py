import re
import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from vision.schemas import SymbolDetectionResult
from vision.utils import normalize_bbox
from vision.config import vision_config

class SymbolDetector:
    """
    Detects packaging symbols and statutory marks:
    - Vegetarian symbol: Green square enclosing a filled green circle
    - Non-Vegetarian symbol: Brown/Red square enclosing a filled circle or triangle
    - FSSAI logo / mark visual area
    Uses combined geometric nested-contour detection and HSV color classification.
    """

    @classmethod
    def detect_symbols(
        cls,
        img_bgr: np.ndarray,
        words: List[Dict[str, Any]] = None
    ) -> List[SymbolDetectionResult]:
        if img_bgr is None or img_bgr.size == 0:
            return []

        h, w = img_bgr.shape[:2]
        symbols: List[SymbolDetectionResult] = []

        # 1. Detect Veg / Non-Veg Nested Symbol
        veg_symbol = cls._detect_veg_nonveg(img_bgr)
        if veg_symbol:
            symbols.append(veg_symbol)

        # 2. Detect FSSAI Visual Mark Area
        fssai_symbol = cls._detect_fssai_mark(img_bgr, words)
        if fssai_symbol:
            symbols.append(fssai_symbol)

        return symbols

    @classmethod
    def _detect_veg_nonveg(cls, img_bgr: np.ndarray) -> Optional[SymbolDetectionResult]:
        """
        Locates the standard statutory nested symbol:
        Outer square (aspect ratio ~1.0) with an inner concentric filled circle/triangle.
        """
        try:
            h, w = img_bgr.shape[:2]
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 40, 140)

            # Find contours with full hierarchy (parent-child relationship)
            contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if hierarchy is None or len(contours) == 0:
                return None

            hierarchy = hierarchy[0]
            for i, c in enumerate(contours):
                # We look for an outer square contour that has at least one child contour inside
                child_idx = hierarchy[i][2]
                if child_idx == -1:
                    continue

                bx, by, bw, bh = cv2.boundingRect(c)
                # Symbol size filter (e.g. 15px to 250px, not full image)
                if bw < 15 or bh < 15 or bw > w * 0.4 or bh > h * 0.4:
                    continue

                aspect = bw / float(bh)
                # Square aspect ratio check
                if 0.75 <= aspect <= 1.30:
                    # Check the child contour inside
                    child_c = contours[child_idx]
                    cbx, cby, cbw, cbh = cv2.boundingRect(child_c)
                    if cbw < bw * 0.20 or cbh < bh * 0.20:
                        continue

                    # Sample color inside the symbol bounding box
                    symbol_crop_hsv = hsv[by:by+bh, bx:bx+bw]
                    if symbol_crop_hsv.size == 0:
                        continue

                    # Green mask: Hue 35 to 85
                    green_mask = cv2.inRange(symbol_crop_hsv, np.array([35, 45, 45]), np.array([85, 255, 255]))
                    green_ratio = float(np.sum(green_mask > 0)) / float(symbol_crop_hsv.shape[0] * symbol_crop_hsv.shape[1])

                    # Brown/Red mask: Hue 0 to 18 or 165 to 180
                    red_mask1 = cv2.inRange(symbol_crop_hsv, np.array([0, 50, 40]), np.array([18, 255, 255]))
                    red_mask2 = cv2.inRange(symbol_crop_hsv, np.array([165, 50, 40]), np.array([180, 255, 255]))
                    red_ratio = float(np.sum((red_mask1 > 0) | (red_mask2 > 0))) / float(symbol_crop_hsv.shape[0] * symbol_crop_hsv.shape[1])

                    bbox = [bx, by, bx + bw, by + bh]
                    norm_box = normalize_bbox(bbox, w, h)

                    if green_ratio > 0.15:
                        conf = min(0.96, 0.75 + (green_ratio * 0.4))
                        return SymbolDetectionResult(
                            symbol_type="VEG",
                            detected=True,
                            confidence=round(conf, 2),
                            confidence_tier=vision_config.get_confidence_tier(conf),
                            bbox=bbox,
                            normalized_bbox=norm_box,
                            color_scheme="GREEN",
                            detection_method="NESTED_CONTOUR_HSV_COLOR",
                            notes="Green square enclosing concentric circle (Vegetarian statutory symbol)",
                            evidence_id="ev_sym_veg_01"
                        )
                    elif red_ratio > 0.15:
                        conf = min(0.96, 0.75 + (red_ratio * 0.4))
                        return SymbolDetectionResult(
                            symbol_type="NON_VEG",
                            detected=True,
                            confidence=round(conf, 2),
                            confidence_tier=vision_config.get_confidence_tier(conf),
                            bbox=bbox,
                            normalized_bbox=norm_box,
                            color_scheme="BROWN_RED",
                            detection_method="NESTED_CONTOUR_HSV_COLOR",
                            notes="Brown/Red square enclosing symbol (Non-Vegetarian statutory symbol)",
                            evidence_id="ev_sym_nonveg_01"
                        )
        except Exception:
            pass
        return None

    @classmethod
    def _detect_fssai_mark(
        cls,
        img_bgr: np.ndarray,
        words: List[Dict[str, Any]] = None
    ) -> Optional[SymbolDetectionResult]:
        """Detect FSSAI visual emblem or logo proximity to licence token."""
        if not words:
            return None
        h, w = img_bgr.shape[:2]
        for wd in words:
            text = str(wd.get('text', '')).lower()
            if "fssai" in text or "fssai" in re.sub(r'[^a-z]', '', text):
                bbox = wd.get('bbox', [0, 0, 0, 0])
                if len(bbox) == 4:
                    # Enlarge bbox slightly to capture emblem if adjacent
                    pad_box = [
                        max(0, bbox[0] - 15),
                        max(0, bbox[1] - 10),
                        min(w, bbox[2] + 45),
                        min(h, bbox[3] + 15)
                    ]
                    conf = 0.90
                    return SymbolDetectionResult(
                        symbol_type="FSSAI_LOGO",
                        detected=True,
                        confidence=conf,
                        confidence_tier=vision_config.get_confidence_tier(conf),
                        bbox=pad_box,
                        normalized_bbox=normalize_bbox(pad_box, w, h),
                        color_scheme="MONOCHROME_COLOR",
                        detection_method="OCR_PROXIMITY_LOCALIZATION",
                        notes="Visual FSSAI statutory mark zone localized. (Registry validation executed independently)",
                        evidence_id="ev_sym_fssai_01"
                    )
        return None

symbol_detector = SymbolDetector()
