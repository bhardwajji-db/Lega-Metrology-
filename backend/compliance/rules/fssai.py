import re
from typing import Dict, Any, Tuple, Optional
from models.schemas import ProductInfo, ComplianceCheck, ComplianceIssue
from compliance.rules.models import RuleDomain, ComplianceStatus, RuleDefinition

FSSAI_RULES: Dict[str, RuleDefinition] = {
    "FS-001": RuleDefinition(
        id="FS-001",
        domain=RuleDomain.FSSAI,
        title="FSSAI Logo and Licence Number",
        requirement="The FSSAI logo and licence number of the food business operator shall be displayed on the principal display panel or information panel in accordance with Regulation 5(4).",
        applicability_description="Mandatory for all pre-packaged food commodities under FSSAI Labelling Regulations.",
        source_name="Food Safety and Standards (Labelling and Display) Regulations, 2020",
        source_reference="Regulation 5(4)",
        source_url="https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Labelling_Display_23_09_2021.pdf",
        authority="Food Safety and Standards Authority of India (FSSAI), Ministry of Health & Family Welfare, GoI",
        amendment_version="F.No. 1-94/FSSAI/SP(L&C)/2017 dated 17 Nov 2020; Amendments: 10 Sep 2021, 9 Sep 2022, 11 Oct 2022, 8 Aug 2025, 24 Mar 2026",
        effective_date="1 Jul 2022 (Consolidated current enforcement as of September 2026)",
        currently_effective=True,
        future_effective_notes="24 March 2026 amendment comes into force on 1 July 2027 (Future-effective; does not alter current presence requirement).",
        last_verified="September 2026",
        screening_scope="Statutory Presence & 14-Digit Format Screening (Authenticity not externally queried)",
        severity="high",
        evidence_fields=["fssai_license"],
        version="2020.amended"
    ),
    "FS-002": RuleDefinition(
        id="FS-002",
        domain=RuleDomain.FSSAI,
        title="Name of Food",
        requirement="Every pre-packaged food shall carry a name indicating the true nature of the food on the principal display panel.",
        applicability_description="Mandatory for all pre-packaged food products under Regulation 5(1).",
        source_name="Food Safety and Standards (Labelling and Display) Regulations, 2020",
        source_reference="Regulation 5(1)",
        source_url="https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Labelling_Display_23_09_2021.pdf",
        authority="Food Safety and Standards Authority of India (FSSAI), Ministry of Health & Family Welfare, GoI",
        amendment_version="F.No. 1-94/FSSAI/SP(L&C)/2017 dated 17 Nov 2020; Amendments: 10 Sep 2021, 9 Sep 2022, 11 Oct 2022, 8 Aug 2025, 24 Mar 2026",
        effective_date="1 Jul 2022 (Consolidated current enforcement as of September 2026)",
        currently_effective=True,
        future_effective_notes="24 March 2026 amendment comes into force on 1 July 2027 (Future-effective; does not alter current presence requirement).",
        last_verified="September 2026",
        screening_scope="Statutory Presence & Food Identity Screening",
        severity="high",
        evidence_fields=["product_name"],
        version="2020.amended"
    ),
    "FS-003": RuleDefinition(
        id="FS-003",
        domain=RuleDomain.FSSAI,
        title="List of Ingredients",
        requirement="Except for single ingredient foods, a list of ingredients shall be declared on the label in descending order of their composition by weight or volume.",
        applicability_description="Mandatory for multi-ingredient pre-packaged foods. Single-ingredient foods are exempt under Regulation 5(2)(a).",
        source_name="Food Safety and Standards (Labelling and Display) Regulations, 2020",
        source_reference="Regulation 5(2)",
        source_url="https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Labelling_Display_23_09_2021.pdf",
        authority="Food Safety and Standards Authority of India (FSSAI), Ministry of Health & Family Welfare, GoI",
        amendment_version="F.No. 1-94/FSSAI/SP(L&C)/2017 dated 17 Nov 2020; Amendments: 10 Sep 2021, 9 Sep 2022, 11 Oct 2022, 8 Aug 2025, 24 Mar 2026",
        effective_date="1 Jul 2022 (Consolidated current enforcement as of September 2026)",
        currently_effective=True,
        future_effective_notes="24 March 2026 amendment comes into force on 1 July 2027 (Future-effective; does not alter current presence requirement).",
        last_verified="September 2026",
        screening_scope="Statutory Presence Screening (Descending order declaration)",
        severity="medium",
        evidence_fields=["ingredients"],
        version="2020.amended"
    ),
    "FS-004": RuleDefinition(
        id="FS-004",
        domain=RuleDomain.FSSAI,
        title="Nutritional Information Panel",
        requirement="Nutritional information per 100g or 100ml or per single consumption pack including energy, protein, carbohydrate, total sugars, added sugars, total fat, saturated fat, trans fat and sodium.",
        applicability_description="Mandatory for pre-packaged foods under Regulation 5(3), subject to statutory exemptions (e.g. raw unprocessed single commodities).",
        source_name="Food Safety and Standards (Labelling and Display) Regulations, 2020",
        source_reference="Regulation 5(3)",
        source_url="https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Labelling_Display_23_09_2021.pdf",
        authority="Food Safety and Standards Authority of India (FSSAI), Ministry of Health & Family Welfare, GoI",
        amendment_version="F.No. 1-94/FSSAI/SP(L&C)/2017 dated 17 Nov 2020; Amendments: 10 Sep 2021, 9 Sep 2022, 11 Oct 2022, 8 Aug 2025, 24 Mar 2026",
        effective_date="1 Jul 2022 (Consolidated current enforcement as of September 2026)",
        currently_effective=True,
        future_effective_notes="24 March 2026 amendment comes into force on 1 July 2027 (Future-effective; does not alter current presence requirement).",
        last_verified="September 2026",
        screening_scope="Statutory Presence Screening (Nutritional table fields: Energy, Protein, Fat, Carbs, Sugars, Sodium)",
        severity="high",
        evidence_fields=["nutritional_info", "nutrition_facts"],
        version="2020.amended"
    ),
    "FS-005": RuleDefinition(
        id="FS-005",
        domain=RuleDomain.FSSAI,
        title="Date Marking (Best Before / Expiry / Use By)",
        requirement="'Date of manufacture' and 'Expiry Date' or 'Best Before' declaration specifying month and year or days/months of shelf life shall be declared on food packages.",
        applicability_description="Mandatory for all pre-packaged foods under Regulation 5(10).",
        source_name="Food Safety and Standards (Labelling and Display) Regulations, 2020",
        source_reference="Regulation 5(10)",
        source_url="https://www.fssai.gov.in/upload/uploadfiles/files/Compendium_Labelling_Display_23_09_2021.pdf",
        authority="Food Safety and Standards Authority of India (FSSAI), Ministry of Health & Family Welfare, GoI",
        amendment_version="F.No. 1-94/FSSAI/SP(L&C)/2017 dated 17 Nov 2020; Amendments: 10 Sep 2021, 9 Sep 2022, 11 Oct 2022, 8 Aug 2025, 24 Mar 2026",
        effective_date="1 Jul 2022 (Consolidated current enforcement as of September 2026)",
        currently_effective=True,
        future_effective_notes="24 March 2026 amendment comes into force on 1 July 2027 (Future-effective; does not alter current presence requirement).",
        last_verified="September 2026",
        screening_scope="Statutory Presence Screening (Expiry date or relative shelf life with mfg date)",
        severity="high",
        evidence_fields=["best_before", "expiry_date"],
        version="2020.amended"
    )
}

def evaluate_fs_001(info: ProductInfo, context: Dict[str, Any], ocr_text: str) -> Tuple[ComplianceStatus, str, Optional[str]]:
    if not context.get('is_food', False):
        return ComplianceStatus.NOT_APPLICABLE, "Non-food commodity; FSSAI licence requirement is not applicable", None
    val = info.fssai_license
    conf = info.declaration_confidences.get('fssai_license', 85.0)
    if val and len(val) == 14 and val.isdigit():
        if conf >= 70:
            return ComplianceStatus.PASS, f"14-digit FSSAI licence number format detected: '{val}' (Authenticity not externally queried)", val
        return ComplianceStatus.WARNING, f"Plausible 14-digit FSSAI licence format detected with moderate confidence ({conf}%): '{val}'", val
    if re.search(r'\b(?:FSSAI|Lic\.?\s*No)\b', ocr_text, re.IGNORECASE):
        return ComplianceStatus.NEEDS_REVIEW, "FSSAI licence marking detected but 14-digit number was unreadable by OCR", None
    return ComplianceStatus.FAIL, "FSSAI licence number or logo was not detected on food package", None

def evaluate_fs_002(info: ProductInfo, context: Dict[str, Any], ocr_text: str) -> Tuple[ComplianceStatus, str, Optional[str]]:
    if not context.get('is_food', False):
        return ComplianceStatus.NOT_APPLICABLE, "Non-food commodity; FSSAI food naming regulation is not applicable", None
    val = info.product_name
    conf = info.declaration_confidences.get('product_name', 85.0)
    if val and len(val.strip()) >= 2:
        if conf >= 70:
            return ComplianceStatus.PASS, f"Food name declared: '{val}'", val
        return ComplianceStatus.WARNING, f"Food name declared with moderate confidence ({conf}%): '{val}'", val
    if not ocr_text or len(ocr_text.split()) < 30:
        return ComplianceStatus.NEEDS_REVIEW, "Label text insufficient to confirm food name declaration", None
    return ComplianceStatus.NEEDS_REVIEW, "Food name could not be reliably extracted from the available image/OCR evidence; manual verification is required", None

def evaluate_fs_003(info: ProductInfo, context: Dict[str, Any], ocr_text: str) -> Tuple[ComplianceStatus, str, Optional[str]]:
    if not context.get('is_food', False):
        return ComplianceStatus.NOT_APPLICABLE, "Non-food commodity; FSSAI ingredient listing requirement is not applicable", None
    if context.get('is_single_ingredient', False):
        return ComplianceStatus.NOT_APPLICABLE, "Single-ingredient food commodity; exempt from ingredients listing under Regulation 5(2)(a)", None
    
    val = info.ingredients
    conf = info.declaration_confidences.get('ingredients', 80.0)
    decl_detected = bool(
        (info.other_declarations and info.other_declarations.get('ingredient_declaration_detected')) or
        re.search(r'\b(?:INGREDIENTS?|INOREDIENTS?|INGREDENTS?|COMPOSITION|CONTAINS|SAMAGRI|सामग्री|घटक)\b', ocr_text, re.IGNORECASE)
    )

    # 1. Ingredients declaration detected on physical package
    if val and len(val.strip()) >= 5:
        if conf >= 70 or decl_detected:
            return ComplianceStatus.PASS, f"Ingredients section declared: '{val[:80]}...'", val
        return ComplianceStatus.NEEDS_REVIEW, f"Ingredients detected with low OCR confidence ({conf}%); manual verification required: '{val[:80]}...'", val

    # 2. Clearly confirmed absent from a reliably inspected relevant region -> FAIL
    if (context.get('confirmed_missing_ingredients') or 
        context.get('ingredients_confirmed_absent') or 
        (info.other_declarations and info.other_declarations.get('ingredients_confirmed_absent')) or
        (info.extraction_mode == 'demo' and not val)):
        return ComplianceStatus.FAIL, "List of ingredients confirmed absent from inspected food package in violation of Regulation 5(2)", None

    # 3. Ingredients header detected, but list details could not be reliably extracted by OCR -> NEEDS_REVIEW
    if decl_detected:
        return ComplianceStatus.NEEDS_REVIEW, "Ingredients header detected, but list details could not be reliably extracted by OCR", None

    # 4. OCR non-detection or low OCR confidence -> NEEDS_REVIEW (NOT confirmed absent)
    return ComplianceStatus.NEEDS_REVIEW, "Ingredients declaration not detected in OCR; manual visual verification required to confirm presence on container", None

def evaluate_fs_004(info: ProductInfo, context: Dict[str, Any], ocr_text: str) -> Tuple[ComplianceStatus, str, Optional[str]]:
    if not context.get('is_food', False):
        return ComplianceStatus.NOT_APPLICABLE, "Non-food commodity; FSSAI nutrition information requirement is not applicable", None
    if context.get('is_single_ingredient', False):
        return ComplianceStatus.NOT_APPLICABLE, "Single-ingredient raw food commodity; exempt from mandatory nutrition labelling under Regulation 5(3)", None
    nut_text = info.nutritional_info
    nut_facts = info.nutrition_facts
    if nut_facts and len(nut_facts) >= 2 or (nut_text and "panel detected" in nut_text.lower()):
        return ComplianceStatus.PASS, "Nutritional information panel detected on food label", nut_text or "Panel Detected"
    if re.search(r'\b(?:NUTRITION|NUTRIENTS|PER\s*100[gG]|ENERGY|PROTEIN)\b', ocr_text, re.IGNORECASE):
        return ComplianceStatus.NEEDS_REVIEW, "Nutritional information markings detected, but complete nutrient breakdown was unreadable by OCR", None
    return ComplianceStatus.FAIL, "Nutritional information panel was not detected", None

def evaluate_fs_005(info: ProductInfo, context: Dict[str, Any], ocr_text: str) -> Tuple[ComplianceStatus, str, Optional[str]]:
    if not context.get('is_food', False):
        return ComplianceStatus.NOT_APPLICABLE, "Non-food commodity; FSSAI date marking requirement is not applicable", None
    
    mfg = info.manufacturing_date or getattr(info, 'manufacture_date', None)
    pkd = getattr(info, 'packaging_date', None)
    exp = info.expiry_date
    use_by = getattr(info, 'use_by_date', None)
    bb = info.best_before
    rel = getattr(info, 'relative_shelf_life', None)
    
    # Check if a calendar date was detected for mfg / pkd
    has_valid_ref_date = bool((mfg and re.search(r'\d', mfg)) or (pkd and re.search(r'\d', pkd)))
    
    # 1. Absolute Expiry Date or Use-by Date declared
    if exp and re.search(r'\b\d{1,2}[/-]\d{2,4}\b', exp):
        ref_text = f" (Mfg/Pkd: {mfg or pkd})" if has_valid_ref_date else ""
        return ComplianceStatus.PASS, f"Expiry date declared: '{exp}'{ref_text}", exp
    if use_by and re.search(r'\b\d{1,2}[/-]\d{2,4}\b', use_by):
        ref_text = f" (Mfg/Pkd: {mfg or pkd})" if has_valid_ref_date else ""
        return ComplianceStatus.PASS, f"Use-by date declared: '{use_by}'{ref_text}", use_by

    # 2. Best Before with explicit calendar date (e.g. MM/YYYY)
    if bb and re.search(r'\b\d{1,2}[/-]\d{2,4}\b', bb):
        return ComplianceStatus.PASS, f"Best before date declared: '{bb}'", bb

    # 3. Relative shelf-life (e.g., "12 MONTHS FROM MANUFACTURE")
    if rel or (bb and 'MONTHS FROM' in bb.upper()):
        detected_rel = rel or bb
        if has_valid_ref_date:
            return ComplianceStatus.PASS, f"Relative shelf-life declared ('{detected_rel}') with verified reference date ('{mfg or pkd}')", f"{detected_rel} (Mfg: {mfg or pkd})"
        return ComplianceStatus.NEEDS_REVIEW, "Relative shelf-life declaration detected, but the required date marking could not be fully verified from the available OCR evidence.", detected_rel

    # 4. If only manufacturing date is declared on a food item without expiry / shelf life
    if has_valid_ref_date:
        return ComplianceStatus.WARNING, f"Manufacturing date declared ('{mfg or pkd}'), but expiry / shelf-life duration could not be fully verified", (mfg or pkd)

    # 5. Header detected in OCR but values unreadable
    if re.search(r'\b(?:BEST\s*BEFORE|EXP|EXPIRY|USE\s*BY|MFG|MFD|DATE\s*OF\s*MFG)\b', ocr_text, re.IGNORECASE):
        return ComplianceStatus.NEEDS_REVIEW, "Date marking label detected but shelf life / expiry value was unreadable by OCR", None

    return ComplianceStatus.FAIL, "Date marking (Best Before / Expiry / Use By) was not detected", None
