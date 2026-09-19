import re
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set

from multilingual.normalizer import (
    normalize_indic_digits,
    normalize_currency,
    normalize_units
)
from models.schemas import ProductInfo, ComplianceResult, ComplianceCheck, ComplianceIssue, EvidenceItem
from models.version_schemas import (
    FieldDiffItem,
    IngredientItemDiff,
    IngredientsDiff,
    NutrientDiffItem,
    NutritionDiff,
    RuleStateDiff,
    IssueResolutionItem,
    VersionSnapshot,
    VersionTimelineEvent,
    VersionComparisonResult
)


# ════════════════════════════════════════════════════════════════════════════
# 1. SEMANTIC NORMALIZATION HELPERS
# ════════════════════════════════════════════════════════════════════════════

def normalize_text_for_comparison(text: Optional[str]) -> str:
    """Standardizes text by converting Indic digits, stripping redundant whitespace and punctuation."""
    if not text:
        return ""
    t = normalize_indic_digits(str(text))
    # Replace multiple spaces/newlines with single space
    t = re.sub(r'[\s\r\n\t]+', ' ', t)
    return t.strip().lower()


def parse_and_normalize_mrp(mrp_str: Optional[str]) -> Tuple[Optional[float], str]:
    """
    Extracts canonical float amount from MRP string and returns (amount, formatted_currency).
    Handles ₹, Rs, INR, Indic numbers, and tax phrases.
    """
    if not mrp_str:
        return None, ""
    t = normalize_currency(str(mrp_str))
    # Extract numerical value (supports decimals)
    m = re.search(r'(\d+(?:\.\d+)?)', t)
    if m:
        try:
            val = float(m.group(1))
            return val, f"₹{val:,.2f}"
        except ValueError:
            pass
    return None, mrp_str.strip()


def parse_and_normalize_quantity(qty_str: Optional[str]) -> Tuple[Optional[float], str, str]:
    """
    Extracts canonical numeric amount and unit from quantity string.
    Returns (amount, unit, formatted_str).
    """
    if not qty_str:
        return None, "", ""
    t = normalize_units(str(qty_str))
    m = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', t)
    if m:
        try:
            amount = float(m.group(1))
            unit = m.group(2).lower()
            return amount, unit, f"{amount} {unit}"
        except ValueError:
            pass
    return None, "", qty_str.strip()


def normalize_fssai(fssai_str: Optional[str]) -> str:
    """Extracts 14-digit FSSAI license number."""
    if not fssai_str:
        return ""
    t = normalize_indic_digits(str(fssai_str))
    digits = re.sub(r'\D', '', t)
    return digits if len(digits) == 14 else digits


# ════════════════════════════════════════════════════════════════════════════
# 2. STRUCTURED INGREDIENTS & NUTRITION COMPARISON
# ════════════════════════════════════════════════════════════════════════════

def compare_ingredients(ing_a: Optional[str], ing_b: Optional[str]) -> IngredientsDiff:
    """
    Compares structured ingredient lists, detecting additions, removals, and reordering.
    """
    if not ing_a and not ing_b:
        return IngredientsDiff(status="UNCHANGED", raw_diff_summary="No ingredients declared in either version.")
    if not ing_a and ing_b:
        items = [IngredientItemDiff(name=i.strip(), status="ADDED") for i in ing_b.split(",") if i.strip()]
        return IngredientsDiff(
            status="ADDED",
            added_ingredients=[i.strip() for i in ing_b.split(",") if i.strip()],
            raw_diff_summary=f"Ingredients list added with {len(items)} items.",
            items=items
        )
    if ing_a and not ing_b:
        items = [IngredientItemDiff(name=i.strip(), status="REMOVED") for i in ing_a.split(",") if i.strip()]
        return IngredientsDiff(
            status="REMOVED",
            removed_ingredients=[i.strip() for i in ing_a.split(",") if i.strip()],
            raw_diff_summary="Ingredients list was removed in the new version.",
            items=items
        )

    # Tokenize and clean both lists
    def _parse_tokens(raw: str) -> List[str]:
        cleaned = re.sub(r'^(?:ingredients|contains|composition)\s*[:\-]?\s*', '', raw, flags=re.IGNORECASE)
        tokens = re.split(r'[,;•\n\r]+', cleaned)
        return [re.sub(r'\s+', ' ', t).strip() for t in tokens if t.strip()]

    tokens_a = _parse_tokens(ing_a or "")
    tokens_b = _parse_tokens(ing_b or "")

    set_a = {t.lower(): t for t in tokens_a}
    set_b = {t.lower(): t for t in tokens_b}

    added = [orig for key, orig in set_b.items() if key not in set_a]
    removed = [orig for key, orig in set_a.items() if key not in set_b]
    common = [orig for key, orig in set_b.items() if key in set_a]

    # Check if order changed (only among common items)
    common_keys_a = [t.lower() for t in tokens_a if t.lower() in set_b]
    common_keys_b = [t.lower() for t in tokens_b if t.lower() in set_a]
    is_order_changed = common_keys_a != common_keys_b

    status = "UNCHANGED"
    if added or removed:
        status = "CHANGED"
    elif is_order_changed:
        status = "REORDERED_ONLY"

    diff_items: List[IngredientItemDiff] = []
    for item in added:
        diff_items.append(IngredientItemDiff(name=item, status="ADDED"))
    for item in removed:
        diff_items.append(IngredientItemDiff(name=item, status="REMOVED"))
    for item in common:
        diff_items.append(IngredientItemDiff(name=item, status="UNCHANGED"))

    summary_parts = []
    if added:
        summary_parts.append(f"+{len(added)} added ({', '.join(added[:3])}{'...' if len(added) > 3 else ''})")
    if removed:
        summary_parts.append(f"-{len(removed)} removed ({', '.join(removed[:3])}{'...' if len(removed) > 3 else ''})")
    if is_order_changed and not added and not removed:
        summary_parts.append("Ingredient declaration order was revised.")

    return IngredientsDiff(
        status=status,
        added_ingredients=added,
        removed_ingredients=removed,
        common_ingredients=common,
        is_order_changed=is_order_changed,
        raw_diff_summary="; ".join(summary_parts) if summary_parts else "Ingredients list is identical.",
        items=diff_items
    )


def compare_nutrition(
    nutr_a: Optional[Dict[str, str]],
    nutr_b: Optional[Dict[str, str]],
    raw_a: Optional[str] = None,
    raw_b: Optional[str] = None
) -> NutritionDiff:
    """
    Compares structured nutrition facts tables (Energy, Protein, Fat, Carbohydrates, Sugar, Sodium).
    """
    table_a = nutr_a or {}
    table_b = nutr_b or {}

    if not table_a and not table_b:
        if raw_a or raw_b:
            norm_a = normalize_text_for_comparison(raw_a)
            norm_b = normalize_text_for_comparison(raw_b)
            if norm_a == norm_b:
                return NutritionDiff(status="UNCHANGED", summary="Nutrition text is identical.")
            return NutritionDiff(status="CHANGED", summary="Nutrition text was revised.")
        return NutritionDiff(status="UNCHANGED", summary="No nutrition table declared in either version.")

    all_keys = set(list(table_a.keys()) + list(table_b.keys()))
    items: List[NutrientDiffItem] = []
    changed_count = 0

    for key in sorted(all_keys):
        val_a = table_a.get(key)
        val_b = table_b.get(key)

        num_a = None
        num_b = None
        unit = ""

        if val_a:
            m = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z%]*)', str(val_a))
            if m:
                try: num_a = float(m.group(1)); unit = m.group(2)
                except ValueError: pass
        if val_b:
            m = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z%]*)', str(val_b))
            if m:
                try: num_b = float(m.group(1)); unit = unit or m.group(2)
                except ValueError: pass

        delta = None
        if num_a is not None and num_b is not None:
            delta = round(num_b - num_a, 2)

        if val_a is None and val_b is not None:
            change_type = "ADDED"
            changed_count += 1
        elif val_a is not None and val_b is None:
            change_type = "REMOVED"
            changed_count += 1
        elif (num_a is not None and num_b is not None and num_a != num_b) or normalize_text_for_comparison(val_a) != normalize_text_for_comparison(val_b):
            change_type = "CHANGED"
            changed_count += 1
        else:
            change_type = "UNCHANGED"

        items.append(NutrientDiffItem(
            nutrient_name=key.replace("_", " ").title(),
            old_value=str(val_a) if val_a is not None else None,
            new_value=str(val_b) if val_b is not None else None,
            old_amount=num_a,
            new_amount=num_b,
            amount_delta=delta,
            unit=unit,
            change_type=change_type
        ))

    status = "CHANGED" if changed_count > 0 else "UNCHANGED"
    return NutritionDiff(
        status=status,
        nutrients=items,
        summary=f"{changed_count} nutrient values revised." if changed_count > 0 else "Nutritional values are identical."
    )


# ════════════════════════════════════════════════════════════════════════════
# 3. FIELD-BY-FIELD COMPARISON ENGINE
# ════════════════════════════════════════════════════════════════════════════

def compare_single_field(
    field_name: str,
    field_label: str,
    val_a: Optional[str],
    val_b: Optional[str],
    evidence_a: Optional[List[EvidenceItem]] = None,
    evidence_b: Optional[List[EvidenceItem]] = None
) -> FieldDiffItem:
    """
    Compares a single field between Version A and Version B with domain-specific normalization.
    """
    str_a = (val_a or "").strip()
    str_b = (val_b or "").strip()

    # 1. Added / Removed Cases
    if not str_a and str_b:
        return FieldDiffItem(
            field=field_name,
            field_label=field_label,
            change_type="ADDED",
            old_value=None,
            new_value=str_b,
            old_normalized_value=None,
            new_normalized_value=normalize_text_for_comparison(str_b),
            explanation=f"Declaration '{field_label}' was added in the new version.",
            evidence_a=evidence_a,
            evidence_b=evidence_b
        )
    if str_a and not str_b:
        return FieldDiffItem(
            field=field_name,
            field_label=field_label,
            change_type="REMOVED",
            old_value=str_a,
            new_value=None,
            old_normalized_value=normalize_text_for_comparison(str_a),
            new_normalized_value=None,
            explanation=f"Declaration '{field_label}' was removed in the new version.",
            evidence_a=evidence_a,
            evidence_b=evidence_b
        )
    if not str_a and not str_b:
        return FieldDiffItem(
            field=field_name,
            field_label=field_label,
            change_type="UNCHANGED",
            old_value=None,
            new_value=None,
            old_normalized_value=None,
            new_normalized_value=None,
            explanation="Not declared in either version.",
            evidence_a=evidence_a,
            evidence_b=evidence_b
        )

    # 2. Specialized Field Handling
    if field_name == "mrp":
        amt_a, fmt_a = parse_and_normalize_mrp(str_a)
        amt_b, fmt_b = parse_and_normalize_mrp(str_b)
        
        if amt_a is not None and amt_b is not None:
            if amt_a == amt_b:
                return FieldDiffItem(
                    field="mrp",
                    field_label=field_label,
                    change_type="UNCHANGED",
                    old_value=str_a,
                    new_value=str_b,
                    old_normalized_value=fmt_a,
                    new_normalized_value=fmt_b,
                    explanation=f"MRP is unchanged at {fmt_a}.",
                    evidence_a=evidence_a,
                    evidence_b=evidence_b
                )
            delta = round(amt_b - amt_a, 2)
            pct = round((delta / amt_a) * 100.0, 1) if amt_a > 0 else 0.0
            direction = "increased" if delta > 0 else "decreased"
            return FieldDiffItem(
                field="mrp",
                field_label=field_label,
                change_type="CHANGED",
                old_value=str_a,
                new_value=str_b,
                old_normalized_value=fmt_a,
                new_normalized_value=fmt_b,
                delta_info={"amount_delta": delta, "percent_delta": pct, "currency": "INR"},
                explanation=f"MRP {direction} from {fmt_a} to {fmt_b} ({'+' if delta > 0 else ''}{delta:,.2f} INR / {'+' if pct > 0 else ''}{pct}%).",
                evidence_a=evidence_a,
                evidence_b=evidence_b
            )

    elif field_name == "net_quantity":
        amt_a, unit_a, fmt_a = parse_and_normalize_quantity(str_a)
        amt_b, unit_b, fmt_b = parse_and_normalize_quantity(str_b)

        if amt_a is not None and amt_b is not None and unit_a == unit_b:
            if amt_a == amt_b:
                return FieldDiffItem(
                    field="net_quantity",
                    field_label=field_label,
                    change_type="UNCHANGED",
                    old_value=str_a,
                    new_value=str_b,
                    old_normalized_value=fmt_a,
                    new_normalized_value=fmt_b,
                    explanation=f"Net quantity is identical at {fmt_a}.",
                    evidence_a=evidence_a,
                    evidence_b=evidence_b
                )
            delta = round(amt_b - amt_a, 2)
            pct = round((delta / amt_a) * 100.0, 1) if amt_a > 0 else 0.0
            return FieldDiffItem(
                field="net_quantity",
                field_label=field_label,
                change_type="CHANGED",
                old_value=str_a,
                new_value=str_b,
                old_normalized_value=fmt_a,
                new_normalized_value=fmt_b,
                delta_info={"amount_delta": delta, "percent_delta": pct, "unit": unit_a},
                explanation=f"Net quantity changed from {fmt_a} to {fmt_b} ({'+' if delta > 0 else ''}{delta} {unit_a} / {'+' if pct > 0 else ''}{pct}%).",
                evidence_a=evidence_a,
                evidence_b=evidence_b
            )

    elif field_name == "fssai_license":
        lic_a = normalize_fssai(str_a)
        lic_b = normalize_fssai(str_b)
        if lic_a == lic_b:
            return FieldDiffItem(
                field="fssai_license",
                field_label=field_label,
                change_type="UNCHANGED",
                old_value=str_a,
                new_value=str_b,
                old_normalized_value=lic_a,
                new_normalized_value=lic_b,
                explanation=f"FSSAI license number is identical ({lic_a}).",
                evidence_a=evidence_a,
                evidence_b=evidence_b
            )
        return FieldDiffItem(
            field="fssai_license",
            field_label=field_label,
            change_type="CHANGED",
            old_value=str_a,
            new_value=str_b,
            old_normalized_value=lic_a,
            new_normalized_value=lic_b,
            explanation=f"FSSAI license changed from {lic_a} to {lic_b}.",
            evidence_a=evidence_a,
            evidence_b=evidence_b
        )

    # 3. General normalized comparison
    norm_a = normalize_text_for_comparison(str_a)
    norm_b = normalize_text_for_comparison(str_b)

    if norm_a == norm_b:
        return FieldDiffItem(
            field=field_name,
            field_label=field_label,
            change_type="UNCHANGED",
            old_value=str_a,
            new_value=str_b,
            old_normalized_value=norm_a,
            new_normalized_value=norm_b,
            explanation=f"{field_label} is semantically unchanged.",
            evidence_a=evidence_a,
            evidence_b=evidence_b
        )

    return FieldDiffItem(
        field=field_name,
        field_label=field_label,
        change_type="CHANGED",
        old_value=str_a,
        new_value=str_b,
        old_normalized_value=norm_a,
        new_normalized_value=norm_b,
        explanation=f"{field_label} was revised.",
        evidence_a=evidence_a,
        evidence_b=evidence_b
    )


# ════════════════════════════════════════════════════════════════════════════
# 4. RULE COMPARISON & ISSUE RESOLUTION TRACKER
# ════════════════════════════════════════════════════════════════════════════

def compare_compliance_rules(
    checks_a: List[ComplianceCheck],
    checks_b: List[ComplianceCheck]
) -> List[RuleStateDiff]:
    """
    Compares statutory rule outcomes (LM-001 through FS-005) between versions.
    """
    map_a = {c.rule_id: c for c in checks_a}
    map_b = {c.rule_id: c for c in checks_b}

    all_rule_ids = set(list(map_a.keys()) + list(map_b.keys()))
    diffs: List[RuleStateDiff] = []

    for r_id in sorted(all_rule_ids):
        chk_a = map_a.get(r_id)
        chk_b = map_b.get(r_id)

        old_status = chk_a.status if chk_a else "NOT_APPLICABLE"
        new_status = chk_b.status if chk_b else "NOT_APPLICABLE"
        r_name = chk_b.field_label if chk_b else (chk_a.field_label if chk_a else r_id)
        domain = chk_b.domain if chk_b else (chk_a.domain if chk_a else "LEGAL_METROLOGY")

        if old_status == new_status:
            t_type = "UNCHANGED"
            exp = f"Rule outcome maintained as {new_status}."
        elif old_status in ("FAIL", "WARNING", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE") and new_status == "PASS":
            t_type = "FIXED"
            exp = f"Resolved! Rule state improved from {old_status} to PASS."
        elif old_status == "PASS" and new_status in ("FAIL", "WARNING", "NEEDS_REVIEW"):
            t_type = "REGRESSED"
            exp = f"Regression detected: Rule state declined from PASS to {new_status}."
        elif old_status == "NOT_APPLICABLE" and new_status != "NOT_APPLICABLE":
            t_type = "NEWLY_EVALUATED"
            exp = f"Rule was newly evaluated with outcome {new_status}."
        else:
            t_type = "MODIFIED"
            exp = f"Rule state transitioned from {old_status} to {new_status}."

        diffs.append(RuleStateDiff(
            rule_id=r_id,
            rule_name=r_name,
            domain=domain,
            old_status=old_status,
            new_status=new_status,
            transition_type=t_type,
            explanation=exp
        ))

    return diffs


def track_issue_resolutions(
    checks_a: List[ComplianceCheck],
    checks_b: List[ComplianceCheck],
    issues_a: List[ComplianceIssue],
    issues_b: List[ComplianceIssue]
) -> List[IssueResolutionItem]:
    """
    Identifies issue resolution states:
    - RESOLVED: Failed in A, Passed in B
    - STILL_PRESENT: Failed in both A and B
    - NEW_ISSUE: Passed/N/A in A, Failed in B
    - UNRESOLVED_REVIEW: Needs human verification in B
    """
    map_a = {c.rule_id: c for c in checks_a}
    map_b = {c.rule_id: c for c in checks_b}

    resolutions: List[IssueResolutionItem] = []

    # 1. Trace issues originating in Version A
    for chk_a in checks_a:
        if chk_a.status in ("FAIL", "WARNING"):
            chk_b = map_b.get(chk_a.rule_id)
            if chk_b and chk_b.status == "PASS":
                resolutions.append(IssueResolutionItem(
                    issue_id=f"res-{chk_a.rule_id}-{uuid.uuid4().hex[:6]}",
                    rule_id=chk_a.rule_id,
                    field=chk_a.field,
                    resolution_status="RESOLVED",
                    old_issue_text=chk_a.description or chk_a.reason,
                    new_issue_text=None,
                    severity=chk_a.severity,
                    explanation=f"Issue on {chk_a.field_label} was resolved in the revised version."
                ))
            elif chk_b and chk_b.status in ("FAIL", "WARNING"):
                resolutions.append(IssueResolutionItem(
                    issue_id=f"res-{chk_a.rule_id}-{uuid.uuid4().hex[:6]}",
                    rule_id=chk_a.rule_id,
                    field=chk_a.field,
                    resolution_status="STILL_PRESENT",
                    old_issue_text=chk_a.description or chk_a.reason,
                    new_issue_text=chk_b.description or chk_b.reason,
                    severity=chk_a.severity,
                    explanation=f"Violation on {chk_a.field_label} remains unresolved."
                ))
            elif chk_b and chk_b.status == "NEEDS_REVIEW":
                resolutions.append(IssueResolutionItem(
                    issue_id=f"res-{chk_a.rule_id}-{uuid.uuid4().hex[:6]}",
                    rule_id=chk_a.rule_id,
                    field=chk_a.field,
                    resolution_status="UNRESOLVED_REVIEW",
                    old_issue_text=chk_a.description or chk_a.reason,
                    new_issue_text=chk_b.description or chk_b.reason,
                    severity=chk_a.severity,
                    explanation=f"Requires human verification: Status is {chk_b.status}."
                ))

    # 2. Identify new issues introduced in Version B
    for chk_b in checks_b:
        if chk_b.status in ("FAIL", "WARNING"):
            chk_a = map_a.get(chk_b.rule_id)
            if not chk_a or chk_a.status == "PASS":
                resolutions.append(IssueResolutionItem(
                    issue_id=f"new-{chk_b.rule_id}-{uuid.uuid4().hex[:6]}",
                    rule_id=chk_b.rule_id,
                    field=chk_b.field,
                    resolution_status="NEW_ISSUE",
                    old_issue_text=None,
                    new_issue_text=chk_b.description or chk_b.reason,
                    severity=chk_b.severity,
                    explanation=f"New violation introduced on {chk_b.field_label}."
                ))

    return resolutions


# ════════════════════════════════════════════════════════════════════════════
# 5. MAIN COMPARISON PIPELINE
# ════════════════════════════════════════════════════════════════════════════

def compare_versions(
    version_a: VersionSnapshot,
    version_b: VersionSnapshot
) -> VersionComparisonResult:
    """
    Deterministic Version A vs Version B comparison pipeline:
    - Declaration differences (Added, Removed, Changed, Unchanged)
    - Specialized diffs (MRP, Quantity, Manufacturer, FSSAI, Ingredients, Nutrition)
    - Compliance score & risk tier shifts
    - Rule-by-rule state transitions
    - Issue resolution matrix
    """
    comp_id = f"cmp-{uuid.uuid4().hex[:12]}"
    info_a = version_a.product_info or ProductInfo()
    info_b = version_b.product_info or ProductInfo()

    # 1. Field Diffs
    target_fields = [
        ("product_name", "Product Name"),
        ("brand", "Brand Name"),
        ("mrp", "Maximum Retail Price (MRP)"),
        ("net_quantity", "Net Quantity"),
        ("unit_sale_price", "Unit Sale Price"),
        ("manufacturing_date", "Date of Manufacture"),
        ("expiry_date", "Best Before / Expiry"),
        ("manufacturer", "Manufacturer Name & Address"),
        ("marketed_by", "Marketed By"),
        ("importer", "Importer Details"),
        ("country_of_origin", "Country of Origin"),
        ("fssai_license", "FSSAI License Number"),
        ("consumer_care", "Consumer Care Details"),
        ("batch_number", "Batch / Lot Number"),
    ]

    all_field_diffs: List[FieldDiffItem] = []
    for f_name, f_label in target_fields:
        val_a = getattr(info_a, f_name, None)
        val_b = getattr(info_b, f_name, None)
        diff_item = compare_single_field(f_name, f_label, val_a, val_b)
        all_field_diffs.append(diff_item)

    added = [d for d in all_field_diffs if d.change_type == "ADDED"]
    removed = [d for d in all_field_diffs if d.change_type == "REMOVED"]
    changed = [d for d in all_field_diffs if d.change_type == "CHANGED"]
    unchanged = [d for d in all_field_diffs if d.change_type == "UNCHANGED"]
    review_req = [d for d in all_field_diffs if d.requires_review]

    # Specialized diffs
    mrp_diff = next((d for d in all_field_diffs if d.field == "mrp"), None)
    qty_diff = next((d for d in all_field_diffs if d.field == "net_quantity"), None)
    mfg_diff = next((d for d in all_field_diffs if d.field == "manufacturer"), None)
    fssai_diff = next((d for d in all_field_diffs if d.field == "fssai_license"), None)

    # Ingredients & Nutrition Diffs
    ingredients_diff = compare_ingredients(info_a.ingredients, info_b.ingredients)
    nutrition_diff = compare_nutrition(
        info_a.nutrition_facts,
        info_b.nutrition_facts,
        info_a.nutritional_info,
        info_b.nutritional_info
    )

    # 2. Score & Rule Comparison
    score_a = round(version_a.score, 1)
    score_b = round(version_b.score, 1)
    score_delta = round(score_b - score_a, 1)

    risk_a = version_a.risk_level.upper()
    risk_b = version_b.risk_level.upper()

    risk_weights = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    w_a = risk_weights.get(risk_a, 2)
    w_b = risk_weights.get(risk_b, 2)
    if w_b < w_a:
        risk_shift = "IMPROVED"
    elif w_b > w_a:
        risk_shift = "DEGRADED"
    else:
        risk_shift = "UNCHANGED"

    checks_a = version_a.compliance_result.checks if version_a.compliance_result else []
    checks_b = version_b.compliance_result.checks if version_b.compliance_result else []
    issues_a = version_a.compliance_result.issues if version_a.compliance_result else []
    issues_b = version_b.compliance_result.issues if version_b.compliance_result else []

    rule_diffs = compare_compliance_rules(checks_a, checks_b)
    issue_resolutions = track_issue_resolutions(checks_a, checks_b, issues_a, issues_b)

    resolved_count = sum(1 for i in issue_resolutions if i.resolution_status == "RESOLVED")
    remaining_count = sum(1 for i in issue_resolutions if i.resolution_status == "STILL_PRESENT")
    new_count = sum(1 for i in issue_resolutions if i.resolution_status == "NEW_ISSUE")

    crit_a = sum(1 for c in checks_a if c.status == "FAIL" and c.severity == "critical")
    crit_b = sum(1 for c in checks_b if c.status == "FAIL" and c.severity == "critical")
    miss_a = sum(1 for c in checks_a if not c.detected and c.required)
    miss_b = sum(1 for c in checks_b if not c.detected and c.required)

    # Verdict summary
    if score_delta > 0 and resolved_count > 0:
        verdict = f"Version B showed compliance improvement (+{score_delta} pts) with {resolved_count} issues resolved."
    elif score_delta < 0:
        verdict = f"Version B showed compliance regression ({score_delta} pts) with {new_count} new issues."
    else:
        verdict = "Compliance scores remained consistent between versions."

    notes = [
        f"Compared {version_a.version_label} (Base) vs {version_b.version_label} (Revised).",
        f"Identified {len(added)} added, {len(removed)} removed, and {len(changed)} changed declarations.",
        f"Ingredients status: {ingredients_diff.status}. Nutrition status: {nutrition_diff.status}."
    ]

    now_iso = datetime.now(timezone.utc).isoformat()
    return VersionComparisonResult(
        comparison_id=comp_id,
        version_a=version_a,
        version_b=version_b,
        created_at=now_iso,
        score_a=score_a,
        score_b=score_b,
        score_delta=score_delta,
        risk_level_a=risk_a,
        risk_level_b=risk_b,
        risk_shift=risk_shift,
        critical_issues_a=crit_a,
        critical_issues_b=crit_b,
        missing_declarations_a=miss_a,
        missing_declarations_b=miss_b,
        declaration_diffs=all_field_diffs,
        added_declarations=added,
        removed_declarations=removed,
        changed_declarations=changed,
        unchanged_declarations=unchanged,
        review_required_declarations=review_req,
        mrp_diff=mrp_diff,
        quantity_diff=qty_diff,
        manufacturer_diff=mfg_diff,
        fssai_diff=fssai_diff,
        ingredients_diff=ingredients_diff,
        nutrition_diff=nutrition_diff,
        rule_diffs=rule_diffs,
        issue_resolutions=issue_resolutions,
        resolved_issues_count=resolved_count,
        remaining_issues_count=remaining_count,
        new_issues_count=new_count,
        summary_verdict=verdict,
        notes=notes
    )
