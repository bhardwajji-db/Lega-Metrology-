import pytest
from models.schemas import ProductInfo, OCRWord, ProductImageEvidence
from extraction.extractor import LocalExtractor
from compliance.engine import ComplianceEngine
from compliance.rules.models import ComplianceStatus

def test_kissan_real_package_extraction_and_compliance():
    """
    Test generic statutory declaration extraction and evidence localization
    against real-world package OCR text from Kissan Fresh Tomato Ketchup.
    """
    front_text = """WITH
100%
kissan
FROM THE FARMER
SINCE1934
FRESH
TOMATO
KETCHUPO
PerServe
(15)
ical
20
1%
OFRDA^"""

    back_text = """kissan
TOMATOKETCHUP
INGREDIENTS:WATER,
TOMATO PASTELIPR%)
SUGAR,IODISED SALT,
ACIDITYREGULATOR-E260
STABILIZERS-E1422.E415
PRESERVATIVE-E211.ONION
POWDER.GARLIC POWDER,SPICES
AND CONDIMENTS
FOR MR INCL.OALL TAXES
USP,NETIGHTPKD.USE BY&
BATCH NO.PLEASE SEE BOTTOM
OFPACK
MKTD.BY:HINDUSTAN UNILEVER LTD.(HUL). UNILEVER
HOUSE,B.D.SAWANT MARG.CHAKALA.ANDHERI(E) MUMBAI
400099,MAHARASHTRA.FOR MFR.&MFG.UNIT ADDRESS,READ
DISTT.PATIALA,PUNJAB 140 401.FSSAI LIC.No.10014063000346
(S) SHIVAMBU INTERNATIONAL,MAHESH NAGAR,P.O.OEL,DISTT.UNA
HIMACHAL PRADESH177 206.FSSAI LIC.No10012062000187
(D) SAHYADRI FARMS POST HARVEST CARE LIMITED.GAT No.314/1,
314/2/1.A/P:MOHADI.TALUKA:DINDORI NASHIK. MAHARASHTRA
PRIVATE LIMITED,LALGANJ-FAKULI ROAD (NEAR RAILWAY CROSSING)
VILLAGE-KOWA MOHABBATPUR POST-LALGANJ, VAISHALI. BIHAR
844 121.FSSA1LIC.No.:10422999000151
Number of serves per pac-in.25
Per Serve:15 g(1Tbsp)
100 g Product Per Serve 15 g).% RDA^
Serve:Energy kcal133,201%Proteing
1.10.2Carbohydrate (g314.6Total
0]Sodium mg 948,1427%
HUL 2O14.IMITATION OF LABEL GRAPHICS IS A PUNISHABLE
OFFENCE.KISSAN IS A REGISTERED TRADEMARK OF HINDUSTAN
Hindusiar Unilever linited
LEVERCARE-QUERY/FEEDBACK
TOLLFREE:1800-10-22-221
POBOX 14760,MUMBAI400099
LEVER.CARE@UNILEVER.COM
FSSAI
Lic.No.10013022001897
SCAN HERE
KISSE
kissan
SE
M5g
g435g
5010.11/g
29/01/26"""

    combined_text = f"=== [FRONT LABEL] ===\n{front_text}\n\n=== [BACK LABEL] ===\n{back_text}"
    extractor = LocalExtractor()
    info = extractor.extract(combined_text)

    # 1. Product Name and Brand
    assert "Ketchup" in info.product_name
    assert "Kissan" in info.brand or "Kissan" in info.product_name
    assert "Unilever Tomato" != info.product_name

    # 2. Net Quantity: Must NOT be 15 g (serving size), must be 435 g
    assert info.net_quantity == "435 g"
    assert info.net_quantity != "15 g"

    # 3. Batch Number: Must NOT be "PLEASE"
    assert info.batch_number != "PLEASE"
    assert info.batch_number is None or info.batch_number in ("SE", "BN", "290126")

    # 4. Consumer Care
    assert info.consumer_care_phone == "1800-10-22-221"
    assert info.consumer_care_email == "LEVER.CARE@UNILEVER.COM"

    # 5. FSSAI License
    assert info.fssai_license == "10014063000346"

    # 6. Manufacturer
    assert "HINDUSTAN UNILEVER" in (info.manufacturer_name or info.manufacturer or "").upper()
    assert "400099" in (info.manufacturer_address or info.manufacturer or "")

    # 7. Compliance Engine Evaluation
    engine = ComplianceEngine()
    result = engine.check(info, ocr_text=combined_text, images=[])

    checks_by_id = {c.rule_id: c for c in result['checks']}

    # LM-001 (Manufacturer): PASS
    assert checks_by_id['LM-001'].status == ComplianceStatus.PASS.value

    # LM-002 (Generic Name): PASS
    assert checks_by_id['LM-002'].status == ComplianceStatus.PASS.value

    # LM-003 (Net Quantity): PASS
    assert checks_by_id['LM-003'].status == ComplianceStatus.PASS.value
    assert checks_by_id['LM-003'].detected_value == "435 g"

    # LM-004 (MRP): NEEDS_REVIEW (since price is faint on stamp)
    assert checks_by_id['LM-004'].status == ComplianceStatus.NEEDS_REVIEW.value

    # LM-005 (Consumer Care): PASS
    assert checks_by_id['LM-005'].status == ComplianceStatus.PASS.value

    # LM-008 (Date Marking for Food): NOT_APPLICABLE (Food Proviso)
    assert checks_by_id['LM-008'].status == ComplianceStatus.NOT_APPLICABLE.value

    # FS-001 (FSSAI): PASS
    assert checks_by_id['FS-001'].status == ComplianceStatus.PASS.value

    # FS-003 (Ingredients): PASS
    assert checks_by_id['FS-003'].status == ComplianceStatus.PASS.value

    # FS-005 (Date marking): PASS or NEEDS_REVIEW
    assert checks_by_id['FS-005'].status in (ComplianceStatus.PASS.value, ComplianceStatus.NEEDS_REVIEW.value)
