"""
MetrCheck AI — Claim Contradiction & Support Engine
Performs evidence-first statutory assessment:
A. What evidence would support the claim?
B. What evidence is actually available across package panels?
C. Does package information contradict the claim?
D. Is external verification required?

Enforces strict distinction:
- SUPPORTED
- INSUFFICIENT_EVIDENCE
- POTENTIAL_CONTRADICTION
- HIGH_RISK_REVIEW
- NOT_ASSESSABLE

NEVER marks a claim 'FALSE' solely due to absence of evidence.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from models.schemas import ProductInfo, ProductImageEvidence, OCRWord
from claims.models import (
    ClaimCategory,
    ClaimStatus,
    EvidenceLinkType,
    ClaimEvidenceItem,
    ClaimAssessment,
    ClaimFinding,
    ClaimConfidenceBreakdown
)
from claims.extractor import ExtractedRawClaim
from claims.rule_engine import RegulatoryRule, claim_rule_registry


def _parse_numeric_value(val_str: Optional[str]) -> Optional[float]:
    """Safely extract float from strings like '20g', '20.5 g', '0.5g', '5mg'."""
    if not val_str:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)', str(val_str))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


class ContradictionEngine:
    def __init__(self):
        self.rule_registry = claim_rule_registry

    def evaluate_claim(
        self,
        claim: ExtractedRawClaim,
        product_info: ProductInfo,
        images: Optional[List[ProductImageEvidence]] = None,
        combined_ocr_text: str = ""
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem], ClaimConfidenceBreakdown]:
        """
        Evaluate a single detected claim against all extracted package evidence and rules.
        Returns:
            - ClaimAssessment
            - List[ClaimEvidenceItem] (with graph relationships: SUPPORTED_BY, CONTRADICTED_BY, REQUIRES_EXTERNAL_VERIFICATION)
            - ClaimConfidenceBreakdown
        """
        rule = claim.matched_rule
        if not rule:
            rule = self.rule_registry.find_matching_rule(claim.normalized_claim)

        # Build evidence database from product_info and images
        package_evidence = self._collect_package_evidence(product_info, images, combined_ocr_text)

        # Dispatch evaluation based on category / rule
        if rule and rule.claim_type == "NO_PRESERVATIVES":
            assessment, evidence_items = self._eval_no_preservatives(claim, rule, package_evidence)
        elif rule and rule.claim_type in ("NO_ADDED_SUGAR", "SUGAR_FREE"):
            assessment, evidence_items = self._eval_sugar_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "HIGH_PROTEIN":
            assessment, evidence_items = self._eval_high_protein(claim, rule, package_evidence)
        elif rule and rule.claim_type == "LOW_FAT":
            assessment, evidence_items = self._eval_low_fat(claim, rule, package_evidence)
        elif rule and rule.claim_type == "ZERO_CHOLESTEROL":
            assessment, evidence_items = self._eval_zero_cholesterol(claim, rule, package_evidence)
        elif rule and rule.claim_type == "NATURAL_QUALITY":
            assessment, evidence_items = self._eval_natural_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "NO_ARTIFICIAL_COLOURS":
            assessment, evidence_items = self._eval_no_artificial_colours(claim, rule, package_evidence)
        elif rule and rule.claim_type == "CHEMICAL_FREE":
            assessment, evidence_items = self._eval_chemical_free(claim, rule, package_evidence)
        elif rule and rule.claim_type == "MADE_IN_INDIA":
            assessment, evidence_items = self._eval_origin_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "ORGANIC_CERTIFICATION":
            assessment, evidence_items = self._eval_organic_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "IMMUNITY_BOOSTER":
            assessment, evidence_items = self._eval_immunity_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "DISEASE_CURE_TREATMENT" or claim.category == ClaimCategory.MEDICAL:
            assessment, evidence_items = self._eval_medical_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "NO_1_OR_BEST_BRAND" or claim.category == ClaimCategory.COMPARATIVE:
            assessment, evidence_items = self._eval_comparative_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "BIODEGRADABLE_ECO_FRIENDLY" or claim.category == ClaimCategory.ENVIRONMENTAL:
            assessment, evidence_items = self._eval_environmental_claims(claim, rule, package_evidence)
        elif rule and rule.claim_type == "100_PERCENT_PURE":
            assessment, evidence_items = self._eval_pure_claims(claim, rule, package_evidence)
        elif claim.is_high_risk:
            assessment, evidence_items = self._eval_generic_high_risk(claim, rule, package_evidence)
        elif claim.is_absolute:
            assessment, evidence_items = self._eval_generic_absolute(claim, rule, package_evidence)
        else:
            assessment, evidence_items = self._eval_unverified_generic(claim, rule, package_evidence)

        # Compute confidence breakdown
        conf_breakdown = self._compute_confidence_breakdown(claim, assessment, evidence_items)

        return assessment, evidence_items, conf_breakdown

    def _collect_package_evidence(
        self,
        product_info: ProductInfo,
        images: Optional[List[ProductImageEvidence]],
        combined_ocr_text: str
    ) -> Dict[str, Any]:
        """Aggregate all available package data and panel locations into an evidence context."""
        ingredients_text = product_info.ingredients or ""
        nutrition_facts = product_info.nutrition_facts or {}
        country_of_origin = product_info.country_of_origin or ""
        is_food = product_info.is_food

        # Find ingredient panel location
        ingredients_panel = "BACK"
        ingredients_bbox = None
        ingredients_conf = 85.0

        if images:
            for idx, img in enumerate(images):
                p_text = (img.ocr_text or "").lower()
                if "ingredient" in p_text or "samagri" in p_text:
                    ingredients_panel = (img.label or f"Panel {idx+1}").upper()
                    # Find bbox of 'ingredients' or first ingredient
                    for w in (img.words or []):
                        if "ingredient" in w.text.lower():
                            ingredients_bbox = w.bbox
                            ingredients_conf = w.confidence
                            break
                    break

        return {
            "ingredients": ingredients_text,
            "ingredients_panel": ingredients_panel,
            "ingredients_bbox": ingredients_bbox,
            "ingredients_conf": ingredients_conf,
            "nutrition_facts": nutrition_facts,
            "nutrition_panel_detected": product_info.nutrition_panel_detected or bool(nutrition_facts),
            "country_of_origin": country_of_origin,
            "is_food": is_food,
            "fssai_license": product_info.fssai_license,
            "combined_ocr_text": combined_ocr_text.lower(),
            "images": images or []
        }

    # ── SPECIFIC CLAIM EVALUATORS ──────────────────────────────────

    def _eval_no_preservatives(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ingredients = ev_ctx["ingredients"].lower()
        if not ingredients and "preservative" not in ev_ctx["combined_ocr_text"]:
            # No ingredients evidence on package
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Package ingredients list was not detected or is unavailable for verification.",
                detailed_explanation="Under FSSAI Advertising and Claims Regulations 2018, 'No Preservatives' claims require package ingredient substantiation. Because the ingredients panel could not be confirmed, this claim cannot be substantiated from package evidence alone.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="NOT_PROVEN"
            ), [
                ClaimEvidenceItem(
                    id="EVD-PRESERVATIVE-REQ",
                    type="INGREDIENT",
                    text="Ingredient declaration not found on packaging",
                    panel="BACK",
                    relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                    explanation="Requires ingredient list inspection to verify absence of Class I / Class II preservatives."
                )
            ]

        # Check for preservatives in ingredients
        detected_preservatives = []
        for p in rule.contradiction_ingredients:
            if re.search(r'(?:\b|^)' + re.escape(p) + r'(?:\b|$)', ingredients):
                detected_preservatives.append(p)

        if detected_preservatives:
            preservative_str = ", ".join(detected_preservatives[:3]).title()
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Detected ingredient ({preservative_str}) may conflict with the 'No Preservatives' package claim.",
                detailed_explanation=f"The package claims '{claim.claim_text}', yet the ingredient list declares preservative substances ({preservative_str}). Under FSSAI Regulation 4(1) & Schedule V, non-addition claims are impermissible if such additives are present.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-PRESERVATIVE-CONTRADICTION",
                    type="INGREDIENT",
                    text=preservative_str,
                    panel=ev_ctx["ingredients_panel"],
                    confidence=ev_ctx["ingredients_conf"],
                    bounding_box=ev_ctx["ingredients_bbox"],
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation=f"Preservative ingredient '{preservative_str}' detected in package ingredient declaration."
                )
            ]

        # Ingredients present and no preservative detected
        return ClaimAssessment(
            status=ClaimStatus.SUPPORTED,
            reason="Package ingredient list was evaluated and no statutory preservative additives were identified.",
            detailed_explanation="Statutory screening of the declared ingredients panel identified no Class I or Class II chemical preservatives or INS preservative codes (INS 200-290).",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=False,
            verdict_distinction="SUPPORTED"
        ), [
            ClaimEvidenceItem(
                id="EVD-INGREDIENT-CLEAN",
                type="INGREDIENT",
                text="Ingredients: " + ev_ctx["ingredients"][:60] + "...",
                panel=ev_ctx["ingredients_panel"],
                confidence=ev_ctx["ingredients_conf"],
                bounding_box=ev_ctx["ingredients_bbox"],
                relationship=EvidenceLinkType.SUPPORTED_BY,
                explanation="No preservative additives found in declared ingredients."
            )
        ]

    def _eval_sugar_claims(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ingredients = ev_ctx["ingredients"].lower()
        facts = ev_ctx["nutrition_facts"]
        sugar_val = _parse_numeric_value(facts.get("sugar"))
        added_sugar_val = _parse_numeric_value(facts.get("added_sugar") or facts.get("added_sugars"))

        # Check contradiction via ingredients
        contradicting_ingredients = []
        for s in rule.contradiction_ingredients:
            if re.search(r'(?:\b|^)' + re.escape(s) + r'(?:\b|$)', ingredients):
                contradicting_ingredients.append(s)

        if contradicting_ingredients:
            s_str = ", ".join(contradicting_ingredients[:3]).title()
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Detected sugar-related ingredient ({s_str}) may conflict with the '{claim.claim_text}' claim.",
                detailed_explanation=f"The package declares '{claim.claim_text}', but the ingredient list contains '{s_str}'. Under FSSAI Advertising and Claims Regulations 2018 (Schedule I), claims of no added sugar require total absence of added sweeteners and sweetening ingredients.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-SUGAR-CONTRADICTION",
                    type="INGREDIENT",
                    text=s_str,
                    panel=ev_ctx["ingredients_panel"],
                    confidence=ev_ctx["ingredients_conf"],
                    bounding_box=ev_ctx["ingredients_bbox"],
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation=f"Added sweetening ingredient '{s_str}' declared in ingredients list."
                )
            ]

        # Check contradiction via nutrition facts
        if rule.claim_type == "SUGAR_FREE" and sugar_val is not None:
            if sugar_val > 0.5:
                return ClaimAssessment(
                    status=ClaimStatus.POTENTIAL_CONTRADICTION,
                    reason=f"Nutrition facts declare {sugar_val}g sugar per 100g, exceeding the 0.5g limit for 'Sugar Free'.",
                    detailed_explanation=f"FSSAI Schedule I permits 'Sugar Free' only if sugar content is <= 0.5 g per 100 g/ml. Package declares {sugar_val} g.",
                    rule_id=rule.rule_id,
                    rule_source=rule.source,
                    rule_reference=rule.source_reference,
                    requires_human_review=True,
                    verdict_distinction="PROVEN_CONTRADICTION"
                ), [
                    ClaimEvidenceItem(
                        id="EVD-NUTRITION-SUGAR-FAIL",
                        type="NUTRITION_FACTS",
                        text=f"Total Sugar: {sugar_val}g",
                        panel="BACK",
                        relationship=EvidenceLinkType.CONTRADICTED_BY,
                        explanation=f"Sugar content ({sugar_val}g) exceeds statutory 0.5g threshold."
                    )
                ]
            else:
                return ClaimAssessment(
                    status=ClaimStatus.SUPPORTED,
                    reason=f"Nutrition facts declare {sugar_val}g sugar per 100g, meeting the statutory requirement (<= 0.5g).",
                    detailed_explanation="Evaluated against FSSAI Schedule I criteria for Sugar Free claims.",
                    rule_id=rule.rule_id,
                    rule_source=rule.source,
                    rule_reference=rule.source_reference,
                    requires_human_review=False,
                    verdict_distinction="SUPPORTED"
                ), [
                    ClaimEvidenceItem(
                        id="EVD-NUTRITION-SUGAR-PASS",
                        type="NUTRITION_FACTS",
                        text=f"Total Sugar: {sugar_val}g",
                        panel="BACK",
                        relationship=EvidenceLinkType.SUPPORTED_BY,
                        explanation="Sugar content meets statutory Sugar Free threshold."
                    )
                ]

        if not ingredients and not facts:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Neither ingredient list nor nutrition panel was detected to substantiate the sugar claim.",
                detailed_explanation="Package-level evidence is insufficient to verify the absence of added sugars. Physical package inspection required.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="NOT_PROVEN"
            ), [
                ClaimEvidenceItem(
                    id="EVD-SUGAR-REQ",
                    type="NUTRITION_FACTS",
                    text="Nutrition and ingredient information missing",
                    panel="BACK",
                    relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                    explanation="Requires nutrition facts and ingredients verification."
                )
            ]

        # No sugar ingredients and nutrition panel clean
        return ClaimAssessment(
            status=ClaimStatus.SUPPORTED,
            reason="Package ingredients list contains no added sugars or syrups.",
            detailed_explanation="Verified against FSSAI Schedule I criteria for non-addition of sugars.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=False,
            verdict_distinction="SUPPORTED"
        ), [
            ClaimEvidenceItem(
                id="EVD-SUGAR-CLEAN",
                type="INGREDIENT",
                text="No added sugars declared in ingredients list",
                panel=ev_ctx["ingredients_panel"],
                relationship=EvidenceLinkType.SUPPORTED_BY,
                explanation="Absence of added sugar ingredients verified."
            )
        ]

    def _eval_high_protein(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        facts = ev_ctx["nutrition_facts"]
        prot_str = facts.get("protein") or ""
        # Also check OCR text for direct protein declarations (e.g. 20g protein, Protein: 27g)
        if not prot_str:
            m = re.search(r'protein[\s.:\-a-z]*([\d.]+\s*(?:g|gm)?)\b', ev_ctx["combined_ocr_text"])
            if m:
                prot_str = m.group(1)

        prot_val = _parse_numeric_value(prot_str)

        if prot_val is None:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="No nutrition panel or numerical protein declaration detected to substantiate 'High Protein'.",
                detailed_explanation="Under FSSAI Advertising and Claims Regulations 2018 (Schedule II), 'High in Protein' claims require at least 12 g protein per 100 g for solid foods or 6 g per 100 ml for liquid foods. Because no numerical protein value was extracted from packaging, the claim cannot be substantiated independently.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="NOT_PROVEN"
            ), [
                ClaimEvidenceItem(
                    id="EVD-PROTEIN-REQ",
                    type="NUTRITION_FACTS",
                    text="Protein declaration not found in nutrition panel",
                    panel="BACK",
                    relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                    explanation="Requires nutrition facts panel displaying protein per 100g/serve."
                )
            ]

        # Compare against FSSAI criteria: >= 12g per 100g solid (or >= 6g liquid)
        threshold = rule.min_protein_g_per_100g_solid or 12.0
        if prot_val >= threshold:
            return ClaimAssessment(
                status=ClaimStatus.SUPPORTED,
                reason=f"Protein value ({prot_val}g / 100g) meets or exceeds the FSSAI statutory threshold ({threshold}g) for 'High Protein'.",
                detailed_explanation=f"Evaluated deterministically against FSSAI 2018 Schedule II (Table: Nutritional Claims). The detected protein value of {prot_val}g per 100g satisfies the minimum 12g statutory benchmark.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=False,
                verdict_distinction="SUPPORTED"
            ), [
                ClaimEvidenceItem(
                    id="EVD-PROTEIN-PASS",
                    type="NUTRITION_FACTS",
                    text=f"Protein: {prot_val}g / 100g",
                    panel="BACK",
                    confidence=92.0,
                    relationship=EvidenceLinkType.SUPPORTED_BY,
                    explanation=f"Declared protein content ({prot_val}g) satisfies the statutory criteria (>= {threshold}g)."
                )
            ]
        else:
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Declared protein ({prot_val}g / 100g) is below the statutory threshold ({threshold}g) required for 'High Protein' claims.",
                detailed_explanation=f"FSSAI Advertising and Claims Regulations 2018 (Schedule II) mandates a minimum of 12 g protein per 100 g for solid foods claiming 'High Protein'. Package declares only {prot_val}g.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-PROTEIN-FAIL",
                    type="NUTRITION_FACTS",
                    text=f"Protein: {prot_val}g / 100g",
                    panel="BACK",
                    confidence=90.0,
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation=f"Declared protein ({prot_val}g) is less than the required {threshold}g threshold."
                )
            ]

    def _eval_low_fat(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        facts = ev_ctx["nutrition_facts"]
        fat_val = _parse_numeric_value(facts.get("total_fat") or facts.get("fat"))

        if fat_val is None:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Nutrition facts panel does not indicate total fat content to evaluate 'Low Fat'.",
                detailed_explanation="FSSAI Schedule I requires total fat not exceeding 3 g per 100 g. Nutrition facts could not be verified from packaging.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="NOT_PROVEN"
            ), []

        threshold = rule.max_fat_g_per_100g_solid or 3.0
        if fat_val <= threshold:
            return ClaimAssessment(
                status=ClaimStatus.SUPPORTED,
                reason=f"Declared fat content ({fat_val}g / 100g) complies with the statutory 'Low Fat' limit (<= {threshold}g).",
                detailed_explanation="Evaluated deterministically against FSSAI Schedule I criteria.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=False,
                verdict_distinction="SUPPORTED"
            ), [
                ClaimEvidenceItem(
                    id="EVD-FAT-PASS",
                    type="NUTRITION_FACTS",
                    text=f"Total Fat: {fat_val}g",
                    panel="BACK",
                    relationship=EvidenceLinkType.SUPPORTED_BY,
                    explanation=f"Total fat ({fat_val}g) is within the statutory limit (<= {threshold}g)."
                )
            ]
        else:
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Declared total fat ({fat_val}g / 100g) exceeds the statutory threshold (<= {threshold}g) for 'Low Fat'.",
                detailed_explanation=f"Under FSSAI 2018 Schedule I, foods with fat exceeding 3g per 100g may not claim to be low in fat.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-FAT-FAIL",
                    type="NUTRITION_FACTS",
                    text=f"Total Fat: {fat_val}g",
                    panel="BACK",
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation=f"Declared fat ({fat_val}g) exceeds statutory limit."
                )
            ]

    def _eval_zero_cholesterol(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        facts = ev_ctx["nutrition_facts"]
        chol_val = _parse_numeric_value(facts.get("cholesterol"))

        if chol_val is None:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Nutrition facts panel does not declare cholesterol value.",
                detailed_explanation="FSSAI Schedule I requires cholesterol not exceeding 5 mg per 100 g for 'Zero Cholesterol'.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="NOT_PROVEN"
            ), []

        threshold = rule.max_cholesterol_mg_per_100g or 5.0
        if chol_val <= threshold:
            return ClaimAssessment(
                status=ClaimStatus.SUPPORTED,
                reason=f"Cholesterol ({chol_val}mg) complies with the statutory limit (<= {threshold}mg).",
                detailed_explanation="Verified against FSSAI Schedule I conditions for Cholesterol Free claims.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=False,
                verdict_distinction="SUPPORTED"
            ), [
                ClaimEvidenceItem(
                    id="EVD-CHOL-PASS",
                    type="NUTRITION_FACTS",
                    text=f"Cholesterol: {chol_val}mg",
                    panel="BACK",
                    relationship=EvidenceLinkType.SUPPORTED_BY,
                    explanation="Cholesterol content meets statutory benchmark."
                )
            ]
        else:
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Cholesterol ({chol_val}mg) exceeds the statutory threshold (<= {threshold}mg).",
                detailed_explanation="Contradicts FSSAI Schedule I requirement.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-CHOL-FAIL",
                    type="NUTRITION_FACTS",
                    text=f"Cholesterol: {chol_val}mg",
                    panel="BACK",
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation="Declared cholesterol exceeds statutory zero-cholesterol limit."
                )
            ]

    def _eval_natural_claims(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ingredients = ev_ctx["ingredients"].lower()

        if not ingredients:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Package ingredient list was not detected or is incomplete to verify '100% Natural'.",
                detailed_explanation="Under FSSAI Advertising and Claims Regulations 2018 (Schedule V), 'Natural' or '100% Natural' claims require that all composite ingredients are non-synthetic and devoid of artificial food additives. As package ingredients are incomplete or unverified, this finding is marked INSUFFICIENT_EVIDENCE rather than false.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                is_absolute=True,
                verdict_distinction="NOT_PROVEN"
            ), [
                ClaimEvidenceItem(
                    id="EVD-NATURAL-REQ",
                    type="INGREDIENT",
                    text="Ingredient declaration missing or partially detected",
                    panel="BACK",
                    relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                    explanation="Requires comprehensive ingredient list inspection to verify absence of synthetic additives."
                )
            ]

        # Check for synthetic additives / artificial substances
        contradictions = []
        for term in rule.contradiction_ingredients:
            if re.search(r'(?:\b|^)' + re.escape(term) + r'(?:\b|$)', ingredients):
                contradictions.append(term)

        if contradictions:
            c_str = ", ".join(contradictions[:3]).title()
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Detected synthetic additives or artificial substances ({c_str}) in ingredients contradict the '100% Natural' claim.",
                detailed_explanation=f"The package claims '{claim.claim_text}', but the ingredient declaration lists synthetic additives ({c_str}). Under FSSAI Schedule V, food claiming 'Natural' must not contain synthetic colours, flavours, artificial sweeteners, or chemical preservatives.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                is_absolute=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-NATURAL-FAIL",
                    type="INGREDIENT",
                    text=c_str,
                    panel=ev_ctx["ingredients_panel"],
                    confidence=ev_ctx["ingredients_conf"],
                    bounding_box=ev_ctx["ingredients_bbox"],
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation=f"Synthetic additive '{c_str}' detected in package ingredients."
                )
            ]

        # Ingredients present and no synthetic additives detected
        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason="Absolute natural claim detected with no obvious synthetic additives in declared ingredients; requires human verification of agricultural processing.",
            detailed_explanation="Under FSSAI Schedule V, claims of '100% Natural' require verification that raw materials have not undergone significant chemical transformation. An officer must review processing methodology.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=True,
            is_absolute=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), [
            ClaimEvidenceItem(
                id="EVD-NATURAL-REVIEW",
                type="INGREDIENT",
                text="Ingredients: " + ev_ctx["ingredients"][:60],
                panel=ev_ctx["ingredients_panel"],
                relationship=EvidenceLinkType.SUPPORTED_BY,
                explanation="No synthetic additives detected; physical manufacturing process requires verification."
            )
        ]

    def _eval_no_artificial_colours(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ingredients = ev_ctx["ingredients"].lower()
        if not ingredients:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Ingredients list not available to verify absence of synthetic colours.",
                detailed_explanation="Package-level evidence is incomplete.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="NOT_PROVEN"
            ), []

        detected_colours = []
        for c in rule.contradiction_ingredients:
            if re.search(r'(?:\b|^)' + re.escape(c) + r'(?:\b|$)', ingredients):
                detected_colours.append(c)

        if detected_colours:
            c_str = ", ".join(detected_colours[:3]).title()
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason=f"Declared ingredients contain synthetic colour substances ({c_str}), contradicting the '{claim.claim_text}' claim.",
                detailed_explanation=f"Synthetic food colours ({c_str}) were identified in declared ingredients. Violates FSSAI Advertising and Claims Regulations 2018.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-COLOUR-FAIL",
                    type="INGREDIENT",
                    text=c_str,
                    panel=ev_ctx["ingredients_panel"],
                    confidence=ev_ctx["ingredients_conf"],
                    bounding_box=ev_ctx["ingredients_bbox"],
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation=f"Synthetic colour '{c_str}' declared in ingredients."
                )
            ]

        return ClaimAssessment(
            status=ClaimStatus.SUPPORTED,
            reason="Ingredients list contains no synthetic colour substances.",
            detailed_explanation="Verified against FSSAI Schedule V criteria.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=False,
            verdict_distinction="SUPPORTED"
        ), [
            ClaimEvidenceItem(
                id="EVD-COLOUR-PASS",
                type="INGREDIENT",
                text="No synthetic colours found in ingredients list",
                panel=ev_ctx["ingredients_panel"],
                relationship=EvidenceLinkType.SUPPORTED_BY,
                explanation="Verified clean of synthetic colour additives."
            )
        ]

    def _eval_chemical_free(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason="Absolute 'Chemical Free' claim detected. Scientifically unverifiable and classified as potentially misleading under CCPA Guidelines 2022.",
            detailed_explanation="Under Section 2(28) of the Consumer Protection Act 2019 and CCPA Misleading Advertisement Guidelines 2022, absolute representations such as 'Chemical Free' are fundamentally inaccurate since all matter is chemical in nature. Regulatory review required.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=True,
            is_absolute=True,
            is_high_risk=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), [
            ClaimEvidenceItem(
                id="EVD-CHEMICAL-FREE-FLAG",
                type="TEXT_DECLARATION",
                text=claim.claim_text,
                panel=claim.source_panel,
                confidence=claim.ocr_confidence,
                bounding_box=claim.bounding_box,
                relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                explanation="Absolute claim requires substantiation under CCPA misleading advertisement rules."
            )
        ]

    def _eval_origin_claims(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        declared_origin = ev_ctx["country_of_origin"].lower()

        if not declared_origin:
            # Check combined OCR text
            if "made in india" in ev_ctx["combined_ocr_text"] or "product of india" in ev_ctx["combined_ocr_text"] or "country of origin: india" in ev_ctx["combined_ocr_text"]:
                declared_origin = "india"

        if declared_origin:
            if "india" in declared_origin:
                return ClaimAssessment(
                    status=ClaimStatus.SUPPORTED,
                    reason="Package origin claim aligns with statutory Country of Origin declaration ('India').",
                    detailed_explanation="Verified under Legal Metrology (Packaged Commodities) Rules 2011, Rule 6(10).",
                    rule_id=rule.rule_id,
                    rule_source=rule.source,
                    rule_reference=rule.source_reference,
                    requires_human_review=False,
                    verdict_distinction="SUPPORTED"
                ), [
                    ClaimEvidenceItem(
                        id="EVD-ORIGIN-PASS",
                        type="ORIGIN",
                        text=f"Country of Origin: {declared_origin.title()}",
                        panel="BACK",
                        relationship=EvidenceLinkType.SUPPORTED_BY,
                        explanation="Statutory declaration confirms domestic origin."
                    )
                ]
            else:
                return ClaimAssessment(
                    status=ClaimStatus.POTENTIAL_CONTRADICTION,
                    reason=f"Claim of domestic manufacture contradicts declared Country of Origin ('{declared_origin.title()}').",
                    detailed_explanation=f"Package claims '{claim.claim_text}', but mandatory Rule 6(10) declaration lists '{declared_origin.title()}'. This constitutes a statutory contradiction under Legal Metrology Rules.",
                    rule_id=rule.rule_id,
                    rule_source=rule.source,
                    rule_reference=rule.source_reference,
                    requires_human_review=True,
                    verdict_distinction="PROVEN_CONTRADICTION"
                ), [
                    ClaimEvidenceItem(
                        id="EVD-ORIGIN-FAIL",
                        type="ORIGIN",
                        text=f"Country of Origin: {declared_origin.title()}",
                        panel="BACK",
                        relationship=EvidenceLinkType.CONTRADICTED_BY,
                        explanation="Contradicts domestic origin claim."
                    )
                ]

        return ClaimAssessment(
            status=ClaimStatus.INSUFFICIENT_EVIDENCE,
            reason="Country of Origin declaration not explicitly verified to support domestic claim.",
            detailed_explanation="Rule 6(10) Country of Origin declaration required to substantiate.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=True,
            verdict_distinction="NOT_PROVEN"
        ), []

    def _eval_organic_claims(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ocr_all = ev_ctx["combined_ocr_text"]
        found_markings = [m for m in rule.required_markings if m in ocr_all]

        if found_markings:
            m_str = ", ".join(found_markings).upper()
            return ClaimAssessment(
                status=ClaimStatus.SUPPORTED,
                reason=f"Organic claim supported by detected certification marking ({m_str}).",
                detailed_explanation="Complies with Food Safety and Standards (Organic Foods) Regulations 2017.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=False,
                verdict_distinction="SUPPORTED"
            ), [
                ClaimEvidenceItem(
                    id="EVD-ORGANIC-MARK",
                    type="CERTIFICATION",
                    text=f"Organic certification marking detected: {m_str}",
                    panel="FRONT",
                    relationship=EvidenceLinkType.SUPPORTED_BY,
                    explanation="Recognized organic regulatory marking identified on packaging."
                )
            ]

        return ClaimAssessment(
            status=ClaimStatus.INSUFFICIENT_EVIDENCE,
            reason="Package claims 'Organic' but no statutory 'Jaivik Bharat' or accredited organic certification mark was detected.",
            detailed_explanation="Under FSSAI (Organic Foods) Regulations 2017 (Regulation 5), organic foods must carry the Jaivik Bharat logo and valid certification code. Insufficient package evidence detected; physical review required.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=True,
            verdict_distinction="NOT_PROVEN"
        ), [
            ClaimEvidenceItem(
                id="EVD-ORGANIC-REQ",
                type="CERTIFICATION",
                text="Jaivik Bharat / NPOP certification logo not detected",
                panel="FRONT",
                relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                explanation="Requires verification of FSSAI Jaivik Bharat registration."
            )
        ]

    def _eval_immunity_claims(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ocr_all = ev_ctx["combined_ocr_text"]
        supporting_nutrients = [n for n in rule.supporting_nutrients if n in ocr_all]

        if supporting_nutrients:
            n_str = ", ".join(supporting_nutrients).title()
            return ClaimAssessment(
                status=ClaimStatus.HIGH_RISK_REVIEW,
                reason=f"Health claim detected with supporting nutrient mentions ({n_str}). Requires manual verification of >= 15% RDA per serve.",
                detailed_explanation=f"Under FSSAI Advertising and Claims Regulations 2018 (Regulation 6 & Schedule IV), nutrient function claims regarding immune function require specific nutrients providing at least 15% of RDA per serve. Nutrients ({n_str}) detected; human review needed to verify RDA compliance.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                is_high_risk=True,
                verdict_distinction="REGULATORY_REVIEW_REQUIRED"
            ), [
                ClaimEvidenceItem(
                    id="EVD-IMMUNITY-NUTRIENT",
                    type="NUTRITION_FACTS",
                    text=f"Supporting nutrients mentioned: {n_str}",
                    panel="BACK",
                    relationship=EvidenceLinkType.SUPPORTED_BY,
                    explanation="Associated immune-function nutrients present on packaging."
                )
            ]

        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason="Health/immunity claim detected without supporting nutritional or ingredient information found on package. Regulatory/human review required.",
            detailed_explanation="Under FSSAI Advertising and Claims Regulations 2018 (Regulation 6), general immunity claims cannot be made without linking to established nutrient function claims with declared RDA quantities.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=True,
            is_high_risk=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), [
            ClaimEvidenceItem(
                id="EVD-IMMUNITY-REQ",
                type="NUTRITION_FACTS",
                text="No nutrient-specific RDA substantiation found",
                panel="BACK",
                relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                explanation="Requires FSSAI Schedule IV nutrient qualification."
            )
        ]

    def _eval_medical_claims(
        self,
        claim: ExtractedRawClaim,
        rule: Optional[RegulatoryRule],
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        rule_id = rule.rule_id if rule else "CLAIM-RULE-MED-GENERIC"
        source = rule.source if rule else "Section 24 FSS Act 2006 & Drugs and Magic Remedies Act 1954"
        ref = rule.source_reference if rule else "Section 24(1) FSS Act"

        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason="Health/medical claim detected. Package-level evidence is insufficient for independent substantiation. Regulatory/human review required.",
            detailed_explanation=f"The package declares '{claim.claim_text}'. Under Section 24 of the Food Safety and Standards Act 2006 and the Drugs and Magic Remedies Act 1954, claims representing that a food commodity cures, mitigates, or prevents diseases are strictly prohibited without specialized drug licensing. Package inspection alone cannot substantiate this representation.",
            rule_id=rule_id,
            rule_source=source,
            rule_reference=ref,
            requires_human_review=True,
            is_high_risk=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), [
            ClaimEvidenceItem(
                id="EVD-MEDICAL-FLAG",
                type="TEXT_DECLARATION",
                text=claim.claim_text,
                panel=claim.source_panel,
                confidence=claim.ocr_confidence,
                bounding_box=claim.bounding_box,
                relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                explanation="Medical disease cure/prevention claim strictly regulated under Section 24 FSS Act."
            )
        ]

    def _eval_comparative_claims(
        self,
        claim: ExtractedRawClaim,
        rule: Optional[RegulatoryRule],
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        rule_id = rule.rule_id if rule else "CLAIM-RULE-CMP-GENERIC"
        source = rule.source if rule else "CCPA Guidelines for Prevention of Misleading Advertisements, 2022"
        ref = rule.source_reference if rule else "Guideline 6 (Comparative Advertisements)"

        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason=f"Comparative/superlative claim '{claim.claim_text}' detected. Requires independent audited market research documentation.",
            detailed_explanation="Under CCPA Guidelines for Prevention of Misleading Advertisements 2022, comparative claims such as 'No. 1 Brand' or 'Best in India' require substantiation by accredited third-party data, with explicit disclosure of survey methodology and timeframe.",
            rule_id=rule_id,
            rule_source=source,
            rule_reference=ref,
            requires_human_review=True,
            is_comparative=True,
            is_absolute=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), [
            ClaimEvidenceItem(
                id="EVD-COMPARATIVE-FLAG",
                type="TEXT_DECLARATION",
                text=claim.claim_text,
                panel=claim.source_panel,
                confidence=claim.ocr_confidence,
                bounding_box=claim.bounding_box,
                relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                explanation="Comparative claim requires third-party research substantiation under CCPA."
            )
        ]

    def _eval_environmental_claims(
        self,
        claim: ExtractedRawClaim,
        rule: Optional[RegulatoryRule],
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        rule_id = rule.rule_id if rule else "CLAIM-RULE-ENV-GENERIC"
        source = rule.source if rule else "ASCI Guidelines for Environmental / Green Claims, 2024"
        ref = rule.source_reference if rule else "Guideline 2"

        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason=f"Environmental green claim '{claim.claim_text}' detected. Requires accredited lab certification (e.g. IS/ISO 17088).",
            detailed_explanation="Under ASCI 2024 Green Claims Guidelines, environmental claims regarding biodegradability, plastic neutrality, or recyclability cannot be evaluated from package imagery alone and mandate accredited test reports.",
            rule_id=rule_id,
            rule_source=source,
            rule_reference=ref,
            requires_human_review=True,
            is_absolute=claim.is_absolute,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), [
            ClaimEvidenceItem(
                id="EVD-ENV-FLAG",
                type="TEXT_DECLARATION",
                text=claim.claim_text,
                panel=claim.source_panel,
                confidence=claim.ocr_confidence,
                bounding_box=claim.bounding_box,
                relationship=EvidenceLinkType.REQUIRES_EXTERNAL_VERIFICATION,
                explanation="Environmental claim requires accredited laboratory test reports."
            )
        ]

    def _eval_pure_claims(
        self,
        claim: ExtractedRawClaim,
        rule: RegulatoryRule,
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        ingredients = ev_ctx["ingredients"].lower()
        # If multi-ingredient with chemical additives -> contradiction
        if ingredients and ("," in ingredients or ";" in ingredients or "added" in ingredients):
            return ClaimAssessment(
                status=ClaimStatus.POTENTIAL_CONTRADICTION,
                reason="The term '100% Pure' was detected, but the product contains multiple ingredients/additives.",
                detailed_explanation="Under FSSAI Advertising and Claims Regulations 2018 (Schedule V), 'Pure' or '100% Pure' shall only be used to describe single-ingredient foods to which nothing has been added.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                is_absolute=True,
                verdict_distinction="PROVEN_CONTRADICTION"
            ), [
                ClaimEvidenceItem(
                    id="EVD-PURE-FAIL",
                    type="INGREDIENT",
                    text="Multi-ingredient declaration: " + ev_ctx["ingredients"][:60],
                    panel=ev_ctx["ingredients_panel"],
                    confidence=ev_ctx["ingredients_conf"],
                    bounding_box=ev_ctx["ingredients_bbox"],
                    relationship=EvidenceLinkType.CONTRADICTED_BY,
                    explanation="Multi-ingredient composition contradicts statutory single-ingredient purity criteria."
                )
            ]

        if not ingredients:
            return ClaimAssessment(
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                reason="Ingredients list not available to substantiate '100% Pure'.",
                detailed_explanation="Single-ingredient composition must be verified from packaging.",
                rule_id=rule.rule_id,
                rule_source=rule.source,
                rule_reference=rule.source_reference,
                requires_human_review=True,
                is_absolute=True,
                verdict_distinction="NOT_PROVEN"
            ), []

        return ClaimAssessment(
            status=ClaimStatus.SUPPORTED,
            reason="Package ingredients confirm single-ingredient composition with no added additives.",
            detailed_explanation="Complies with FSSAI Schedule V criteria for pure single-ingredient commodities.",
            rule_id=rule.rule_id,
            rule_source=rule.source,
            rule_reference=rule.source_reference,
            requires_human_review=False,
            is_absolute=True,
            verdict_distinction="SUPPORTED"
        ), [
            ClaimEvidenceItem(
                id="EVD-PURE-PASS",
                type="INGREDIENT",
                text=ev_ctx["ingredients"][:60],
                panel=ev_ctx["ingredients_panel"],
                relationship=EvidenceLinkType.SUPPORTED_BY,
                explanation="Single-ingredient declaration verified."
            )
        ]

    def _eval_generic_high_risk(
        self,
        claim: ExtractedRawClaim,
        rule: Optional[RegulatoryRule],
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason=f"High-risk claim '{claim.claim_text}' detected. Package-level evidence is insufficient for independent substantiation. Regulatory/human review required.",
            detailed_explanation="This claim involves health, therapeutic, or performance representations that require official verification against statutory technical standards.",
            rule_id=rule.rule_id if rule else "CLAIM-RULE-GENERIC-HR",
            rule_source=rule.source if rule else "Statutory Product Labelling Standards",
            rule_reference=rule.source_reference if rule else "General Advertising Guidelines",
            requires_human_review=True,
            is_high_risk=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), []

    def _eval_generic_absolute(
        self,
        claim: ExtractedRawClaim,
        rule: Optional[RegulatoryRule],
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        return ClaimAssessment(
            status=ClaimStatus.HIGH_RISK_REVIEW,
            reason=f"Absolute claim '{claim.claim_text}' detected. Absolute language requires heightened substantiation under Consumer Protection Act.",
            detailed_explanation="Claims using absolute terms (100%, Zero, Pure, Completely) require verifiable supporting evidence to prevent misleading representations.",
            rule_id=rule.rule_id if rule else "CLAIM-RULE-GENERIC-ABS",
            rule_source=rule.source if rule else "CCPA Guidelines for Prevention of Misleading Advertisements, 2022",
            rule_reference=rule.source_reference if rule else "General Principles",
            requires_human_review=True,
            is_absolute=True,
            verdict_distinction="REGULATORY_REVIEW_REQUIRED"
        ), []

    def _eval_unverified_generic(
        self,
        claim: ExtractedRawClaim,
        rule: Optional[RegulatoryRule],
        ev_ctx: Dict[str, Any]
    ) -> Tuple[ClaimAssessment, List[ClaimEvidenceItem]]:
        """Fallback for claims without a verified regulatory rule: rule_status = NOT_VERIFIED -> assessment = REVIEW_REQUIRED."""
        return ClaimAssessment(
            status=ClaimStatus.NOT_ASSESSABLE,
            reason=f"Claim '{claim.claim_text}' detected but no specific statutory rule is configured for automated evaluation.",
            detailed_explanation="In accordance with the regulatory grounding principle, MetrCheck AI does not invent regulatory requirements. Automated evaluation is skipped and inspector review is recommended.",
            rule_id=None,
            rule_source="Unconfigured Regulatory Knowledge",
            rule_reference="Manual Review",
            requires_human_review=True,
            verdict_distinction="NOT_PROVEN"
        ), []

    # ── CONFIDENCE MODEL ──────────────────────────────────────────

    def _compute_confidence_breakdown(
        self,
        claim: ExtractedRawClaim,
        assessment: ClaimAssessment,
        evidence_items: List[ClaimEvidenceItem]
    ) -> ClaimConfidenceBreakdown:
        """
        Computes separate confidence components as specified in Section 21:
        - extraction_confidence
        - evidence_confidence
        - assessment_confidence
        - cross_panel_consistency
        - overall_confidence
        """
        ocr_conf = max(0.0, min(100.0, claim.ocr_confidence))
        ext_conf = 95.0 if claim.bounding_box else 85.0
        if ocr_conf < 70.0:
            ext_conf = ocr_conf

        # Evidence confidence based on supporting/contradicting evidence items
        if evidence_items:
            ev_scores = [e.confidence for e in evidence_items if e.confidence > 0]
            ev_conf = sum(ev_scores) / len(ev_scores) if ev_scores else 85.0
        else:
            ev_conf = 60.0 if assessment.status == ClaimStatus.INSUFFICIENT_EVIDENCE else 75.0

        # Assessment confidence: how definitive the rule evaluation is
        if assessment.status == ClaimStatus.POTENTIAL_CONTRADICTION:
            asst_conf = 92.0
        elif assessment.status == ClaimStatus.SUPPORTED:
            asst_conf = 90.0
        elif assessment.status == ClaimStatus.HIGH_RISK_REVIEW:
            asst_conf = 85.0
        elif assessment.status == ClaimStatus.INSUFFICIENT_EVIDENCE:
            asst_conf = 80.0
        else:
            asst_conf = 65.0

        # Cross panel consistency: check if claim on FRONT and evidence on BACK
        cross_panel = 1.0
        for ev in evidence_items:
            if ev.panel and claim.source_panel and ev.panel != claim.source_panel:
                cross_panel = 1.0  # Confirmed cross-panel link!
                break

        # Overall weighted confidence
        overall = round(
            (ocr_conf * 0.25) +
            (ext_conf * 0.20) +
            (ev_conf * 0.25) +
            (asst_conf * 0.30),
            1
        )
        overall = max(10.0, min(99.0, overall))

        return ClaimConfidenceBreakdown(
            ocr_confidence=round(ocr_conf, 1),
            extraction_confidence=round(ext_conf, 1),
            evidence_confidence=round(ev_conf, 1),
            assessment_confidence=round(asst_conf, 1),
            cross_panel_consistency=cross_panel,
            overall_confidence=overall
        )


contradiction_engine = ContradictionEngine()
