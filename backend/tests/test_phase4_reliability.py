import os
import io
import asyncio
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from testing_utils import isolated_test_env
from main import app
from ocr.factory import get_ocr_engine, reset_ocr_engine
from ocr.paddle_engine import PaddleOCREngine, _init_paddle_ocr
from services.analysis_service import analyze_products, analyze_text
from models.schemas import AnalysisResponse, OCRWord, EvidenceItem


def _create_test_image_bytes(width: int = 200, height: int = 100, color: str = "white") -> bytes:
    """Helper to generate in-memory valid image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_paddleocr_model_lifecycle_singleton_reuse():
    """Verify PaddleOCR engine and internal instance are singletons and reused across calls."""
    reset_ocr_engine()
    engine1 = get_ocr_engine()
    engine2 = get_ocr_engine()
    assert engine1 is engine2, "Factory must return the exact same OCREngine instance"

    if engine1.is_available():
        inst1 = _init_paddle_ocr()
        inst2 = _init_paddle_ocr()
        assert inst1 is inst2, "Internal PaddleOCR model must be a singleton and never re-initialized"


def test_malformed_image_non_image_rejection():
    """Verify corrupted / non-image data with .jpg extension is rejected with clean HTTP 400."""
    with isolated_test_env():
        client = TestClient(app)
        fake_bytes = b"NOT_A_REAL_IMAGE_DATA_CORRUPTED_BYTES"
        response = client.post(
            "/api/analyze",
            files=[("files", ("corrupted.jpg", fake_bytes, "image/jpeg"))]
        )
        assert response.status_code == 400
        assert "not a valid or readable image" in response.json()["detail"].lower() or "corrupted" in response.json()["detail"].lower()


def test_empty_file_rejection():
    """Verify 0-byte file is rejected with clean HTTP 400."""
    with isolated_test_env():
        client = TestClient(app)
        response = client.post(
            "/api/analyze",
            files=[("files", ("empty.png", b"", "image/png"))]
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


def test_unsupported_file_extension_rejection():
    """Verify unsupported file extensions are rejected with HTTP 400."""
    with isolated_test_env():
        client = TestClient(app)
        response = client.post(
            "/api/analyze",
            files=[("files", ("document.pdf", b"%PDF-1.4 ...", "application/pdf"))]
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()


def test_oversized_file_rejection():
    """Verify files exceeding 10MB are rejected with HTTP 400."""
    with isolated_test_env():
        client = TestClient(app)
        # Create bytes larger than 10MB (10.5 MB)
        oversized_bytes = b"X" * (10 * 1024 * 1024 + 512 * 1024)
        response = client.post(
            "/api/analyze",
            files=[("files", ("huge_image.png", oversized_bytes, "image/png"))]
        )
        assert response.status_code == 400
        assert "exceeds" in response.json()["detail"].lower() or "too large" in response.json()["detail"].lower()


def test_failure_isolation_and_server_recovery():
    """Verify a failed request (malformed image) does not affect subsequent valid requests."""
    with isolated_test_env():
        client = TestClient(app)
        # 1. Send invalid image -> 400
        bad_resp = client.post(
            "/api/analyze",
            files=[("files", ("bad.jpg", b"invalid_bytes_data", "image/jpeg"))]
        )
        assert bad_resp.status_code == 400

        # 2. Immediately send valid text analysis -> 200
        sample_text = "NutriHarvest Oats 500g MRP Rs 199 incl of taxes. Mfg by NH Ltd."
        good_resp = client.post(
            "/api/analyze/text",
            json={"text": sample_text}
        )
        assert good_resp.status_code == 200
        data = good_resp.json()
        assert data["id"] is not None
        assert "NutriHarvest" in data["ocr_result"]["full_text"]


def test_determinism_repeated_execution():
    """Verify repeated compliance analysis on identical text produces 100% deterministic results."""
    sample_text = (
        "ALPINO SUPER OATS 400 g \n"
        "MRP Rs. 299.00 (Incl. of all taxes) \n"
        "Unit Sale Price: Rs. 0.74 / g \n"
        "Mfg Date: 01/2026 \n"
        "Best Before 12 Months from manufacture \n"
        "Lic No. 10716022000249 \n"
        "Country of Origin: India \n"
        "Manufactured by: Alpino Health Foods Pvt Ltd, Surat, Gujarat \n"
        "Customer Care: +91-8347688000 support@alpino.co.in"
    )

    with isolated_test_env():
        results = []
        for _ in range(5):
            res = asyncio.run(analyze_text(sample_text))
            results.append(res)

        # Compare runs against run 0
        base = results[0]
        for r in results[1:]:
            assert r.compliance_result.score == base.compliance_result.score
            assert r.compliance_result.status == base.compliance_result.status
            assert len(r.compliance_result.checks) == len(base.compliance_result.checks)
            for c_base, c_test in zip(base.compliance_result.checks, r.compliance_result.checks):
                assert c_base.rule_id == c_test.rule_id
                assert c_base.status == c_test.status


def test_no_tesseract_in_live_engine():
    """Verify that OCREngine is strictly PaddleOCR and no Tesseract fallback or engine is configured."""
    engine = get_ocr_engine()
    assert isinstance(engine, PaddleOCREngine)
    assert not hasattr(engine, "tesseract")
    assert not hasattr(engine, "pytesseract")


def test_no_fake_data_in_api_response():
    """Verify /api/analyze endpoints do not contain hardcoded demo mocks or fake coordinates."""
    with isolated_test_env():
        client = TestClient(app)
        img_bytes = _create_test_image_bytes(100, 50)
        resp = client.post(
            "/api/analyze",
            files=[("files", ("test.png", img_bytes, "image/png"))]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not data["id"].startswith("demo-")
        assert data["id"] not in ("1", "2", "3")
