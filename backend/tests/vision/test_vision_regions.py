import cv2
import numpy as np
import pytest
from vision.region_detector import semantic_region_detector

def test_mrp_region_detected():
    img = np.ones((600, 600, 3), dtype=np.uint8) * 255
    words = [
        {"text": "MRP", "bbox": [100, 450, 160, 480], "confidence": 0.95},
        {"text": "Rs.", "bbox": [170, 450, 210, 480], "confidence": 0.95},
        {"text": "499.00", "bbox": [220, 450, 300, 480], "confidence": 0.96},
        {"text": "(INCL.", "bbox": [100, 490, 160, 515], "confidence": 0.92},
        {"text": "OF", "bbox": [170, 490, 195, 515], "confidence": 0.92},
        {"text": "ALL", "bbox": [205, 490, 240, 515], "confidence": 0.92},
        {"text": "TAXES)", "bbox": [250, 490, 310, 515], "confidence": 0.92}
    ]

    regions = semantic_region_detector.detect_all_regions(img, words)
    mrp_reg = next((r for r in regions if r.region_type == "mrp"), None)
    assert mrp_reg is not None
    assert mrp_reg.detected is True
    assert mrp_reg.bbox is not None
    assert mrp_reg.confidence > 0.70

def test_net_quantity_region_detected():
    img = np.ones((600, 600, 3), dtype=np.uint8) * 255
    words = [
        {"text": "NET", "bbox": [100, 300, 150, 330], "confidence": 0.95},
        {"text": "QUANTITY:", "bbox": [160, 300, 280, 330], "confidence": 0.95},
        {"text": "1000", "bbox": [290, 300, 340, 330], "confidence": 0.96},
        {"text": "g", "bbox": [350, 300, 370, 330], "confidence": 0.96}
    ]

    regions = semantic_region_detector.detect_all_regions(img, words)
    net_reg = next((r for r in regions if r.region_type == "net_quantity"), None)
    assert net_reg is not None
    assert net_reg.detected is True
    assert net_reg.confidence > 0.70

def test_manufacturer_and_consumer_care_regions():
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    words = [
        {"text": "MANUFACTURED", "bbox": [50, 100, 180, 125], "confidence": 0.95},
        {"text": "BY:", "bbox": [190, 100, 220, 125], "confidence": 0.95},
        {"text": "ALPINO", "bbox": [50, 130, 120, 150], "confidence": 0.92},
        {"text": "FOODS", "bbox": [130, 130, 190, 150], "confidence": 0.92},
        {"text": "CONSUMER", "bbox": [50, 300, 150, 325], "confidence": 0.94},
        {"text": "CARE", "bbox": [160, 300, 210, 325], "confidence": 0.94},
        {"text": "HELPLINE:", "bbox": [220, 300, 310, 325], "confidence": 0.94},
        {"text": "1800123456", "bbox": [50, 335, 170, 355], "confidence": 0.91}
    ]

    regions = semantic_region_detector.detect_all_regions(img, words)
    mfg_reg = next((r for r in regions if r.region_type == "manufacturer"), None)
    cc_reg = next((r for r in regions if r.region_type == "consumer_care"), None)

    assert mfg_reg is not None
    assert cc_reg is not None
    assert mfg_reg.detected is True
    assert cc_reg.detected is True

def test_nutrition_table_grid_detection():
    # Draw a synthetic table with horizontal & vertical lines
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    # Table rect from (50, 100) to (550, 400)
    cv2.rectangle(img, (50, 100), (550, 400), (0, 0, 0), 2)
    # Horizontal grid lines
    for y in range(150, 400, 50):
        cv2.line(img, (50, y), (550, y), (0, 0, 0), 1)
    # Vertical divider
    cv2.line(img, (300, 100), (300, 400), (0, 0, 0), 1)

    words = [
        {"text": "NUTRITIONAL", "bbox": [60, 110, 200, 140], "confidence": 0.96},
        {"text": "INFORMATION", "bbox": [210, 110, 350, 140], "confidence": 0.96},
        {"text": "ENERGY", "bbox": [60, 160, 140, 190], "confidence": 0.94},
        {"text": "580 kcal", "bbox": [320, 160, 400, 190], "confidence": 0.94},
        {"text": "PROTEIN", "bbox": [60, 210, 150, 240], "confidence": 0.94},
        {"text": "30 g", "bbox": [320, 210, 370, 240], "confidence": 0.94}
    ]

    regions = semantic_region_detector.detect_all_regions(img, words)
    nutr_reg = next((r for r in regions if r.region_type == "nutrition_table"), None)
    assert nutr_reg is not None
    assert nutr_reg.is_table_structure is True
    assert nutr_reg.confidence > 0.80
