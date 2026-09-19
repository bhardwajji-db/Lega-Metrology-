import numpy as np
import pytest
from vision.pipeline import vision_pipeline
from vision.schemas import VisionAnalysisResult

def test_full_vision_pipeline_execution():
    img = np.ones((800, 600, 3), dtype=np.uint8) * 220
    # Add dummy text tokens
    ocr_words = [
        {"text": "ALPINO", "bbox": [50, 50, 150, 80], "confidence": 0.96},
        {"text": "PEANUT", "bbox": [160, 50, 260, 80], "confidence": 0.95},
        {"text": "BUTTER", "bbox": [270, 50, 360, 80], "confidence": 0.95},
        {"text": "NET", "bbox": [50, 120, 100, 145], "confidence": 0.92},
        {"text": "QUANTITY:", "bbox": [110, 120, 200, 145], "confidence": 0.92},
        {"text": "1kg", "bbox": [210, 120, 250, 145], "confidence": 0.93},
        {"text": "MRP:", "bbox": [50, 160, 100, 185], "confidence": 0.95},
        {"text": "Rs.", "bbox": [110, 160, 140, 185], "confidence": 0.95},
        {"text": "499", "bbox": [150, 160, 190, 185], "confidence": 0.95},
        {"text": "MANUFACTURED", "bbox": [50, 220, 180, 245], "confidence": 0.90},
        {"text": "BY:", "bbox": [190, 220, 220, 245], "confidence": 0.90},
        {"text": "ALPINO", "bbox": [50, 250, 130, 270], "confidence": 0.91},
        {"text": "CONSUMER", "bbox": [50, 320, 150, 345], "confidence": 0.94},
        {"text": "CARE:", "bbox": [160, 320, 210, 345], "confidence": 0.94},
        {"text": "1800-111-222", "bbox": [220, 320, 340, 345], "confidence": 0.93}
    ]

    result = vision_pipeline.analyze_image(img, ocr_words=ocr_words)

    assert isinstance(result, VisionAnalysisResult)
    assert result.quality is not None
    assert result.geometry is not None
    assert result.package_boundary is not None
    assert result.panel_classification is not None
    assert result.text_regions is not None
    assert len(result.semantic_regions) > 0
    assert result.symbols is not None
    assert result.barcode is not None
    assert result.qr_code is not None
    assert result.timing is not None
    assert result.timing.total_vision_ms >= 0
    assert len(result.evidence_items) > 0

def test_pipeline_fail_safe_on_empty_image():
    empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
    result = vision_pipeline.analyze_image(empty_img, ocr_words=[])
    assert isinstance(result, VisionAnalysisResult)
    assert result.quality.is_acceptable is False
    assert result.quality.decision == "REJECT"

def test_pipeline_evidence_generation():
    img = np.ones((500, 500, 3), dtype=np.uint8) * 240
    words = [
        {"text": "MRP", "bbox": [100, 100, 150, 120], "confidence": 0.95},
        {"text": "500", "bbox": [160, 100, 200, 120], "confidence": 0.95}
    ]
    result = vision_pipeline.analyze_image(img, ocr_words=words)
    assert len(result.evidence_items) > 0
    field_types = [item.field_type for item in result.evidence_items]
    assert "REGION" in field_types
