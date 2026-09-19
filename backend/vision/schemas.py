from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

class NormalizedBBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class Point2D(BaseModel):
    x: float
    y: float

class ImageQualityMetrics(BaseModel):
    blur_score: float = 0.0
    sharpness_score: float = 0.0
    motion_blur_detected: bool = False
    motion_blur_ratio: float = 1.0
    brightness: float = 0.0
    contrast: float = 0.0
    dark_pixel_ratio: float = 0.0
    bright_pixel_ratio: float = 0.0
    clipping_ratio: float = 0.0
    glare_detected: bool = False
    glare_severity: float = 0.0
    glare_regions: List[List[int]] = []
    skew_angle_deg: float = 0.0
    recommended_rotation: int = 0
    small_text_detected: bool = False
    small_text_ratio: float = 0.0
    resolution: str = "0x0"
    width: int = 0
    height: int = 0

class ImageQualityIssue(BaseModel):
    category: str
    severity: str  # INFO, WARNING, SEVERE
    message: str
    metric_value: Optional[float] = None
    bbox: Optional[List[int]] = None

class ImageQualityResult(BaseModel):
    overall_score: float = 100.0  # 0.0 to 100.0
    decision: str = "PASS"  # PASS, WARN, REJECT
    is_acceptable: bool = True
    metrics: ImageQualityMetrics = Field(default_factory=ImageQualityMetrics)
    issues: List[ImageQualityIssue] = []
    summary: str = "Image quality is suitable for statutory analysis."

class PerspectiveCorrectionResult(BaseModel):
    detected: bool = False
    is_perspective_skewed: bool = False
    skew_severity: float = 0.0
    quadrilateral: Optional[List[List[float]]] = None
    transform_matrix: Optional[List[List[float]]] = None
    corrected_dimensions: Optional[List[int]] = None
    confidence: float = 0.0
    method: str = "CONTOUR_APPROX_DP"

class PackageBoundaryResult(BaseModel):
    detected: bool = False
    bbox: Optional[List[int]] = None
    normalized_bbox: Optional[List[float]] = None
    polygon: Optional[List[List[int]]] = None
    area_ratio: float = 0.0
    aspect_ratio: float = 1.0
    confidence: float = 0.0
    method: str = "CANNY_OTSU_CONTOUR"

class PanelCandidate(BaseModel):
    id: str
    panel_type: str = "unknown"  # front_candidate, back_candidate, side_candidate, top_candidate, bottom_candidate, unknown
    confidence: float = 0.0
    confidence_tier: str = "MEDIUM"  # HIGH, MEDIUM, LOW, VERY_LOW
    bbox: List[int]
    normalized_bbox: List[float]
    polygon: Optional[List[List[int]]] = None
    supporting_signals: List[str] = []
    estimated_aspect_ratio: float = 1.0

class PanelClassificationResult(BaseModel):
    primary_panel: str = "front_candidate"
    confidence: float = 0.0
    confidence_tier: str = "MEDIUM"
    panels: List[PanelCandidate] = []
    classification_signals: List[str] = []

class TextRegionInfo(BaseModel):
    id: str
    bbox: List[int]
    normalized_bbox: List[float]
    text: str
    confidence: float
    estimated_font_height_px: float = 0.0
    is_small_text: bool = False
    orientation: float = 0.0
    script: Optional[str] = None
    language: Optional[str] = None

class SemanticRegionResult(BaseModel):
    region_type: str  # mrp, net_quantity, date_stamp, manufacturer, consumer_care, nutrition_table, ingredients, allergen, barcode, qr
    detected: bool = False
    confidence: float = 0.0
    confidence_tier: str = "MEDIUM"
    bbox: Optional[List[int]] = None
    normalized_bbox: Optional[List[float]] = None
    polygon: Optional[List[List[int]]] = None
    detection_method: str = "LAYOUT_KEYWORD_HEURISTIC"
    matched_keywords: List[str] = []
    associated_text: str = ""
    is_table_structure: bool = False
    evidence_id: Optional[str] = None

class SymbolDetectionResult(BaseModel):
    symbol_type: str  # VEG, NON_VEG, FSSAI_LOGO, ISI_MARK, GREEN_DOT, RECYCLE_SYMBOL, UNKNOWN
    detected: bool = False
    confidence: float = 0.0
    confidence_tier: str = "MEDIUM"
    bbox: Optional[List[int]] = None
    normalized_bbox: Optional[List[float]] = None
    color_scheme: Optional[str] = None  # GREEN, BROWN, BLACK, OTHER
    detection_method: str = "GEOMETRIC_COLOR_TEMPLATE"
    notes: Optional[str] = None
    evidence_id: Optional[str] = None

class LogoDetectionResult(BaseModel):
    logo_name: str
    detected: bool = False
    confidence: float = 0.0
    bbox: Optional[List[int]] = None
    normalized_bbox: Optional[List[float]] = None
    detection_method: str = "TEMPLATE_OCR_PROXIMITY"
    evidence_id: Optional[str] = None

class BarcodeDetectionResult(BaseModel):
    detected: bool = False
    barcode_type: str = "1D_BARCODE"  # EAN_13, UPC_A, CODE_128, 1D_BARCODE
    bbox: Optional[List[int]] = None
    normalized_bbox: Optional[List[float]] = None
    orientation: str = "HORIZONTAL"  # HORIZONTAL, VERTICAL
    decoded_value: Optional[str] = None
    confidence: float = 0.0
    confidence_tier: str = "MEDIUM"
    detection_method: str = "MORPHOLOGICAL_GRADIENT"

class QRDetectionResult(BaseModel):
    detected: bool = False
    bbox: Optional[List[int]] = None
    normalized_bbox: Optional[List[float]] = None
    decoded_payload: Optional[str] = None
    is_safe_payload: bool = True
    confidence: float = 0.0
    confidence_tier: str = "MEDIUM"
    detection_method: str = "OPENCV_QR_DETECTOR"
    warning: Optional[str] = None

class VisionTimingMetrics(BaseModel):
    quality_gate_ms: float = 0.0
    geometry_ms: float = 0.0
    package_boundary_ms: float = 0.0
    panel_classification_ms: float = 0.0
    text_regions_ms: float = 0.0
    semantic_regions_ms: float = 0.0
    symbols_ms: float = 0.0
    barcodes_ms: float = 0.0
    total_vision_ms: float = 0.0

class VisionAnalysisResult(BaseModel):
    image_index: int = 0
    image_label: str = "Front"
    source_filename: str = ""
    quality: ImageQualityResult = Field(default_factory=ImageQualityResult)
    geometry: PerspectiveCorrectionResult = Field(default_factory=PerspectiveCorrectionResult)
    package_boundary: PackageBoundaryResult = Field(default_factory=PackageBoundaryResult)
    panel_classification: PanelClassificationResult = Field(default_factory=PanelClassificationResult)
    semantic_regions: List[SemanticRegionResult] = []
    symbols: List[SymbolDetectionResult] = []
    logos: List[LogoDetectionResult] = []
    barcode: BarcodeDetectionResult = Field(default_factory=BarcodeDetectionResult)
    qr_code: QRDetectionResult = Field(default_factory=QRDetectionResult)
    text_regions: List[TextRegionInfo] = []
    timing: VisionTimingMetrics = Field(default_factory=VisionTimingMetrics)
    evidence_items: List[Any] = []
    overall_confidence: float = 0.0
    overall_confidence_tier: str = "MEDIUM"
    status: str = "SUCCESS"  # SUCCESS, DEGRADED, FAILED
    error_message: Optional[str] = None
