import pytest
from fastapi.testclient import TestClient
from main import app
from multilingual.registry import (
    is_supported_language,
    get_language_name,
    get_native_name,
)
from models.schemas import (
    AnalysisResponse, ProductInfo, ComplianceResult, ComplianceCheck,
    OCRResult
)
from services.report_service import generate_pdf_report

EXPECTED_10_LANGUAGES = [
    ("en", "English", "English"),
    ("hi", "Hindi", "\u0939\u093f\u0928\u094d\u0926\u0940"),
    ("bn", "Bengali", "\u09ac\u09be\u0982\u09b2\u09be"),
    ("mr", "Marathi", "\u092e\u0930\u093e\u0920\u0940"),
    ("gu", "Gujarati", "\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0"),
    ("pa", "Punjabi", "\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40"),
    ("ta", "Tamil", "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd"),
    ("te", "Telugu", "\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41"),
    ("kn", "Kannada", "\u0c95\u0ca8\u0ccd\u0ca8\u0ca1"),
    ("ml", "Malayalam", "\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02"),
]

def test_01_all_10_languages_registered_and_mapped():
    codes = [l[0] for l in EXPECTED_10_LANGUAGES]
    assert len(codes) == 10
    for code, english_name, native_name in EXPECTED_10_LANGUAGES:
        assert is_supported_language(code) is True, f"Code {code} not recognized"
        assert get_language_name(code) == english_name, f"English name mismatch for {code}"
        assert get_native_name(code) == native_name, f"Native name mismatch for {code}"

from auth.security import create_token, ROLE_ADMIN

def test_02_default_report_is_english():
    client = TestClient(app)
    token = create_token("admin", ROLE_ADMIN)
    resp = client.get("/api/report/demo-1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "metrcheck-report-demo-1-en.pdf" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 1000

@pytest.mark.parametrize("lang_code", ["en", "hi", "bn", "mr", "gu", "pa", "ta", "te", "kn", "ml"])
def test_03_api_report_all_10_languages(lang_code):
    client = TestClient(app)
    token = create_token("admin", ROLE_ADMIN)
    resp = client.get(f"/api/report/demo-1?lang={lang_code}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"Failed for {lang_code}: {resp.status_code}"
    assert resp.headers["content-type"] == "application/pdf"
    assert f"metrcheck-report-demo-1-{lang_code}.pdf" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 1000

def test_04_canonical_data_and_compliance_invariance_across_reports():
    analysis = AnalysisResponse(
        id="test-multilingual-invariance",
        product_name="Alpino Peanut Butter 1kg",
        image_url="/placeholder.png",
        images=[],
        ocr_result=OCRResult(
            full_text="MRP Rs. 499 Net Wt: 1000g Mfg: 03/2024",
            words=[],
            language="eng",
            processing_time=0.1,
        ),
        product_info=ProductInfo(
            product_name="Alpino Peanut Butter 1kg",
            brand="Alpino",
            net_quantity="1000 g",
            mrp="\u20b9499",
            manufacturing_date="03/2024",
            country_of_origin="India",
        ),
        compliance_result=ComplianceResult(
            status="NON_COMPLIANT",
            score=70.0,
            passed_rules=1,
            failed_rules=1,
            needs_review_rules=0,
            not_applicable_rules=0,
            total_rules=2,
            checks=[
                ComplianceCheck(
                    rule_id="LM-001",
                    field="mrp",
                    field_label="Maximum Retail Price (MRP)",
                    status="PASS",
                    detected_value="\u20b9499",
                    explanation="MRP \u20b9499 clearly declared.",
                ),
                ComplianceCheck(
                    rule_id="LM-008",
                    field="fssai_license",
                    field_label="FSSAI License Number",
                    status="FAIL",
                    explanation="FSSAI License Number is missing.",
                ),
            ],
            recommendations=[],
        ),
        recommendations=[],
        created_at="2026-03-16T12:00:00Z",
    )

    for code in ["en", "hi", "bn", "mr", "gu", "pa", "ta", "te", "kn", "ml"]:
        pdf_bytes = generate_pdf_report(analysis, lang=code)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 2000
        assert analysis.product_info.mrp == "\u20b9499"
        assert analysis.product_info.net_quantity == "1000 g"
        assert analysis.compliance_result.status == "NON_COMPLIANT"
        assert analysis.compliance_result.score == 70.0
