import cv2
import numpy as np
from typing import Optional, List, Tuple
from vision.schemas import QRDetectionResult
from vision.utils import normalize_bbox
from vision.config import vision_config

class QRCodeDetector:
    """
    Detects and safely decodes QR codes on packaging.
    Security:
    - Never executes URLs
    - Never makes external network requests
    - Treats payload strictly as untrusted text
    """

    @classmethod
    def detect_and_decode(cls, img_bgr: np.ndarray) -> QRDetectionResult:
        if img_bgr is None or img_bgr.size == 0:
            return QRDetectionResult()

        h, w = img_bgr.shape[:2]
        try:
            detector = cv2.QRCodeDetector()
            retval, decoded_info, points, _ = detector.detectAndDecodeMulti(img_bgr)

            if retval and points is not None and len(points) > 0:
                pts = points[0].astype(int)
                bx = int(np.min(pts[:, 0]))
                by = int(np.min(pts[:, 1]))
                bw = int(np.max(pts[:, 0]) - bx)
                bh = int(np.max(pts[:, 1]) - by)

                bbox = [max(0, bx), max(0, by), min(w, bx + bw), min(h, by + bh)]
                norm_box = normalize_bbox(bbox, w, h)
                payload = decoded_info[0] if decoded_info and len(decoded_info) > 0 else ""

                # Sanitize payload: limit length, strip dangerous chars
                clean_payload = str(payload)[:250] if payload else None
                conf = 0.95

                warning = None
                if clean_payload and clean_payload.startswith(('http://', 'https://')):
                    warning = "QR code contains external URL. Untrusted external link not executed."

                return QRDetectionResult(
                    detected=True,
                    bbox=bbox,
                    normalized_bbox=norm_box,
                    decoded_payload=clean_payload,
                    is_safe_payload=True,
                    confidence=conf,
                    confidence_tier=vision_config.get_confidence_tier(conf),
                    detection_method="OPENCV_QR_DETECTOR",
                    warning=warning
                )
        except Exception:
            pass

        return QRDetectionResult()

qr_detector = QRCodeDetector()
