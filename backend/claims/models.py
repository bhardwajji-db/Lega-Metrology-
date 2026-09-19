"""
MetrCheck AI — Misleading Claim Detection Data Models
Defines extensible taxonomies, internal claim statuses, evidence linkages,
confidence breakdowns, and analysis result structures.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ClaimCategory(str, Enum):
    NUTRITIONAL = "NUTRITIONAL"
    HEALTH = "HEALTH"
    MEDICAL = "MEDICAL"
    INGREDIENT = "INGREDIENT"
    QUALITY = "QUALITY"
    ABSOLUTE = "ABSOLUTE"
    COMPARATIVE = "COMPARATIVE"
    CERTIFICATION = "CERTIFICATION"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    ORIGIN = "ORIGIN"
    MANUFACTURING = "MANUFACTURING"
    PRODUCT_PERFORMANCE = "PRODUCT_PERFORMANCE"
    SAFETY = "SAFETY"
    OTHER = "OTHER"


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    POTENTIAL_CONTRADICTION = "POTENTIAL_CONTRADICTION"
    HIGH_RISK_REVIEW = "HIGH_RISK_REVIEW"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class EvidenceLinkType(str, Enum):
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRADICTED_BY = "CONTRADICTED_BY"
    REQUIRES_EXTERNAL_VERIFICATION = "REQUIRES_EXTERNAL_VERIFICATION"


class ClaimEvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: "EVD-001")
    type: str  # INGREDIENT, NUTRITION_FACTS, CERTIFICATION, ORIGIN, REGISTRATION, TEXT_DECLARATION
    text: str
    panel: str = "FRONT"  # FRONT, BACK, SIDE_1, etc.
    image_index: int = 0
    confidence: float = 0.0  # 0.0 - 100.0
    bounding_box: Optional[List[int]] = None  # [x1, y1, x2, y2]
    relationship: EvidenceLinkType = EvidenceLinkType.SUPPORTED_BY
    explanation: Optional[str] = None


class ClaimConfidenceBreakdown(BaseModel):
    ocr_confidence: float = 0.0  # 0.0 - 100.0
    extraction_confidence: float = 0.0  # 0.0 - 100.0
    evidence_confidence: float = 0.0  # 0.0 - 100.0
    assessment_confidence: float = 0.0  # 0.0 - 100.0
    cross_panel_consistency: float = 1.0  # 0.0 - 1.0
    overall_confidence: float = 0.0  # 0.0 - 100.0


class ClaimAssessment(BaseModel):
    status: ClaimStatus
    reason: str
    detailed_explanation: str
    rule_id: Optional[str] = None
    rule_source: Optional[str] = None
    rule_reference: Optional[str] = None
    jurisdiction: str = "IN"
    requires_human_review: bool = False
    is_absolute: bool = False
    is_comparative: bool = False
    is_high_risk: bool = False
    verdict_distinction: str = "INSUFFICIENT_EVIDENCE"  # PROVEN_CONTRADICTION, NOT_PROVEN, SUPPORTED, REGULATORY_REVIEW_REQUIRED


class ClaimFinding(BaseModel):
    claim_id: str  # e.g. "CLM-001"
    claim_text: str
    normalized_claim: str
    category: ClaimCategory
    secondary_categories: List[ClaimCategory] = []
    source_panel: str = "FRONT"
    image_index: int = 0
    bounding_box: Optional[List[int]] = None  # [x1, y1, x2, y2]
    confidence: float = 0.0  # 0.0 - 100.0
    confidence_breakdown: ClaimConfidenceBreakdown
    evidence: List[ClaimEvidenceItem] = []
    assessment: ClaimAssessment
    model_version: str = "MetrCheck-ClaimEngine-v1.0"


class ClaimSummary(BaseModel):
    total_detected: int = 0
    supported: int = 0
    insufficient_evidence: int = 0
    potential_contradictions: int = 0
    high_risk_review: int = 0
    not_assessable: int = 0
    requires_human_review_count: int = 0


class ClaimAnalysisResult(BaseModel):
    claims_detected: int = 0
    summary: ClaimSummary
    claims: List[ClaimFinding] = []
    processing_time_ms: float = 0.0
    analyzed_panels: List[str] = []
    engine_version: str = "1.0.0"
