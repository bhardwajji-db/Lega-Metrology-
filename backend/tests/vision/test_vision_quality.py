import cv2
import numpy as np
import pytest
from vision.quality import quality_gate
from vision.schemas import ImageQualityResult

def test_clean_image_quality_pass():
    # Synthetic clean image: high contrast text on uniform background
    img = np.ones((600, 800, 3), dtype=np.uint8) * 240
    # Add sharp high-contrast text lines
    for y in range(80, 500, 40):
        cv2.putText(img, f"MetrCheck AI Statutory Inspection Line {y}", (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    
    result = quality_gate.analyze(img)
    assert isinstance(result, ImageQualityResult)
    assert result.decision in ("PASS", "WARN")
    assert result.is_acceptable is True
    assert result.metrics.blur_score > 50.0
    assert result.metrics.width == 800
    assert result.metrics.height == 600

def test_severely_blurred_image_detected():
    # Synthetic blurred image
    img = np.ones((600, 800, 3), dtype=np.uint8) * 200
    cv2.putText(img, "Faint blurred text", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (50, 50, 50), 2)
    blurred = cv2.GaussianBlur(img, (31, 31), 10.0)

    result = quality_gate.analyze(blurred)
    assert result.metrics.blur_score < 70.0
    blur_issues = [i for i in result.issues if i.category == "BLUR"]
    assert len(blur_issues) > 0

def test_underexposed_dark_image_detected():
    # Very dark image
    dark_img = np.ones((500, 500, 3), dtype=np.uint8) * 25
    result = quality_gate.analyze(dark_img)
    assert result.metrics.brightness < 40.0
    assert any(i.category == "UNDEREXPOSURE" for i in result.issues)

def test_overexposed_bright_image_detected():
    # Bleached white image
    bright_img = np.ones((500, 500, 3), dtype=np.uint8) * 248
    result = quality_gate.analyze(bright_img)
    assert result.metrics.brightness > 230.0
    assert any(i.category == "OVEREXPOSURE" for i in result.issues)

def test_glare_hotspot_localized_with_bbox():
    # Image with intense localized specular reflection
    img = np.ones((600, 600, 3), dtype=np.uint8) * 120
    # Add bright glare spot in center
    cv2.circle(img, (300, 300), 50, (255, 255, 255), -1)

    result = quality_gate.analyze(img)
    assert result.metrics.glare_detected is True
    assert len(result.metrics.glare_regions) > 0
    # Check bbox covers the hotspot
    bbox = result.metrics.glare_regions[0]
    assert bbox[0] <= 260 and bbox[2] >= 340
    assert bbox[1] <= 260 and bbox[3] >= 340

def test_empty_or_corrupt_image_failsafe():
    empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
    result = quality_gate.analyze(empty_img)
    assert result.decision == "REJECT"
    assert result.is_acceptable is False
