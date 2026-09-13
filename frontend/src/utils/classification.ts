import type { ComplianceCheck, ComplianceResult } from '../types';

export type AnalysisOutcome = 'COMPLIANT' | 'NEEDS_REVIEW' | 'FAILURE';

/**
 * Authoritative classification precedence: FAILED > REVIEW > COMPLIANT.
 * Does NOT infer status from score.
 */
export function classifyAnalysisOutcome(
  status?: string | null,
  complianceResult?: ComplianceResult | null
): AnalysisOutcome {
  if (complianceResult) {
    const checks = complianceResult.checks || [];
    if (checks.length > 0) {
      const hasFail = checks.some((c: ComplianceCheck) => {
        const s = (c.status || '').toUpperCase();
        return s === 'FAIL' || s === 'NON_COMPLIANT' || s === 'FAILED';
      });
      if (hasFail) return 'FAILURE';

      const hasReview = checks.some((c: ComplianceCheck) => {
        const s = (c.status || '').toUpperCase();
        return s === 'NEEDS_REVIEW' || s === 'WARNING' || s === 'REVIEW_REQUIRED';
      });
      if (hasReview) return 'NEEDS_REVIEW';

      const hasPass = checks.some((c: ComplianceCheck) => {
        const s = (c.status || '').toUpperCase();
        return s === 'PASS' || s === 'COMPLIANT' || s === 'PASSED';
      });
      if (hasPass) return 'COMPLIANT';
    } else {
      if ((complianceResult.failed_rules ?? 0) > 0) return 'FAILURE';
      if ((complianceResult.needs_review_rules ?? 0) + (complianceResult.warning_rules ?? 0) > 0) return 'NEEDS_REVIEW';
      if ((complianceResult.passed_rules ?? 0) > 0 || (complianceResult.status || '').toUpperCase() === 'COMPLIANT') {
        return 'COMPLIANT';
      }
    }
  }

  const s = (status || '').toUpperCase();
  if (s.includes('FAIL') || s.includes('NON_COMPLIANCE') || s.includes('NON-COMPLIANCE')) {
    return 'FAILURE';
  }
  if (s.includes('REVIEW') || s.includes('WARNING')) {
    return 'NEEDS_REVIEW';
  }
  if (s.includes('COMPLIANT') || s.includes('PASS')) {
    return 'COMPLIANT';
  }

  return 'NEEDS_REVIEW';
}
