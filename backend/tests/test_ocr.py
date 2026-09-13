import os
import pytest
from unittest.mock import patch, MagicMock
from config import settings
from ocr.factory import get_ocr_engine, reset_ocr_engine
from ocr.paddle_engine import PaddleOCREngine, _sync_paddle_extract
from models.schemas import OCRResult, OCRWord
from ocr.cleaner import clean_ocr_text


def test_factory_paddle_engine():
    """Verify factory initializes PaddleOCREngine as the sole OCR engine."""
    reset_ocr_engine()
    settings.OCR_ENGINE = "paddleocr"
    engine = get_ocr_engine()
    assert isinstance(engine, PaddleOCREngine)


def test_factory_always_paddle():
    """Verify factory always returns PaddleOCREngine regardless of configuration values."""
    reset_ocr_engine()
    settings.OCR_ENGINE = "any_custom_value"
    engine = get_ocr_engine()
    assert isinstance(engine, PaddleOCREngine)
    reset_ocr_engine()
    settings.OCR_ENGINE = "paddleocr"


def test_paddle_engine_is_available():
    """Verify is_available returns a boolean value."""
    engine = PaddleOCREngine()
    avail = engine.is_available()
    assert isinstance(avail, bool)


@pytest.mark.asyncio
async def test_paddle_engine_extract_mock():
    """Test PaddleOCREngine extraction formatting and parsing logic with mocked paddleocr 3.x dict output."""
    engine = PaddleOCREngine()

    mock_paddle_3x_output = [
        {
            "rec_texts": ["METRCHECK COLD BREW", "Net Qty: 400 9", "Lic No: FSSA1 10019022009876", "MRP Rs. 299.00"],
            "rec_scores": [0.985, 0.942, 0.961, 0.991],
            "rec_boxes": [[10, 20, 100, 50], [15, 60, 120, 90], [20, 100, 150, 130], [25, 140, 110, 170]],
        }
    ]

    with patch("ocr.paddle_engine._is_paddle_available", return_value=True), \
         patch("ocr.paddle_engine._init_paddle_ocr") as mock_init:
        mock_instance = MagicMock()
        mock_instance.predict.return_value = mock_paddle_3x_output
        mock_init.return_value = mock_instance

        # Test extraction
        result = await engine.extract("dummy_path.jpg")

        assert isinstance(result, OCRResult)
        assert "PaddleOCR" in result.engine
        assert result.word_count > 0
        assert result.average_confidence > 90.0

        # Verify statutory repair (400 9 -> 400 g and FSSA1 -> FSSAI)
        assert "400 g" in result.full_text
        assert "FSSAI" in result.full_text

        # Verify word bounding boxes are generated
        assert len(result.words) > 0
        first_word = result.words[0]
        assert isinstance(first_word, OCRWord)
        assert len(first_word.bbox) == 4
        assert first_word.bbox[0] < first_word.bbox[2]
        assert first_word.bbox[1] < first_word.bbox[3]


@pytest.mark.asyncio
async def test_paddle_engine_extract_legacy_mock():
    """Test PaddleOCREngine extraction formatting with legacy 2.x list output."""
    engine = PaddleOCREngine()

    mock_paddle_2x_output = [
        [
            [[[10, 20], [100, 20], [100, 50], [10, 50]], ("METRCHECK COLD BREW", 0.985)],
            [[[15, 60], [120, 60], [120, 90], [15, 90]], ("Net Qty: 400 9", 0.942)],
        ]
    ]

    with patch("ocr.paddle_engine._is_paddle_available", return_value=True), \
         patch("ocr.paddle_engine._init_paddle_ocr") as mock_init:
        mock_instance = MagicMock(spec=["ocr"])
        mock_instance.ocr.return_value = mock_paddle_2x_output
        mock_init.return_value = mock_instance

        # Test extraction
        result = await engine.extract("dummy_path.jpg")

        assert isinstance(result, OCRResult)
        assert "PaddleOCR" in result.engine
        assert result.word_count > 0
        assert "400 g" in result.full_text


@pytest.mark.asyncio
async def test_paddle_engine_unavailable_handling():
    """Test PaddleOCREngine graceful handling when Paddle is not available (no Tesseract fallback)."""
    engine = PaddleOCREngine()

    with patch("ocr.paddle_engine._is_paddle_available", return_value=False):
        result = await engine.extract("dummy_test_image.jpg")
        assert isinstance(result, OCRResult)
        assert result.average_confidence == 0.0
        assert "Unavailable" in result.engine
        assert "unavailable" in result.full_text.lower()


def test_clean_ocr_text_preserves_statutory_symbols():
    """Verify that cleaner preserves rupee symbol, units, and statutory keywords."""
    raw = "MRP ₹ 299.00 \n Net Qty: 500 g \n Lic No: FSSA1 12345678901234"
    cleaned = clean_ocr_text(raw)
    assert "₹" in cleaned
    assert "299.00" in cleaned
    assert "FSSAI" in cleaned
