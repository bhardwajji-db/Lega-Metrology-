from fastapi import APIRouter
from models.schemas import ProductInfo, ComplianceResult
from compliance.engine import engine
from compliance.rules.registry import registry

router = APIRouter()

@router.post("/compliance/check", response_model=ComplianceResult)
async def check_compliance(info: ProductInfo):
    result_dict = engine.check(info)
    return ComplianceResult(**result_dict)

@router.get("/compliance/rules")
async def get_rules():
    return [r.model_dump() for r in registry.get_all_rules()]

