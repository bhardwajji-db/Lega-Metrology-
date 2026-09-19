import pytest
from extraction.extractor import LocalExtractor
from models.schemas import ProductInfo, ExtractionCandidate, FieldProvenance

@pytest.fixture
def extractor():
    return LocalExtractor()

def test_candidate_based_extraction_structure(extractor):
    text = (
        "ABC Foods Pvt Ltd\n"
        "MRP: Rs. 150.00 (Incl. of all taxes)\n"
        "Net Qty: 500 g\n"
        "Mfg Date: 05/2024\n"
        "Expiry Date: 05/2025\n"
        "Consumer Care: 1800-111-2222, support@abcfoods.com\n"
        "Country of Origin: India\n"
    )
    product_info = extractor.extract(text)
    assert isinstance(product_info, ProductInfo)
    assert hasattr(product_info, "candidates")
    assert hasattr(product_info, "field_status")
    assert isinstance(product_info.candidates, dict)
    assert isinstance(product_info.field_status, dict)

    expected_fields = [
        "mrp", "net_quantity", "manufacturer", "consumer_care",
        "manufacturing_date", "expiry_date", "country_of_origin"
    ]
    for field in expected_fields:
        assert field in product_info.field_status
        assert product_info.field_status[field] in ["FOUND", "NOT_FOUND", "UNCERTAIN", "CONFLICT", "NOT_APPLICABLE"]

    assert len(product_info.candidates.get("mrp", [])) >= 1
    mrp_cand = product_info.candidates["mrp"][0]
    assert isinstance(mrp_cand, ExtractionCandidate)
    assert mrp_cand.field == "mrp"
    assert "150" in mrp_cand.normalized_value
    assert mrp_cand.confidence > 0.5
    assert mrp_cand.validation_status == "FOUND"

def test_four_way_entity_role_separation(extractor):
    text = (
        "Manufactured by: Alpha Industries, Plot 10, Sector 5, Gurgaon - 122001, Haryana\n"
        "Packed by: Beta Packaging Ltd, Shed 4, Industrial Area, Bhiwadi - 301019, Rajasthan\n"
        "Marketed by: Gamma Brands Corp, 5th Floor, Tower B, Cyber City, Gurugram 122002\n"
        "Imported by: Delta Imports India Pvt Ltd, Port Area, Nhava Sheva, Navi Mumbai - 400707, Country of Origin: Germany\n"
        "MRP Rs. 999.00\n"
        "Net Wt: 1 kg\n"
    )
    product_info = extractor.extract(text)

    # 1. Manufacturer
    assert product_info.manufacturer_name is not None
    assert "Alpha Industries" in product_info.manufacturer_name
    assert "122001" in (product_info.manufacturer_address or "")
    assert product_info.field_status.get("manufacturer") == "FOUND"

    # 2. Packer
    assert product_info.packer_name is not None
    assert "Beta Packaging" in product_info.packer_name
    assert product_info.field_status.get("packer") == "FOUND"

    # 3. Marketed by
    assert product_info.marketed_by is not None
    assert "Gamma Brands" in product_info.marketed_by
    assert product_info.field_status.get("marketed_by") == "FOUND"

    # 4. Importer
    assert product_info.importer_name is not None
    assert "Delta Imports" in product_info.importer_name
    assert product_info.field_status.get("importer") == "FOUND"

def test_mrp_conflict_detection(extractor):
    text = (
        "Special Offer!\n"
        "MRP: Rs. 150.00 (Incl. of taxes)\n"
        "Sticker price: MRP Rs. 220.00\n"
        "Net Qty: 200 g\n"
        "Mfg by: Super Snacks Ltd, Mumbai 400001\n"
    )
    product_info = extractor.extract(text)
    assert product_info.field_status.get("mrp") == "CONFLICT"
    assert len(product_info.candidates.get("mrp", [])) >= 2
    for cand in product_info.candidates["mrp"]:
        assert cand.validation_status == "CONFLICT"
        assert cand.details is not None

def test_unprinted_mrp_uncertain_status(extractor):
    text = (
        "Pure Wheat Flour\n"
        "MRP Rs. [   ] (Inclusive of all taxes)\n"
        "Net Weight: 5 kg\n"
        "Mfg by: Flour Mills Ltd, Delhi 110001\n"
    )
    product_info = extractor.extract(text)
    assert product_info.field_status.get("mrp") == "UNCERTAIN"
    assert len(product_info.candidates.get("mrp", [])) >= 1
    cand = product_info.candidates["mrp"][0]
    assert cand.validation_status == "UNCERTAIN"
    assert "unprinted" in cand.details.lower() or "unprinted" in cand.raw_value.lower()

def test_chronological_date_conflict_detection(extractor):
    text = (
        "Mfg Date: 12/2025\n"
        "Expiry Date: 01/2024\n"
        "MRP Rs. 50\n"
        "Net Qty: 100 g\n"
        "Mfg by: Quick Pack, Noida 201301\n"
    )
    product_info = extractor.extract(text)
    assert product_info.field_status.get("manufacturing_date") == "CONFLICT"
    assert product_info.field_status.get("expiry_date") == "CONFLICT"
    mfg_cands = product_info.candidates.get("manufacturing_date", [])
    assert len(mfg_cands) >= 1
    assert mfg_cands[0].validation_status == "CONFLICT"

def test_spatial_provenance_multi_token_binding(extractor):
    ocr_tokens = [
        {"text": "MRP", "box": [10, 10, 50, 30], "confidence": 0.98},
        {"text": "Rs.", "box": [55, 10, 80, 30], "confidence": 0.97},
        {"text": "250.00", "box": [85, 10, 140, 30], "confidence": 0.99},
        {"text": "(Incl. of all taxes)", "box": [145, 10, 260, 30], "confidence": 0.95},
        {"text": "Net Weight:", "box": [10, 40, 100, 60], "confidence": 0.96},
        {"text": "500", "box": [105, 40, 135, 60], "confidence": 0.99},
        {"text": "g", "box": [140, 40, 155, 60], "confidence": 0.98},
        {"text": "Mfg by: Global Naturals Ltd", "box": [10, 70, 250, 90], "confidence": 0.94},
        {"text": "New Delhi 110001", "box": [10, 95, 180, 115], "confidence": 0.95}
    ]
    raw_text = "\n".join(tok["text"] for tok in ocr_tokens)
    product_info = extractor.extract(raw_text, ocr_data=ocr_tokens)
    assert product_info.field_provenance is not None
    assert "mrp" in product_info.field_provenance
    assert "net_quantity" in product_info.field_provenance
    assert "manufacturer" in product_info.field_provenance

def test_multilingual_indic_numeral_extraction(extractor):
    hindi_text = (
        "अधिकतम खुदरा मूल्य: रु ५०.००\n"
        "शुद्ध मात्रा: १०० ग्राम\n"
        "उत्पादक: नमस्ते फूड्स, जयपुर ३०२००१\n"
    )
    product_info = extractor.extract(hindi_text)
    assert "50" in product_info.mrp
    assert "100" in product_info.net_quantity
    assert "302001" in (product_info.manufacturer_address or "") or "३०२००१" in (product_info.manufacturer_address or "")
    assert product_info.field_status.get("mrp") == "FOUND"
    assert product_info.field_status.get("net_quantity") == "FOUND"

def test_fssai_and_barcode_candidate_recording(extractor):
    text = (
        "FSSAI Lic. No. 10012011000123\n"
        "8901030887123\n"
        "MRP Rs. 75.00\n"
        "Net Wt: 250 g\n"
        "Mfg: Fresh Daily Ltd, Kolkata 700001\n"
    )
    product_info = extractor.extract(text)
    assert product_info.fssai_license == "10012011000123"
    assert product_info.field_status.get("fssai_license") == "FOUND"
    assert product_info.barcode_detected == "8901030887123"
    assert product_info.field_status.get("barcode_detected") == "FOUND"
