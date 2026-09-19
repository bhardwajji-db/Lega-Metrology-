import cv2
import numpy as np
import pytest
from vision.geometry import geometric_analyzer
from vision.package_detector import package_boundary_detector
from vision.panel_detector import panel_detector

def test_package_boundary_detection_rectangular():
    # White package box on dark background
    img = np.ones((800, 800, 3), dtype=np.uint8) * 30
    # Draw package rect from (150, 100) to (650, 700)
    cv2.rectangle(img, (150, 100), (650, 700), (220, 220, 220), -1)
    # Add some inner texture
    cv2.putText(img, "BRAND HEADER", (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)

    res = package_boundary_detector.detect(img)
    assert res.detected is True
    assert res.bbox is not None
    x1, y1, x2, y2 = res.bbox
    assert abs(x1 - 150) < 40
    assert abs(y1 - 100) < 40
    assert abs(x2 - 650) < 40
    assert abs(y2 - 700) < 40
    assert res.confidence > 0.60

def test_perspective_analyzer_on_trapezoid():
    # Create trapezoidal distorted package
    img = np.zeros((800, 800, 3), dtype=np.uint8)
    pts = np.array([[200, 150], [600, 120], [700, 680], [100, 700]], dtype=np.int32)
    cv2.fillPoly(img, [pts], (200, 200, 200))

    res, warped = geometric_analyzer.analyze_perspective(img)
    assert res.detected is True
    assert res.is_perspective_skewed is True
    assert res.quadrilateral is not None
    assert len(res.quadrilateral) == 4
    assert res.transform_matrix is not None
    assert warped is not None

def test_panel_classifier_front_vs_back():
    front_text = "ALPINO PEANUT BUTTER CRUNCHY 1KG HIGH PROTEIN DELICIOUS"
    front_words = [
        {"text": "ALPINO", "bbox": [100, 100, 400, 250], "confidence": 0.98},
        {"text": "PEANUT", "bbox": [100, 260, 350, 340], "confidence": 0.95},
        {"text": "BUTTER", "bbox": [100, 350, 350, 430], "confidence": 0.95},
    ]
    res_front = panel_detector.detect_and_classify(
        img_bgr=np.ones((600, 500, 3), dtype=np.uint8) * 200,
        ocr_text=front_text,
        words=front_words
    )
    assert res_front.primary_panel == "front_candidate"
    assert res_front.confidence > 0.50

    back_text = "INGREDIENTS: ROASTED PEANUTS. NUTRITION INFORMATION PER 100G: ENERGY 580KCAL, PROTEIN 30G. MANUFACTURED BY ALPINO HEALTH FOODS PVT LTD, SURAT GUJARAT. CONSUMER CARE HELPLINE 1800-123-456."
    back_words = [{"text": w, "bbox": [50, i*20, 400, i*20+18], "confidence": 0.92} for i, w in enumerate(back_text.split())]
    res_back = panel_detector.detect_and_classify(
        img_bgr=np.ones((800, 600, 3), dtype=np.uint8) * 200,
        ocr_text=back_text,
        words=back_words,
        has_nutrition_table=True
    )
    assert res_back.primary_panel == "back_candidate"
    assert res_back.confidence > 0.60
