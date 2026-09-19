import cv2
import numpy as np
from typing import Dict, Any, List, Tuple
from PIL import Image
from vision.schemas import ImageQualityResult, ImageQualityMetrics, ImageQualityIssue
from vision.config import vision_config

class ImageQualityGate:
    """
    Evaluates packaging image quality before OCR and extraction.
    Analyzes:
    - Blur & sharpness (Laplacian variance, gradient energy)
    - Motion blur (directional gradient imbalance)
    - Luminance, low-light, underexposure, overexposure
    - Glare & reflection hotspots with bounding boxes
    - Image skew angle (Hough lines & contour orientation)
    - Small text readability risk
    Produces an aggregate quality score (0..100) and gate decision (PASS, WARN, REJECT).
    """

    @classmethod
    def analyze(cls, img_bgr: np.ndarray) -> ImageQualityResult:
        if img_bgr is None or img_bgr.size == 0:
            return ImageQualityResult(
                overall_score=0.0,
                decision="REJECT",
                is_acceptable=False,
                summary="Image is unreadable or empty.",
                issues=[ImageQualityIssue(
                    category="FILE_INTEGRITY",
                    severity="SEVERE",
                    message="Image buffer is empty or corrupted."
                )]
            )

        h, w = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        metrics = ImageQualityMetrics(
            width=w,
            height=h,
            resolution=f"{w}x{h}"
        )
        issues: List[ImageQualityIssue] = []

        # ── 1. Resolution Check ──
        if w < vision_config.MIN_RESOLUTION_WIDTH or h < vision_config.MIN_RESOLUTION_HEIGHT:
            issues.append(ImageQualityIssue(
                category="RESOLUTION",
                severity="WARNING",
                message=f"Low resolution ({w}x{h}). Fine statutory print may be degraded.",
                metric_value=float(min(w, h))
            ))

        # ── 2. Blur & Sharpness Analysis ──
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobelx**2 + sobely**2)
        sharpness_score = float(np.mean(grad_mag))

        metrics.blur_score = round(laplacian_var, 2)
        metrics.sharpness_score = round(sharpness_score, 2)

        if laplacian_var < vision_config.BLUR_LAPLACIAN_SEVERELY_DEGRADED:
            issues.append(ImageQualityIssue(
                category="BLUR",
                severity="SEVERE",
                message=f"Severe camera blur detected (Laplacian: {laplacian_var:.1f}). Text readability critically impaired.",
                metric_value=laplacian_var
            ))
        elif laplacian_var < vision_config.BLUR_LAPLACIAN_DEGRADED:
            issues.append(ImageQualityIssue(
                category="BLUR",
                severity="WARNING",
                message=f"Moderate camera blur detected (Laplacian: {laplacian_var:.1f}). Fine print might be softened.",
                metric_value=laplacian_var
            ))

        # ── 3. Motion Blur Detection (Directional Gradient Imbalance) ──
        var_x = float(np.var(sobelx))
        var_y = float(np.var(sobely))
        motion_ratio = max(var_x, var_y) / max(min(var_x, var_y), 1e-4)
        metrics.motion_blur_ratio = round(motion_ratio, 2)

        if motion_ratio > vision_config.MOTION_BLUR_GRADIENT_RATIO_THRESHOLD and laplacian_var < 150.0:
            metrics.motion_blur_detected = True
            direction = "Horizontal" if var_x > var_y else "Vertical"
            issues.append(ImageQualityIssue(
                category="MOTION_BLUR",
                severity="WARNING",
                message=f"Directional motion blur suspected ({direction}, ratio: {motion_ratio:.2f}).",
                metric_value=motion_ratio
            ))

        # ── 4. Luminance, Exposure & Contrast ──
        mean_lum = float(np.mean(gray))
        contrast = float(np.std(gray))
        dark_pixels = float(np.sum(gray < 30)) / float(gray.size)
        bright_pixels = float(np.sum(gray > 235)) / float(gray.size)
        clipping_ratio = dark_pixels + bright_pixels

        metrics.brightness = round(mean_lum, 2)
        metrics.contrast = round(contrast, 2)
        metrics.dark_pixel_ratio = round(dark_pixels, 4)
        metrics.bright_pixel_ratio = round(bright_pixels, 4)
        metrics.clipping_ratio = round(clipping_ratio, 4)

        if mean_lum < vision_config.LUMINANCE_UNDEREXPOSURE_THRESHOLD or dark_pixels > 0.45:
            issues.append(ImageQualityIssue(
                category="UNDEREXPOSURE",
                severity="WARNING",
                message=f"Image is significantly underexposed / dark (mean: {mean_lum:.1f}).",
                metric_value=mean_lum
            ))
        elif mean_lum > vision_config.LUMINANCE_SEVERE_OVEREXPOSURE or bright_pixels > 0.50:
            issues.append(ImageQualityIssue(
                category="OVEREXPOSURE",
                severity="SEVERE",
                message=f"Severe overexposure / bleached lighting (mean: {mean_lum:.1f}).",
                metric_value=mean_lum
            ))
        elif mean_lum > vision_config.LUMINANCE_OVEREXPOSURE_THRESHOLD:
            issues.append(ImageQualityIssue(
                category="OVEREXPOSURE",
                severity="WARNING",
                message=f"High brightness / potential overexposure (mean: {mean_lum:.1f}).",
                metric_value=mean_lum
            ))

        if contrast < 22.0:
            issues.append(ImageQualityIssue(
                category="LOW_CONTRAST",
                severity="WARNING",
                message=f"Very low contrast ({contrast:.1f}) between text and packaging substrate.",
                metric_value=contrast
            ))

        # ── 5. Glare & Specular Reflection Hotspots ──
        glare_mask = (gray >= vision_config.GLARE_PIXEL_INTENSITY_MIN).astype(np.uint8) * 255
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(glare_mask)
        glare_boxes: List[List[int]] = []
        total_glare_area = 0

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= vision_config.GLARE_CONCENTRATION_AREA_MIN:
                gx = int(stats[i, cv2.CC_STAT_LEFT])
                gy = int(stats[i, cv2.CC_STAT_TOP])
                gw = int(stats[i, cv2.CC_STAT_WIDTH])
                gh = int(stats[i, cv2.CC_STAT_HEIGHT])
                glare_boxes.append([gx, gy, gx + gw, gy + gh])
                total_glare_area += area

        glare_ratio = float(total_glare_area) / float(gray.size)
        metrics.glare_severity = round(glare_ratio, 4)
        metrics.glare_regions = glare_boxes[:5]  # top 5 regions

        if glare_ratio > vision_config.GLARE_SEVERITY_RATIO_THRESHOLD or len(glare_boxes) > 0:
            metrics.glare_detected = True
            severity_level = "SEVERE" if glare_ratio > 0.10 else "WARNING"
            issues.append(ImageQualityIssue(
                category="GLARE",
                severity=severity_level,
                message=f"Specular reflection/glare detected across {len(glare_boxes)} localized packaging zones.",
                metric_value=glare_ratio,
                bbox=glare_boxes[0] if glare_boxes else None
            ))

        # ── 6. Skew Angle Detection ──
        skew_angle, rec_rot = cls._estimate_skew_angle(gray)
        metrics.skew_angle_deg = round(skew_angle, 2)
        metrics.recommended_rotation = rec_rot

        if abs(skew_angle) > vision_config.SKEW_ANGLE_TOLERANCE_DEG:
            issues.append(ImageQualityIssue(
                category="SKEW",
                severity="INFO",
                message=f"Packaging orientation skew detected ({skew_angle:+.1f}°). Angle normalization recommended.",
                metric_value=skew_angle
            ))

        # ── 7. Aggregate Quality Score & Decision ──
        score = 100.0
        # Deductions
        if laplacian_var < vision_config.BLUR_LAPLACIAN_SEVERELY_DEGRADED:
            score -= 40.0
        elif laplacian_var < vision_config.BLUR_LAPLACIAN_DEGRADED:
            score -= 20.0
        elif laplacian_var < vision_config.BLUR_LAPLACIAN_ACCEPTABLE:
            score -= 10.0

        if mean_lum < 35.0 or mean_lum > 240.0:
            score -= 25.0
        elif mean_lum < 50.0 or mean_lum > 220.0:
            score -= 15.0

        if contrast < 25.0:
            score -= 15.0

        if metrics.glare_detected:
            score -= min(25.0, glare_ratio * 200.0)

        if metrics.motion_blur_detected:
            score -= 10.0

        if w < 500 or h < 500:
            score -= 10.0

        score = max(0.0, min(100.0, round(score, 1)))

        severe_issues = [iss for iss in issues if iss.severity == "SEVERE"]
        warning_issues = [iss for iss in issues if iss.severity == "WARNING"]

        if score < 40.0 or len(severe_issues) >= 2:
            decision = "REJECT"
            is_acceptable = False
            summary = "Image quality is severely degraded. Recommended to recapture under better lighting and focus."
        elif score < 75.0 or len(warning_issues) > 0 or len(severe_issues) == 1:
            decision = "WARN"
            is_acceptable = True
            summary = "Image quality is acceptable but degraded by lighting, blur, or glare."
        else:
            decision = "PASS"
            is_acceptable = True
            summary = "Image quality is good and suitable for statutory packaging verification."

        return ImageQualityResult(
            overall_score=score,
            decision=decision,
            is_acceptable=is_acceptable,
            metrics=metrics,
            issues=issues,
            summary=summary
        )

    @classmethod
    def _estimate_skew_angle(cls, gray: np.ndarray) -> Tuple[float, int]:
        """Estimate dominant text/edge skew using Hough Line Transform."""
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=50, maxLineGap=10)

            if lines is None or len(lines) == 0:
                return 0.0, 0

            angles = []
            for line in lines[:50]:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 == 0:
                    continue
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                # Only keep near-horizontal lines (-45 to +45 deg)
                if abs(angle) < 45.0:
                    angles.append(angle)

            if not angles:
                return 0.0, 0

            median_angle = float(np.median(angles))
            rec_rot = 0
            if abs(median_angle) > 40.0:
                rec_rot = 90 if median_angle > 0 else -90

            return median_angle, rec_rot
        except Exception:
            return 0.0, 0

quality_gate = ImageQualityGate()
