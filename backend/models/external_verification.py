"""
MetrCheck AI — External Product & Licence Verification Data Models
Defines the three-layer data architecture:
Layer 1: PACKAGE_OCR_DATA
Layer 2: EXTERNAL_VERIFICATION_DATA
Layer 3: CROSS_SOURCE_COMPARISON
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ExternalVerificationStatus(str, Enum):
    OCR_DETECTED = "OCR_DETECTED"
    FORMAT_VALID = "FORMAT_VALID"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"           # Data came from a live official external API (FoSCoS / GS1 DataKart)
    LOCAL_REFERENCE_MATCH = "LOCAL_REFERENCE_MATCH"       # Data matched in local/offline verified reference registry (NOT official external)
    EXTERNAL_LOOKUP_FAILED = "EXTERNAL_LOOKUP_FAILED"
    EXTERNAL_DATA_NOT_FOUND = "EXTERNAL_DATA_NOT_FOUND"
    EXTERNAL_VERIFICATION_UNAVAILABLE = "EXTERNAL_VERIFICATION_UNAVAILABLE"
    INVALID_FORMAT = "INVALID_FORMAT"
    NOT_DETECTED = "NOT_DETECTED"


class ComparisonResult(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    NOT_FOUND = "NOT_FOUND"
    NOT_VERIFIED = "NOT_VERIFIED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class FSSAIExtractionData(BaseModel):
    detected: bool = False
    number: Optional[str] = None
    original_ocr_text: Optional[str] = None
    source: str = "ocr"
    confidence: float = 0.0
    evidence_image: Optional[str] = None
    evidence_bbox: Optional[List[int]] = None
    format_valid: bool = False
    number_type: str = "NOT_DETECTED"  # LICENCE, REGISTRATION, INVALID_FORMAT, NOT_DETECTED
    state_code: Optional[str] = None
    state_name: Optional[str] = None


class BarcodeExtractionData(BaseModel):
    detected: bool = False
    type: str = "EAN-13"  # EAN-13, EAN-8, UPC-A, Code 128, QR, etc.
    value: Optional[str] = None
    source: str = "barcode_decoder"
    confidence: float = 0.0
    evidence_image: Optional[str] = None
    evidence_bbox: Optional[List[int]] = None
    is_valid_checksum: bool = True
    country_of_origin: Optional[str] = None
    country_flag: Optional[str] = None
    gs1_prefix: Optional[str] = None
    qr_payload: Optional[str] = None


class ExternalFSSAIData(BaseModel):
    status: ExternalVerificationStatus = ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE
    source: str = "FoSCoS Official Registry API"
    licence_number: Optional[str] = None
    business_name: Optional[str] = None
    registered_address: Optional[str] = None
    licence_status: Optional[str] = None  # ACTIVE, EXPIRED, SUSPENDED, etc.
    valid_upto: Optional[str] = None
    business_type: Optional[str] = None
    food_categories: Optional[List[str]] = None
    lookup_timestamp: Optional[str] = None
    message: str = ""
    error_details: Optional[str] = None
    raw_reference: Optional[Dict[str, Any]] = None
    manual_verification_url: Optional[str] = "https://foscos.fssai.gov.in"
    manual_verification_instructions: Optional[str] = None
    provenance: str = "UNAVAILABLE"  # REAL_EXTERNAL, LOCAL_CACHE, OCR, UNAVAILABLE


class ExternalProductData(BaseModel):
    status: ExternalVerificationStatus = ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE
    source: str = "GS1 India DataKart / Verified Registry"
    gtin: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    net_quantity: Optional[str] = None
    category: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    raw_reference: Optional[Dict[str, Any]] = None
    lookup_timestamp: Optional[str] = None
    message: str = ""
    error_details: Optional[str] = None
    manual_verification_url: Optional[str] = "https://www.gs1india.org"
    manual_verification_instructions: Optional[str] = None
    provenance: str = "UNAVAILABLE"  # REAL_EXTERNAL, LOCAL_CACHE, OCR, UNAVAILABLE


class CrossSourceFieldComparison(BaseModel):
    field: str
    package_value: Optional[str] = None
    external_value: Optional[str] = None
    result: ComparisonResult = ComparisonResult.NOT_VERIFIED
    details: Optional[str] = None
    source: Optional[str] = None


class ExternalProductVerificationPipelineResult(BaseModel):
    # Layer 1: Package OCR Data
    package_ocr_data: Dict[str, Any] = Field(default_factory=dict)
    fssai_extraction: FSSAIExtractionData = Field(default_factory=FSSAIExtractionData)
    barcode_extractions: List[BarcodeExtractionData] = Field(default_factory=list)

    # Layer 2: External Verification Data
    external_fssai: ExternalFSSAIData = Field(default_factory=ExternalFSSAIData)
    external_product: ExternalProductData = Field(default_factory=ExternalProductData)

    # Layer 3: Cross-Source Comparison
    cross_source_comparisons: List[CrossSourceFieldComparison] = Field(default_factory=list)

    # Status and limitations
    verification_status: str = "EXTERNAL_VERIFICATION_UNAVAILABLE"
    overall_pipeline_status: str = "EXTERNAL_VERIFICATION_UNAVAILABLE"
    limitations_notice: str = (
        "External verification availability may depend on the source, "
        "network availability, and applicable access controls. Absence of external record "
        "does not by itself establish that the product is counterfeit."
    )

