import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint_operational():
    """Verify GET /api/health returns operational status with all services operational."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "operational"
    assert "services" in data
    assert data["services"]["backend"] == "operational"
    assert data["services"]["database"] == "operational"
    assert data["services"]["ocr"] == "operational"
    assert data["ocr_available"] is True
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert "version" in data

    # Verify no secrets or sensitive internal paths are leaked
    body_text = resp.text.lower()
    assert "password" not in body_text
    assert "token" not in body_text
    assert "secret" not in body_text
    assert "c:\\" not in body_text


def test_health_endpoint_root_alias():
    """Verify root GET /health alias responds with 200 OK."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "operational", "healthy")


def test_health_endpoint_ocr_degraded():
    """Verify GET /api/health reports degraded status when OCR engine is unavailable."""
    mock_ocr = MagicMock()
    mock_ocr.is_available.return_value = False
    mock_ocr.__class__.__name__ = "MockOCREngine"

    with patch("api.health.get_ocr_engine", return_value=mock_ocr):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["services"]["ocr"] == "degraded"
        assert data["services"]["backend"] == "operational"
        assert data["services"]["database"] == "operational"
        assert data["ocr_available"] is False


def test_health_endpoint_db_unavailable():
    """Verify GET /api/health reports degraded/offline status when database query fails."""
    with patch("api.health.get_db", side_effect=RuntimeError("Database lock")):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"]["database"] == "unavailable"
        assert data["database"] == "unavailable"
        assert data["status"] in ("degraded", "offline")
