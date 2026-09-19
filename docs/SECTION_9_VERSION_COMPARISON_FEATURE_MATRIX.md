# MetrCheck AI — Master Roadmap Section 9: Version Comparison Feature Matrix

## Overview
Master Roadmap Section 9 implements comprehensive **Version Comparison** across physical packaging screenings and pre-print artwork iterations. The system enables automated, deterministic, and explainable change tracking for statutory declarations, ingredients, nutrition panels, compliance scores, and issue resolutions with sub-20ms latency.

---

## 14/14 Statutory & Technical Requirements Matrix

| # | Requirement | Implementation Component | Status | Verification Reference |
|---|-------------|---------------------------|--------|------------------------|
| **1** | **Product versioning** | `VersionSnapshot` schema with support for physical package screening snapshots (`analyses`) | **COMPLETE** | `test_version_comparison.py::test_api_version_targets_and_compare_saved` |
| **2** | **Packaging versioning** | Pre-print packaging artwork iterations (`artworks`, `iteration_number`, `parent_artwork_id`) | **COMPLETE** | `test_version_comparison.py::test_artwork_iterations_and_cross_comparison` |
| **3** | **Version A vs Version B** | Deterministic comparison pipeline (`compare_versions`) across both screening & artwork snapshots | **COMPLETE** | `test_version_comparison.py::test_identical_versions_no_changes`, `test_artwork_iterations_and_cross_comparison` |
| **4** | **Added declaration detection** | `compare_single_field` identifies declarations added in Version B (`change_type="ADDED"`) | **COMPLETE** | `test_version_comparison.py::test_added_and_removed_declaration_detection` |
| **5** | **Removed declaration detection** | `compare_single_field` flags mandatory or optional items omitted in Version B (`change_type="REMOVED"`) | **COMPLETE** | `test_version_comparison.py::test_added_and_removed_declaration_detection` |
| **6** | **Changed MRP detection** | `parse_and_normalize_mrp` extracts amounts, computes delta (₹) and percentage shift (%), with direction | **COMPLETE** | `test_version_comparison.py::test_changed_mrp_detection` |
| **7** | **Changed quantity detection** | `parse_and_normalize_quantity` normalizes units (g, kg, ml, l), computes net quantity delta | **COMPLETE** | `test_version_comparison.py::test_changed_quantity_detection` |
| **8** | **Changed manufacturer detection** | Entity comparison normalizes name, address, pin code, and flags manufacturer entity changes | **COMPLETE** | `test_version_comparison.py::test_changed_manufacturer_detection` |
| **9** | **Changed FSSAI number detection** | `normalize_fssai` extracts 14-digit license number and compares state of registration | **COMPLETE** | `test_version_comparison.py::test_changed_fssai_detection` |
| **10** | **Changed ingredients detection** | `compare_ingredients` performs token-level set difference (added, removed, common) & order detection | **COMPLETE** | `test_version_comparison.py::test_changed_ingredients_detection`, `test_ingredients_reordered_only` |
| **11** | **Changed nutrition information detection** | `compare_nutrition` generates per-100g nutrient delta table (Energy, Protein, Carbs, Sugar, Fat, Sodium) | **COMPLETE** | `test_version_comparison.py::test_changed_nutrition_detection` |
| **12** | **Compliance score comparison** | `score_diff` computes score delta (0–100), risk rating transition (e.g. HIGH → LOW), and score shift | **COMPLETE** | `test_version_comparison.py::test_compliance_score_and_rule_comparison` |
| **13** | **Issue-resolution tracking** | `track_issue_resolutions` matches rule IDs to classify issues: `RESOLVED`, `STILL_PRESENT`, `NEW_ISSUE` | **COMPLETE** | `test_version_comparison.py::test_compliance_score_and_rule_comparison` |
| **14** | **Version timeline** | `get_version_timeline` generates chronological audit trail across screenings, artworks, and diff events | **COMPLETE** | `test_version_comparison.py::test_version_timeline_generation`, `test_api_timeline_endpoint` |

---

## Architectural & Non-Functional Verification

- **Zero LLM / Zero OCR Overhead**: Purely deterministic AST-based and regex-normalized differencing engine with execution latency `< 20ms`.
- **Cross-Domain Comparison**: Supports physical screening vs physical screening, pre-print iteration vs pre-print iteration, and physical screening vs pre-print artwork.
- **Multilingual Token Normalization**: Preserves Indic numeral normalization (Devanagari, Bengali, Gujarati, Gurmukhi, Tamil, Telugu, Kannada, Malayalam, Odia) and currency variants.
- **Security & Data Integrity**: Role-based access control (RBAC), user isolation via `owner_user_id`, and full database persistence in `version_comparisons`.
