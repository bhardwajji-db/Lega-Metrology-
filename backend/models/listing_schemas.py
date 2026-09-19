from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from models.schemas import ProductInfo, ComplianceResult


class ListingFieldComparisonItem(BaseModel):
    """Result of cross-comparing a statutory field between physical package and e-commerce listing."""
    field: str
    field_label: str
    status: str  # "MATCH", "MISMATCH", "INSUFFICIENT_DATA"
    package_value: Optional[str] = None
    listing_value: Optional[str] = None
    explanation: str = ""
    severity: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"


class ListingCheckRequest(BaseModel):
    """Request payload for checking an e-commerce product listing."""
    mode: str = "RAW_TEXT"  # "URL", "RAW_TEXT", "STRUCTURED"
    url: Optional[str] = None
    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    package_analysis_id: Optional[str] = None
    package_data: Optional[Dict[str, Any]] = None


class ListingCheckResponse(BaseModel):
    """Complete response for an e-commerce product listing compliance check."""
    id: str
    source_mode: str
    source_url: Optional[str] = None
    listing_text: str
    extracted_info: ProductInfo
    compliance_result: ComplianceResult
    score: float
    status: str
    comparison_performed: bool = False
    package_analysis_id: Optional[str] = None
    package_product_name: Optional[str] = None
    field_comparisons: List[ListingFieldComparisonItem] = []
    match_count: int = 0
    mismatch_count: int = 0
    insufficient_data_count: int = 0
    cross_verdict: Optional[str] = None  # COMPLIANT_MATCH, MISMATCH_DETECTED, INSUFFICIENT_ONLINE_DATA, NO_PACKAGE_LINKED
    created_at: str
