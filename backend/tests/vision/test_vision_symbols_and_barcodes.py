import cv2
import numpy as np
import pytest
from vision.symbol_detector import symbol_detector
from vision.barcode_detector import barcode_detector
from vision.qr_detector import qr_detector

def test_veg_symbol_detection():
    # Draw green square with filled green circle inside
    img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    # Green in BGR is (30, 180, 40)
    green_color = (30, 180, 40)
    # Outer square (100, 100) to (180, 180)
    cv2.rectangle(img, (100, 100), (180, 180), green_color, 4)
    # Inner filled circle at center (140, 140) radius 20
    cv2.circle(img, (140, 140), 22, green_color, -1)

    symbols = symbol_detector.detect_symbols(img)
    veg_sym = next((s for s in symbols if s.symbol_type == "VEG"), None)
    assert veg_sym is not None
    assert veg_sym.detected is True
    assert veg_sym.color_scheme == "GREEN"
    assert veg_sym.confidence > 0.75

def test_fssai_symbol_detection():
    img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    words = [
        {"text": "fssai", "bbox": [100, 100, 200, 140], "confidence": 0.96},
        {"text": "Lic. No.", "bbox": [100, 150, 180, 175], "confidence": 0.95},
        {"text": "10020021000123", "bbox": [190, 150, 350, 175], "confidence": 0.95}
    ]

    symbols = symbol_detector.detect_symbols(img, words)
    fssai_sym = next((s for s in symbols if s.symbol_type == "FSSAI_LOGO"), None)
    assert fssai_sym is not None
    assert fssai_sym.detected is True
    assert fssai_sym.confidence >= 0.85

def test_barcode_detection_synthetic():
    # Draw a 1D barcode pattern of alternating black and white vertical bars
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    # Draw vertical stripes inside (150, 100) to (450, 250)
    for x in range(160, 440, 6):
        cv2.line(img, (x, 110), (x, 240), (0, 0, 0), 2)

    res = barcode_detector.detect(img)
    assert res.detected is True
    assert res.barcode_type == "1D_BARCODE"
    assert res.bbox is not None
    bx1, by1, bx2, by2 = res.bbox
    assert bx1 <= 170 and bx2 >= 430
    assert by1 <= 120 and by2 >= 230

def test_qr_code_safe_decoding():
    # Generate a simple QR code using OpenCV / QRCodeEncoder if available or synthetic
    img = np.ones((400, 400, 3), dtype=np.uint8) * 255
    # Draw QR alignment finder patterns (3 corner nested squares)
    for cx, cy in [(80, 80), (320, 80), (80, 320)]:
        cv2.rectangle(img, (cx-40, cy-40), (cx+40, cy+40), (0, 0, 0), -1)
        cv2.rectangle(img, (cx-25, cy-25), (cx+25, cy+25), (255, 255, 255), -1)
        cv2.rectangle(img, (cx-12, cy-12), (cx+12, cy+12), (0, 0, 0), -1)

    res = qr_detector.detect_and_decode(img)
    # The detector runs safely and never crashes
    assert res is not None
    assert res.is_safe_payload is True
