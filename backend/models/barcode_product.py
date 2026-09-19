"""
MetrCheck AI — Barcode & GTIN Product Data Models
Defines schema for:
- Barcode/QR Code extractions (symbologies, check digits, bboxes, timestamps)
- GTIN Normalization & GS1 prefix jurisdiction
- External Product Master (standard fields, dynamic provider attributes, raw response)
- Provenance & Audit Trail
- Package OCR vs Barcode deterministic comparison
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class ProvenanceType(str, Enum):
    OCR = "OCR"
    REAL_EXTERNAL = "REAL_EXTERNAL"
    LOCAL_CACHE = "LOCAL_CACHE"
    MANUAL = "MANUAL"
    UNAVAILABLE = "UNAVAILABLE"


class FieldState(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_PROVIDED = "NOT_PROVIDED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    LOOKUP_UNAVAILABLE = "LOOKUP_UNAVAILABLE"


class BarcodeLookupStatus(str, Enum):
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    LOCAL_REFERENCE_MATCH = "LOCAL_REFERENCE_MATCH"
    LOCAL_CACHE = "LOCAL_CACHE"
    BARCODE_DETECTED = "BARCODE_DETECTED"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PARTIAL_PRODUCT_RECORD = "PARTIAL_PRODUCT_RECORD"
    INVALID_GTIN = "INVALID_GTIN"
    EXTERNAL_LOOKUP_UNAVAILABLE = "EXTERNAL_LOOKUP_UNAVAILABLE"
    EXTERNAL_VERIFICATION_UNAVAILABLE = "EXTERNAL_VERIFICATION_UNAVAILABLE"
    EXTERNAL_LOOKUP_FAILED = "EXTERNAL_LOOKUP_FAILED"
    NOT_DETECTED = "NOT_DETECTED"


class ComparisonStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    NOT_PROVIDED = "NOT_PROVIDED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    LOOKUP_UNAVAILABLE = "LOOKUP_UNAVAILABLE"


class ProvenanceValue(BaseModel):
    """Encapsulates a single field value with its exact source, provenance, and state."""
    value: Optional[Any] = None
    source: str = "External Provider"
    provenance: ProvenanceType = ProvenanceType.UNAVAILABLE
    state: FieldState = FieldState.NOT_PROVIDED
    raw_key: Optional[str] = None


class DetectedBarcodeCode(BaseModel):
    """Full detail of an individual 1D/2D code detected on packaging."""
    raw_value: str
    normalized_value: str
    symbology: str  # EAN-13, EAN-8, UPC-A, UPC-E, GTIN-14, Code 128, Code 39, ITF, DataMatrix, QR Code, GS1-128, GS1 DataMatrix, GS1 Digital Link
    gtin: Optional[str] = None  # Normalized GTIN if applicable
    gtin_format: Optional[str] = None  # GTIN-8, GTIN-12, GTIN-13, GTIN-14
    checksum_valid: bool = True
    detection_confidence: float = 0.95
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    evidence_image: Optional[str] = None  # Front, Back, etc.
    extraction_timestamp: str = ""
    country_prefix: Optional[str] = None
    country_name: Optional[str] = None
    country_flag: Optional[str] = None
    country_note: str = (
        "GS1 prefix designates issuing Member Organization, not guaranteed country of manufacturing."
    )
    digital_link_data: Optional[Dict[str, Any]] = None
    fssai_from_barcode: Optional[str] = None  # FSSAI license if explicitly embedded in QR payload


class ProductIdentityFields(BaseModel):
    product_name: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_description: ProvenanceValue = Field(default_factory=ProvenanceValue)
    brand_name: ProvenanceValue = Field(default_factory=ProvenanceValue)
    sub_brand: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_category: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_type: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_family: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_variant: ProvenanceValue = Field(default_factory=ProvenanceValue)
    model_number: ProvenanceValue = Field(default_factory=ProvenanceValue)
    sku: ProvenanceValue = Field(default_factory=ProvenanceValue)
    gtin: ProvenanceValue = Field(default_factory=ProvenanceValue)
    upc: ProvenanceValue = Field(default_factory=ProvenanceValue)
    ean: ProvenanceValue = Field(default_factory=ProvenanceValue)


class ManufacturerCompanyFields(BaseModel):
    manufacturer_name: ProvenanceValue = Field(default_factory=ProvenanceValue)
    manufacturer_legal_name: ProvenanceValue = Field(default_factory=ProvenanceValue)
    manufacturer_address: ProvenanceValue = Field(default_factory=ProvenanceValue)
    manufacturer_country: ProvenanceValue = Field(default_factory=ProvenanceValue)
    brand_owner: ProvenanceValue = Field(default_factory=ProvenanceValue)
    brand_owner_address: ProvenanceValue = Field(default_factory=ProvenanceValue)
    packer: ProvenanceValue = Field(default_factory=ProvenanceValue)
    importer: ProvenanceValue = Field(default_factory=ProvenanceValue)
    distributor: ProvenanceValue = Field(default_factory=ProvenanceValue)
    company_identifiers: ProvenanceValue = Field(default_factory=ProvenanceValue)
    company_contact: ProvenanceValue = Field(default_factory=ProvenanceValue)


class PackagingFields(BaseModel):
    package_type: ProvenanceValue = Field(default_factory=ProvenanceValue)
    package_size: ProvenanceValue = Field(default_factory=ProvenanceValue)
    net_quantity: ProvenanceValue = Field(default_factory=ProvenanceValue)
    quantity_value: ProvenanceValue = Field(default_factory=ProvenanceValue)
    quantity_unit: ProvenanceValue = Field(default_factory=ProvenanceValue)
    pack_count: ProvenanceValue = Field(default_factory=ProvenanceValue)
    number_of_units: ProvenanceValue = Field(default_factory=ProvenanceValue)
    variant_flavour: ProvenanceValue = Field(default_factory=ProvenanceValue)
    size_weight_volume: ProvenanceValue = Field(default_factory=ProvenanceValue)
    packaging_dimensions: ProvenanceValue = Field(default_factory=ProvenanceValue)


class ClassificationFields(BaseModel):
    category: ProvenanceValue = Field(default_factory=ProvenanceValue)
    subcategory: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_group: ProvenanceValue = Field(default_factory=ProvenanceValue)
    industry_codes: ProvenanceValue = Field(default_factory=ProvenanceValue)
    unspsc: ProvenanceValue = Field(default_factory=ProvenanceValue)
    gpc_code: ProvenanceValue = Field(default_factory=ProvenanceValue)


class AttributeFields(BaseModel):
    material: ProvenanceValue = Field(default_factory=ProvenanceValue)
    colour: ProvenanceValue = Field(default_factory=ProvenanceValue)
    size: ProvenanceValue = Field(default_factory=ProvenanceValue)
    flavour: ProvenanceValue = Field(default_factory=ProvenanceValue)
    ingredients: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_features: ProvenanceValue = Field(default_factory=ProvenanceValue)
    technical_specifications: ProvenanceValue = Field(default_factory=ProvenanceValue)
    consumer_attributes: ProvenanceValue = Field(default_factory=ProvenanceValue)


class MediaFields(BaseModel):
    product_image_url: ProvenanceValue = Field(default_factory=ProvenanceValue)
    additional_images: ProvenanceValue = Field(default_factory=ProvenanceValue)
    front_image: ProvenanceValue = Field(default_factory=ProvenanceValue)
    back_image: ProvenanceValue = Field(default_factory=ProvenanceValue)
    package_image: ProvenanceValue = Field(default_factory=ProvenanceValue)
    thumbnail: ProvenanceValue = Field(default_factory=ProvenanceValue)


class DatesStatusFields(BaseModel):
    creation_date: ProvenanceValue = Field(default_factory=ProvenanceValue)
    update_date: ProvenanceValue = Field(default_factory=ProvenanceValue)
    launch_date: ProvenanceValue = Field(default_factory=ProvenanceValue)
    product_status: ProvenanceValue = Field(default_factory=ProvenanceValue)
    active_status: ProvenanceValue = Field(default_factory=ProvenanceValue)


class RegulatoryIdentifierFields(BaseModel):
    gtin: ProvenanceValue = Field(default_factory=ProvenanceValue)
    gln: ProvenanceValue = Field(default_factory=ProvenanceValue)
    gpc_code: ProvenanceValue = Field(default_factory=ProvenanceValue)
    gs1_company_info: ProvenanceValue = Field(default_factory=ProvenanceValue)
    other_identifiers: ProvenanceValue = Field(default_factory=ProvenanceValue)


class StandardProductFields(BaseModel):
    identity: ProductIdentityFields = Field(default_factory=ProductIdentityFields)
    manufacturer: ManufacturerCompanyFields = Field(default_factory=ManufacturerCompanyFields)
    packaging: PackagingFields = Field(default_factory=PackagingFields)
    classification: ClassificationFields = Field(default_factory=ClassificationFields)
    attributes: AttributeFields = Field(default_factory=AttributeFields)
    media: MediaFields = Field(default_factory=MediaFields)
    dates: DatesStatusFields = Field(default_factory=DatesStatusFields)
    regulatory: RegulatoryIdentifierFields = Field(default_factory=RegulatoryIdentifierFields)


class ExternalLookupAudit(BaseModel):
    """Audit log of external lookup request/response without exposing credentials."""
    provider_name: str
    request_timestamp: str
    gtin_queried: str
    response_timestamp: str
    http_status: Optional[int] = None
    provider_response_id: Optional[str] = None
    normalized_fields: Dict[str, Any] = Field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = None
    provenance: ProvenanceType = ProvenanceType.UNAVAILABLE
    api_version: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None


class ExternalProductMaster(BaseModel):
    """
    Comprehensive product record preserving ALL standard fields, dynamic provider attributes,
    and the raw response.
    """
    gtin: str
    lookup_status: BarcodeLookupStatus = BarcodeLookupStatus.EXTERNAL_VERIFICATION_UNAVAILABLE
    source: str = "Unconfigured Provider"
    provenance: ProvenanceType = ProvenanceType.UNAVAILABLE
    lookup_timestamp: str = ""
    message: str = ""
    standard_fields: StandardProductFields = Field(default_factory=StandardProductFields)
    provider_attributes: Dict[str, ProvenanceValue] = Field(default_factory=dict)
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    audit: Optional[ExternalLookupAudit] = None
    fssai_from_provider: Optional[ProvenanceValue] = None
    manual_verification_url: Optional[str] = "https://www.gs1india.org"
    manual_verification_instructions: Optional[str] = None

    # Flattened convenience accessors
    @property
    def product_name(self) -> Optional[str]:
        val = self.standard_fields.identity.product_name.value
        return str(val) if val is not None else None

    @property
    def brand(self) -> Optional[str]:
        val = self.standard_fields.identity.brand_name.value
        return str(val) if val is not None else None

    @property
    def manufacturer(self) -> Optional[str]:
        val = (self.standard_fields.manufacturer.manufacturer_name.value or
               self.standard_fields.manufacturer.manufacturer_legal_name.value or
               self.standard_fields.manufacturer.brand_owner.value)
        return str(val) if val is not None else None

    @property
    def net_quantity(self) -> Optional[str]:
        val = self.standard_fields.packaging.net_quantity.value
        return str(val) if val is not None else None

    @property
    def category(self) -> Optional[str]:
        val = self.standard_fields.classification.category.value or self.standard_fields.identity.product_category.value
        return str(val) if val is not None else None


class DeterministicFieldComparison(BaseModel):
    """Comparison of a single attribute between Package OCR and External Product Data."""
    field_name: str
    package_ocr_value: Optional[str] = None
    external_value: Optional[str] = None
    status: ComparisonStatus = ComparisonStatus.NOT_PROVIDED
    details: str = ""
    source: str = ""
    provenance: ProvenanceType = ProvenanceType.UNAVAILABLE


class BarcodeProductLookupResult(BaseModel):
    """Top-level result of the Barcode/GTIN product lookup and OCR comparison system."""
    barcode_detected: bool = False
    detected_codes: List[DetectedBarcodeCode] = Field(default_factory=list)
    primary_code: Optional[DetectedBarcodeCode] = None
    gtin_valid: bool = False
    lookup_status: BarcodeLookupStatus = BarcodeLookupStatus.NOT_DETECTED
    product_master: Optional[ExternalProductMaster] = None
    field_comparisons: List[DeterministicFieldComparison] = Field(default_factory=list)
    fssai_from_barcode: Optional[str] = None
    audit: Optional[ExternalLookupAudit] = None
    summary: str = ""
    country_note: str = (
        "GS1 prefix designates issuing Member Organization, not guaranteed country of manufacturing."
    )
