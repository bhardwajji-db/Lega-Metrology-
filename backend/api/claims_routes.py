"""
MetrCheck AI — Misleading Claim Detection API Endpoints
Provides dedicated endpoints for analyzing packaging claims, querying configured regulatory rules,
and retrieving persisted claim findings with evidence provenance.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from pydantic import BaseModel
from claims.models import ClaimAnalysisResult, ClaimCategory, ClaimFinding
from claims.engine import claim_engine
from claims.rule_engine import claim_rule_registry
from database.db import get_analysis, get_claim_findings_by_analysis_id, get_claim_evidence_links_by_analysis_id
from models.schemas import ProductInfo, ProductImageEvidence
from extraction.llm_extractor import llm_extractor
from auth.security import public_user
import json

router = APIRouter()


class ClaimAnalyzeRequest(BaseModel):
    analysis_id: Optional[str] = None
    text: Optional[str] = None
    product_info: Optional[ProductInfo] = None


@router.post("/claims/analyze", response_model=ClaimAnalysisResult, tags=["Misleading Claims"])
async def analyze_claims_endpoint(
    req: ClaimAnalyzeRequest,
    user: Optional[dict] = Depends(public_user)
):
    """
    Evaluate product packaging for misleading, contradictory, or unsubstantiated claims.
    Accepts an existing analysis_id, raw text, or structured product information.
    """
    if req.analysis_id:
        data = await get_analysis(req.analysis_id)
        if not data:
            if req.analysis_id.startswith("demo-") or req.analysis_id in ("1", "2", "3"):
                from api.demo import build_demo_response
                demo_resp = build_demo_response(req.analysis_id)
                if demo_resp.claims_analysis:
                    return demo_resp.claims_analysis
                return claim_engine.analyze(
                    product_info=demo_resp.product_info,
                    ocr_text=demo_resp.ocr_result.full_text,
                    images=demo_resp.images
                )
            raise HTTPException(status_code=404, detail=f"Analysis '{req.analysis_id}' not found.")

        # Check if already stored
        if data.get('claims_analysis'):
            try:
                raw_c = json.loads(data['claims_analysis']) if isinstance(data['claims_analysis'], str) else data['claims_analysis']
                return ClaimAnalysisResult(**raw_c)
            except Exception:
                pass

        # Reconstruct and analyze
        ext_dict = json.loads(data['extracted_data']) if isinstance(data['extracted_data'], str) else data['extracted_data']
        prod_info = ProductInfo(**ext_dict)
        imgs = []
        if data.get('images'):
            try:
                raw_imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
                imgs = [ProductImageEvidence(**im) for im in raw_imgs]
            except Exception:
                imgs = []

        return claim_engine.analyze(
            product_info=prod_info,
            ocr_text=data.get('ocr_text', ''),
            images=imgs
        )

    if req.text:
        text = req.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Provided text is empty.")
        prod_info = req.product_info or llm_extractor.extract(text)
        return claim_engine.analyze(
            product_info=prod_info,
            ocr_text=text,
            images=[]
        )

    if req.product_info:
        return claim_engine.analyze(
            product_info=req.product_info,
            ocr_text="",
            images=[]
        )

    raise HTTPException(
        status_code=400,
        detail="Must provide either analysis_id, text, or product_info for claim analysis."
    )


@router.get("/claims/rules", tags=["Misleading Claims"])
async def list_claim_rules(
    category: Optional[str] = Query(None, description="Filter rules by claim category (e.g. NUTRITIONAL, INGREDIENT, HEALTH, MEDICAL, COMPARATIVE, ENVIRONMENTAL)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (LOW, MEDIUM, HIGH, CRITICAL)")
):
    """Retrieve all configured statutory regulatory rules applied by the claim verification engine."""
    rules = claim_rule_registry.get_all_rules()

    if category:
        c_upper = category.upper()
        rules = [r for r in rules if r.category.value == c_upper]

    if risk_level:
        r_upper = risk_level.upper()
        rules = [r for r in rules if r.risk_level.upper() == r_upper]

    return [r.to_dict() for r in rules]


@router.get("/claims/rules/{rule_id}", tags=["Misleading Claims"])
async def get_claim_rule(rule_id: str):
    """Retrieve details for a specific statutory claim rule."""
    rule = claim_rule_registry.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Claim rule with ID '{rule_id}' not found.")
    return rule.to_dict()


@router.get("/claims/{analysis_id}", tags=["Misleading Claims"])
async def get_analysis_claims(analysis_id: str, user: Optional[dict] = Depends(public_user)):
    """Retrieve persisted claim findings and graph evidence links for an inspection record."""
    data = await get_analysis(analysis_id)
    if not data and (analysis_id.startswith("demo-") or analysis_id in ("1", "2", "3")):
        from api.demo import build_demo_response
        demo_resp = build_demo_response(analysis_id)
        if demo_resp.claims_analysis:
            return demo_resp.claims_analysis
        return claim_engine.analyze(
            product_info=demo_resp.product_info,
            ocr_text=demo_resp.ocr_result.full_text,
            images=demo_resp.images
        )

    if not data:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")

    findings = await get_claim_findings_by_analysis_id(analysis_id)
    links = await get_claim_evidence_links_by_analysis_id(analysis_id)

    # If findings already in database, return structured findings
    if findings:
        # Group links by claim_id
        links_by_claim: Dict[str, list] = {}
        for l in links:
            cid = l.get('claim_id')
            if cid not in links_by_claim:
                links_by_claim[cid] = []
            links_by_claim[cid].append(l)

        structured_claims = []
        for f in findings:
            cid = f.get('claim_id')
            c_links = links_by_claim.get(cid, [])
            bbox = json.loads(f.get('bounding_box') or '[]')
            structured_claims.append({
                "claim_id": cid,
                "claim_text": f.get('claim_text'),
                "normalized_claim": f.get('normalized_claim'),
                "category": f.get('category'),
                "source_panel": f.get('source_panel'),
                "image_index": f.get('image_index', 0),
                "bounding_box": bbox if bbox else None,
                "confidence": f.get('confidence', 0.0),
                "confidence_breakdown": {
                    "ocr_confidence": f.get('confidence', 0.0),
                    "extraction_confidence": f.get('extraction_confidence', 0.0),
                    "evidence_confidence": f.get('evidence_confidence', 0.0),
                    "assessment_confidence": f.get('assessment_confidence', 0.0),
                    "cross_panel_consistency": 1.0,
                    "overall_confidence": f.get('confidence', 0.0)
                },
                "evidence": [
                    {
                        "id": f"EVD-{i+1:03d}",
                        "type": l.get('evidence_type'),
                        "text": l.get('evidence_text'),
                        "panel": l.get('evidence_panel'),
                        "image_index": l.get('image_index', 0),
                        "confidence": l.get('confidence', 0.0),
                        "bounding_box": json.loads(l.get('bounding_box') or '[]') or None,
                        "relationship": l.get('link_type'),
                        "explanation": l.get('explanation')
                    }
                    for i, l in enumerate(c_links)
                ],
                "assessment": {
                    "status": f.get('status'),
                    "reason": f.get('reason'),
                    "detailed_explanation": f.get('detailed_explanation'),
                    "rule_id": f.get('rule_id'),
                    "rule_source": f.get('rule_source'),
                    "rule_reference": f.get('rule_reference'),
                    "jurisdiction": f.get('jurisdiction', 'IN'),
                    "requires_human_review": bool(f.get('requires_human_review')),
                    "is_absolute": bool(f.get('is_absolute')),
                    "is_comparative": bool(f.get('is_comparative')),
                    "is_high_risk": bool(f.get('is_high_risk')),
                    "verdict_distinction": f.get('verdict_distinction', 'NOT_PROVEN')
                }
            })

        return {
            "analysis_id": analysis_id,
            "claims_detected": len(structured_claims),
            "claims": structured_claims
        }

    # Fallback to claims_analysis column or recompute
    if data.get('claims_analysis'):
        try:
            return json.loads(data['claims_analysis']) if isinstance(data['claims_analysis'], str) else data['claims_analysis']
        except Exception:
            pass

    ext_dict = json.loads(data['extracted_data']) if isinstance(data['extracted_data'], str) else data['extracted_data']
    prod_info = ProductInfo(**ext_dict)
    imgs = []
    if data.get('images'):
        try:
            raw_imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
            imgs = [ProductImageEvidence(**im) for im in raw_imgs]
        except Exception:
            imgs = []

    res = claim_engine.analyze(product_info=prod_info, ocr_text=data.get('ocr_text', ''), images=imgs)
    return res.model_dump()
