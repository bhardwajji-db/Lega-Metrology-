"""
Live Packaging & Barcode Scanner End-to-End API Test Suite
Covers:
- Real-time frame processing (/api/barcode/live-frame)
- QR code detection & GS1 Digital Link decoding
- FSSAI extraction from QR data
- 1D Barcode (EAN-13) detection from real packaging imagery
- Empty and blank frame handling
- Malformed base64 input rejection (HTTP 400)
- HUD morphological bounding box localization
- Barcode verification against statutory declarations (/api/barcode/verify)
- Master product registry lookup (/api/barcode/lookup/{gtin})
- Multi-angle snapshot batch analysis (/api/analyze/batch)
- GS1 Country of origin resolution and checksum verification
"""

import io
import base64
import os
import pytest
import cv2
import numpy as np
import qrcode
from PIL import Image
from fastapi.testclient import TestClient

from main import app
from services.barcode_service import barcode_service, BarcodeItem

client = TestClient(app)


def _cv2_to_b64(img_bgr: np.ndarray) -> str:
    """Helper to convert OpenCV BGR image to base64 JPEG string."""
    _, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return base64.b64encode(buf).decode("utf-8")


def _generate_qr_b64(content: str) -> str:
    """Generate a real synthetic QR code image and return as base64 string."""
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    img_pil = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img_pil.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_live_frame_blank_image():
    """Verify blank camera frame returns detected=False and empty barcodes list."""
    blank = np.zeros((360, 640, 3), dtype=np.uint8)
    b64 = _cv2_to_b64(blank)

    res = client.post("/api/barcode/live-frame", json={
        "image_base64": b64,
        "include_text_boxes": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is False
    assert len(data["barcodes"]) == 0
    assert "fps_estimate" in data
    assert "summary" in data


def test_live_frame_malformed_base64():
    """Verify malformed base64 payload returns HTTP 400 Bad Request."""
    res = client.post("/api/barcode/live-frame", json={
        "image_base64": "invalid_corrupted_base64_data",
        "include_text_boxes": True
    })
    assert res.status_code == 400
    assert "Failed to decode" in res.json()["detail"]


def test_live_frame_qr_gs1_digital_link_detection():
    """Verify live-frame endpoint detects and parses a real GS1 Digital Link QR code."""
    digital_link_uri = "https://id.gs1.org/01/08901030383748/10/LOT42/17/270101"
    b64 = _generate_qr_b64(digital_link_uri)

    res = client.post("/api/barcode/live-frame", json={
        "image_base64": b64,
        "include_text_boxes": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert len(data["barcodes"]) >= 1

    barcode = data["barcodes"][0]
    assert barcode["symbology"] == "GS1_DIGITAL_LINK"
    assert barcode["country_of_origin"] == "India"
    assert barcode["country_flag"] == "🇮🇳"
    assert barcode["digital_link_data"]["gtin"] == "08901030383748"
    assert barcode["digital_link_data"]["lot"] == "LOT42"
    assert barcode["digital_link_data"]["expiry_yymmdd"] == "270101"


def test_live_frame_qr_with_fssai_license():
    """Verify QR code encoding FSSAI license is detected and FSSAI is extracted."""
    qr_content = "PRODUCT: Biscuits | FSSAI: 10013022001897 | BATCH: B2026"
    b64 = _generate_qr_b64(qr_content)

    res = client.post("/api/barcode/live-frame", json={
        "image_base64": b64,
        "include_text_boxes": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert len(data["barcodes"]) >= 1

    raw_val = data["barcodes"][0]["raw_value"]
    assert "10013022001897" in raw_val
    fssai = barcode_service.extract_fssai_from_qr_data(raw_val)
    assert fssai == "10013022001897"


def test_live_frame_with_real_packaging_1d_barcode():
    """Verify live-frame endpoint detects real 1D EAN-13 barcode from packaging upload."""
    sample_path = os.path.join(os.path.dirname(__file__), "..", "uploads", "71ff202b-c0cd-466b-a648-ba0efe2b5f11_back_barcode_back.jpeg")
    if not os.path.exists(sample_path):
        pytest.skip("Sample packaging image not found")

    img = cv2.imread(sample_path)
    assert img is not None
    b64 = _cv2_to_b64(img)

    res = client.post("/api/barcode/live-frame", json={
        "image_base64": b64,
        "include_text_boxes": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["detected"] is True
    assert len(data["barcodes"]) >= 1
    assert data["barcodes"][0]["raw_value"] == "8901030921797"
    assert data["barcodes"][0]["country_of_origin"] == "India"
    assert data["barcodes"][0]["country_flag"] == "🇮🇳"


def test_live_frame_hud_morphological_text_boxes():
    """Verify morphological text region detection creates HUD bounding boxes."""
    # Create an image with simulated packaging text blocks
    canvas = np.ones((480, 640, 3), dtype=np.uint8) * 255
    cv2.putText(canvas, "BEST BEFORE 12 MONTHS FROM MANUFACTURE", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(canvas, "MAXIMUM RETAIL PRICE RS 150.00", (40, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(canvas, "NET QUANTITY: 500 g", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    b64 = _cv2_to_b64(canvas)

    res = client.post("/api/barcode/live-frame", json={
        "image_base64": b64,
        "include_text_boxes": True
    })
    assert res.status_code == 200
    data = res.json()
    assert len(data["hud_boxes"]) > 0
    # Confirm boxes have valid coordinates
    for box in data["hud_boxes"]:
        assert len(box["bbox"]) == 4
        assert box["bbox"][2] > box["bbox"][0]
        assert box["bbox"][3] > box["bbox"][1]


def test_barcode_verify_compliant():
    """Verify POST /api/barcode/verify returns PASS when label matches registered master."""
    res = client.post("/api/barcode/verify", json={
        "raw_value": "8901030829147",
        "symbology": "EAN-13",
        "brand": "Kissan",
        "net_quantity": "950 g",
        "country_of_origin": "India",
        "fssai_license": "10013022001897",
        "mrp": "145.00"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["compliance_status"] == "PASS"
    assert data["net_quantity_match"] is True
    assert data["brand_match"] is True
    assert data["country_match"] is True
    assert data["fssai_match"] is True
    assert len(data["discrepancies"]) == 0


def test_barcode_verify_mismatch_discrepancy():
    """Verify POST /api/barcode/verify detects discrepancies when label contradicts barcode master."""
    res = client.post("/api/barcode/verify", json={
        "raw_value": "8901030829143",
        "symbology": "EAN-13",
        "brand": "Fake Brand Name",
        "net_quantity": "200 g",
        "country_of_origin": "China",
        "fssai_license": "99999999999999",
        "mrp": "999.00"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["compliance_status"] == "FAIL"
    assert data["net_quantity_match"] is False
    assert data["brand_match"] is False
    assert len(data["discrepancies"]) >= 2


def test_barcode_lookup_endpoint():
    """Verify GET /api/barcode/lookup/{gtin} for registered vs unregistered barcodes."""
    # Registered
    r_reg = client.get("/api/barcode/lookup/8901030829143")
    assert r_reg.status_code == 200
    d_reg = r_reg.json()
    assert d_reg["found"] is True
    assert d_reg["record"]["brand_name"] == "Kissan"
    assert d_reg["record"]["net_quantity"] == "950 g"

    # Unregistered
    r_unreg = client.get("/api/barcode/lookup/8909999999999")
    assert r_unreg.status_code == 200
    d_unreg = r_unreg.json()
    assert d_unreg["found"] is False
    assert d_unreg["country_of_origin"] == "India"
    assert d_unreg["country_flag"] == "🇮🇳"


def test_analyze_batch_from_live_scanner_snapshots():
    """Verify POST /api/analyze/batch accepts multiple panel snapshots from Live Scanner."""
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    buf_front = io.BytesIO()
    img.save(buf_front, format="JPEG")
    buf_front.seek(0)

    buf_back = io.BytesIO()
    img.save(buf_back, format="JPEG")
    buf_back.seek(0)

    files = [
        ("files", ("front_scan.jpg", buf_front.getvalue(), "image/jpeg")),
        ("files", ("back_scan.jpg", buf_back.getvalue(), "image/jpeg"))
    ]
    data = {
        "labels": '["Front", "Back"]'
    }

    res = client.post("/api/analyze/batch", files=files, data=data)
    assert res.status_code == 200
    res_data = res.json()
    assert "id" in res_data
    assert "compliance_result" in res_data
    assert len(res_data["images"]) == 2
