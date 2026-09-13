from typing import List, Dict, Any, Optional
from models.schemas import ProductInfo, ComplianceCheck, ComplianceIssue, ProductImageEvidence
from compliance.rules.registry import registry
from compliance.rules.applicability import PackageContext
from compliance.rules.models import ComplianceStatus, RuleDomain
from compliance.rules.legal_metrology import (
    evaluate_lm_001, evaluate_lm_002, evaluate_lm_003, evaluate_lm_004,
    evaluate_lm_005, evaluate_lm_006, evaluate_lm_007, evaluate_lm_008,
    evaluate_lm_009
)
from compliance.rules.fssai import (
    evaluate_fs_001, evaluate_fs_002, evaluate_fs_003, evaluate_fs_004, evaluate_fs_005
)
from compliance.scorer import calculate_score

EVALUATORS = {
    "LM-001": evaluate_lm_001,
    "LM-002": evaluate_lm_002,
    "LM-003": evaluate_lm_003,
    "LM-004": evaluate_lm_004,
    "LM-005": evaluate_lm_005,
    "LM-006": evaluate_lm_006,
    "LM-007": evaluate_lm_007,
    "LM-008": evaluate_lm_008,
    "LM-009": evaluate_lm_009,
    "FS-001": evaluate_fs_001,
    "FS-002": evaluate_fs_002,
    "FS-003": evaluate_fs_003,
    "FS-004": evaluate_fs_004,
    "FS-005": evaluate_fs_005,
}

FIELD_LABELS = {
    "LM-001": "Manufacturer / Packer / Importer",
    "LM-002": "Common / Generic Name",
    "LM-003": "Net Quantity",
    "LM-004": "Maximum Retail Price (MRP)",
    "LM-005": "Consumer Care Details",
    "LM-006": "Country of Origin",
    "LM-007": "Unit Sale Price",
    "LM-008": "Date of Manufacture / Pre-pack / Import",
    "FS-001": "FSSAI Licence Number / Logo",
    "FS-002": "Name of Food",
    "FS-003": "List of Ingredients",
    "FS-004": "Nutritional Information Panel",
    "FS-005": "Date Marking (Best Before / Expiry)",
}

FIELD_REGIONS = {
    "LM-001": ("Back", "lower_stamp"),
    "LM-002": ("Front", "header_brand"),
    "LM-003": ("Back", "lower_stamp"),
    "LM-004": ("Back", "stamp_box"),
    "LM-005": ("Back", "middle_statutory"),
    "LM-006": ("Back", "middle_statutory"),
    "LM-007": ("Back", "stamp_box"),
    "LM-008": ("Back", "stamp_box"),
    "FS-001": ("Back", "middle_statutory"),
    "FS-002": ("Front", "header_brand"),
    "FS-003": ("Back", "middle_statutory"),
    "FS-004": ("Back", "nutrition_panel"),
    "FS-005": ("Back", "stamp_box"),
}

from compliance.evidence_locator import locate_evidence_for_rule


class ComplianceEngine:
    """
    Centralized, Evidence-Linked Compliance Engine.
    Evaluates packages against official Legal Metrology (Packaged Commodities) Rules, 2011
    and FSSAI (Labelling & Display) Regulations, 2020.
    """

    def check(self, product_info: ProductInfo, ocr_text: str = "", images: Optional[List[ProductImageEvidence]] = None, analysis_id: Optional[str] = None) -> dict:
        checks: List[ComplianceCheck] = []
        issues: List[ComplianceIssue] = []
        
        passed_count = 0
        failed_count = 0
        warning_count = 0
        needs_review_count = 0
        not_applicable_count = 0

        # 1. Infer package applicability context (food, import status, single-ingredient)
        context = PackageContext.infer_context(product_info, ocr_text)

        # 2. Iterate all rules registered in the centralized rule registry
        all_rules = registry.get_all_rules()
        for r_def in all_rules:
            r_id = r_def.id
            eval_fn = EVALUATORS.get(r_id)
            if not eval_fn:
                continue

            status, reason, detected_val = eval_fn(product_info, context, ocr_text)
            
            # Map default evidence region and image panel
            default_img, default_reg = FIELD_REGIONS.get(r_id, ("Back", "label_body"))
            if images and len(images) == 1:
                default_img = images[0].label

            primary_field = r_def.evidence_fields[0] if r_def.evidence_fields else "unknown"

            # Match precise token bounding box and evidence items via deterministic locator
            ev_items, found_img, found_bbox, bx, by, bw, bh = locate_evidence_for_rule(
                rule_def=r_def,
                product_info=product_info,
                status=status,
                reason=reason,
                detected_value=detected_val,
                images=images,
                analysis_id=analysis_id
            )
            evidence_img = found_img if found_img else default_img
            conf = ev_items[0].confidence if ev_items else product_info.declaration_confidences.get(primary_field)

            # Update count metrics
            if status == ComplianceStatus.PASS:
                passed_count += 1
            elif status == ComplianceStatus.FAIL:
                failed_count += 1
                issues.append(ComplianceIssue(
                    what=f"{r_def.title} was not detected",
                    expected=r_def.requirement,
                    why=f"{r_def.source_name} ({r_def.source_reference})",
                    action=f"Ensure {r_def.title.lower()} is conspicuously printed on the package.",
                    severity=r_def.severity,
                    field=primary_field,
                    domain=r_def.domain.value
                ))
            elif status == ComplianceStatus.WARNING:
                warning_count += 1
                issues.append(ComplianceIssue(
                    what=f"{r_def.title} potential issue: {reason}",
                    expected=r_def.requirement,
                    why=f"{r_def.source_name} ({r_def.source_reference})",
                    action="Review label printing quality and clarity for compliance verification.",
                    severity="low",
                    field=primary_field,
                    domain=r_def.domain.value
                ))
            elif status == ComplianceStatus.NEEDS_REVIEW:
                needs_review_count += 1
            elif status == ComplianceStatus.NOT_APPLICABLE:
                not_applicable_count += 1

            checks.append(ComplianceCheck(
                rule_id=r_id,
                field=primary_field,
                field_label=FIELD_LABELS.get(r_id, r_def.title),
                required=status != ComplianceStatus.NOT_APPLICABLE,
                detected=detected_val is not None,
                detected_value=detected_val,
                severity=r_def.severity,
                status=status.value,
                description=r_def.requirement,
                source=f"{r_def.source_name} — {r_def.source_reference}",
                explanation=reason,
                recommendation=f"Ensure compliance with {r_def.source_reference}" if status != ComplianceStatus.PASS else None,
                domain=r_def.domain.value,
                source_name=r_def.source_name,
                source_reference=r_def.source_reference,
                source_url=r_def.source_url,
                confidence=conf,
                evidence_image_label=evidence_img,
                evidence_region=default_reg,
                reason=reason,
                bbox=found_bbox,
                bbox_x=bx,
                bbox_y=by,
                bbox_width=bw,
                bbox_height=bh,
                evidence=ev_items
            ))

        # 3. Calculate score using explainable weighting
        score_data = calculate_score(checks)

        # 4. Generate deterministic, evidence-linked recommendations
        from compliance.recommendations import generate_recommendations
        recommendations = generate_recommendations(checks)

        return {
            "checks": checks,
            "score": score_data['score'],
            "status": score_data['status'],
            "total_rules": len(all_rules),
            "passed_rules": passed_count,
            "failed_rules": failed_count,
            "warning_rules": warning_count,
            "needs_review_rules": needs_review_count,
            "not_applicable_rules": not_applicable_count,
            "issues": issues,
            "recommendations": recommendations
        }

engine = ComplianceEngine()

