"""MetrCheck AI — Enforcement API routes.

Endpoints:
  POST /api/enforcement/penalty   — advisory penalty estimate for an analysis (officer+admin)
  POST /api/enforcement/notice    — generate show-cause notice text for an analysis
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from auth.security import ROLE_ADMIN, ROLE_ENFORCEMENT, get_current_user
from enforcement.penalties import estimate_penalty, generate_show_cause
from database.db import get_analysis
from models.schemas import ProductInfo

router = APIRouter(prefix="/enforcement", tags=["Enforcement"])

GUARD = Depends(get_current_user)


# ── Schemas ──────────────────────────────────────────────────────────────
class PenaltyRequest(BaseModel):
    analysis_id: str
    repeat_offence: bool = False
    prior_notices: int = 0


class NoticeRequest(BaseModel):
    analysis_id: str
    officer_name: str = "Legal Metrology Inspector"
    officer_designation: str = "Inspector, Legal Metrology"
    jurisdiction: str = "Consumer Affairs & Legal Metrology Directorate"
    deadline_days: int = Field(default=15, ge=1, le=90)


def _violations_from_analysis(data) -> list:
    """Convert stored compliance checks into {'severity','what','why','source_reference'} dicts."""
    import json
    violations = []
    try:
        comp = json.loads(data["compliance_result"]) if isinstance(data["compliance_result"], str) else data["compliance_result"]
        for c in comp.get("checks", []):
            status = (c.get("status") or "").upper()
            if status in ("FAIL", "FAILED", "NON_COMPLIANT"):
                violations.append({
                    "severity": "high" if c.get("required", True) else "medium",
                    "rule_id": c.get("rule_id", ""),
                    "what": f"{c.get('field_label') or c.get('field')} — {c.get('reason') or c.get('message') or 'not declared'}'".replace("''", ""),
                    "why": c.get("rule_id", "Legal Metrology (PC) Rules, 2011"),
                    "source_reference": c.get("rule_id", "LMPC Rules, 2011"),
                })
    except Exception:
        pass

    # Include font-size / readability failure if present
    try:
        import ast
        fs = data.get("font_size_analysis")
        if not fs:
            fs = data.get("font_size_analysis_json")
        if fs:
            if isinstance(fs, str):
                fs = ast.literal_eval(fs)
            if isinstance(fs, dict) and (fs.get("rule_12_verdict") or "").startswith("FAIL"):
                violations.append({
                    "severity": "medium",
                    "rule_id": "LM-012",
                    "what": f"Rule 12 font-size violation — net qty font {fs.get('net_quantity_font_height_mm')}mm below required {fs.get('min_required_font_height_mm')}mm",
                    "why": "Rule 12, LMPC Rules, 2011",
                    "source_reference": "Rule 12",
                })
    except Exception:
        pass
    return violations


# ── Routes ───────────────────────────────────────────────────────────────
@router.post("/penalty")
async def penalty_estimate(req: PenaltyRequest, user: dict = GUARD):
    if user["role"] not in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        raise HTTPException(status_code=403, detail="Enforcement or Admin role required.")
    data = await get_analysis(req.analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    violations = _violations_from_analysis(data)
    result = estimate_penalty(
        violations,
        repeat_offence=req.repeat_offence,
        prior_notices=req.prior_notices,
    )
    result["analysis_id"] = req.analysis_id
    result["product_name"] = data.get("product_name", "Unknown product")
    result["violations"] = violations
    result["issued_by"] = user.get("username")
    return result


@router.post("/notice")
async def show_cause(req: NoticeRequest, user: dict = GUARD):
    if user["role"] not in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        raise HTTPException(status_code=403, detail="Enforcement or Admin role required.")
    data = await get_analysis(req.analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    violations = _violations_from_analysis(data)
    if not violations:
        return {
            "notice": "No violations recorded for this analysis — show-cause notice is not applicable.",
            "analysis_id": req.analysis_id,
        }

    notice = generate_show_cause(
        analysis_id=req.analysis_id,
        product_name=data.get("product_name", "Unknown product"),
        manufacturer=data.get("manufacturer") or data.get("product_name") or "Manufacturer",
        violations=violations,
        officer_name=req.officer_name,
        officer_designation=req.officer_designation,
        jurisdiction=req.jurisdiction,
        deadline_days=req.deadline_days,
    )
    return {"notice": notice, "analysis_id": req.analysis_id, "generated_by": user.get("username")}