from typing import List, Dict, Any, Optional
from models.schemas import (
    RuleScore, CategoryScore, ConfidenceSummary, RiskFactor, RiskAssessment,
    ScoringConfiguration, ProductInfo, ComplianceCheck
)

# ── Configured Global Scoring Engine Instance ─────────────────────────────────
DEFAULT_SCORING_CONFIG = ScoringConfiguration(
    scoring_version="2026.1",
    weight_pass=1.0,
    weight_warning=0.5,
    weight_needs_review=0.85,
    weight_fail=0.0,
    critical_risk_threshold=1,
    high_risk_failures_threshold=2,
    medium_risk_review_threshold=2,
    enabled_factors=["MANDATORY_PRESENCE", "CONFIDENCE_ADJUSTMENT", "CONFLICT_DETECTION", "SEVERITY_WEIGHTING"]
)

_active_config: ScoringConfiguration = DEFAULT_SCORING_CONFIG


def get_scoring_config() -> ScoringConfiguration:
    return _active_config


def set_scoring_config(config: ScoringConfiguration) -> ScoringConfiguration:
    global _active_config
    _active_config = config
    return _active_config


def calculate_score(
    checks: list,
    product_info: Optional[ProductInfo] = None,
    conflicts: Optional[list] = None,
    config: Optional[ScoringConfiguration] = None
) -> dict:
    """
    Section 7 Compliance Scoring & Risk Assessment Engine:
    Calculates:
    1. Overall statutory conformity score (0.0 - 100.0)
    2. Rule-level scores (RuleScore per check)
    3. Domain & category scores (CategoryScore)
    4. Aggregated confidence summary (ConfidenceSummary)
    5. Comprehensive risk assessment (RiskAssessment: CRITICAL, HIGH, MEDIUM, LOW)
    """
    cfg = config or _active_config
    conflicts = conflicts or []

    applicable_count = 0
    earned_points = 0.0
    passed_count = 0
    failed_count = 0
    warning_count = 0
    needs_review_count = 0
    insufficient_ev_count = 0
    not_applicable_count = 0

    rule_scores: List[RuleScore] = []
    failed_critical_checks: List[Any] = []
    failed_general_checks: List[Any] = []
    review_checks: List[Any] = []

    # Category buckets for Legal Metrology, FSSAI, and Packaging Domains
    categories_map: Dict[str, Dict[str, Any]] = {
        "LEGAL_METROLOGY": {
            "name": "Legal Metrology Declarations",
            "earned": 0.0,
            "total": 0,
            "applicable": 0,
            "passed": 0,
            "failed": 0,
            "review": 0,
            "not_applicable": 0
        },
        "FSSAI": {
            "name": "Food Safety & Standards (FSSAI)",
            "earned": 0.0,
            "total": 0,
            "applicable": 0,
            "passed": 0,
            "failed": 0,
            "review": 0,
            "not_applicable": 0
        }
    }

    # 1. Evaluate Rule-Level Scores and Counts
    for check in checks:
        st = (getattr(check, 'status', None) or (check.get('status') if isinstance(check, dict) else 'FAIL')).upper()
        rule_id = getattr(check, 'rule_id', None) or (check.get('rule_id') if isinstance(check, dict) else 'UNKNOWN')
        field = getattr(check, 'field', None) or (check.get('field') if isinstance(check, dict) else '')
        severity = (getattr(check, 'severity', None) or (check.get('severity') if isinstance(check, dict) else 'medium')).lower()
        domain = (getattr(check, 'domain', None) or (check.get('domain') if isinstance(check, dict) else ('FSSAI' if rule_id.startswith('FS-') else 'LEGAL_METROLOGY'))).upper()
        rel_score = getattr(check, 'reliability_score', None) or (check.get('reliability_score') if isinstance(check, dict) else None)
        conf_val = getattr(check, 'confidence', None) or (check.get('confidence') if isinstance(check, dict) else None)

        cat_bucket = categories_map.get(domain)
        if cat_bucket:
            cat_bucket["total"] += 1

        is_applicable = st != 'NOT_APPLICABLE'
        check_earned = 0.0
        risk_contribution = "NONE"

        if not is_applicable:
            not_applicable_count += 1
            if cat_bucket:
                cat_bucket["not_applicable"] += 1
            risk_contribution = "NONE"
        else:
            applicable_count += 1
            if cat_bucket:
                cat_bucket["applicable"] += 1

            if st == 'PASS':
                passed_count += 1
                check_earned = cfg.weight_pass
                earned_points += check_earned
                if cat_bucket:
                    cat_bucket["passed"] += 1
                    cat_bucket["earned"] += check_earned
                risk_contribution = "LOW" if (rel_score and rel_score < 60.0) else "NONE"

            elif st == 'WARNING':
                warning_count += 1
                check_earned = cfg.weight_warning
                earned_points += check_earned
                review_checks.append(check)
                if cat_bucket:
                    cat_bucket["review"] += 1
                    cat_bucket["earned"] += check_earned
                risk_contribution = "MEDIUM"

            elif st == 'NEEDS_REVIEW':
                needs_review_count += 1
                check_earned = cfg.weight_needs_review
                earned_points += check_earned
                review_checks.append(check)
                if cat_bucket:
                    cat_bucket["review"] += 1
                    cat_bucket["earned"] += check_earned
                risk_contribution = "MEDIUM"

            elif st == 'INSUFFICIENT_EVIDENCE':
                insufficient_ev_count += 1
                needs_review_count += 1
                check_earned = cfg.weight_warning
                earned_points += check_earned
                review_checks.append(check)
                if cat_bucket:
                    cat_bucket["review"] += 1
                    cat_bucket["earned"] += check_earned
                risk_contribution = "MEDIUM"

            elif st == 'FAIL':
                failed_count += 1
                check_earned = cfg.weight_fail
                earned_points += check_earned
                if cat_bucket:
                    cat_bucket["failed"] += 1
                    cat_bucket["earned"] += check_earned

                if severity in ('high', 'critical'):
                    failed_critical_checks.append(check)
                    risk_contribution = "CRITICAL"
                else:
                    failed_general_checks.append(check)
                    risk_contribution = "HIGH"

        rule_scores.append(RuleScore(
            rule_id=rule_id,
            field=field,
            rule_category=domain,
            domain=domain,
            status=st,
            earned_points=round(check_earned, 2),
            max_points=1.0 if is_applicable else 0.0,
            weight=1.0,
            severity=severity,
            evidence_reliability_score=rel_score,
            extraction_confidence=conf_val,
            risk_contribution=risk_contribution,
            is_applicable=is_applicable
        ))

    # 2. Overall Score Calculation
    overall_score = (earned_points / applicable_count) * 100 if applicable_count > 0 else 100.0
    overall_score = round(overall_score, 1)

    # 3. Overall Screening Status
    if failed_count > 0:
        overall_status = 'POTENTIAL NON-COMPLIANCE'
    elif (needs_review_count + warning_count + insufficient_ev_count) > 0:
        overall_status = 'REVIEW REQUIRED'
    elif overall_score >= 80.0:
        overall_status = 'COMPLIANT'
    else:
        overall_status = 'REVIEW REQUIRED'

    # 4. Category Scores Generation
    category_scores: List[CategoryScore] = []
    for cat_id, data in categories_map.items():
        app_cnt = data["applicable"]
        if app_cnt == 0:
            c_score = 100.0
            c_status = "NOT_APPLICABLE"
        else:
            c_score = round((data["earned"] / app_cnt) * 100, 1)
            if data["failed"] > 0:
                c_status = "NON_COMPLIANT"
            elif data["review"] > 0:
                c_status = "REVIEW_REQUIRED"
            else:
                c_status = "COMPLIANT"

        category_scores.append(CategoryScore(
            category_id=cat_id,
            category_name=data["name"],
            score=c_score,
            total_rules=data["total"],
            applicable_rules=app_cnt,
            passed_rules=data["passed"],
            failed_rules=data["failed"],
            review_rules=data["review"],
            not_applicable_rules=data["not_applicable"],
            status=c_status
        ))

    # 5. Extraction & Evidence Confidence Summary
    ext_confs = []
    ev_rels = []
    high_conf_cnt = 0
    low_conf_cnt = 0
    uncertain_cnt = 0

    if product_info and hasattr(product_info, 'declaration_confidences') and product_info.declaration_confidences:
        for val in product_info.declaration_confidences.values():
            if isinstance(val, (int, float)):
                ext_confs.append(float(val))
                if val >= 75.0:
                    high_conf_cnt += 1
                elif val < 60.0:
                    low_conf_cnt += 1

    if product_info and hasattr(product_info, 'field_status') and product_info.field_status:
        for f_st in product_info.field_status.values():
            if f_st in ('UNCERTAIN', 'CONFLICT', 'AMBIGUOUS'):
                uncertain_cnt += 1

    for c in checks:
        rel = getattr(c, 'reliability_score', None) or (c.get('reliability_score') if isinstance(c, dict) else None)
        if rel is not None and isinstance(rel, (int, float)):
            ev_rels.append(float(rel))

    avg_ext_conf = round(sum(ext_confs) / len(ext_confs), 1) if ext_confs else 85.0
    avg_ev_rel = round(sum(ev_rels) / len(ev_rels), 1) if ev_rels else 85.0
    agg_conf = round((avg_ext_conf * 0.5) + (avg_ev_rel * 0.5), 1)
    conf_tier = "HIGH" if agg_conf >= 75.0 else ("MEDIUM" if agg_conf >= 55.0 else "LOW")

    confidence_summary = ConfidenceSummary(
        overall_confidence=agg_conf,
        extraction_confidence_avg=avg_ext_conf,
        evidence_reliability_avg=avg_ev_rel,
        high_confidence_declarations_count=high_conf_cnt,
        low_confidence_declarations_count=low_conf_cnt,
        uncertain_declarations_count=uncertain_cnt,
        candidate_conflict_count=len(conflicts),
        confidence_tier=conf_tier
    )

    # 6. Structured Risk Factors & Explanation
    risk_factors: List[RiskFactor] = []
    critical_factors: List[RiskFactor] = []
    review_factors: List[RiskFactor] = []

    def _get_chk_val(chk, attr, default=""):
        if isinstance(chk, dict):
            return chk.get(attr, default)
        return getattr(chk, attr, default) or default

    # Process Critical Violations
    for chk in failed_critical_checks:
        r_id = _get_chk_val(chk, 'rule_id', '')
        f_name = _get_chk_val(chk, 'field', '')
        f_label = _get_chk_val(chk, 'field_label', f_name)
        expl = _get_chk_val(chk, 'explanation', 'Mandatory declaration missing')
        src = _get_chk_val(chk, 'source', 'Statutory Rules')

        rf = RiskFactor(
            factor_id=f"RF-CRIT-{r_id}",
            factor_type="CRITICAL_STATUTORY_FAILURE",
            source_rule_id=r_id,
            source_field=f_name,
            severity="CRITICAL",
            title=f"Critical Non-Compliance: {f_label}",
            description=f"{f_label} was not detected or violates mandatory requirements. {expl}. Required by {src}.",
            resolution_action=f"Ensure {f_label} is conspicuously and accurately printed on the retail package."
        )
        risk_factors.append(rf)
        critical_factors.append(rf)

    # Process General Failures
    for chk in failed_general_checks:
        r_id = _get_chk_val(chk, 'rule_id', '')
        f_name = _get_chk_val(chk, 'field', '')
        f_label = _get_chk_val(chk, 'field_label', f_name)
        expl = _get_chk_val(chk, 'explanation', 'Statutory requirement not met')

        rf = RiskFactor(
            factor_id=f"RF-FAIL-{r_id}",
            factor_type="MISSING_MANDATORY_DECLARATION",
            source_rule_id=r_id,
            source_field=f_name,
            severity="HIGH",
            title=f"Missing Declaration: {f_label}",
            description=f"Statutory requirement for {f_label} is unfulfilled ({expl}).",
            resolution_action=f"Verify label artwork and add compliant {f_label} declaration."
        )
        risk_factors.append(rf)

    # Process Reviews and Uncertainties
    for chk in review_checks:
        r_id = _get_chk_val(chk, 'rule_id', '')
        f_name = _get_chk_val(chk, 'field', '')
        f_label = _get_chk_val(chk, 'field_label', f_name)
        reason = _get_chk_val(chk, 'reason', 'Manual verification required')

        rf = RiskFactor(
            factor_id=f"RF-REV-{r_id}",
            factor_type="DATA_AMBIGUITY",
            source_rule_id=r_id,
            source_field=f_name,
            severity="MEDIUM",
            title=f"Inspection Required: {f_label}",
            description=f"{f_label} detected but requires visual verification ({reason}).",
            resolution_action="Review physical packaging to verify stamp legibility and correctness."
        )
        risk_factors.append(rf)
        review_factors.append(rf)

    # Process Rule & Candidate Conflicts
    for idx, c in enumerate(conflicts):
        c_type = c.get('conflict_type', 'RULE_CONFLICT') if isinstance(c, dict) else getattr(c, 'conflict_type', 'RULE_CONFLICT')
        c_desc = c.get('description', '') if isinstance(c, dict) else getattr(c, 'description', '')
        c_rids = c.get('rule_ids', []) if isinstance(c, dict) else getattr(c, 'rule_ids', [])

        rf = RiskFactor(
            factor_id=f"RF-CONF-{idx+1}",
            factor_type="RULE_CONFLICT",
            source_rule_id=c_rids[0] if c_rids else None,
            severity="HIGH" if "CHRONOLOGICAL" in c_type or "IMPORT" in c_type else "MEDIUM",
            title=f"Cross-Declaration Conflict: {c_type}",
            description=c_desc,
            resolution_action="Verify physical package to resolve contradictory declarations."
        )
        risk_factors.append(rf)
        if rf.severity == "CRITICAL":
            critical_factors.append(rf)
        else:
            review_factors.append(rf)

    # 7. Risk Level Determination
    critical_violation_count = len(failed_critical_checks)
    missing_declaration_count = failed_count
    review_required_count = len(review_checks) + len(conflicts)

    # Check for severe conflicts (e.g. inverted shelf-life dates)
    has_critical_conflict = any(
        (c.get('conflict_type') if isinstance(c, dict) else getattr(c, 'conflict_type', '')) == 'CHRONOLOGICAL_INCONSISTENCY'
        for c in conflicts
    )

    if critical_violation_count >= cfg.critical_risk_threshold or has_critical_conflict:
        risk_level = "CRITICAL"
        risk_score = round(min(100.0, 85.0 + (critical_violation_count * 5.0) + (len(conflicts) * 3.0)), 1)
        risk_explanation = (
            f"Critical compliance risk: {critical_violation_count} mandatory high-severity statutory declaration(s) "
            f"are missing or non-compliant."
        )
    elif missing_declaration_count >= cfg.high_risk_failures_threshold or failed_count > 0:
        risk_level = "HIGH"
        risk_score = round(min(84.0, 65.0 + (missing_declaration_count * 6.0)), 1)
        risk_explanation = (
            f"High compliance risk: {missing_declaration_count} statutory declaration(s) failed standard screening requirements."
        )
    elif review_required_count >= cfg.medium_risk_review_threshold or insufficient_ev_count > 0 or len(conflicts) > 0:
        risk_level = "MEDIUM"
        risk_score = round(min(64.0, 35.0 + (review_required_count * 5.0)), 1)
        risk_explanation = (
            f"Medium compliance risk: {review_required_count} declaration(s) or evidence reading(s) require manual officer verification."
        )
    else:
        risk_level = "LOW"
        risk_score = round(max(5.0, 100.0 - overall_score), 1)
        risk_explanation = "Low compliance risk: All mandatory declarations are present and verified with acceptable confidence."

    risk_assessment = RiskAssessment(
        risk_level=risk_level,
        risk_score=risk_score,
        missing_declaration_count=missing_declaration_count,
        critical_violation_count=critical_violation_count,
        review_required_count=review_required_count,
        insufficient_evidence_count=insufficient_ev_count,
        risk_explanation=risk_explanation,
        risk_factors=risk_factors,
        critical_factors=critical_factors,
        review_factors=review_factors,
        confidence_summary=confidence_summary,
        scoring_version=cfg.scoring_version
    )

    return {
        'score': overall_score,
        'status': overall_status,
        'scoring_version': cfg.scoring_version,
        'rule_scores': rule_scores,
        'category_scores': category_scores,
        'confidence_summary': confidence_summary,
        'risk_assessment': risk_assessment,
        'missing_declaration_count': missing_declaration_count,
        'critical_violation_count': critical_violation_count,
        'review_required_count': review_required_count,
        'insufficient_evidence_count': insufficient_ev_count,
        'earned_points': round(earned_points, 2),
        'applicable_count': applicable_count
    }


