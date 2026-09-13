# Configured statutory screening weights
WEIGHT_PASS = 1.0
WEIGHT_WARNING = 0.5
WEIGHT_NEEDS_REVIEW = 0.85
WEIGHT_FAIL = 0.0

def calculate_score(checks: list) -> dict:
    """
    Statutory Compliance Screening Score:
    Evaluates all applicable rules with configured, explicit weights:
    - PASS: 1.0 (100% compliance earned)
    - WARNING: 0.5 (partial conformity / cautionary finding)
    - NEEDS_REVIEW: 0.85 (uncertainty / unverified text, not penalized as failure)
    - FAIL: 0.0 (confirmed violation / missing mandatory declaration)
    - NOT_APPLICABLE: excluded completely from denominator
    
    Formula:
      Score = (1.0 * pass + 0.5 * warn + 0.85 * review + 0.0 * fail) / applicable_rules * 100
    """
    applicable_count = 0
    earned_points = 0.0
    
    for check in checks:
        # Standardize check status string
        st = (getattr(check, 'status', None) or check.get('status', 'FAIL')).upper()
        
        # Exclude NOT_APPLICABLE from denominator
        if st == 'NOT_APPLICABLE':
            continue
            
        applicable_count += 1
        
        if st == 'PASS':
            earned_points += WEIGHT_PASS
        elif st == 'WARNING':
            earned_points += WEIGHT_WARNING
        elif st == 'NEEDS_REVIEW':
            earned_points += WEIGHT_NEEDS_REVIEW
        elif st == 'FAIL':
            earned_points += WEIGHT_FAIL
            
    score = (earned_points / applicable_count) * 100 if applicable_count > 0 else 100.0
    
    # Categorize overall product screening status based on verified rule outcomes
    has_fail = any((getattr(c, 'status', None) or c.get('status', '')).upper() == 'FAIL' for c in checks)
    has_review = any((getattr(c, 'status', None) or c.get('status', '')).upper() == 'NEEDS_REVIEW' for c in checks)
    
    if has_fail:
        # One or more genuine statutory failures confirmed
        status = 'POTENTIAL NON-COMPLIANCE'
    elif has_review:
        # No confirmed failure, but one or more declarations require manual inspector verification
        status = 'REVIEW REQUIRED'
    elif score >= 80.0:
        # No failures or unresolved critical review issues
        status = 'COMPLIANT'
    else:
        status = 'REVIEW REQUIRED'
        
    return {
        'score': round(score, 1),
        'status': status
    }

