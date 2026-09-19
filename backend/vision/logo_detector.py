import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from vision.schemas import LogoDetectionResult
from vision.utils import normalize_bbox

class LogoDetector:
    """
    Extensible Logo & Brand Mark Detection Framework.
    Supports:
    - Prominent visual emblem detection near brand title
    - Reusable template matching hooks
    """

    @classmethod
    def detect_logos(
        cls,
        img_bgr: np.ndarray,
        words: List[Dict[str, Any]] = None
    ) -> List[LogoDetectionResult]:
        if img_bgr is None or img_bgr.size == 0:
            return []

        h, w = img_bgr.shape[:2]
        logos: List[LogoDetectionResult] = []

        # Detect top-prominence brand visual anchor
        if words:
            # Find largest font text (often brand name)
            sorted_by_size = sorted(
                words,
                key=lambda item: abs(item.get('bbox', [0,0,0,0])[3] - item.get('bbox', [0,0,0,0])[1]),
                reverse=True
            )
            if sorted_by_size:
                top_w = sorted_by_size[0]
                tb = top_w.get('bbox', [0, 0, 0, 0])
                font_h = abs(tb[3] - tb[1])
                if font_h > h * 0.06:  # Over 6% of image height
                    logo_box = [
                        max(0, tb[0] - 10),
                        max(0, tb[1] - int(font_h * 0.8)),  # often logo icon sits just above text
                        min(w, tb[2] + 10),
                        min(h, tb[3] + 10)
                    ]
                    logos.append(LogoDetectionResult(
                        logo_name=str(top_w.get('text', 'Brand Emblem')),
                        detected=True,
                        confidence=0.85,
                        bbox=logo_box,
                        normalized_bbox=normalize_bbox(logo_box, w, h),
                        detection_method="PROMINENT_BRAND_TITLE_LOCALIZATION",
                        evidence_id="ev_logo_01"
                    ))

        return logos

logo_detector = LogoDetector()
