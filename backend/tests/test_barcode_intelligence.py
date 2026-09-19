import pytest
from fastapi.testclient import TestClient
from main import app
from services.barcode_service import (
    barcode_service,
    BarcodeItem,
    GS1_COUNTRY_PREFIXES,
    VERIFIED_PRODUCT_REGISTRY
)

client = TestClient(app)

def test_gs1_checksum_calculation():
    # Valid check digits
    assert barcode_service.validate_checksum("8901030383748") is True
    assert barcode_service.validate_checksum("8901234567890") is True
    assert barcode_service.validate_checksum("8901030829147") is True
    assert barcode_service.validate_checksum("8901491101837") is True

    # Invalid check digits
    assert barcode_service.validate_checksum("8901030383749") is False
    assert barcode_service.validate_checksum("8901234567891") is False

def test_country_of_origin_resolution():
    # India: 890
    country, flag, prefix = barcode_service.resolve_country_of_origin("8901030383748")
    assert country == "India"
    assert flag == "🇮🇳"
    assert prefix == "890"

    # United States: 000-139
    country_us, flag_us, prefix_us = barcode_service.resolve_country_of_origin("012345678905")
    assert "United States" in country_us

    # United Kingdom: 500-509
    country_uk, flag_uk, prefix_uk = barcode_service.resolve_country_of_origin("5012345678900")
    assert country_uk == "United Kingdom"

    # Germany: 400-440
    country_de, flag_de, prefix_de = barcode_service.resolve_country_of_origin("4001234567890")
    assert country_de == "Germany"

    # France: 300-379
    country_fr, flag_fr, prefix_fr = barcode_service.resolve_country_of_origin("3001234567890")
    assert country_fr == "France"

def test_barcode_verification_matching():
    item = BarcodeItem(
        raw_value="8901030383748",
        symbology="EAN-13",
        confidence=0.98,
        is_valid_checksum=True,
        country_of_origin="India",
        country_flag="🇮🇳",
        gs1_prefix="890"
    )

    class CompliantProduct:
        brand = "Kissan"
        net_quantity = "950 g"
        country_of_origin = "India"
        fssai_license = "10013022001897"
        mrp = "145.00"

    result = barcode_service.verify_against_declarations(item, CompliantProduct())
    assert result.compliance_status == "PASS"
    assert result.net_quantity_match is True
    assert result.brand_match is True
    assert result.country_match is True
    assert len(result.discrepancies) == 0

def test_barcode_verification_mismatches():
    item = BarcodeItem(
        raw_value="8901030383748",
        symbology="EAN-13",
        confidence=0.98,
        is_valid_checksum=True,
        country_of_origin="India",
        country_flag="🇮🇳",
        gs1_prefix="890"
    )

    class MismatchedProduct:
        brand = "Different Brand"
        net_quantity = "500 g"
        country_of_origin = "China"
        fssai_license = "99999999999999"
        mrp = "200.00"

    result = barcode_service.verify_against_declarations(item, MismatchedProduct())
    assert result.compliance_status == "FAIL"
    assert result.net_quantity_match is False
    assert result.brand_match is False
    assert result.country_match is False
    assert len(result.discrepancies) >= 3

def test_barcode_api_endpoints():
    # 1. Lookup
    r1 = client.get("/api/barcode/lookup/8901030383748")
    assert r1.status_code == 200
    assert r1.json()["found"] is True
    assert r1.json()["record"]["brand_name"] == "Kissan"

    # 2. Verify
    r2 = client.post("/api/barcode/verify", json={
        "raw_value": "8901030383748",
        "symbology": "EAN-13",
        "brand": "Kissan",
        "net_quantity": "950 g",
        "country_of_origin": "India"
    })
    assert r2.status_code == 200
    assert r2.json()["compliance_status"] == "PASS"

    # 3. Live frame
    import base64
    import numpy as np
    import cv2
    blank = np.zeros((120, 120, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", blank)
    b64 = base64.b64encode(buf).decode("utf-8")

    r3 = client.post("/api/barcode/live-frame", json={
        "image_base64": b64,
        "include_text_boxes": True
    })
    assert r3.status_code == 200
    assert "fps_estimate" in r3.json()


def test_analyze_batch_route_alias():
    """Verify that POST /api/analyze/batch alias works for multi-angle live scanner submissions."""
    import io
    from PIL import Image

    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf1 = io.BytesIO()
    img.save(buf1, format="JPEG")
    buf1.seek(0)

    buf2 = io.BytesIO()
    img.save(buf2, format="JPEG")
    buf2.seek(0)

    files = [
        ("files", ("front.jpg", buf1.getvalue(), "image/jpeg")),
        ("files", ("back.jpg", buf2.getvalue(), "image/jpeg"))
    ]
    data = {
        "labels": '["Front", "Back"]'
    }

    res = client.post("/api/analyze/batch", files=files, data=data)
    assert res.status_code == 200
    res_data = res.json()
    assert "id" in res_data
    assert "ocr_result" in res_data
    assert len(res_data["images"]) == 2

