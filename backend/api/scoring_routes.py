from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from models.schemas import (
    ScoringConfiguration,
    ProductRiskHistory,
    BatchRiskDistribution,
    ScoreHistoryEntry
)
from compliance.scorer import get_scoring_config, set_scoring_config
from database.db import (
    get_analysis,
    get_product_risk_history,
    get_batch_risk_distribution,
    _extract_analysis_risk_info,
    log_security_event
)
from auth.security import require_roles, ROLE_ADMIN, ROLE_MERCHANT, get_current_user, check_tenant_access
import json

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("/config", response_model=ScoringConfiguration)
async def get_configuration():
    """Retrieve the current active scoring weights and risk thresholds."""
    return get_scoring_config()


@router.put("/config", response_model=ScoringConfiguration)
async def update_configuration(
    new_config: ScoringConfiguration,
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Update active scoring weights and risk thresholds (Admin only)."""
    updated = set_scoring_config(new_config)
    try:
        await log_security_event(
            event_type="SCORING_CONFIG_UPDATE",
            actor_username=user.get("username", "admin"),
            resource_id="global_scoring_config",
            details=f"Admin updated scoring configuration (version: {new_config.scoring_version})."
        )
    except Exception:
        pass
    return updated


@router.get("/history/{analysis_id}", response_model=ScoreHistoryEntry)
async def get_analysis_score_history(
    analysis_id: str,
    user: dict = Depends(get_current_user)
):
    """Retrieve scoring breakdown and risk tier for a specific analysis record."""
    analysis = await get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")
    
    check_tenant_access(user, analysis, raise_exception=True)
    info = _extract_analysis_risk_info(analysis)
    return ScoreHistoryEntry(**info)


@router.get("/product/{product_name}/history", response_model=ProductRiskHistory)
async def get_product_history(
    product_name: str,
    user: dict = Depends(get_current_user)
):
    """Retrieve historical compliance scores and risk trajectory for a product scoped to tenant/user."""
    user_role = user.get("role")
    org_id = user.get("organization_id")
    owner = user.get("username")

    data = await get_product_risk_history(
        product_name=product_name,
        organization_id=org_id,
        owner_user_id=owner if user_role == ROLE_MERCHANT else None,
        user_role=user_role
    )
    return ProductRiskHistory(**data)


@router.get("/batch-distribution", response_model=BatchRiskDistribution)
async def get_batch_distribution(
    owner_user_id: Optional[str] = Query(None, description="Optional owner filter"),
    user: dict = Depends(get_current_user)
):
    """Retrieve aggregated batch risk level distribution scoped to tenant/user."""
    user_role = user.get("role")
    org_id = user.get("organization_id")

    if user_role == ROLE_ADMIN:
        data = await get_batch_risk_distribution(owner_user_id=owner_user_id, user_role=user_role)
    elif user_role == ROLE_MERCHANT:
        # Enforce merchant's own organization and username regardless of query params
        data = await get_batch_risk_distribution(
            organization_id=org_id,
            owner_user_id=user.get("username"),
            user_role=user_role
        )
    else:
        data = await get_batch_risk_distribution(
            organization_id=org_id,
            owner_user_id=owner_user_id,
            user_role=user_role
        )
    return BatchRiskDistribution(**data)
