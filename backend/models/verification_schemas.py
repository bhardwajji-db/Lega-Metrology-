from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus
from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus


class CrossCheckStatus(str, Enum):
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    MISMATCH = "MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNVERIFIED = "UNVERIFIED"
    NOT_FOUND = "NOT_FOUND"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ApiAvailabilityState(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNCONFIGURED = "UNCONFIGURED"
    DEGRADED = "DEGRADED"


class VerificationConfidenceTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ZERO = "ZERO"


class CrossCheckFieldResult(BaseModel):
    check_type: str  # e.g., "FSSAI_MANUFACTURER_CONSISTENCY", "GS1_PRODUCT_CONSISTENCY", "QR_STATUTORY_CONSISTENCY", "IDENTIFIER_CONSISTENCY"
    field_name: str  # e.g., "manufacturer_name", "product_name", "net_quantity", "mrp"
    extracted_value: Optional[str] = None
    registry_value: Optional[str] = None
    status: CrossCheckStatus = CrossCheckStatus.NOT_APPLICABLE
    similarity_score: float = 0.0  # 0.0 to 1.0
    matched_tokens: List[str] = []
    discrepancy_details: Optional[str] = None
    verification_source: str = "STATUTORY_CROSS_CHECK_ENGINE"
    is_critical_mismatch: bool = False


class VerificationConfidence(BaseModel):
    score: float = 0.0  # 0.0 to 1.0
    tier: VerificationConfidenceTier = VerificationConfidenceTier.ZERO
    checksum_passed: bool = False
    registry_confirmed: bool = False
    field_agreement_rate: float = 0.0  # 0.0 to 1.0
    cache_freshness_sec: Optional[int] = None
    factors: Dict[str, Any] = {}
    verdict: str = ""


class ApiAvailabilityStatus(BaseModel):
    service_name: str
    state: ApiAvailabilityState
    endpoint: Optional[str] = None
    last_checked: Optional[str] = None
    latency_ms: Optional[float] = None
    message: str = ""


class ExternalVerificationSummary(BaseModel):
    fssai_verification: Optional[FSSAIVerificationRecord] = None
    gs1_verification: Optional[GS1VerificationRecord] = None
    qr_payload: Optional[str] = None
    barcode_detected: Optional[str] = None
    cross_checks: List[CrossCheckFieldResult] = []
    overall_consistency_status: CrossCheckStatus = CrossCheckStatus.NOT_APPLICABLE
    confidence: VerificationConfidence = Field(default_factory=VerificationConfidence)
    api_availability: Dict[str, ApiAvailabilityStatus] = {}
    offline_mode: bool = False
    verification_timestamp: str = ""
    verification_sources: List[str] = []
    discrepancies: List[str] = []
    summary_verdict: str = ""


class CrossCheckRequest(BaseModel):
    product_name: Optional[str] = None
    brand_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    fssai_license: Optional[str] = None
    gtin_barcode: Optional[str] = None
    qr_payload: Optional[str] = None
    net_quantity: Optional[str] = None
    mrp: Optional[str] = None
    offline_mode: bool = False


class CacheSeedItem(BaseModel):
    identifier_type: str  # "FSSAI" | "GS1_GTIN"
    identifier_value: str
    record_data: Dict[str, Any]
    source: str = "OFFICIAL_SEED"
    ttl_seconds: int = 86400 * 30  # 30 days default
