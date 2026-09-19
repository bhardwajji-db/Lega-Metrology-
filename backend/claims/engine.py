"""
MetrCheck AI — Misleading Claim Detection Pipeline Engine
Coordinates Claim Extraction, Multi-Panel Evidence Linking, Contradiction Engine,
Confidence Model, and Summary Aggregation.
"""

import time
import uuid
import logging
from typing import List, Optional
from models.schemas import ProductInfo, ProductImageEvidence
from claims.models import (
    ClaimAnalysisResult,
    ClaimSummary,
    ClaimFinding,
    ClaimCategory,
    ClaimStatus
)
from claims.extractor import claim_extractor
from claims.contradiction_engine import contradiction_engine

logger = logging.getLogger(__name__)


class MisleadingClaimEngine:
    def __init__(self):
        self.extractor = claim_extractor
        self.contradiction_engine = contradiction_engine

    def analyze(
        self,
        product_info: ProductInfo,
        ocr_text: str = "",
        images: Optional[List[ProductImageEvidence]] = None
    ) -> ClaimAnalysisResult:
        """
        Executes the full claim verification pipeline over extracted product info and images.
        """
        start_time = time.perf_counter()

        # Step 1: Extract claims across all package panels
        raw_claims = self.extractor.extract_claims(ocr_text, images)

        findings: List[ClaimFinding] = []
        analyzed_panels = set()
        if images:
            for img in images:
                analyzed_panels.add((img.label or "FRONT").upper())
        if not analyzed_panels:
            analyzed_panels.add("FRONT")

        # Step 2: Evaluate each claim against package evidence
        for idx, rc in enumerate(raw_claims):
            claim_id = f"CLM-{idx+1:03d}"
            analyzed_panels.add(rc.source_panel)

            assessment, evidence_items, conf_breakdown = self.contradiction_engine.evaluate_claim(
                claim=rc,
                product_info=product_info,
                images=images,
                combined_ocr_text=ocr_text
            )

            # Determine secondary categories if applicable
            sec_cats = []
            if rc.is_absolute and rc.category != ClaimCategory.ABSOLUTE:
                sec_cats.append(ClaimCategory.ABSOLUTE)
            if rc.is_comparative and rc.category != ClaimCategory.COMPARATIVE:
                sec_cats.append(ClaimCategory.COMPARATIVE)

            finding = ClaimFinding(
                claim_id=claim_id,
                claim_text=rc.claim_text,
                normalized_claim=rc.normalized_claim,
                category=rc.category,
                secondary_categories=sec_cats,
                source_panel=rc.source_panel,
                image_index=rc.image_index,
                bounding_box=rc.bounding_box,
                confidence=conf_breakdown.overall_confidence,
                confidence_breakdown=conf_breakdown,
                evidence=evidence_items,
                assessment=assessment,
                model_version="MetrCheck-ClaimEngine-v1.0"
            )
            findings.append(finding)

        # Step 3: Compute summary counts
        supported_count = sum(1 for f in findings if f.assessment.status == ClaimStatus.SUPPORTED)
        insufficient_count = sum(1 for f in findings if f.assessment.status == ClaimStatus.INSUFFICIENT_EVIDENCE)
        contradiction_count = sum(1 for f in findings if f.assessment.status == ClaimStatus.POTENTIAL_CONTRADICTION)
        high_risk_count = sum(1 for f in findings if f.assessment.status == ClaimStatus.HIGH_RISK_REVIEW)
        not_assessable_count = sum(1 for f in findings if f.assessment.status == ClaimStatus.NOT_ASSESSABLE)
        review_count = sum(1 for f in findings if f.assessment.requires_human_review)

        summary = ClaimSummary(
            total_detected=len(findings),
            supported=supported_count,
            insufficient_evidence=insufficient_count,
            potential_contradictions=contradiction_count,
            high_risk_review=high_risk_count,
            not_assessable=not_assessable_count,
            requires_human_review_count=review_count
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return ClaimAnalysisResult(
            claims_detected=len(findings),
            summary=summary,
            claims=findings,
            processing_time_ms=round(elapsed_ms, 2),
            analyzed_panels=sorted(list(analyzed_panels)),
            engine_version="1.0.0"
        )


claim_engine = MisleadingClaimEngine()
