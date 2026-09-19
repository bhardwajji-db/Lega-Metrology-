# -*- coding: utf-8 -*-
import numpy as np
import pytest
from vision.region_detector import semantic_region_detector

def test_multilingual_semantic_regions_10_languages():
    img = np.ones((800, 800, 3), dtype=np.uint8) * 255
    
    # 1. Hindi
    hindi_words = [
        {"text": "अधिकतम", "bbox": [50, 50, 120, 80], "confidence": 0.95},
        {"text": "खुदरा", "bbox": [130, 50, 180, 80], "confidence": 0.95},
        {"text": "मूल्य", "bbox": [190, 50, 240, 80], "confidence": 0.95},
        {"text": "₹250", "bbox": [250, 50, 300, 80], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, hindi_words)
    assert any(r.region_type == "mrp" for r in regions)

    # 2. Bengali
    bengali_words = [
        {"text": "নিট", "bbox": [50, 100, 100, 130], "confidence": 0.95},
        {"text": "পরিমাণ", "bbox": [110, 100, 180, 130], "confidence": 0.95},
        {"text": "500g", "bbox": [190, 100, 240, 130], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, bengali_words)
    assert any(r.region_type == "net_quantity" for r in regions)

    # 3. Marathi
    marathi_words = [
        {"text": "उत्पादक", "bbox": [50, 150, 120, 180], "confidence": 0.95},
        {"text": "कंपनी", "bbox": [130, 150, 180, 180], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, marathi_words)
    assert any(r.region_type == "manufacturer" for r in regions)

    # 4. Gujarati
    gujarati_words = [
        {"text": "ગ્રાહક", "bbox": [50, 200, 120, 230], "confidence": 0.95},
        {"text": "સેવા", "bbox": [130, 200, 180, 230], "confidence": 0.95},
        {"text": "1800000000", "bbox": [190, 200, 300, 230], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, gujarati_words)
    assert any(r.region_type == "consumer_care" for r in regions)

    # 5. Punjabi
    punjabi_words = [
        {"text": "ਸਮੱਗਰੀ", "bbox": [50, 250, 120, 280], "confidence": 0.95},
        {"text": "ਕਣਕ", "bbox": [130, 250, 180, 280], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, punjabi_words)
    assert any(r.region_type == "ingredients" for r in regions)

    # 6. Tamil
    tamil_words = [
        {"text": "அதிகபட்ச", "bbox": [50, 300, 130, 330], "confidence": 0.95},
        {"text": "சில்லறை", "bbox": [140, 300, 220, 330], "confidence": 0.95},
        {"text": "விலை", "bbox": [230, 300, 280, 330], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, tamil_words)
    assert any(r.region_type == "mrp" for r in regions)

    # 7. Telugu
    telugu_words = [
        {"text": "నికర", "bbox": [50, 350, 100, 380], "confidence": 0.95},
        {"text": "పరిమాణం", "bbox": [110, 350, 200, 380], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, telugu_words)
    assert any(r.region_type == "net_quantity" for r in regions)

    # 8. Kannada
    kannada_words = [
        {"text": "ತಯಾರಕರು", "bbox": [50, 400, 150, 430], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, kannada_words)
    assert any(r.region_type == "manufacturer" for r in regions)

    # 9. Malayalam
    malayalam_words = [
        {"text": "ചേരുവകൾ", "bbox": [50, 450, 150, 480], "confidence": 0.95}
    ]
    regions = semantic_region_detector.detect_all_regions(img, malayalam_words)
    assert any(r.region_type == "ingredients" for r in regions)
