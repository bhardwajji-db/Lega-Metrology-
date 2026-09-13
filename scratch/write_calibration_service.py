import os
import pathlib

code = """import cv2
import numpy as np
import logging
from typing import Optional, List, Tuple
from backend.models.schemas import CalibrationResult
from backend.config import settings

logger = logging.getLogger(__name__)

class PhysicalCalibrationService:
    \"\"\"
    Optical Calibration & Metric Scale Service for Packaged Commodities.
    
    Implements metrological verification of physical dimensions (Rule 12 font heights)
    by detecting reference calibration targets (standard 50mm ArUco fiducials / ID-1 reference scales)
    in the captured package image.
    
    Distinguishes:
    - PHYSICAL_MEASUREMENT_VERIFIED: Standard fiducial scale detected, geometry validated, px/mm computed.
    - PHYSICAL_MEASUREMENT_ESTIMATED: No fiducial scale present; estimated using estimated DPI / fallback factor.
    - CALIBRATION_INVALID: Fiducial scale detected but excessive perspective distortion / acute angle.
    - CALIBRATION_MISSING: No calibration target present in image.
    \"\"\"
    
    ARUCO_DICTS = [
        cv2.aruco.DICT_4X4_50,
        cv2.aruco.DICT_5X5_50,
        cv2.aruco.DICT_6X6_50,
        cv2.aruco.DICT_4X4_100,
        cv2.aruco.DICT_5X5_100
    ]

    @classmethod
    def detect_aruco_marker(
        cls, 
        image_path: str, 
        target_size_mm: float = 50.0
    ) -> CalibrationResult:
        if not settings.CALIBRATION_ENABLED:
            return CalibrationResult(
                status="PHYSICAL_MEASUREMENT_ESTIMATED",
                target_type="NONE",
                pixels_per_mm=None,
                message="Optical calibration disabled in system settings. Using estimated DPI metric conversion."
            )

        try:
            img = cv2.imread(image_path)
            if img is None:
                return CalibrationResult(
                    status="MEASUREMENT_UNRELIABLE",
                    target_type="NONE",
                    pixels_per_mm=None,
                    message="Unable to read image file for calibration detection."
                )

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

            detector_params = cv2.aruco.DetectorParameters()
            # Enhance corner detection robustness
            detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

            best_corners = None
            best_id = None
            used_dict_name = None

            for dict_id in cls.ARUCO_DICTS:
                dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
                detector = cv2.aruco.ArucoDetector(dictionary, detector_params)
                corners, ids, _ = detector.detectMarkers(gray)

                if corners and len(corners) > 0 and ids is not None and len(ids) > 0:
                    best_corners = corners[0][0]
                    best_id = int(ids[0][0])
                    used_dict_name = f"ARUCO_{dict_id}"
                    break

            if best_corners is None:
                return CalibrationResult(
                    status="CALIBRATION_MISSING",
                    target_type="NONE",
                    pixels_per_mm=None,
                    target_bbox=None,
                    confidence=0.0,
                    message="No physical calibration target (ArUco marker / reference scale) detected. Rule 12 heights will be estimated."
                )

            # Analyze geometric integrity of the detected marker
            c = best_corners
            s1 = float(np.linalg.norm(c[0] - c[1]))
            s2 = float(np.linalg.norm(c[1] - c[2]))
            s3 = float(np.linalg.norm(c[2] - c[3]))
            s4 = float(np.linalg.norm(c[3] - c[0]))

            avg_side_px = (s1 + s2 + s3 + s4) / 4.0
            
            # Check aspect ratio distortion (s1/s2, s3/s4)
            ratio_1 = min(s1, s2) / max(s1, s2, 1e-5)
            ratio_2 = min(s3, s4) / max(s3, s4, 1e-5)
            min_ratio = min(ratio_1, ratio_2)

            xs = [float(pt[0]) for pt in c]
            ys = [float(pt[1]) for pt in c]
            bbox = [int(round(min(xs))), int(round(min(ys))), int(round(max(xs))), int(round(max(ys)))]

            if min_ratio < 0.75:
                # Acute perspective tilt makes planar metric measurement unreliable
                return CalibrationResult(
                    status="CALIBRATION_INVALID",
                    target_type=used_dict_name,
                    pixels_per_mm=None,
                    target_bbox=bbox,
                    confidence=round(min_ratio * 100, 1),
                    message=f"ArUco marker ID {best_id} detected, but severe perspective skew/tilt detected (ratio {min_ratio:.2f} < 0.75). Physical measurement uncalibrated."
                )

            px_per_mm = round(avg_side_px / target_size_mm, 4)
            conf = round(min_ratio * 100.0, 1)

            return CalibrationResult(
                status="PHYSICAL_MEASUREMENT_VERIFIED",
                target_type=f"{used_dict_name}_ID_{best_id}",
                pixels_per_mm=px_per_mm,
                target_bbox=bbox,
                confidence=conf,
                message=f"Optical calibration verified via ArUco reference target (ID {best_id}, {target_size_mm}mm, {px_per_mm:.2f} px/mm)."
            )

        except Exception as e:
            logger.warning(f"Error during optical calibration detection: {e}")
            return CalibrationResult(
                status="MEASUREMENT_UNRELIABLE",
                target_type="NONE",
                pixels_per_mm=None,
                message=f"Optical calibration detection encountered an error: {str(e)}"
            )

calibration_service = PhysicalCalibrationService()
"""

target = pathlib.Path("backend/services/calibration_service.py")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(code.strip() + "\n", encoding="utf-8")
print(f"Created {target}")
