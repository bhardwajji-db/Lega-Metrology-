from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from models.schemas import (
    ProductInfo, 
    ComplianceResult, 
    ComplianceCheck, 
    ComplianceIssue, 
    EvidenceItem,
    Recommendation
)


class ReviewStatus(str):
    PENDING_REVIEW = "PENDING_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    VERIFIED_PASS = "VERIFIED_PASS"
    VERIFIED_FAIL = "VERIFIED_FAIL"
    VERIFIED_NEEDS_REVIEW = "VERIFIED_NEEDS_REVIEW"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    REOPENED = "REOPENED"
    CLOSED = "CLOSED"


class HumanVerifiedStatus(str):
    VERIFIED_PASS = "VERIFIED_PASS"
    VERIFIED_FAIL = "VERIFIED_FAIL"
    VERIFIED_NEEDS_REVIEW = "VERIFIED_NEEDS_REVIEW"
    REJECTED = "REJECTED"
    NOT_VERIFIED = "NOT_VERIFIED"


class FieldCorrectionItem(BaseModel):
    """Record of an officer correcting a statutory declaration value."""
    field_name: str
    field_label: str
    original_value: Optional[str] = None
    corrected_value: str
    reason: Optional[str] = None
    officer_username: str
    officer_role: str
    timestamp: str
    evidence_id: Optional[str] = None


class OfficerCommentItem(BaseModel):
    """Structured comment / note entered by an officer during review."""
    comment_id: str
    comment_type: str = "GENERAL"  # GENERAL, CORRECTION, REJECTION, ESCALATION, REOPEN, SIGN_OFF
    text: str
    officer_username: str
    officer_role: str
    timestamp: str


class ReviewHistoryEvent(BaseModel):
    """Immutable audit trail event for officer review actions."""
    event_id: str
    action: str  # CREATED, ASSIGNED, STATUS_CHANGED, FIELD_CORRECTED, EVIDENCE_ADDED, EVIDENCE_REMOVED, ACCEPTED, REJECTED, ESCALATED, REOPENED, VERIFIED, COMMENT_ADDED
    actor_username: str
    actor_role: str
    details: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any] = {}


class AssignReviewRequest(BaseModel):
    """Payload to assign a review to an officer."""
    assigned_officer: str
    comments: Optional[str] = None


class AcceptReviewRequest(BaseModel):
    """Payload to accept AI results as authoritative human verification."""
    comments: Optional[str] = None
    final_status: Optional[str] = None  # Auto-inferred if None (VERIFIED_PASS / VERIFIED_FAIL)


class RejectReviewRequest(BaseModel):
    """Payload to reject AI results."""
    rejection_reason: str  # INCORRECT_EXTRACTION, INSUFFICIENT_EVIDENCE, WRONG_RULE_EVALUATION, IMAGE_QUALITY_ISSUE, OTHER
    comments: str


class CorrectFieldRequest(BaseModel):
    """Payload for an officer correcting an extracted statutory field."""
    field_name: str
    field_label: str
    corrected_value: str
    reason: Optional[str] = None
    evidence_id: Optional[str] = None


class AddEvidenceRequest(BaseModel):
    """Payload for an officer annotating missing evidence."""
    image_index: int = 0
    image_label: str = "Front"
    text: str
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    linked_rule_id: str
    linked_field: str
    comments: Optional[str] = None


class RemoveEvidenceRequest(BaseModel):
    """Payload for an officer marking/soft-removing incorrect evidence."""
    evidence_id: str
    reason: str


class AddCommentRequest(BaseModel):
    """Payload to add a review comment."""
    comment_type: str = "GENERAL"
    text: str


class EscalateReviewRequest(BaseModel):
    """Payload to escalate an audit review to senior officials/admin."""
    escalation_target: Optional[str] = None  # e.g. "ADMIN" or specific supervisor
    escalation_reason: str
    comments: Optional[str] = None


class ReopenReviewRequest(BaseModel):
    """Payload to reopen a completed/verified review."""
    reopen_reason: str
    comments: Optional[str] = None


class AIvsHumanDiffItem(BaseModel):
    """Single item difference between AI automated output and Human-verified output."""
    field_name: str
    field_label: str
    ai_value: Optional[str] = None
    human_value: Optional[str] = None
    is_changed: bool = False
    change_type: str = "UNCHANGED"  # UNCHANGED, CORRECTED, ADDED, REMOVED
    officer_username: Optional[str] = None
    timestamp: Optional[str] = None
    reason: Optional[str] = None


class AIvsHumanComparison(BaseModel):
    """Comprehensive comparison between original automated AI result and final Human Verified result."""
    analysis_id: str
    review_id: str
    ai_score: float
    human_score: float
    score_delta: float
    ai_risk_level: str
    human_risk_level: str
    ai_status: str
    human_status: str
    total_fields_evaluated: int
    corrected_fields_count: int
    field_diffs: List[AIvsHumanDiffItem] = []
    summary: str = ""


class ReviewItem(BaseModel):
    """Summary item for the Officer Review Queue."""
    review_id: str
    analysis_id: str
    target_type: str = "ANALYSIS"  # ANALYSIS, ARTWORK
    product_name: str
    status: str
    assigned_officer: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[str] = None
    created_at: str
    updated_at: str
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    final_human_status: Optional[str] = None
    ai_score: float
    ai_risk_level: str
    ai_status: str
    critical_issues_count: int = 0
    review_reasons: List[str] = []
    age_hours: float = 0.0


class ReviewDetailResponse(BaseModel):
    """Full detail record of an officer review."""
    review_id: str
    analysis_id: str
    target_type: str = "ANALYSIS"
    product_name: str
    status: str
    assigned_officer: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[str] = None
    created_at: str
    updated_at: str
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    final_human_status: Optional[str] = None
    ai_score: float
    ai_risk_level: str
    ai_status: str
    human_score: Optional[float] = None
    human_risk_level: Optional[str] = None
    critical_issues_count: int = 0
    review_reasons: List[str] = []
    
    # Original AI Snapshot (immutable)
    ai_snapshot: Dict[str, Any] = {}
    
    # Human Verified Working Result (mutable until final verification)
    human_verified_result: Optional[Dict[str, Any]] = None
    
    # Audit lists
    field_corrections: List[FieldCorrectionItem] = []
    evidence_modifications: List[Dict[str, Any]] = []
    comments: List[OfficerCommentItem] = []
    history: List[ReviewHistoryEvent] = []


class OfficerWorkloadItem(BaseModel):
    """Workload breakdown for a single officer."""
    officer_username: str
    officer_name: str
    officer_role: str
    total_assigned: int = 0
    pending_count: int = 0
    in_review_count: int = 0
    completed_count: int = 0
    escalated_count: int = 0


class OfficerDashboardSummary(BaseModel):
    """Officer Dashboard summary metrics."""
    total_queue: int = 0
    pending_review: int = 0
    assigned: int = 0
    in_review: int = 0
    verified: int = 0
    rejected: int = 0
    escalated: int = 0
    reopened: int = 0
    workload: List[OfficerWorkloadItem] = []
