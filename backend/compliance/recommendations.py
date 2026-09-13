"""
Deterministic, evidence-linked Recommendation & Corrective Action Engine for MetrCheck AI.
Generates structured, rule-based recommendations covering all 13 statutory rules.
No external LLM or network requests are used.
"""

from typing import List, Optional
from models.schemas import ComplianceCheck, Recommendation


def generate_recommendation_for_check(check: ComplianceCheck) -> Recommendation:
    rule_id = check.rule_id
    status = (check.status or "").upper()
    domain = check.domain or ("FSSAI" if rule_id.startswith("FS-") else "LEGAL_METROLOGY")
    det_val = check.detected_value
    reason = check.reason or check.explanation or ""
    
    # Preserve evidence location and confidence
    img_label = check.evidence_image_label or "Back"
    region = check.evidence_region or "Evidence location unavailable — manual review required."
    conf = check.confidence
    
    source_name = check.source_name
    source_ref = check.source_reference
    source_url = check.source_url

    # 1. NOT_APPLICABLE
    if status == "NOT_APPLICABLE":
        if rule_id == "LM-008":
            rec_action = (
                "No corrective action required under this Legal Metrology rule. "
                "For this food product, applicable date-marking requirements are being evaluated under the FSSAI domain."
            )
        elif rule_id == "LM-006":
            rec_action = (
                "No corrective action required. Country-of-origin screening was not applicable "
                "based on the current domestic-product context."
            )
        else:
            rec_action = "No corrective action required. Not applicable based on the current package context."

        return Recommendation(
            rule_id=rule_id,
            domain=domain,
            status=status,
            priority="INFO",
            action_category="NO_ACTION",
            title=f"{check.field_label or rule_id} — Not Applicable",
            issue=reason or "Declaration not required for this commodity/package type.",
            recommended_action=rec_action,
            corrective_action=None,
            verification_step=None,
            evidence_image_label=img_label,
            evidence_region=region,
            confidence=conf,
            source_name=source_name,
            source_reference=source_ref,
            source_url=source_url,
            requires_human_review=False
        )

    # 2. PASS
    if status == "PASS":
        if rule_id == "FS-001":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="INFO",
                action_category="VERIFY_OFFICIAL_RECORD",
                title="FSSAI Licence / Registration",
                issue="FSSAI licence information was detected and its format/presence passed automated screening.",
                recommended_action=(
                    "No immediate corrective action required. "
                    "Live licence authenticity should be verified through the official FoSCoS system when required."
                ),
                corrective_action=None,
                verification_step="Verify licence status on official FoSCoS portal if validation is needed.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=False
            )
        elif rule_id == "LM-001":
            rec_action = "No corrective action required. Manufacturer/packer/importer information was detected during screening."
        elif rule_id == "LM-007":
            rec_action = "No corrective action required. Unit sale price declaration was detected during screening."
        elif rule_id == "FS-004":
            rec_action = "No corrective action required based on automated screening."
        else:
            rec_action = "No corrective action required. Requirement detected and passed automated screening."

        return Recommendation(
            rule_id=rule_id,
            domain=domain,
            status=status,
            priority="INFO",
            action_category="NO_ACTION",
            title=f"{check.field_label or rule_id} — Verified",
            issue=f"Requirement detected ({det_val})" if det_val else "Requirement detected and verified during screening.",
            recommended_action=rec_action,
            corrective_action=None,
            verification_step="Continue to maintain the declaration in the verified format.",
            evidence_image_label=img_label,
            evidence_region=region,
            confidence=conf,
            source_name=source_name,
            source_reference=source_ref,
            source_url=source_url,
            requires_human_review=False
        )

    # 3. NEEDS_REVIEW
    if status == "NEEDS_REVIEW":
        if rule_id == "LM-004":  # MRP
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify MRP Declaration",
                issue="MRP marking detected but numeric value could not be reliably read.",
                recommended_action=(
                    "Manually verify the MRP value in the package stamp area because "
                    "the MRP marking was detected but the numeric value could not be reliably read."
                ),
                corrective_action=(
                    "If the printed MRP is missing, incorrect, or unreadable on the physical package, "
                    "correct the marking as required before retail distribution, subject to applicable requirements."
                ),
                verification_step="Capture a clear image of the MRP stamp and re-run the analysis.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "FS-003":  # Ingredients
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Ingredients Declaration",
                issue=(
                    "Ingredients declaration was not detected in OCR. "
                    "The current image/OCR evidence is insufficient to confirm whether the declaration is present."
                ),
                recommended_action=(
                    "Manually inspect the package for the ingredients declaration. "
                    "The current image/OCR evidence is insufficient to confirm whether the declaration is present."
                ),
                corrective_action=(
                    "If the applicable ingredients declaration is actually absent, "
                    "review and correct the label before distribution."
                ),
                verification_step="Capture a clear image of the ingredients panel and re-run the analysis.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "FS-005":  # Date Marking
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Date Marking",
                issue=(
                    "Relative shelf-life was detected without a verified reference date, "
                    "or date information could not be fully verified from OCR evidence."
                ),
                recommended_action=(
                    "Manually verify the applicable date marking on the physical package. "
                    "A relative shelf-life statement was detected, but the required date information "
                    "could not be fully verified from the available OCR evidence."
                ),
                corrective_action=(
                    "If required date information is missing or incorrectly declared, "
                    "review and correct the package label according to the applicable FSSAI requirements."
                ),
                verification_step="Capture a clear image of the date-marking area and re-run the analysis.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "LM-001":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Manufacturer / Packer Declaration",
                issue=reason or "Manufacturer/packer details could not be fully verified from OCR evidence.",
                recommended_action="Manually verify the manufacturer/packer/importer name and applicable address details on the package.",
                corrective_action="Review and correct the applicable manufacturer, packer, or importer declaration before retail distribution if incomplete.",
                verification_step="Re-scan the relevant package panel and confirm the declaration is clearly readable.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "LM-002":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Common / Generic Name",
                issue=reason or "Commodity name declaration requires manual verification.",
                recommended_action="Verify that the package clearly declares the applicable common or generic name of the commodity.",
                corrective_action="Review the package and ensure the generic/common name is prominently displayed on the Principal Display Panel.",
                verification_step="Re-scan the front panel and confirm the commodity name declaration.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "LM-003":
            rec_act = (
                f"Verify that the detected net quantity '{det_val}' is the intended package declaration."
                if det_val else "Manually verify the net quantity and unit printed on the package."
            )
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Net Quantity Declaration",
                issue=reason or "Net quantity declaration could not be conclusively verified.",
                recommended_action=rec_act,
                corrective_action="Review and correct the net quantity declaration and verify the applicable measurement/unit requirements.",
                verification_step="Confirm the declared net weight/volume meets Legal Metrology standard units.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "LM-005":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Consumer Care Details",
                issue=reason or "Consumer care contact details require manual verification.",
                recommended_action="Verify that the applicable consumer-care contact details are complete and clearly readable on the package.",
                corrective_action="Ensure consumer care contact details (including phone, email, or physical address) are fully declared.",
                verification_step="Check that all required contact channels are clearly legible on the package.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "LM-006":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_APPLICABILITY",
                title="Verify Country of Origin",
                issue=reason or "Country of origin status could not be conclusively verified.",
                recommended_action="Verify whether the package is an imported product and, if so, verify the applicable country-of-origin declaration.",
                corrective_action="Review the applicable country-of-origin declaration for the imported package.",
                verification_step="Inspect package for imported commodity markings.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "LM-007":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_APPLICABILITY",
                title="Verify Unit Sale Price Applicability",
                issue=reason or "Unit sale price applicability could not be conclusively determined from available package evidence.",
                recommended_action="Verify the applicable unit sale price declaration manually against the current Legal Metrology requirements and package type.",
                corrective_action="If applicable under Rule 6(11), declare the Unit Sale Price rounded off to the nearest two decimal places.",
                verification_step="Manual legal verification is recommended because applicability could not be conclusively determined from the available package evidence.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "FS-001":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify FSSAI Licence Display",
                issue=reason or "FSSAI licence number requires manual inspection.",
                recommended_action="Manually verify the FSSAI licence information and package display.",
                corrective_action="Ensure 14-digit FSSAI licence number and logo are clearly printed on the food label.",
                verification_step="Check against official FoSCoS portal records.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "FS-002":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Name of Food",
                issue=reason or "Food name declaration requires manual verification.",
                recommended_action="Verify that the declared name of the food is clearly visible and accurately represents the product.",
                corrective_action="Review and ensure the true nature and name of the food is clearly declared on the Principal Display Panel.",
                verification_step="Re-scan the front label to confirm visibility.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        elif rule_id == "FS-004":
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title="Verify Nutrition Information Panel",
                issue=reason or "Nutrition information panel requires manual clarity verification.",
                recommended_action="Manually verify the nutrition information panel and ensure the relevant declarations are clearly readable.",
                corrective_action="Ensure statutory nutritional values per 100g/serving are conspicuously printed.",
                verification_step="Check print legibility of energy, protein, carbohydrate, and fat lines.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )
        else:
            return Recommendation(
                rule_id=rule_id,
                domain=domain,
                status=status,
                priority="MEDIUM",
                action_category="VERIFY_MANUALLY",
                title=f"Verify {check.field_label or rule_id}",
                issue=reason or "Manual verification recommended to confirm statutory declaration.",
                recommended_action=f"Manually verify {check.field_label or rule_id} on the physical package.",
                corrective_action="Review label printing quality and clarity for compliance verification.",
                verification_step="Re-scan the package with clear lighting and check declaration visibility.",
                evidence_image_label=img_label,
                evidence_region=region,
                confidence=conf,
                source_name=source_name,
                source_reference=source_ref,
                source_url=source_url,
                requires_human_review=True
            )

    # 4. WARNING
    if status == "WARNING":
        return Recommendation(
            rule_id=rule_id,
            domain=domain,
            status=status,
            priority="MEDIUM",
            action_category="VERIFY_MANUALLY",
            title=f"Review {check.field_label or rule_id} Declaration",
            issue=reason or "Potential formatting or legibility ambiguity detected.",
            recommended_action=f"Review {check.field_label or rule_id} printing quality and clarity for compliance verification.",
            corrective_action="Consider correcting the package declaration formatting if ambiguity is confirmed during manual review.",
            verification_step="Re-scan the package with higher resolution/lighting and verify legibility.",
            evidence_image_label=img_label,
            evidence_region=region,
            confidence=conf,
            source_name=source_name,
            source_reference=source_ref,
            source_url=source_url,
            requires_human_review=True
        )

    # 5. FAIL
    # (Confirmed non-compliance identified during automated screening)
    if rule_id == "LM-001":
        corr = "Review and correct the applicable manufacturer, packer, or importer declaration before retail distribution."
    elif rule_id == "LM-002":
        corr = "Review the package and add/correct the applicable common or generic commodity name."
    elif rule_id == "LM-003":
        corr = "Review and correct the net quantity declaration and verify the applicable measurement/unit requirements."
    elif rule_id == "LM-004":
        corr = "Review and correct the applicable MRP declaration before retail distribution."
    elif rule_id == "LM-006":
        corr = "Review the applicable country-of-origin declaration for the imported package."
    elif rule_id == "LM-007":
        corr = "Review and correct the applicable unit sale price declaration."
    elif rule_id == "FS-001":
        corr = "Review the FSSAI licence declaration on the package and verify the correct licence information through the appropriate official channel."
    elif rule_id == "FS-002":
        corr = "Review and correct the applicable food name declaration."
    elif rule_id == "FS-003":
        corr = "Review the applicable ingredients declaration and correct the label as required."
    elif rule_id == "FS-004":
        corr = "Review and correct the applicable nutrition information on the package."
    elif rule_id == "FS-005":
        corr = "Review and correct the package label according to the applicable FSSAI date-marking requirements."
    else:
        corr = f"Ensure the mandatory statutory declaration for {check.field_label or rule_id} is conspicuously printed on the package."

    return Recommendation(
        rule_id=rule_id,
        domain=domain,
        status=status,
        priority="HIGH",
        action_category="CORRECT_LABEL",
        title=f"Potential Non-Compliance — {check.field_label or rule_id}",
        issue=reason or f"Potential non-compliance identified: {check.field_label or rule_id} was not detected or does not meet statutory requirements.",
        recommended_action=f"Review and correct the applicable {check.field_label or rule_id} declaration before retail distribution.",
        corrective_action=corr,
        verification_step="Re-scan the package after label correction and verify compliance.",
        evidence_image_label=img_label,
        evidence_region=region,
        confidence=conf,
        source_name=source_name,
        source_reference=source_ref,
        source_url=source_url,
        requires_human_review=True
    )


def generate_recommendations(checks: List[ComplianceCheck]) -> List[Recommendation]:
    """
    Generate deterministic recommendations for all compliance checks in the order they appear.
    """
    recs: List[Recommendation] = []
    for c in checks:
        r = generate_recommendation_for_check(c)
        r.bbox = c.bbox
        r.bbox_x = c.bbox_x
        r.bbox_y = c.bbox_y
        r.bbox_width = c.bbox_width
        r.bbox_height = c.bbox_height
        r.evidence = c.evidence
        recs.append(r)
    return recs
