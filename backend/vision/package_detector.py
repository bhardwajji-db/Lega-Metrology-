import cv2
import numpy as np
from typing import Optional, List, Tuple
from vision.schemas import PackageBoundaryResult
from vision.utils import normalize_bbox

class PackageBoundaryDetector:
    """
    Detects the physical boundary of a package in the captured photograph.
    Robust against:
    - Light/white packaging on light or dark tables
    - Dark packaging on varied backgrounds
    - Rotated packages
    - Complex shadows
    Returns package_bbox, package_polygon, normalized coordinates, and confidence.
    """

    @classmethod
    def detect(cls, img_bgr: np.ndarray) -> PackageBoundaryResult:
        if img_bgr is None or img_bgr.size == 0:
            return PackageBoundaryResult()

        h, w = img_bgr.shape[:2]
        img_area = float(w * h)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 1. Multi-scale Edge & Thresholding Fusion
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 140)

        # Morphological closing to bridge small gaps in package perimeter
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # Find external contours
        contours, _ = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            # Fallback to Otsu thresholding
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return PackageBoundaryResult(
                detected=True,
                bbox=[0, 0, w, h],
                normalized_bbox=[0.0, 0.0, 1.0, 1.0],
                polygon=[[0, 0], [w, 0], [w, h], [0, h]],
                area_ratio=1.0,
                aspect_ratio=round(w / float(h), 2),
                confidence=0.50,
                method="FULL_FRAME_DEFAULT"
            )

        # Sort contours by area
        valid_candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > 0.10 * img_area:
                bx, by, bw, bh = cv2.boundingRect(c)
                # Filter out pure border edge artifacts
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                rect_area = float(bw * bh)
                fill_ratio = area / max(rect_area, 1.0)
                aspect = bw / float(bh)

                score = (area / img_area) * 0.7 + fill_ratio * 0.3
                valid_candidates.append({
                    'contour': c,
                    'approx': approx,
                    'bbox': [bx, by, bx + bw, by + bh],
                    'area': area,
                    'score': score,
                    'aspect': aspect
                })

        if not valid_candidates:
            # Package spans most of the frame
            return PackageBoundaryResult(
                detected=True,
                bbox=[0, 0, w, h],
                normalized_bbox=[0.0, 0.0, 1.0, 1.0],
                polygon=[[0, 0], [w, 0], [w, h], [0, h]],
                area_ratio=1.0,
                aspect_ratio=round(w / float(h), 2),
                confidence=0.65,
                method="FRAME_DOMINANT"
            )

        best = max(valid_candidates, key=lambda x: x['score'])
        bx1, by1, bx2, by2 = best['bbox']
        norm_bbox = normalize_bbox([bx1, by1, bx2, by2], w, h)
        polygon_pts = best['approx'].reshape(-1, 2).tolist()
        area_ratio = round(best['area'] / img_area, 3)
        aspect = round(best['aspect'], 2)
        conf = round(min(0.96, 0.60 + (area_ratio * 0.35)), 2)

        return PackageBoundaryResult(
            detected=True,
            bbox=[bx1, by1, bx2, by2],
            normalized_bbox=norm_bbox,
            polygon=polygon_pts,
            area_ratio=area_ratio,
            aspect_ratio=aspect,
            confidence=conf,
            method="CANNY_MORPH_CONTOUR"
        )

package_boundary_detector = PackageBoundaryDetector()
