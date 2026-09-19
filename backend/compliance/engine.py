import time
from typing import List, Dict, Any, Optional
from models.schemas import ProductInfo, ComplianceCheck, ComplianceIssue, ProductImageEvidence, RuleTestResponse
from compliance.rules.registry import registry
from compliance.rules.applicability import PackageContext
from compliance.rules.models import ComplianceStatus, RuleDomain, RuleExecutionTrace, RuleConflictItem
from compliance.rules.legal_metrology import (
    evaluate_lm_001, evaluate_lm_002, evaluate_lm_003, evaluate_lm_004,
    evaluate_lm_005, evaluate_lm_006, evaluate_lm_007, evaluate_lm_008,
    evaluate_lm_009
)
from compliance.rules.fssai import (
    evaluate_fs_001, evaluate_fs_002, evaluate_fs_003, evaluate_fs_004, evaluate_fs_005
)
from compliance.scorer import calculate_score
from compliance.evidence_locator import locate_evidence_for_rule

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


class ComplianceEngine:
    """
    Centralized, Evidence-Linked Compliance Engine with Section 6 Compliance Intelligence.
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

            t_start = time.perf_counter()
            status, reason, detected_val = eval_fn(product_info, context, ocr_text)
            t_elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            
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
            elif status in (ComplianceStatus.NEEDS_REVIEW, ComplianceStatus.INSUFFICIENT_EVIDENCE):
                needs_review_count += 1
                if status == ComplianceStatus.INSUFFICIENT_EVIDENCE:
                    issues.append(ComplianceIssue(
                        what=f"{r_def.title} insufficient evidence: {reason}",
                        expected=r_def.requirement,
                        why=f"{r_def.source_name} ({r_def.source_reference})",
                        action="Ensure label image is well-lit, in focus, and un-obscured.",
                        severity="medium",
                        field=primary_field,
                        domain=r_def.domain.value
                    ))
            elif status == ComplianceStatus.NOT_APPLICABLE:
                not_applicable_count += 1

            # Generate deterministic, grounded pass/fail/review explanations
            pass_r = None
            fail_r = None
            rev_r = None
            if status == ComplianceStatus.PASS:
                pass_r = f"Verified: Mandatory declaration '{r_def.title}' was successfully detected ('{detected_val}') on {evidence_img} panel adhering to {r_def.source_reference}."
            elif status == ComplianceStatus.FAIL:
                fail_r = f"Non-Compliance: Mandatory statutory declaration '{r_def.title}' was missing or non-compliant ({reason}). Required by {r_def.source_name} ({r_def.source_reference})."
            elif status in (ComplianceStatus.NEEDS_REVIEW, ComplianceStatus.WARNING, ComplianceStatus.INSUFFICIENT_EVIDENCE):
                rev_r = f"Review Required: '{r_def.title}' requires manual officer verification ({reason}). Source: {r_def.source_reference}."
            elif status == ComplianceStatus.NOT_APPLICABLE:
                rev_r = f"Exempt / Not Applicable: '{r_def.title}' is exempt under identified package context ({reason})."

            f_status = product_info.field_status.get(primary_field, "FOUND" if detected_val else "NOT_FOUND") if hasattr(product_info, 'field_status') else ("FOUND" if detected_val else "NOT_FOUND")
            raw_cands = product_info.candidates.get(primary_field, []) if hasattr(product_info, 'candidates') else []
            formatted_cands = [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in raw_cands]
            rel_score = ev_items[0].reliability_score if (ev_items and getattr(ev_items[0], 'reliability_score', None) is not None) else (conf or 80.0)
            rel_tier = ev_items[0].reliability_tier if (ev_items and getattr(ev_items[0], 'reliability_tier', None) is not None) else "HIGH"
            reg_ref = f"{r_def.source_name} — {r_def.source_reference}" if getattr(r_def, 'source_reference', None) else None

            # Build inputs dictionary for execution trace
            trace_inputs = {}
            for ef in r_def.evidence_fields:
                val = getattr(product_info, ef, None)
                if val is not None:
                    trace_inputs[ef] = str(val)

            # Synthesize RuleExecutionTrace
            ex_applied = None
            if status == ComplianceStatus.NOT_APPLICABLE:
                ex_applied = r_def.exemptions[0] if r_def.exemptions else reason

            exec_trace = RuleExecutionTrace(
                rule_id=r_id,
                rule_name=r_def.title,
                rule_version=r_def.rule_version,
                category=r_def.category_applicability[0] if isinstance(r_def.category_applicability, list) else str(r_def.category_applicability),
                effective_from=r_def.effective_from,
                effective_to=r_def.effective_to,
                evaluated_fields=r_def.evidence_fields,
                inputs=trace_inputs,
                prerequisites_met=True,
                conditions_evaluated=r_def.conditions,
                exemption_applied=ex_applied,
                output_status=status.value,
                execution_ms=t_elapsed_ms,
                explanation=reason
            )

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
                evidence=ev_items,
                pass_reason=pass_r,
                fail_reason=fail_r,
                review_reason=rev_r,
                linked_rule_id=r_id,
                linked_field=r_def.evidence_fields[0] if (getattr(r_def, 'evidence_fields', None) and len(r_def.evidence_fields) > 0) else primary_field,
                regulation_reference=reg_ref,
                reliability_score=rel_score,
                reliability_tier=rel_tier,
                field_status=f_status,
                candidates=formatted_cands,
                execution_trace=exec_trace.model_dump() if hasattr(exec_trace, 'model_dump') else exec_trace.dict(),
                rule_version=r_def.rule_version
            ))

        # 3. Detect Rule & Evidence Conflicts
        conflicts = self.detect_rule_conflicts(product_info=product_info, checks=checks, context=context)

        # 4. Calculate score using explainable weighting
        score_data = calculate_score(checks, product_info=product_info, conflicts=conflicts)

        # 5. Generate deterministic, evidence-linked recommendations
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
            "recommendations": recommendations,
            "conflicts": [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in conflicts],
            "rule_scores": score_data.get('rule_scores'),
            "category_scores": score_data.get('category_scores'),
            "risk_assessment": score_data.get('risk_assessment'),
            "confidence_summary": score_data.get('confidence_summary'),
            "scoring_version": score_data.get('scoring_version', "2026.1"),
        }

    def detect_rule_conflicts(self, product_info: ProductInfo, checks: List[ComplianceCheck], context: PackageContext) -> List[RuleConflictItem]:
        """
        Deterministic Rule and Evidence Conflict Detector.
        Identifies logical contradictions, conflicting field candidates, cross-rule mismatches,
        and temporal/date inconsistencies across evaluated rules.
        """
        conflicts: List[RuleConflictItem] = []

        # 1. Date chronological conflict: Date of Mfg (LM-008) vs Date of Expiry / Best Before (FS-005)
        mfg_date = getattr(product_info, 'manufacturing_date', None) or getattr(product_info, 'manufacture_date', None) or getattr(product_info, 'packaging_date', None) or getattr(product_info, 'date_of_manufacture', None)
        exp_date = getattr(product_info, 'best_before', None) or getattr(product_info, 'expiry_date', None) or getattr(product_info, 'use_by_date', None)
        if mfg_date and exp_date:
            try:
                import re
                mfg_years = re.findall(r'(?:20|19)\d{2}', str(mfg_date))
                exp_years = re.findall(r'(?:20|19)\d{2}', str(exp_date))
                if mfg_years and exp_years:
                    mfg_y = int(mfg_years[-1])
                    exp_y = int(exp_years[-1])
                    if exp_y < mfg_y:
                        conflicts.append(RuleConflictItem(
                            conflict_id="CONF-CHRONO-01",
                            conflict_type="CHRONOLOGICAL_INCONSISTENCY",
                            rule_ids=["LM-008", "FS-005"],
                            description=f"Expiry year ({exp_y}) occurs before Manufacturing year ({mfg_y}).",
                            severity="HIGH",
                            resolution_hint="Verify date stamps on primary package to confirm valid shelf life."
                        ))
            except Exception:
                pass

        # 2. Unit Sale Price vs Net Quantity / MRP conflict (LM-004 vs LM-007)
        mrp = getattr(product_info, 'mrp', None)
        usp = getattr(product_info, 'unit_sale_price', None)
        net_qty = getattr(product_info, 'net_quantity', None)
        if mrp and usp:
            try:
                import re
                mrp_nums = re.findall(r'\d+(?:\.\d+)?', str(mrp))
                usp_nums = re.findall(r'\d+(?:\.\d+)?', str(usp))
                if mrp_nums and usp_nums:
                    mrp_val = float(mrp_nums[0])
                    usp_val = float(usp_nums[0])
                    if usp_val > mrp_val:
                        conflicts.append(RuleConflictItem(
                            conflict_id="CONF-USP-01",
                            conflict_type="MATHEMATICAL_MISMATCH",
                            rule_ids=["LM-004", "LM-007"],
                            description=f"Unit Sale Price ({usp}) exceeds total Maximum Retail Price ({mrp}) for package.",
                            severity="MEDIUM",
                            resolution_hint="Confirm whether Unit Sale Price is computed per gram/ml versus standard 100g/1kg base."
                        ))
            except Exception:
                pass

        # 3. Country of Origin vs Importation / Manufacturer status (LM-001 vs LM-006)
        is_imported = getattr(context, 'is_imported', False) or getattr(product_info, 'is_imported', False)
        origin = getattr(product_info, 'country_of_origin', None)
        importer = getattr(product_info, 'importer_name', None) or getattr(product_info, 'importer_address', None)
        if origin:
            is_india = "india" in str(origin).lower() or "bharat" in str(origin).lower()
            if not is_india and not is_imported and not importer:
                conflicts.append(RuleConflictItem(
                    conflict_id="CONF-IMP-01",
                    conflict_type="IMPORT_DECLARATION_MISMATCH",
                    rule_ids=["LM-001", "LM-006"],
                    description=f"Package declared origin as '{origin}' but lacks mandatory Importer declaration under Rule 6(1)(a).",
                    severity="HIGH",
                    resolution_hint="For imported goods, both Country of Origin and Name/Address of Importer are mandatory."
                ))

        # 4. Field candidate conflicts extracted in Section 4
        if hasattr(product_info, 'conflicts') and product_info.conflicts:
            for c in product_info.conflicts:
                field_name = c.get("field", "unknown") if isinstance(c, dict) else getattr(c, "field", "unknown")
                c_type = c.get("conflict_type", "OCR_VALUE_DISCREPANCY") if isinstance(c, dict) else getattr(c, "conflict_type", "OCR_VALUE_DISCREPANCY")
                c_desc = c.get("description", "") if isinstance(c, dict) else getattr(c, "description", "")
                
                # Map field to rules
                matching_rules = [r.id for r in registry.get_all_rules() if field_name in r.evidence_fields]
                if matching_rules:
                    conflicts.append(RuleConflictItem(
                        conflict_id=f"CONF-CAND-{field_name}",
                        conflict_type=c_type,
                        rule_ids=matching_rules,
                        description=f"Discrepancy in extracted evidence for {field_name}: {c_desc}",
                        severity="MEDIUM",
                        resolution_hint=f"Review candidate readings for {field_name} in the Evidence tab."
                    ))

        return conflicts

    def test_single_rule(self, rule_id: str, product_info: ProductInfo, ocr_text: str = "", context_override: Optional[Dict[str, Any]] = None) -> RuleTestResponse:
        """
        Isolated In-Memory Rule Simulation.
        Evaluates a single rule without persisting data to the database or creating audit entries.
        """
        r_def = registry.get_rule(rule_id)
        if not r_def:
            raise ValueError(f"Rule ID '{rule_id}' not found in registry.")

        eval_fn = EVALUATORS.get(rule_id)
        if not eval_fn:
            raise ValueError(f"No evaluator registered for Rule '{rule_id}'.")

        # Infer base context and apply overrides
        context = PackageContext.infer_context(product_info, ocr_text)
        if context_override:
            for k, v in context_override.items():
                if hasattr(context, k):
                    setattr(context, k, v)

        t_start = time.perf_counter()
        status, reason, detected_val = eval_fn(product_info, context, ocr_text)
        t_elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

        pass_r = None
        fail_r = None
        rev_r = None
        if status == ComplianceStatus.PASS:
            pass_r = f"Verified: Mandatory declaration '{r_def.title}' was successfully detected ('{detected_val}') adhering to {r_def.source_reference}."
        elif status == ComplianceStatus.FAIL:
            fail_r = f"Non-Compliance: Mandatory statutory declaration '{r_def.title}' was missing or non-compliant ({reason}). Required by {r_def.source_name} ({r_def.source_reference})."
        elif status in (ComplianceStatus.NEEDS_REVIEW, ComplianceStatus.WARNING, ComplianceStatus.INSUFFICIENT_EVIDENCE):
            rev_r = f"Review Required: '{r_def.title}' requires manual officer verification ({reason}). Source: {r_def.source_reference}."
        elif status == ComplianceStatus.NOT_APPLICABLE:
            rev_r = f"Exempt / Not Applicable: '{r_def.title}' is exempt under identified package context ({reason})."

        trace_inputs = {}
        for ef in r_def.evidence_fields:
            val = getattr(product_info, ef, None)
            if val is not None:
                trace_inputs[ef] = str(val)

        ex_applied = None
        if status == ComplianceStatus.NOT_APPLICABLE:
            ex_applied = r_def.exemptions[0] if r_def.exemptions else reason

        exec_trace = RuleExecutionTrace(
            rule_id=rule_id,
            rule_name=r_def.title,
            rule_version=r_def.rule_version,
            category=r_def.category_applicability[0] if isinstance(r_def.category_applicability, list) else str(r_def.category_applicability),
            effective_from=r_def.effective_from,
            effective_to=r_def.effective_to,
            evaluated_fields=r_def.evidence_fields,
            inputs=trace_inputs,
            prerequisites_met=True,
            conditions_evaluated=r_def.conditions,
            exemption_applied=ex_applied,
            output_status=status.value,
            execution_ms=t_elapsed_ms,
            explanation=reason
        )

        return RuleTestResponse(
            rule_id=rule_id,
            rule_name=r_def.title,
            domain=r_def.domain.value,
            status=status.value,
            reason=reason,
            detected_value=detected_val,
            pass_reason=pass_r,
            fail_reason=fail_r,
            review_reason=rev_r,
            execution_trace=exec_trace.model_dump() if hasattr(exec_trace, 'model_dump') else exec_trace.dict(),
            is_simulation=True
        )

    def evaluate(self, product_info: ProductInfo, ocr_text: str = "", images: Optional[List[ProductImageEvidence]] = None, analysis_id: Optional[str] = None):
        """Convenience evaluation wrapper that returns a ComplianceResult object."""
        from models.schemas import ComplianceResult
        res_dict = self.check(product_info=product_info, ocr_text=ocr_text, images=images, analysis_id=analysis_id)
        return ComplianceResult(**res_dict)


engine = ComplianceEngine()


