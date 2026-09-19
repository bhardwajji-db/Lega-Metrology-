from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from models.schemas import ComplianceCheck, ComplianceIssue, RuleScore, CategoryScore, RiskAssessment, ConfidenceSummary, ProductInfo, ComplianceResult


class ArtworkLayoutRegion(BaseModel):
    """Semantic region identified on a digital artwork page / artboard."""
    region_id: str
    region_type: str  # BRAND_HEADER, MRP_STAMP, NET_QTY_AREA, MANUFACTURER_BLOCK, NUTRITION_PANEL, CONSUMER_CARE, OTHER
    page_number: int = 1
    bbox: List[float] = []
    bbox_normalized: List[float] = []
    normalized_bbox: List[float] = []
    bbox_pixels: List[float] = []
    confidence: float = 0.90
    linked_field: Optional[str] = None
    extracted_text: str = ""
    text_content: str = ""
    font_size_pt_estimated: Optional[float] = None
    detection_source: str = "LAYOUT_HEURISTIC"


class ArtworkPageInfo(BaseModel):
    """Metadata, text, and layout information for a single page or artboard of packaging artwork."""
    page_number: int = 1
    width: int = 800
    height: int = 1000
    width_pt: float = 0.0
    height_pt: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0
    rendered_width_px: int = 800
    rendered_height_px: int = 1000
    dpi: float = 150.0
    image_url: str = ""
    preview_image_path: Optional[str] = None
    extracted_text: str = ""
    text_source: str = "OCR"  # PDF_VECTOR, OCR, HYBRID
    word_count: int = 0
    average_confidence: float = 85.0
    layout_regions: List[ArtworkLayoutRegion] = []
    text_tokens: List[Dict[str, Any]] = []


class PlacementCheckResult(BaseModel):
    """Detailed placement assessment for key statutory declarations (MRP, Net Qty)."""
    check_name: str = "Placement Check"
    field_name: str = ""
    passed: bool = True
    status: str = "PASS"  # PASS, FAIL, REVIEW, NOT_APPLICABLE
    finding: str = ""
    recommended_zone: str = "Principal Display Panel"
    actual_zone: Optional[str] = None
    legal_citation: str = "Legal Metrology Rules 2011"
    bbox_normalized: Optional[List[float]] = None
    declaration_type: Optional[str] = None
    is_prominently_placed: bool = True
    context_notes: str = ""


class FontSizeEstimateResult(BaseModel):
    """Optical font height assistance for packaging artwork (strictly labeled as ESTIMATED)."""
    field_name: str = ""
    field: Optional[str] = None
    field_label: Optional[str] = None
    text_sample: str = ""
    estimated_height_mm: float = 0.0
    estimated_pt_size: float = 0.0
    mandated_minimum_mm: float = 2.0
    min_required_height_mm: Optional[float] = 2.0
    is_compliant: bool = True
    is_compliant_estimated: Optional[bool] = True
    confidence: float = 85.0
    estimation_method: str = "OPTICAL_DPI_BOUNDING_BOX"
    disclaimer: str = "ESTIMATED optical font size. Physical proof verification recommended before cylinder engraving or mass plate production."
    bbox_normalized: Optional[List[float]] = None


class DesignerCorrectionItem(BaseModel):
    """Grounded, actionable correction item for packaging designers."""
    item_id: str = ""
    issue_id: Optional[str] = None
    rule_id: Optional[str] = None
    field_name: str = ""
    field: Optional[str] = None
    field_label: Optional[str] = None
    severity: str = "MEDIUM"  # CRITICAL, MAJOR, MINOR, INFO
    issue: str = ""
    title: Optional[str] = None
    suggested_action: str = ""
    recommended_action: Optional[str] = None
    affected_area: Optional[str] = None
    legal_reference: str = "Legal Metrology (Packaged Commodities) Rules, 2011"
    is_blocking_for_print: bool = False
    page_number: int = 1
    bbox: Optional[List[float]] = None
    status: str = "OPEN"


class PreprintApprovalRecord(BaseModel):
    """Immutable audit record of a human reviewer sign-off decision."""
    approval_id: str
    artwork_id: str
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewer_username: Optional[str] = None
    reviewer_role: str = "MERCHANT_PUBLIC"
    decision: str = "APPROVED"  # APPROVED, REJECTED, REQUEST_CHANGES
    comments: str = ""
    timestamp: str
    conditions: Optional[List[str]] = None
    legal_disclaimer_acknowledged: bool = True


class PreprintApprovalRequest(BaseModel):
    """Request payload to submit an artwork approval decision."""
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = "Reviewer"
    reviewer_role: Optional[str] = "MERCHANT_PUBLIC"
    decision: str = "APPROVED"  # APPROVED, REJECTED, REQUEST_CHANGES
    comments: Optional[str] = ""
    conditions: Optional[List[str]] = None
    legal_disclaimer_acknowledged: bool = False


class ArtworkDocument(BaseModel):
    """Full structured document model for pre-print packaging artwork."""
    id: str
    parent_artwork_id: Optional[str] = None
    iteration_number: int = 1
    filename: str
    file_path: str = ""
    file_type: str = "PDF"
    file_size: int = 0
    page_count: int = 1
    dimensions: Dict[str, Any] = {}
    dpi: float = 150.0
    source_identity: str = "PRE-PRINT ARTWORK"
    compliance_ruleset: str = "Legal Metrology (Packaged Commodities) Rules, 2011"
    workflow_status: str = "DRAFT"
    approval_status: str = "PENDING"
    approval_record: Optional[PreprintApprovalRecord] = None
    analysis_result: Optional[Dict[str, Any]] = None
    pages_data: List[ArtworkPageInfo] = []
    owner_user_id: str = ""
    created_at: str
    updated_at: Optional[str] = None


class PreprintUploadResponse(BaseModel):
    """Response returned upon successful artwork upload and page extraction."""
    success: bool = True
    artwork_id: str
    filename: str
    file_type: str
    file_size: int = 0
    page_count: int = 1
    dimensions: Dict[str, Any] = {}
    dpi: float = 150.0
    pages: List[ArtworkPageInfo] = []
    message: str = "Artwork uploaded successfully."


class PreprintAnalysisResponse(BaseModel):
    """Complete pre-print artwork compliance verification response."""
    artwork_id: str
    filename: str
    file_type: str
    page_count: int = 1
    source_identity: str = "PRE-PRINT ARTWORK"
    compliance_ruleset: str = "Legal Metrology (Packaged Commodities) Rules, 2011"
    iteration_number: int = 1
    parent_artwork_id: Optional[str] = None
    overall_status: str = "COMPLIANT"  # COMPLIANT, NEEDS_REVIEW, NON_COMPLIANT
    overall_score: float = 100.0
    workflow_status: str = "DRAFT"  # DRAFT, ACTION_REQUIRED, CHANGES_REQUESTED, READY_FOR_PRINT, REJECTED
    missing_declarations: List[str] = []
    mandatory_checklist: Dict[str, bool] = {}
    placement_checks: List[PlacementCheckResult] = []
    font_size_estimates: List[FontSizeEstimateResult] = []
    designer_corrections: List[DesignerCorrectionItem] = []
    pages: List[ArtworkPageInfo] = []
    product_info: Optional[ProductInfo] = None
    compliance_result: Optional[ComplianceResult] = None
    scoring_breakdown: Optional[Dict[str, Any]] = None
    ready_for_print_eligible: bool = True
    print_blocking_issues_count: int = 0
    summary_notes: List[str] = []
