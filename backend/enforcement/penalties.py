"""MetrCheck AI — Enforcement support module.

Implements two enforcement artefacts demanded by DoCA workflows:

1. Penalty estimation under the Legal Metrology Act, 2009:
   - Section 36 : punishment for contravention of provisions
       1st offence  -> fine up to INR 25,000 (+ imprisonment up to 1 yr)
       subsequent   -> fine up to INR 50,000 (+ imprisonment 6 mo - 2 yrs)
   - Section 38 : penalty for non-registration / other specified offences

2. Show-Cause Notice generation — statutory notice template addressed to the
   manufacturer/packer/importer quoting detected violations + clauses.

NOTE: Estimates are advisory (for enforcement officer use) and clearly
labelled as such; final sanction order remains with the legal authority.
"""
from typing import Dict, List, Optional


# ── Severity weights used by the estimator ───────────────────────────────
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def estimate_penalty(
    violations: List[dict],
    repeat_offence: bool = False,
    prior_notices: int = 0,
) -> Dict:
    """Estimate penalty bracket under LM Act 2009 Sec 36 / Sec 38.

    violations: list of dicts with keys {'severity': 'high'|'medium'|'low',
                                        'rule_id'?, 'what'?}
    Returns deterministic advisory estimate.
    """
    if not violations:
        return {
            "applicable": False,
            "estimated_fine_inr": 0,
            "fine_range_inr": (0, 0),
            "basis": "No violations detected — no penalty estimated.",
            "sections": [],
        }

    weighted = sum(SEVERITY_WEIGHT.get(v.get("severity", "low"), 1) for v in violations)

    # Brute violation of a high-severity declaration (e.g. missing MRP/Net Qty)
    has_critical = any(v.get("severity") == "high" for v in violations)
    count = len(violations)

    sections = ["Section 36, Legal Metrology Act, 2009"]

    if repeat_offence or prior_notices > 0:
        # Subsequent offence — Sec 36(1) proviso: imprisonment 6 months to 2 years + fine
        fine_cap = 50_000
        base = 10_000 + weighted * 2_000 + count * 1_500
        sections.append("Section 36(1) proviso (subsequent offence)")
    elif has_critical:
        fine_cap = 25_000
        base = 5_000 + weighted * 1_500 + count * 1_000
    else:
        fine_cap = 25_000
        base = 2_000 + weighted * 1_000 + count * 500

    estimated = min(base, fine_cap)
    floor = max(1_000, estimated // 2)

    basis = (
        f"Advisory estimate based on {count} detected violation(s) "
        f"(weighted severity score {weighted}). "
        "Final penalty is determined by the competent authority under "
        "Section 36, Legal Metrology Act, 2009."
    )

    return {
        "applicable": True,
        "estimated_fine_inr": estimated,
        "fine_range_inr": (floor, estimated),
        "basis": basis,
        "sections": sections,
        "repeat_offence": repeat_offence,
        "prior_notices": prior_notices,
        "violation_count": count,
    }


def generate_show_cause(
    analysis_id: str,
    product_name: str,
    manufacturer: str,
    violations: List[dict],
    officer_name: str = "Legal Metrology Inspector",
    officer_designation: str = "Inspector, Legal Metrology",
    jurisdiction: str = "Consumer Affairs & Legal Metrology Directorate",
    deadline_days: int = 15,
) -> str:
    """Build a statutory show-cause notice (plain text, court-ready formatting)."""
    lines = []
    lines.append("=" * 72)
    lines.append("SHOW CAUSE NOTICE")
    lines.append("Under the Legal Metrology Act, 2009 read with")
    lines.append("Legal Metrology (Packaged Commodities) Rules, 2011")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Notice No: MC/SCN/{analysis_id[:8].upper()}")
    lines.append(f"Date    : (system issued)")
    lines.append(f"To      : {manufacturer or 'The Manufacturer / Packer / Importer'}")
    lines.append(f"Product : {product_name}")
    lines.append(f"Analysis ID: {analysis_id}")
    lines.append("")
    lines.append(f"Sir/Madam,")
    lines.append("")
    lines.append(
        "Whereas the above product was examined through the MetrCheck AI compliance "
        "screening system and the following non-compliances were recorded:"
    )
    lines.append("")
    for i, v in enumerate(violations, 1):
        lines.append(f"  {i}. {v.get('what', 'Declaration issue')}")
        lines.append(f"     Cause/Clause: {v.get('why', v.get('source_reference', 'Legal Metrology (PC) Rules, 2011'))}")
        lines.append(f"     Severity     : {v.get('severity', 'medium').upper()}")
    lines.append("")
    lines.append(
        f"You are hereby called upon to show cause within {deadline_days} days from the "
        "receipt of this notice as to why action under Section 36 of the Legal Metrology "
        "Act, 2009 should not be taken against you. Your reply, along with supporting "
        "documents, may be submitted to the undersigned."
    )
    lines.append("")
    lines.append("If no reply is received within the stipulated period, ex-parte action ")
    lines.append("shall be initiated as per law.")
    lines.append("")
    lines.append("-" * 72)
    lines.append(f"{officer_name}")
    lines.append(f"{officer_designation}")
    lines.append(f"{jurisdiction}")
    lines.append("-" * 72)
    lines.append("")
    lines.append("DISCLAIMER: This notice is auto-generated by MetrCheck AI as an advisory")
    lines.append("draft for enforcement officers. It must be reviewed, dated, signed and")
    lines.append("served by the competent authority.")
    return "\n".join(lines)