# MetrCheck AI — Master Roadmap Section 7: Compliance Scoring & Risk Feature Matrix

**Status:** Implementation Baseline  
**Date:** September 17, 2026  
**Module:** Master Roadmap Section 7 (Compliance Scoring & Risk)  

---

## 1. Requirement Classification Matrix (All 20 Requirements)

| # | Requirement Name | Scope & Architectural Mapping | Implementation Target | Status |
| :- | :--- | :--- | :--- | :--- |
| **1** | **Overall compliance score** | Deterministic score aggregating applicable rule points with configurable weights (`0.0 - 100.0`). | `backend/compliance/scorer.py` | Ready for Implementation |
| **2** | **Rule-level score** | Structured `RuleScore` per evaluated rule with points earned, max points, weight, reliability, confidence, risk contribution. | `backend/compliance/scorer.py` | Ready for Implementation |
| **3** | **Category score** | Aggregated `CategoryScore` for Legal Metrology, FSSAI, and specific product categories (`FOOD`, `NON_FOOD`, etc.). | `backend/compliance/scorer.py` | Ready for Implementation |
| **4** | **Evidence confidence** | Aggregated summary of Section 5 evidence reliability scores, tiers, and spatial token density. | `backend/compliance/scorer.py` | Ready for Implementation |
| **5** | **Extraction confidence** | Aggregated summary of Section 4 candidate confidences, validation statuses, and candidate conflict uncertainty. | `backend/compliance/scorer.py` | Ready for Implementation |
| **6** | **Risk level** | 4-Tier deterministic classification: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. | `backend/compliance/scorer.py` | Ready for Implementation |
| **7** | **Critical-risk identification** | High-severity mandatory rule failures (`LM-001`, `LM-004`, `FS-001`, `FS-005` expired) or critical chronological conflicts. | `backend/compliance/scorer.py` | Ready for Implementation |
| **8** | **High-risk identification** | Medium/high severity failures, 2+ missing declarations, or severe cross-rule discrepancies. | `backend/compliance/scorer.py` | Ready for Implementation |
| **9** | **Medium-risk identification** | Low-severity failures, 2+ declarations requiring review, or low evidence reliability. | `backend/compliance/scorer.py` | Ready for Implementation |
| **10** | **Low-risk identification** | Full statutory compliance or minor non-critical review items. | `backend/compliance/scorer.py` | Ready for Implementation |
| **11** | **Risk explanation** | Grounded narrative explaining why the product was assigned its specific risk level. | `backend/compliance/scorer.py` | Ready for Implementation |
| **12** | **Risk-factor breakdown** | List of structured `RiskFactor` items with factor type, source rule, severity, evidence ref, and action. | `backend/compliance/scorer.py` | Ready for Implementation |
| **13** | **Missing-declaration count** | Exact count of applicable rules where mandatory declarations were missing (`FAIL` status). | `backend/compliance/scorer.py` | Ready for Implementation |
| **14** | **Critical violation count** | Count of failed rules with high or critical statutory severity. | `backend/compliance/scorer.py` | Ready for Implementation |
| **15** | **Review-required count** | Count of applicable items needing human review (`NEEDS_REVIEW`, `WARNING`, `INSUFFICIENT_EVIDENCE`, conflicts). | `backend/compliance/scorer.py` | Ready for Implementation |
| **16** | **Confidence-adjusted reporting** | Separating high-confidence conclusive findings from low-confidence items flagged for human verification. | `backend/compliance/scorer.py` | Ready for Implementation |
| **17** | **Configurable scoring rules** | Backend-defined `ScoringConfiguration` with configurable weights, thresholds, and factors. | `backend/compliance/scorer.py` | Ready for Implementation |
| **18** | **Score history** | Preserving scoring version, score, risk level, and counts on historical analysis records. | `backend/database/db.py` | Ready for Implementation |
| **19** | **Product risk history** | Querying risk level progression and historical compliance events across analyses for a product. | `backend/database/db.py` | Ready for Implementation |
| **20** | **Batch risk distribution** | Computing distribution of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` risk across stored analyses in a batch/query. | `backend/database/db.py` | Ready for Implementation |

---

## 2. Distinction Safeguards

- **Statutory Rule Version (`rule_version`):** Represents gazette amendment history (e.g. `2011.amended`, `2022.1`).
- **Scoring Engine Version (`scoring_version`):** Represents MetrCheck mathematical scoring model version (e.g. `2026.1`).
- **OCR Confidence:** Raw character-recognition certainty (0-100%).
- **Extraction Confidence:** Semantic field extraction candidate certainty (0-100%).
- **Evidence Reliability:** Provenance, spatial geometry, and token density score (0-100%).
- **Compliance Score:** Mathematical percentage of statutory screening conformity (0-100%).
- **Risk Level:** Decision-support categorization (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
