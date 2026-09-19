from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class MultilingualLanguageInfo(BaseModel):
    code: str
    name: str
    script: str
    confidence: float = 0.0
    token_count: int = 0

class MultilingualMetadata(BaseModel):
    primary_language: str = "en"
    primary_script: str = "Latin"
    detected_languages: List[MultilingualLanguageInfo] = []
    detected_scripts: List[str] = []
    mixed_language: bool = False
    language_confidence: float = 0.0

class OCRWord(BaseModel):
    text: str
    confidence: float
    bbox: List[int]
    language: Optional[str] = None
    script: Optional[str] = None

class OCRResult(BaseModel):
    full_text: str
    words: List[OCRWord]
    language: str
    processing_time: float
    average_confidence: float = 0.0
    word_count: int = 0
    engine: str = "PaddleOCR (PP-OCRv4)"
    preprocessing_variant: str = "Deep Learning Det + Rec + Angle Classifier"
    regions_processed: int = 1
    ocr_passes: int = 2
    multilingual: Optional[MultilingualMetadata] = None

class ExtractionCandidate(BaseModel):
    field: str
    raw_value: str
    normalized_value: Optional[str] = None
    confidence: float = 0.0
    source_tokens: List[str] = []
    source_bbox: Optional[List[int]] = None
    image_index: int = 0
    image_label: str = "Front"
    extraction_method: str = "DIRECT_OCR"  # DIRECT_OCR, SPATIAL_BINDING, REGEX_ANCHOR, FALLBACK, MULTILINGUAL
    validation_status: str = "FOUND"  # FOUND, NOT_FOUND, UNCERTAIN, CONFLICT, NOT_APPLICABLE
    details: Optional[str] = None
    role: Optional[str] = None  # MANUFACTURER, PACKER, MARKETER, IMPORTER

class FieldProvenance(BaseModel):
    field_name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    image_index: int = 0
    image_label: str = "Front"
    source_text: str = ""
    source_token_ids: List[str] = []
    source_bbox: Optional[List[int]] = None
    confidence: float = 0.0
    match_method: str = "DIRECT_OCR"  # DIRECT_OCR, MULTI_TOKEN_OCR, CONTEXTUAL_OCR, SEMANTIC_PANEL, MULTILINGUAL_DICTIONARY, NONE
    language: Optional[str] = None
    script: Optional[str] = None
    language_confidence: Optional[float] = None

class ProductInfo(BaseModel):
    product_name: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    packer: Optional[str] = None
    packer_name: Optional[str] = None
    packer_address: Optional[str] = None
    marketed_by: Optional[str] = None
    marketed_by_name: Optional[str] = None
    marketed_by_address: Optional[str] = None
    importer: Optional[str] = None
    importer_name: Optional[str] = None
    importer_address: Optional[str] = None
    importer_country: Optional[str] = None
    category: Optional[str] = None
    is_food: Optional[bool] = None
    net_quantity: Optional[str] = None
    mrp: Optional[str] = None
    unit_sale_price: Optional[str] = None
    manufacturing_date: Optional[str] = None
    manufacture_date: Optional[str] = None
    packaging_date: Optional[str] = None
    expiry_date: Optional[str] = None
    use_by_date: Optional[str] = None
    best_before: Optional[str] = None
    relative_shelf_life: Optional[str] = None
    batch_number: Optional[str] = None
    fssai_license: Optional[str] = None
    consumer_care: Optional[str] = None
    consumer_care_phone: Optional[str] = None
    consumer_care_email: Optional[str] = None
    country_of_origin: Optional[str] = None
    ingredients: Optional[str] = None
    nutritional_info: Optional[str] = None
    nutrition_panel_detected: Optional[bool] = None
    nutrition_facts: Optional[Dict[str, str]] = None
    allergen_info: Optional[str] = None
    veg_nonveg_status: Optional[str] = None
    barcode_detected: Optional[str] = None
    fssai_decoded_state: Optional[str] = None
    fssai_license_type: Optional[str] = None
    other_declarations: Dict[str, str] = {}
    declaration_confidences: Dict[str, float] = {}
    field_provenance: Dict[str, FieldProvenance] = {}
    candidates: Dict[str, List[ExtractionCandidate]] = {}
    field_status: Dict[str, str] = {}
    extraction_mode: str = 'local'
    multilingual: Optional[MultilingualMetadata] = None

class EvidenceItem(BaseModel):
    id: Optional[str] = None
    image_index: int = 0
    image_label: str = "Front"
    text: str = ""
    normalized_value: Optional[str] = None
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    geometry_type: str = "WORD_UNION"  # WORD_UNION, LINE, TOKEN, NONE
    match_method: str = "DIRECT_OCR"  # DIRECT_OCR, MULTI_TOKEN_OCR, CONTEXTUAL_OCR, SEMANTIC_PANEL, TOKEN_SEQUENCE, EXACT_TOKEN, MULTILINGUAL_DICTIONARY, NONE
    confidence: float = 0.0
    evidence_status: str = "VERIFIED"  # VERIFIED, CONTEXTUAL, NEEDS_REVIEW, NO_EVIDENCE, NOT_APPLICABLE, UNAVAILABLE
    evidence_type: str = "DIRECT_OCR"  # DIRECT_OCR, DERIVED_FIELD, PROVISO_DELEGATION, NONE
    explanation: Optional[str] = None
    source_token_ids: List[str] = []
    field_type: str = "FIELD"  # FIELD, PANEL, REGION
    quality_score: Optional[float] = None
    analysis_id: Optional[str] = None
    language: Optional[str] = None
    script: Optional[str] = None
    language_confidence: Optional[float] = None
    # Section 5 Enhanced Traceability & Audit Metadata
    linked_rule_id: Optional[str] = None
    linked_field: Optional[str] = None
    regulation_reference: Optional[str] = None
    source_region: Optional[str] = "Mandatory Declaration Panel"
    reliability_score: Optional[float] = None
    reliability_tier: str = "HIGH"  # HIGH, MEDIUM, LOW, NEEDS_VERIFICATION
    approval_status: str = "PENDING"  # PENDING, APPROVED, REJECTED, CORRECTED
    reviewer: Optional[str] = None
    officer_comments: Optional[str] = None
    correction_history: List[Dict[str, Any]] = []

class ComplianceCheck(BaseModel):
    rule_id: str
    field: str
    field_label: str
    required: bool = True
    detected: bool = False
    detected_value: Optional[str] = None
    severity: str = "medium"
    status: str = "PASS"  # PASS, FAIL, WARNING, NOT_APPLICABLE, NEEDS_REVIEW
    description: str = ""
    source: str = ""
    explanation: Optional[str] = None
    recommendation: Optional[str] = None
    # Phase 4 Regulatory Grounding & Evidence Links:
    domain: str = "LEGAL_METROLOGY"  # LEGAL_METROLOGY or FSSAI
    source_name: Optional[str] = None
    source_reference: Optional[str] = None
    source_url: Optional[str] = None
    confidence: Optional[float] = None
    evidence_image_label: Optional[str] = None
    evidence_region: Optional[str] = None
    reason: Optional[str] = None
    # Phase 5B Optional Evidence Localization Coordinates (Default None)
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_width: Optional[int] = None
    bbox_height: Optional[int] = None
    # Phase 3 Visual Proof & Explainability
    evidence: List[EvidenceItem] = []
    # Section 5 Structured Grounded Explanations & Multi-Candidate Tracking
    pass_reason: Optional[str] = None
    fail_reason: Optional[str] = None
    review_reason: Optional[str] = None
    linked_rule_id: Optional[str] = None
    linked_field: Optional[str] = None
    regulation_reference: Optional[str] = None
    reliability_score: Optional[float] = None
    reliability_tier: Optional[str] = "HIGH"
    field_status: Optional[str] = None  # FOUND, NOT_FOUND, UNCERTAIN, CONFLICT, NOT_APPLICABLE
    candidates: List[Dict[str, Any]] = []
    # Section 6 Compliance Intelligence & Execution Trace
    execution_trace: Optional[Dict[str, Any]] = None
    rule_version: Optional[str] = None

class Recommendation(BaseModel):
    rule_id: str
    domain: str = "LEGAL_METROLOGY"
    status: str
    priority: str = "MEDIUM"  # HIGH, MEDIUM, LOW, INFO
    action_category: str = "VERIFY_MANUALLY"  # VERIFY_MANUALLY, RECAPTURE_IMAGE, CORRECT_LABEL, VERIFY_APPLICABILITY, VERIFY_OFFICIAL_RECORD, NO_ACTION
    title: str
    issue: str
    recommended_action: str
    corrective_action: Optional[str] = None
    verification_step: Optional[str] = None
    evidence_image_label: Optional[str] = None
    evidence_region: Optional[str] = None
    confidence: Optional[float] = None
    source_name: Optional[str] = None
    source_reference: Optional[str] = None
    source_url: Optional[str] = None
    requires_human_review: bool = False
    # Phase 5B Optional Evidence Localization Coordinates (Default None)
    bbox: Optional[List[int]] = None
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_width: Optional[int] = None
    bbox_height: Optional[int] = None
    # Phase 3 Visual Proof & Explainability
    evidence: List[EvidenceItem] = []

class ComplianceIssue(BaseModel):
    what: str
    expected: str
    why: str
    action: str
    severity: str = 'medium'
    field: str = ''
    domain: str = 'LEGAL_METROLOGY'

class RuleScore(BaseModel):
    rule_id: str
    field: str
    rule_category: str = "ALL"
    domain: str = "LEGAL_METROLOGY"
    status: str
    earned_points: float
    max_points: float = 1.0
    weight: float = 1.0
    severity: str = "medium"
    evidence_reliability_score: Optional[float] = None
    extraction_confidence: Optional[float] = None
    risk_contribution: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW, NONE
    is_applicable: bool = True

class CategoryScore(BaseModel):
    category_id: str
    category_name: str
    score: float
    total_rules: int
    applicable_rules: int
    passed_rules: int
    failed_rules: int
    review_rules: int
    not_applicable_rules: int
    status: str = "COMPLIANT"  # COMPLIANT, NON_COMPLIANT, REVIEW_REQUIRED, NOT_APPLICABLE

class ConfidenceSummary(BaseModel):
    overall_confidence: float = 0.0
    extraction_confidence_avg: float = 0.0
    evidence_reliability_avg: float = 0.0
    high_confidence_declarations_count: int = 0
    low_confidence_declarations_count: int = 0
    uncertain_declarations_count: int = 0
    candidate_conflict_count: int = 0
    confidence_tier: str = "HIGH"  # HIGH, MEDIUM, LOW

class RiskFactor(BaseModel):
    factor_id: str
    factor_type: str  # MISSING_MANDATORY_DECLARATION, CRITICAL_STATUTORY_FAILURE, DATA_AMBIGUITY, EVIDENCE_UNRELIABILITY, RULE_CONFLICT, REGISTRATION_UNVERIFIED
    source_rule_id: Optional[str] = None
    source_field: Optional[str] = None
    severity: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    description: str
    evidence_ref: Optional[str] = None
    confidence: Optional[float] = None
    resolution_action: str

class RiskAssessment(BaseModel):
    risk_level: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    risk_score: float = 0.0  # 0.0 - 100.0 (Product risk index)
    missing_declaration_count: int = 0
    critical_violation_count: int = 0
    review_required_count: int = 0
    insufficient_evidence_count: int = 0
    risk_explanation: str = "All mandatory declarations verified with acceptable confidence."
    risk_factors: List[RiskFactor] = []
    critical_factors: List[RiskFactor] = []
    review_factors: List[RiskFactor] = []
    confidence_summary: Optional[ConfidenceSummary] = None
    scoring_version: str = "2026.1"

class ScoringConfiguration(BaseModel):
    scoring_version: str = "2026.1"
    weight_pass: float = 1.0
    weight_warning: float = 0.5
    weight_needs_review: float = 0.85
    weight_fail: float = 0.0
    critical_risk_threshold: int = 1
    high_risk_failures_threshold: int = 2
    medium_risk_review_threshold: int = 2
    enabled_factors: List[str] = ["MANDATORY_PRESENCE", "CONFIDENCE_ADJUSTMENT", "CONFLICT_DETECTION", "SEVERITY_WEIGHTING"]

class ScoreHistoryEntry(BaseModel):
    analysis_id: str
    product_name: str
    timestamp: str
    score: float
    risk_level: str
    scoring_version: str
    applicable_rules_count: int
    passed_rules: int
    failed_rules: int
    review_rules: int
    category_scores: List[CategoryScore] = []

class ProductRiskHistory(BaseModel):
    product_name: str
    total_analyses: int
    current_risk_level: str
    current_score: float
    risk_trend: str = "STABLE"  # IMPROVING, DEGRADING, STABLE
    history_entries: List[ScoreHistoryEntry] = []

class BatchRiskDistribution(BaseModel):
    total_analyzed: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    failure_count: int
    review_required_count: int
    compliant_count: int
    average_score: float
    average_risk_score: float
    distribution_percentages: Dict[str, float] = {}

class ComplianceResult(BaseModel):
    checks: List[ComplianceCheck]
    score: float
    status: str
    total_rules: int
    passed_rules: int
    failed_rules: int
    warning_rules: int = 0
    needs_review_rules: int = 0
    not_applicable_rules: int = 0
    issues: List[ComplianceIssue] = []
    recommendations: List[Recommendation] = []
    conflicts: List[Dict[str, Any]] = []
    # Section 7 Compliance Scoring & Risk Models
    rule_scores: List[RuleScore] = []
    category_scores: List[CategoryScore] = []
    risk_assessment: Optional[RiskAssessment] = None
    confidence_summary: Optional[ConfidenceSummary] = None
    scoring_version: str = "2026.1"

class RuleTestRequest(BaseModel):
    rule_id: str
    product_info: ProductInfo
    ocr_text: Optional[str] = ""
    context_override: Optional[Dict[str, Any]] = None

class RuleTestResponse(BaseModel):
    rule_id: str
    rule_name: str
    domain: str
    status: str
    reason: str
    detected_value: Optional[str] = None
    pass_reason: Optional[str] = None
    fail_reason: Optional[str] = None
    review_reason: Optional[str] = None
    execution_trace: Dict[str, Any]
    is_simulation: bool = True


from vision.schemas import VisionAnalysisResult

class ProductImageEvidence(BaseModel):
    filename: str = ""
    image_url: str = ""
    label: str = 'Front'
    ocr_text: str = ''
    words: List[OCRWord] = []
    word_count: int = 0
    average_confidence: float = 0.0
    preprocessing_variant: str = 'Deep Learning Det + Rec + Angle Classifier'
    image_quality: Optional[Dict[str, Any]] = None
    quality_warning: Optional[str] = None
    vision_analysis: Optional[VisionAnalysisResult] = None

class CalibrationResult(BaseModel):
    status: str = "CALIBRATION_MISSING"  # PHYSICAL_MEASUREMENT_VERIFIED, PHYSICAL_MEASUREMENT_ESTIMATED, CALIBRATION_MISSING, CALIBRATION_INVALID, MEASUREMENT_UNRELIABLE
    target_type: Optional[str] = None  # ARUCO_DICT_4X4_50, ID1_REFERENCE_CARD, NONE
    pixels_per_mm: Optional[float] = None
    target_bbox: Optional[List[int]] = None
    confidence: Optional[float] = None
    message: str = "No physical calibration reference scale detected in image. Measurement values are estimated."

from integrations.fssai.schemas import FSSAIVerificationRecord as FSSAIVerificationResult
from integrations.gs1.schemas import GS1VerificationRecord as GS1VerificationResult
from models.verification_schemas import ExternalVerificationSummary
from claims.models import ClaimAnalysisResult

class FontSizeAnalysis(BaseModel):
    net_quantity_font_height_mm: Optional[float] = None
    mrp_font_height_mm: Optional[float] = None
    min_required_font_height_mm: float = 2.0
    is_font_compliant: bool = True
    readability_score: float = 85.0
    readability_tier: str = "GOOD"  # EXCELLENT, GOOD, MODERATE, POOR
    rule_12_verdict: str = "Compliant with Legal Metrology Rule 12 Table font height minimums"
    details: str = "Font height meets or exceeds statutory requirements."
    calibration_status: str = "PHYSICAL_MEASUREMENT_ESTIMATED"  # PHYSICAL_MEASUREMENT_VERIFIED, PHYSICAL_MEASUREMENT_ESTIMATED, CALIBRATION_MISSING, CALIBRATION_INVALID, MEASUREMENT_UNRELIABLE
    pixels_per_mm: Optional[float] = None
    calibration_target: Optional[str] = None
    measurement_method: str = "ESTIMATED_DPI"  # ARUCO_OPTICAL_SCALE, ESTIMATED_DPI

class AnalysisResponse(BaseModel):
    id: str
    product_name: str
    image_url: str
    images: List[ProductImageEvidence] = []
    ocr_result: OCRResult
    product_info: ProductInfo
    compliance_result: ComplianceResult
    recommendations: List[Recommendation] = []
    created_at: str
    image_quality_warning: Optional[str] = None
    font_size_analysis: Optional[FontSizeAnalysis] = None
    fssai_verification: Optional[FSSAIVerificationResult] = None
    gs1_verification: Optional[GS1VerificationResult] = None
    calibration_result: Optional[CalibrationResult] = None
    owner_user_id: Optional[str] = None
    organization_id: Optional[str] = None
    multilingual: Optional[MultilingualMetadata] = None
    vision_analysis: Optional[VisionAnalysisResult] = None
    external_verification: Optional[ExternalVerificationSummary] = None
    officer_review: Optional[Dict[str, Any]] = None
    product_identity: Optional[Any] = None
    cross_validation: Optional[Any] = None
    external_product_verification: Optional[Any] = None
    # Section 15 Security, Integrity & Auditability
    integrity_hash: Optional[str] = None
    system_version: Optional[str] = None
    ocr_engine_version: Optional[str] = None
    ruleset_version: Optional[str] = None
    claims_analysis: Optional[ClaimAnalysisResult] = None

class HistoryItem(BaseModel):
    id: str
    product_name: str
    score: float
    status: str
    created_at: str
    image_url: str
    owner_user_id: Optional[str] = None
    organization_id: Optional[str] = None
    integrity_hash: Optional[str] = None

class DashboardStats(BaseModel):
    total_analyzed: int
    compliant: int
    needs_review: int = 0
    failures: int = 0
    violations: int = 0
    average_score: float
    recent: List[HistoryItem]
    packages_screened: Optional[int] = None
    compliant_packages: Optional[int] = None
    review_findings: Optional[int] = None
    failed_findings: Optional[int] = None

# ── Section 5 Evidence API Request / Response Schemas ──

class EvidenceCorrectionRequest(BaseModel):
    evidence_id: Optional[str] = ""
    rule_id: str
    corrected_value: str
    comments: Optional[str] = None
    corrected_bbox: Optional[List[int]] = None

class EvidenceReviewActionRequest(BaseModel):
    evidence_id: Optional[str] = ""
    rule_id: str
    action: str  # APPROVE, REJECT, REQUEST_RESCAN
    comments: Optional[str] = None

class EvidenceAuditLogItem(BaseModel):
    id: int
    analysis_id: str
    evidence_id: str
    rule_id: str
    actor_username: str
    action_type: str  # CORRECTION, APPROVAL, REJECTION, CREATION
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    comments: Optional[str] = None
    created_at: str

class EvidenceHistoryResponse(BaseModel):
    analysis_id: str
    logs: List[EvidenceAuditLogItem] = []
    total_records: int = 0

class HeatmapPoint(BaseModel):
    x: int
    y: int
    weight: float
    field: Optional[str] = None
    rule_id: Optional[str] = None

class EvidenceHeatmapResponse(BaseModel):
    analysis_id: str
    image_index: int
    image_label: str
    width: int = 1000
    height: int = 1000
    points: List[HeatmapPoint] = []
    total_tokens: int = 0
    density_tier: str = "MODERATE"  # HIGH, MODERATE, LOW

class PanelZoneSummary(BaseModel):
    zone_name: str  # PDP, INFORMATION_PANEL, STAMP_AREA, NUTRITION_ZONE
    panel_label: str  # Front, Back
    status: str  # PASS, FAIL, NEEDS_REVIEW, NOT_APPLICABLE
    rules_total: int
    rules_passed: int
    rules_failed: int
    rules_under_review: int
    checked_fields: List[str] = []

class PanelComplianceHeatmapResponse(BaseModel):
    analysis_id: str
    panels: List[PanelZoneSummary] = []
    overall_status: str


# ── Section 8 Pre-Print Compliance Schemas ──
from models.preprint_schemas import (
    ArtworkLayoutRegion,
    ArtworkPageInfo,
    DesignerCorrectionItem,
    PlacementCheckResult,
    FontSizeEstimateResult,
    PreprintApprovalRecord,
    PreprintApprovalRequest,
    ArtworkDocument,
    PreprintUploadResponse,
    PreprintAnalysisResponse,
)

# ── Section 9 Version Comparison Schemas ──
from models.version_schemas import (
    FieldDiffItem,
    IngredientItemDiff,
    IngredientsDiff,
    NutrientDiffItem,
    NutritionDiff,
    RuleStateDiff,
    IssueResolutionItem,
    VersionSnapshot,
    VersionTimelineEvent,
    VersionComparisonRequest,
    VersionComparisonResult,
)

# ── Section 10 Human Verification / Officer Workflow Schemas ──
from models.review_schemas import (
    ReviewStatus,
    HumanVerifiedStatus,
    FieldCorrectionItem,
    OfficerCommentItem,
    ReviewHistoryEvent,
    AssignReviewRequest,
    AcceptReviewRequest,
    RejectReviewRequest,
    CorrectFieldRequest,
    AddEvidenceRequest,
    RemoveEvidenceRequest,
    AddCommentRequest,
    EscalateReviewRequest,
    ReopenReviewRequest,
    AIvsHumanDiffItem,
    AIvsHumanComparison,
    ReviewItem,
    ReviewDetailResponse,
    OfficerWorkloadItem,
    OfficerDashboardSummary,
)



