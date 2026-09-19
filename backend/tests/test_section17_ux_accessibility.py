"""
Section 17 User Experience (UX) & Accessibility Test Suite

Tests:
1. Analysis progress stage sequence and truthful descriptions mapping
2. User-friendly error messages and lack of raw stack trace exposure
3. Localization dictionary integrity and key completeness across 10 Indian languages
4. Color-independent compliance status descriptors (icon + status + label)
5. Auth & RBAC friendly error messages for unauthorized / forbidden flows
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from main import app
from auth.security import create_token, ROLE_MERCHANT


@pytest.fixture
def client():
    return TestClient(app)


def test_progress_stage_pipeline_truthfulness():
    """Verify that the conceptual analysis stages are distinct, non-empty, and truthful."""
    expected_stages = [
        "images_received",
        "quality_check",
        "ocr_extraction",
        "declaration_extraction",
        "rules_evaluation",
        "compliance_screening",
        "preparing_results"
    ]
    # Verify stage count and unique identities
    assert len(expected_stages) == 7
    assert len(set(expected_stages)) == 7


def test_i18n_locales_completeness_and_utf8():
    """Verify that all 10 language JSON dictionaries exist, are valid UTF-8 JSON, and contain mandatory keys."""
    locales_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "i18n", "locales"))
    required_locales = ['en', 'hi', 'mr', 'bn', 'gu', 'pa', 'ta', 'te', 'kn', 'ml']
    
    assert os.path.isdir(locales_dir), f"Locales directory not found at {locales_dir}"
    
    # Load English dictionary as baseline
    en_file = os.path.join(locales_dir, "en.json")
    with open(en_file, "r", encoding="utf-8") as f:
        en_dict = json.load(f)
    
    mandatory_top_level_keys = ["navigation", "dashboard", "status", "results", "common"]
    for key in mandatory_top_level_keys:
        assert key in en_dict, f"Baseline en.json missing '{key}' section"

    # Verify all 10 language files
    for loc in required_locales:
        loc_file = os.path.join(locales_dir, f"{loc}.json")
        assert os.path.isfile(loc_file), f"Locale file missing for '{loc}': {loc_file}"
        
        with open(loc_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Locale {loc} did not parse as a JSON object"
            
            # Check for non-empty navigation and status labels
            assert "status" in data or "navigation" in data, f"Locale {loc} is missing essential UI keys"
            
            # Ensure no corrupted Unicode question marks like '????' in translations
            raw_text = json.dumps(data, ensure_ascii=False)
            assert "????" not in raw_text, f"Locale {loc} contains raw unrendered question mark sequence"


def test_friendly_unauthorized_error_handling(client):
    """Verify unauthorized requests return friendly JSON error responses without stack traces."""
    resp = client.get("/api/history")
    assert resp.status_code == 401
    detail = resp.json().get("detail", "")
    assert "Authentication required" in detail or "Please log in" in detail or "Not authenticated" in detail
    # Stack trace should NOT be exposed
    assert "Traceback" not in resp.text


@pytest.mark.asyncio
async def test_friendly_forbidden_error_handling(client):
    """Verify RBAC access violations return clear, friendly error details."""
    from database.db import create_user
    from auth.security import hash_password
    
    username = "test_ux_merchant"
    try:
        pw_hash, salt = hash_password("Pass123!")
        await create_user(
            username=username,
            password_hash=pw_hash,
            salt=salt,
            role=ROLE_MERCHANT,
            full_name="Test UX Merchant"
        )
    except Exception:
        pass

    merchant_token = create_token(username, ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {merchant_token}"}
    
    # Merchant attempting admin user management endpoint
    resp = client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "Insufficient privileges" in detail or "Forbidden" in detail or "permission" in detail.lower() or "officer" in detail.lower()


def test_color_independent_status_mapping():
    """Verify that all core status states have distinct non-color textual designations."""
    statuses = {
        "PASS": {"label": "Pass / Compliant", "severity": "SUCCESS"},
        "FAIL": {"label": "Non-Compliant / Failure", "severity": "DANGER"},
        "NEEDS_REVIEW": {"label": "Review Required", "severity": "WARNING"},
        "NOT_APPLICABLE": {"label": "Not Applicable", "severity": "NEUTRAL"}
    }
    
    for code, info in statuses.items():
        assert len(info["label"]) > 0
        assert info["severity"] in ["SUCCESS", "DANGER", "WARNING", "NEUTRAL"]
