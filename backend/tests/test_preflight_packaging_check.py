import asyncio
import pytest
from fastapi.testclient import TestClient
from testing_utils import isolated_test_env
from services.analysis_service import analyze_text
from models.schemas import AnalysisResponse
from main import app


def test_preflight_structured_food_payload():
    """Verify structured food declarations are parsed and evaluated correctly by backend."""
    structured_payload = """
Product Name: Alpino Super High Protein Rolled Oats - Dark Chocolate
Brand: Alpino Health Foods
Category: Packaged Food / Breakfast Cereals
Net Quantity: 400 g
Maximum Retail Price (MRP): Rs. 299.00 (Inclusive of all taxes)
Unit Sale Price: Rs. 747.50 / kg
Date of Manufacture: 10/2026
Best Before: 12 months from date of manufacture
Batch Number: BATCH-ALP-2026-10
Country of Origin: India

Manufactured & Packed by:
Alpino Health Foods Pvt. Ltd.
Plot No. 12, GIDC Industrial Estate,
Surat, Gujarat - 395007

Marketed by:
Alpino Health Foods Pvt. Ltd.
Plot No. 12, GIDC Industrial Estate,
Surat, Gujarat - 395007

Consumer Care Cell:
Helpline Phone: 1800-123-4567
Email: care@alpino.store
Address: Plot No. 12, GIDC Industrial Estate, Surat, Gujarat - 395007

FSSAI License No.: 10716022000249

Ingredients:
Rolled Oats (75%), Whey Protein Isolate (15%), Cocoa Powder (7%), Natural Sweetener (Stevia).

Nutritional Information (per 100g):
Energy: 412 kcal, Protein: 30.5 g, Carbohydrates: 54.2 g (Total Sugars: 3.1 g, Added Sugars: 0 g, Dietary Fibre: 9.8 g), Total Fat: 7.2 g (Saturated Fat: 1.4 g, Trans Fat: 0 g, Cholesterol: 0 mg), Sodium: 140 mg.

Allergen Declaration:
Contains Gluten and Milk. Processed in a facility that also handles nuts and soy.
""".strip()

    with isolated_test_env():
        client = TestClient(app)
        response = client.post("/api/analyze/text", json={"text": structured_payload})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["product_info"]["product_name"] is not None
        assert data["product_info"]["mrp"] is not None
        assert data["product_info"]["net_quantity"] is not None
        assert data["product_info"]["fssai_license"] == "10716022000249"
        assert len(data["compliance_result"]["checks"]) > 0
        assert data["ocr_result"]["word_count"] > 0


def test_preflight_structured_non_food_payload():
    """Verify non-food declarations evaluate Legal Metrology without requiring FSSAI."""
    structured_payload = """
Product Name: Sparkle Ultra Clean Laundry Detergent
Brand: Sparkle Care
Category: Non-Food / Household Care
Net Quantity: 1 kg
Maximum Retail Price (MRP): Rs. 199.00 (Inclusive of all taxes)
Unit Sale Price: Rs. 199.00 / kg
Date of Manufacture: 09/2026
Batch Number: LOT-SC-2026-09
Country of Origin: India

Manufactured & Packed by:
Sparkle Cleaners India LLP
Plot 88, Phase 2, Industrial Area,
Pune, Maharashtra - 411018

Marketed by:
Sparkle Cleaners India LLP
Plot 88, Phase 2, Industrial Area,
Pune, Maharashtra - 411018

Consumer Care Cell:
Helpline Phone: 1800-555-0199
Email: support@sparklecare.in
""".strip()

    with isolated_test_env():
        client = TestClient(app)
        response = client.post("/api/analyze/text", json={"text": structured_payload})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["product_info"]["mrp"] is not None
        assert data["product_info"]["net_quantity"] is not None
        checks = {c["field"]: c for c in data["compliance_result"]["checks"]}
        assert "mrp" in checks
        assert "net_quantity" in checks
        assert "manufacturer" in checks


def test_preflight_missing_mandatory_declarations():
    """Verify missing mandatory declarations are flagged without crashes."""
    incomplete_payload = """
Product Name: Mystery Snack
Brand: UnknownBrand
Net Quantity: 200 g
""".strip()

    with isolated_test_env():
        client = TestClient(app)
        response = client.post("/api/analyze/text", json={"text": incomplete_payload})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        failed_or_review = [
            c for c in data["compliance_result"]["checks"]
            if c["status"] in ("FAIL", "NEEDS_REVIEW", "NON_COMPLIANT")
        ]
        assert len(failed_or_review) > 0
