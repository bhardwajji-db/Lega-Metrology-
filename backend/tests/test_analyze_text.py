import asyncio
from fastapi.testclient import TestClient
from testing_utils import isolated_test_env
from services.analysis_service import analyze_text
from models.schemas import AnalysisResponse
from main import app


def test_analyze_text_service():
    """Verify analyze_text extracts declarations, computes compliance, and saves to DB."""
    sample_text = (
        "Maggi Noodles 70g MRP Rs 12 incl of all taxes, "
        "manufactured by Nestle India Ltd, valid for 100 years from packing date, "
        "batch no XYZ, Consumer care: 1800-200-8899 care@nestle.in"
    )
    with isolated_test_env():
        result = asyncio.run(analyze_text(sample_text))
        assert isinstance(result, AnalysisResponse)
        assert result.id is not None
        assert result.product_name != ""
        assert result.ocr_result.full_text == sample_text
        assert result.ocr_result.word_count > 0
        assert result.compliance_result is not None
        assert len(result.compliance_result.checks) > 0
        assert result.image_url == "/placeholder.png"
        assert result.images == []
        assert result.font_size_analysis is not None


def test_analyze_text_api_endpoint():
    """Verify POST /api/analyze/text endpoint returns valid AnalysisResponse."""
    sample_text = (
        "Brand: HealthyBites Organic Almonds 500g MRP Rs. 450 incl of all taxes. "
        "Mfg by: HealthyBites Ltd. Customer Care: care@healthybites.in"
    )
    with isolated_test_env():
        client = TestClient(app)
        response = client.post("/api/analyze/text", json={"text": sample_text})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["ocr_result"]["full_text"] == sample_text
        assert "compliance_result" in data
        assert "product_info" in data
        assert data["image_url"] == "/placeholder.png"


def test_analyze_text_empty_input():
    """Verify POST /api/analyze/text rejects empty text input with HTTP 400."""
    with isolated_test_env():
        client = TestClient(app)
        response = client.post("/api/analyze/text", json={"text": "   "})
        assert response.status_code == 400
