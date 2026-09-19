import pytest
from fastapi.testclient import TestClient

from main import app
from models.schemas import ProductInfo
from models.listing_schemas import ListingCheckRequest
from services.listing_service import (
    validate_ssrf_safety,
    compare_package_vs_listing,
    check_listing_compliance,
    build_listing_text_from_structured
)
from database.db import save_analysis

client = TestClient(app)


# ════════════════════════════════════════════════════════════════════════════
# 1. SSRF VALIDATION TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_ssrf_blocks_loopback_and_localhost():
    """Verify SSRF validator rejects 127.0.0.1 and localhost."""
    is_safe, err = validate_ssrf_safety("http://127.0.0.1:8000/secret")
    assert is_safe is False
    assert "prohibited" in err.lower() or "non-routable" in err.lower()

    is_safe_lh, err_lh = validate_ssrf_safety("http://localhost:3000/api")
    assert is_safe_lh is False
    assert "restricted" in err_lh.lower() or "prohibited" in err_lh.lower()


def test_ssrf_blocks_cloud_metadata():
    """Verify SSRF validator blocks AWS/GCP metadata IP (169.254.169.254)."""
    is_safe, err = validate_ssrf_safety("http://169.254.169.254/latest/meta-data/")
    assert is_safe is False
    assert "prohibited" in err.lower() or "restricted" in err.lower() or "non-routable" in err.lower()


def test_ssrf_blocks_private_networks():
    """Verify SSRF validator blocks RFC 1918 private ranges (10.x, 192.168.x, 172.16.x)."""
    is_safe_10, _ = validate_ssrf_safety("http://10.0.0.1/admin")
    assert is_safe_10 is False

    is_safe_192, _ = validate_ssrf_safety("http://192.168.1.1/router")
    assert is_safe_192 is False

    is_safe_172, _ = validate_ssrf_safety("http://172.16.0.1/internal")
    assert is_safe_172 is False


def test_ssrf_blocks_invalid_protocols():
    """Verify SSRF validator blocks non-http/https protocols."""
    is_safe_file, err_file = validate_ssrf_safety("file:///etc/passwd")
    assert is_safe_file is False
    assert "unsupported url protocol" in err_file.lower()

    is_safe_ftp, err_ftp = validate_ssrf_safety("ftp://example.com/file.txt")
    assert is_safe_ftp is False


# ════════════════════════════════════════════════════════════════════════════
# 2. PACKAGE VS LISTING CROSS-COMPARISON LOGIC TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_cross_comparison_compliant_match():
    """Verify that identical package and listing declarations result in COMPLIANT_MATCH."""
    pkg = ProductInfo(
        product_name="Britannia Good Day Butter Cookies",
        net_quantity="200 g",
        mrp="40.00",
        manufacturer="Britannia Industries Ltd",
        fssai_license="10014011000123",
        country_of_origin="India"
    )
    lst = ProductInfo(
        product_name="Britannia Good Day Butter Cookies 200g Pack",
        net_quantity="200 g",
        mrp="Rs. 40.00",
        manufacturer="Britannia Industries Ltd",
        fssai_license="10014011000123",
        country_of_origin="India"
    )

    diffs, verdict, matches, mismatches, insufficient = compare_package_vs_listing(pkg, lst)
    assert verdict == "COMPLIANT_MATCH"
    assert mismatches == 0
    assert matches >= 4
    for d in diffs:
        assert d.status == "MATCH"


def test_cross_comparison_price_and_qty_mismatch():
    """Verify detection of price and net quantity discrepancies."""
    pkg = ProductInfo(
        product_name="Premium Almonds",
        net_quantity="200 g",
        mrp="200.00",
        country_of_origin="India"
    )
    lst = ProductInfo(
        product_name="Premium Almonds",
        net_quantity="500 g",     # Mismatch
        mrp="250.00",            # Higher price mismatch
        country_of_origin="India"
    )

    diffs, verdict, matches, mismatches, insufficient = compare_package_vs_listing(pkg, lst)
    assert verdict == "MISMATCH_DETECTED"
    assert mismatches >= 2

    mrp_diff = next((d for d in diffs if d.field == "mrp"), None)
    assert mrp_diff is not None
    assert mrp_diff.status == "MISMATCH"
    assert mrp_diff.severity == "CRITICAL"

    qty_diff = next((d for d in diffs if d.field == "net_quantity"), None)
    assert qty_diff is not None
    assert qty_diff.status == "MISMATCH"


def test_cross_comparison_insufficient_online_data():
    """Verify that missing mandatory online declarations trigger INSUFFICIENT_ONLINE_DATA."""
    pkg = ProductInfo(
        product_name="Organic Honey",
        net_quantity="500 g",
        mrp="350.00",
        fssai_license="10019011000555",
        country_of_origin="India"
    )
    # Online listing omits FSSAI and Country of Origin
    lst = ProductInfo(
        product_name="Organic Honey",
        net_quantity="500 g",
        mrp="350.00"
    )

    diffs, verdict, matches, mismatches, insufficient = compare_package_vs_listing(pkg, lst)
    assert verdict == "INSUFFICIENT_ONLINE_DATA"
    assert insufficient >= 1

    fssai_diff = next((d for d in diffs if d.field == "fssai_license"), None)
    assert fssai_diff is not None
    assert fssai_diff.status == "INSUFFICIENT_DATA"


# ════════════════════════════════════════════════════════════════════════════
# 3. END-TO-END LISTING API ENDPOINTS TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_api_check_listing_raw_text():
    """Test POST /api/listing/check using raw text input."""
    raw_text = """
    Product Name: Alpino Super Rolled Oats
    Brand: Alpino
    Net Quantity: 400 g
    Maximum Retail Price (MRP): Rs. 299.00
    Unit Sale Price: Rs. 747.50 / kg
    Date of Manufacture: 10/2026
    FSSAI License No.: 10716022000249
    Country of Origin: India
    Manufactured & Packed by: Alpino Health Foods Pvt Ltd, Surat, Gujarat
    Consumer Care: 1800-123-4567, care@alpino.store
    Ingredients: Rolled Oats, Whey Protein, Stevia
    """

    res = client.post("/api/listing/check", json={
        "mode": "RAW_TEXT",
        "raw_text": raw_text
    })

    assert res.status_code == 200
    data = res.json()
    assert data["id"].startswith("lst-")
    assert data["source_mode"] == "RAW_TEXT"
    assert data["score"] > 60.0
    assert data["extracted_info"]["product_name"] is not None
    assert data["comparison_performed"] is False


@pytest.mark.asyncio
async def test_api_check_listing_structured_with_package_comparison():
    """Test POST /api/listing/check with structured form and package cross-comparison."""
    # First, save a physical package screening in the database
    pkg_analysis = {
        "id": "ana-pkg-test-01",
        "product_name": "NutriHarvest California Almonds",
        "score": 95.0,
        "status": "PASS",
        "created_at": "2026-09-18T10:00:00Z",
        "extracted_data": {
            "product_name": "NutriHarvest California Almonds",
            "net_quantity": "500 g",
            "mrp": "499.00",
            "manufacturer": "NutriHarvest Foods Pvt Ltd",
            "fssai_license": "10020011000123",
            "country_of_origin": "India"
        },
        "compliance_result": {"checks": [], "score": 95.0, "status": "PASS"}
    }
    await save_analysis(pkg_analysis)

    # Cross-compare with an e-commerce listing for the same item
    res = client.post("/api/listing/check", json={
        "mode": "STRUCTURED",
        "structured_data": {
            "productName": "NutriHarvest California Almonds",
            "brand": "NutriHarvest",
            "netQtyAmount": "500",
            "netQtyUnit": "g",
            "mrp": "499.00",
            "manufacturerName": "NutriHarvest Foods Pvt Ltd",
            "fssaiLicense": "10020011000123",
            "countryOfOrigin": "India"
        },
        "package_analysis_id": "ana-pkg-test-01"
    })

    assert res.status_code == 200
    data = res.json()
    assert data["comparison_performed"] is True
    assert data["package_analysis_id"] == "ana-pkg-test-01"
    assert data["cross_verdict"] == "COMPLIANT_MATCH"
    assert data["match_count"] >= 4
    assert data["mismatch_count"] == 0


def test_api_check_listing_ssrf_rejection():
    """Test POST /api/listing/check with private IP URL returns 400."""
    res = client.post("/api/listing/check", json={
        "mode": "URL",
        "url": "http://127.0.0.1:8000/internal-admin"
    })

    assert res.status_code == 400
    assert "SSRF Security Violation" in res.json()["detail"]


def test_api_get_package_targets():
    """Test GET /api/listing/package-targets returns recent packages for cross-comparison."""
    res = client.get("/api/listing/package-targets")
    assert res.status_code == 200
    data = res.json()
    assert "targets" in data
    assert "total" in data
    assert isinstance(data["targets"], list)
