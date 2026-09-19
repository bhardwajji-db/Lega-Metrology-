"""
MetrCheck AI — Product Identity & Verification Schemas
Defines standardized field-evidence containers, product identity structures,
and cross-validation results in accordance with SIH Problem Statement 26034.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# Standardized Status Constants
class FieldStatus:
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_DETERMINED = "NOT_DETERMINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FieldEvidenceItem(BaseModel):
    """
    Standardized field-evidence container.
    Every extracted field in Product Identity adheres to this structure.
    """
    value: Optional[str] = None
    normalized_value: Optional[str] = None
    confidence: float = 0.0
    source: str = "OCR"  # OCR, QR_CODE, BARCODE, MASTER_REGISTRY, MULTILINGUAL_DICT
    bounding_box: Optional[List[int]] = None  # [x1, y1, x2, y2]
    image_id: Optional[str] = None  # Source panel or image filename
    status: str = FieldStatus.NOT_FOUND
    explanation: Optional[str] = None
    nearby_text: Optional[str] = None
    raw_tokens: List[str] = Field(default_factory=list)


class QRContentData(BaseModel):
    raw_value: str
    content_type: str = "TEXT"  # URL, GS1_DIGITAL_LINK, IDENTIFIER, STRUCTURED_JSON, TEXT
    is_safe_url: bool = True
    parsed_url: Optional[str] = None
    hostname: Optional[str] = None
    gs1_ai_data: Optional[Dict[str, Any]] = None
    bounding_box: Optional[List[int]] = None
    image_id: Optional[str] = None
    confidence: float = 0.95
    status: str = FieldStatus.FOUND
    security_warning: Optional[str] = None


class BarcodeIdentityData(BaseModel):
    raw_value: str
    symbology: str = "EAN-13"  # EAN-13, EAN-8, UPC-A, CODE-128, etc.
    is_valid_checksum: bool = True
    country_of_origin: Optional[str] = None
    country_flag: Optional[str] = None
    gs1_prefix: Optional[str] = None
    bounding_box: Optional[List[int]] = None
    image_id: Optional[str] = None
    confidence: float = 0.95
    status: str = FieldStatus.FOUND
    external_verified: bool = False
    verification_status: str = "NOT_VERIFIED"  # VERIFIED, NOT_FOUND, SERVICE_UNAVAILABLE, NOT_VERIFIED
    provenance_label: str = "Extracted from package"  # Extracted from package, Externally verified, Not found, Verification unavailable
    registered_brand: Optional[str] = None
    registered_product: Optional[str] = None
    registered_company: Optional[str] = None
    registered_net_quantity: Optional[str] = None
    provider: Optional[str] = None


class DateDeclarations(BaseModel):
    date_of_manufacture: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    date_of_packaging: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    date_of_import: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    best_before: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    expiry_date: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    use_by_date: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)


class ConsumerCareDeclarations(BaseModel):
    phone: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    email: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    address: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    website: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)


class FoodDeclarations(BaseModel):
    is_food: bool = False
    ingredients: List[str] = Field(default_factory=list)
    ingredients_evidence: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    allergens: List[str] = Field(default_factory=list)
    allergens_evidence: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    nutritional_info: Dict[str, str] = Field(default_factory=dict)
    nutrition_evidence: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    veg_nonveg_status: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)  # VEGETARIAN, NON_VEGETARIAN, NOT_APPLICABLE
    serving_info: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    storage_instructions: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)


class OtherDeclarations(BaseModel):
    product_code: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    model_number: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    certifications: List[FieldEvidenceItem] = Field(default_factory=list)


class ConflictItem(BaseModel):
    field_name: str
    source_a: str  # e.g., "OCR"
    value_a: str
    source_b: str  # e.g., "QR_CODE" or "BARCODE_MASTER"
    value_b: str
    severity: str = "HIGH"  # HIGH, MEDIUM, WARNING
    description: str = ""
    evidence_boxes: List[Dict[str, Any]] = Field(default_factory=list)


class CrossValidationSummary(BaseModel):
    status: str = "PASS"  # PASS, CONFLICT_DETECTED, REVIEW_REQUIRED, NOT_APPLICABLE
    has_conflicts: bool = False
    conflicts: List[ConflictItem] = Field(default_factory=list)
    fssai_cross_check: Optional[Dict[str, Any]] = None
    barcode_cross_check: Optional[Dict[str, Any]] = None
    summary_message: str = "All cross-validated sources are consistent."


class ProductIdentity(BaseModel):
    """
    Comprehensive product identity object for an inspection.
    Encapsulates all extracted product data, quality diagnostics,
    standardized field evidence, and cross-source verification.
    """
    # Core Identity
    product_name: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    brand_name: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    product_variant: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    product_category: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)

    # Barcodes & QR Codes
    barcodes: List[BarcodeIdentityData] = Field(default_factory=list)
    qr_codes: List[QRContentData] = Field(default_factory=list)

    # FSSAI Information
    fssai_license_number: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    fssai_state_name: Optional[str] = None
    fssai_license_type: Optional[str] = None  # STATE_LICENSE, CENTRAL_LICENSE, BASIC_REGISTRATION
    fssai_external_verified: bool = False
    fssai_verification_status: str = "NOT_VERIFIED"  # VERIFIED, NOT_FOUND, SERVICE_UNAVAILABLE, NOT_VERIFIED, NOT_APPLICABLE
    fssai_provenance_label: str = "Not found"  # Extracted from package, Externally verified, Not found, Verification unavailable
    fssai_verification_details: Optional[Dict[str, Any]] = None

    # Barcode External Verification & Provenance
    barcode_external_verified: bool = False
    barcode_verification_status: str = "NOT_VERIFIED"  # VERIFIED, NOT_FOUND, SERVICE_UNAVAILABLE, NOT_VERIFIED, NOT_APPLICABLE
    barcode_provenance_label: str = "Not found"  # Extracted from package, Externally verified, Not found, Verification unavailable
    barcode_registered_details: Optional[Dict[str, Any]] = None

    # Manufacturer / Packer / Importer / Marketer
    manufacturer: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    packer: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    importer: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    marketer: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    complete_address: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    country_of_origin: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)

    # Legal Metrology Core Declarations
    mrp: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    net_quantity: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    unit: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)
    batch_number: FieldEvidenceItem = Field(default_factory=FieldEvidenceItem)

    # Dates & Consumer Care
    dates: DateDeclarations = Field(default_factory=DateDeclarations)
    customer_care: ConsumerCareDeclarations = Field(default_factory=ConsumerCareDeclarations)

    # Food-Related Declarations
    food_declarations: FoodDeclarations = Field(default_factory=FoodDeclarations)

    # Other Declarations
    other_declarations: OtherDeclarations = Field(default_factory=OtherDeclarations)

    # Quality Gate & Diagnostics
    image_quality_status: str = "PASS"  # PASS, REVIEW_REQUIRED, REJECT
    quality_reasons: List[str] = Field(default_factory=list)

    # Cross-Validation Layer
    cross_validation: CrossValidationSummary = Field(default_factory=CrossValidationSummary)
