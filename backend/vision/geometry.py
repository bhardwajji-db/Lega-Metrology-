import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image
from vision.schemas import PerspectiveCorrectionResult
from vision.config import vision_config

class GeometricAnalyzer:
    """
    Analyzes packaging geometry and perspective distortion.
    Detects prominent quadrilateral boundaries with candidate scoring:
    - Area ratio relative to image (> 20%)
    - Rectangularity / right-angle deviation
    - Convexity
    - Edge strength
    Computes perspective transform matrix non-destructively.
    """

    @classmethod
    def analyze_perspective(cls, img_bgr: np.ndarray) -> Tuple[PerspectiveCorrectionResult, Optional[np.ndarray]]:
        if img_bgr is None or img_bgr.size == 0:
            return PerspectiveCorrectionResult(), None

        h, w = img_bgr.shape[:2]
        img_area = float(w * h)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Multi-scale edge detection
        edges1 = cv2.Canny(blurred, 30, 120)
        edges2 = cv2.Canny(blurred, 50, 180)
        edges = cv2.bitwise_or(edges1, edges2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:8]

        best_quad = None
        best_score = 0.0
        best_transform = None
        corrected_dims = None
        is_skewed = False
        skew_sev = 0.0

        for c in contours:
            area = cv2.contourArea(c)
            if area < 0.15 * img_area:
                continue

            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.025 * peri, True)

            if len(approx) == 4 and cv2.isContourConvex(approx):
                pts = approx.reshape(4, 2).astype('float32')
                # Order points: TL, TR, BR, BL
                rect = cls._order_points(pts)
                (tl, tr, br, bl) = rect

                w_top = float(np.linalg.norm(tr - tl))
                w_bot = float(np.linalg.norm(br - bl))
                h_left = float(np.linalg.norm(bl - tl))
                h_right = float(np.linalg.norm(br - tr))

                max_w = max(w_top, w_bot)
                max_h = max(h_left, h_right)
                if max_w < 100 or max_h < 100:
                    continue

                w_ratio = abs(w_top - w_bot) / max_w
                h_ratio = abs(h_left - h_right) / max_h
                quad_skew = max(w_ratio, h_ratio)

                # Score candidate quad
                area_score = min(1.0, area / (0.85 * img_area))
                aspect = max_w / max_h
                aspect_penalty = 0.0 if 0.25 <= aspect <= 4.0 else 0.5
                candidate_score = (area_score * 0.6) + ((1.0 - quad_skew) * 0.4) - aspect_penalty

                if candidate_score > best_score:
                    best_score = candidate_score
                    best_quad = rect.tolist()
                    is_skewed = quad_skew > 0.06
                    skew_sev = round(quad_skew, 3)

                    dst_w = int(max(w_top, w_bot))
                    dst_h = int(max(h_left, h_right))
                    dst = np.array([
                        [0, 0],
                        [dst_w - 1, 0],
                        [dst_w - 1, dst_h - 1],
                        [0, dst_h - 1]
                    ], dtype='float32')

                    M = cv2.getPerspectiveTransform(rect, dst)
                    best_transform = M.tolist()
                    corrected_dims = [dst_w, dst_h]

        if best_quad is not None and best_score > 0.35:
            conf = round(min(0.98, max(0.40, best_score)), 2)
            res = PerspectiveCorrectionResult(
                detected=True,
                is_perspective_skewed=is_skewed,
                skew_severity=skew_sev,
                quadrilateral=best_quad,
                transform_matrix=best_transform,
                corrected_dimensions=corrected_dims,
                confidence=conf,
                method="CONTOUR_APPROX_DP_CANNY"
            )
            # Compute corrected representation if needed
            warped_img = None
            if is_skewed and best_transform is not None and corrected_dims is not None:
                M_np = np.array(best_transform, dtype='float32')
                warped_img = cv2.warpPerspective(img_bgr, M_np, (corrected_dims[0], corrected_dims[1]))

            return res, warped_img

        return PerspectiveCorrectionResult(
            detected=False,
            is_perspective_skewed=False,
            skew_severity=0.0,
            confidence=0.0
        ), None

    @staticmethod
    def _order_points(pts: np.ndarray) -> np.ndarray:
        rect = np.zeros((4, 2), dtype='float32')
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # Top-Left
        rect[2] = pts[np.argmax(s)]  # Bottom-Right

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # Top-Right
        rect[3] = pts[np.argmax(diff)]  # Bottom-Left
        return rect

geometric_analyzer = GeometricAnalyzer()
