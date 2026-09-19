from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from models.schemas import ProductInfo, ComplianceResult, RuleTestRequest, RuleTestResponse
from compliance.engine import engine
from compliance.rules.registry import registry
from database.db import get_analysis
from auth.security import get_current_user, check_tenant_access

router = APIRouter()

@router.post("/compliance/check", response_model=ComplianceResult)
async def check_compliance(info: ProductInfo):
    result_dict = engine.check(info)
    return ComplianceResult(**result_dict)

@router.get("/compliance/rules")
async def get_rules(
    category: Optional[str] = Query(None, description="Filter by category (ALL, FOOD, NON_FOOD, COSMETICS, MEDICAL_DEVICES, EXPORT)"),
    domain: Optional[str] = Query(None, description="Filter by domain (LEGAL_METROLOGY, FSSAI)"),
    version: Optional[str] = Query(None, description="Filter by rule version string")
):
    rules = registry.get_all_rules()
    if category:
        c_upper = category.upper()
        rules = [
            r for r in rules
            if (
                c_upper == "ALL"
                or (isinstance(r.category_applicability, list) and (c_upper in r.category_applicability or "ALL" in r.category_applicability))
                or (hasattr(r.category_applicability, "value") and (r.category_applicability.value in (c_upper, "ALL")))
                or str(r.category_applicability) in (c_upper, "ALL")
            )
        ]
    if domain:
        d_upper = domain.upper()
        rules = [r for r in rules if r.domain.value == d_upper]
    if version:
        rules = [r for r in rules if r.rule_version == version]
    return [r.model_dump() if hasattr(r, 'model_dump') else r.dict() for r in rules]

@router.get("/compliance/rules/{rule_id}")
async def get_rule_detail(rule_id: str):
    rule = registry.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule with ID '{rule_id}' not found in registry.")
    return rule.model_dump() if hasattr(rule, 'model_dump') else rule.dict()

@router.post("/compliance/test-rule", response_model=RuleTestResponse)
async def test_rule(req: RuleTestRequest):
    """
    Simulate single rule evaluation in memory with zero database side-effects.
    """
    try:
        response = engine.test_single_rule(
            rule_id=req.rule_id,
            product_info=req.product_info,
            ocr_text=req.ocr_text or "",
            context_override=req.context_override
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")

@router.get("/compliance/conflicts/{analysis_id}")
async def get_analysis_conflicts(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    import json
    analysis_data = await get_analysis(analysis_id)
    if not analysis_data:
        raise HTTPException(status_code=404, detail=f"Analysis with ID '{analysis_id}' not found")
    
    check_tenant_access(user, analysis_data, raise_exception=True)
    
    compliance_raw = analysis_data.get("compliance_result") or analysis_data.get("result") or {}
    if isinstance(compliance_raw, str):
        try:
            compliance_raw = json.loads(compliance_raw)
        except Exception:
            compliance_raw = {}
    
    conflicts = []
    if isinstance(compliance_raw, dict):
        if "conflicts" in compliance_raw and isinstance(compliance_raw["conflicts"], list):
            conflicts = compliance_raw["conflicts"]
        elif "compliance" in compliance_raw and isinstance(compliance_raw["compliance"], dict):
            conflicts = compliance_raw["compliance"].get("conflicts", [])

    return {"analysis_id": analysis_id, "conflicts": conflicts}



