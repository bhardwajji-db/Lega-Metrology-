from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class OCRWord(BaseModel):
    text: str
    confidence: float
    bbox: List[int]

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
    match_method: str = "DIRECT_OCR"  # DIRECT_OCR, MULTI_TOKEN_OCR, CONTEXTUAL_OCR, SEMANTIC_PANEL, NONE

class ProductInfo(BaseModel):
    product_name: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    marketed_by: Optional[str] = None
    marketed_by_name: Optional[str] = None
    marketed_by_address: Optional[str] = None
    category: Optional[str] = None
    is_food: Optional[bool] = None
    net_quantity: Optional[str] = None
    mrp: Optional[str] = None
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
    extraction_mode: str = 'local'

class EvidenceItem(BaseModel):
    id: Optional[str] = None
    image_index: int = 0
    image_label: str = "Front"
    text: str = ""
    normalized_value: Optional[str] = None
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    geometry_type: str = "WORD_UNION"  # WORD_UNION, LINE, TOKEN, NONE
    match_method: str = "DIRECT_OCR"  # DIRECT_OCR, MULTI_TOKEN_OCR, CONTEXTUAL_OCR, SEMANTIC_PANEL, TOKEN_SEQUENCE, EXACT_TOKEN, NONE
    confidence: float = 0.0
    evidence_status: str = "VERIFIED"  # VERIFIED, CONTEXTUAL, NEEDS_REVIEW, NO_EVIDENCE, NOT_APPLICABLE, UNAVAILABLE
    evidence_type: str = "DIRECT_OCR"  # DIRECT_OCR, DERIVED_FIELD, PROVISO_DELEGATION, NONE
    explanation: Optional[str] = None
    source_token_ids: List[str] = []
    field_type: str = "FIELD"  # FIELD, PANEL, REGION
    quality_score: Optional[float] = None
    analysis_id: Optional[str] = None

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


class ProductImageEvidence(BaseModel):
    filename: str
    image_url: str
    label: str = 'Front'
    ocr_text: str = ''
    words: List[OCRWord] = []
    word_count: int = 0
    average_confidence: float = 0.0
    preprocessing_variant: str = 'Deep Learning Det + Rec + Angle Classifier'
    image_quality: Optional[Dict[str, Any]] = None
    quality_warning: Optional[str] = None

class CalibrationResult(BaseModel):
    status: str = "CALIBRATION_MISSING"  # PHYSICAL_MEASUREMENT_VERIFIED, PHYSICAL_MEASUREMENT_ESTIMATED, CALIBRATION_MISSING, CALIBRATION_INVALID, MEASUREMENT_UNRELIABLE
    target_type: Optional[str] = None  # ARUCO_DICT_4X4_50, ID1_REFERENCE_CARD, NONE
    pixels_per_mm: Optional[float] = None
    target_bbox: Optional[List[int]] = None
    confidence: Optional[float] = None
    message: str = "No physical calibration reference scale detected in image. Measurement values are estimated."

from integrations.fssai.schemas import FSSAIVerificationRecord as FSSAIVerificationResult
from integrations.gs1.schemas import GS1VerificationRecord as GS1VerificationResult

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

class HistoryItem(BaseModel):
    id: str
    product_name: str
    score: float
    status: str
    created_at: str
    image_url: str
    owner_user_id: Optional[str] = None

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
