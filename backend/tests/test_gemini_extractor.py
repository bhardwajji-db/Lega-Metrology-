"""
Unit tests for Gemini AI Extractor in MetrCheck AI
Tests extraction fallback, API payload formatting, model resolution, and safe field merging.
"""

import pytest
from unittest.mock import AsyncMock, patch
from config import settings
from models.schemas import ProductInfo, ProductImageEvidence
from extraction.llm_extractor import LLMExtractor


def test_gemini_model_resolution():
    extractor = LLMExtractor()
    with patch.object(settings, 'GEMINI_MODEL', 'gemini-2.5-flash'):
        assert extractor.get_model() == 'gemini-2.5-flash'

    with patch.object(settings, 'GEMINI_MODEL', 'gemini-3.8'):
        assert extractor.get_model() == 'gemini-2.5-flash'


def test_gemini_api_key_resolution():
    extractor = LLMExtractor()
    with patch.object(settings, 'GEMINI_API_KEY', 'test-key-123'):
        assert extractor.get_api_key() == 'test-key-123'

    with patch.object(settings, 'GEMINI_API_KEY', ''):
        with patch.object(settings, 'LLM_API_KEY', 'fallback-key-456'):
            assert extractor.get_api_key() == 'fallback-key-456'


def test_gemini_offline_safe_fallback():
    extractor = LLMExtractor()
    sample_text = "Cadbury Dairy Milk Chocolate MRP Rs 50.00 Net Qty 50g Mfd 08/2026 FSSAI 10014022002711"
    info = extractor.extract(sample_text)
    assert info is not None
    assert info.mrp is not None
    assert "50" in info.mrp
    assert info.extraction_mode == 'local'


@pytest.mark.asyncio
async def test_gemini_mock_api_enrichment():
    extractor = LLMExtractor()
    mock_gemini_response = {
        "product_name": "Cadbury Dairy Milk Silk",
        "brand": "Cadbury",
        "category": "Confectionery",
        "is_food": True,
        "net_quantity": "50 g",
        "mrp": "₹50.00",
        "unit_sale_price": "₹1.00 / g",
        "manufacture_date": "08/2026",
        "fssai_license": "10014022002711",
        "country_of_origin": "India",
        "veg_nonveg_status": "GREEN"
    }

    with patch.object(settings, 'TEST_MODE', False):
        with patch.object(settings, 'GEMINI_ENABLED', True):
            with patch.object(settings, 'GEMINI_API_KEY', 'mock-valid-api-key'):
                with patch.object(extractor, 'call_gemini_api', new=AsyncMock(return_value=mock_gemini_response)):
                    info = await extractor.extract_async("Cadbury Dairy Milk")
                    assert info.product_name == "Cadbury Dairy Milk Silk"
                    assert info.brand == "Cadbury"
                    assert info.net_quantity == "50 g"
                    assert info.mrp == "₹50.00"
                    assert info.is_food is True
                    assert info.veg_nonveg_status == "GREEN"
                    assert "gemini" in info.extraction_mode
