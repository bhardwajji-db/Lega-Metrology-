from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel

class GS1VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    MISMATCH = "MISMATCH"
    INVALID_FORMAT = "INVALID_FORMAT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NOT_VERIFIED = "NOT_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class GS1VerificationRecord(BaseModel):
    gtin: Optional[str] = None
    status: GS1VerificationStatus = GS1VerificationStatus.NOT_VERIFIED
    provider: str = "GS1 India DataKart / Verified Registry Provider"
    brand_name: Optional[str] = None
    product_description: Optional[str] = None
    company_name: Optional[str] = None
    gpc_category: Optional[str] = None
    net_content: Optional[str] = None
    country_of_sale: Optional[str] = None
    is_live: bool = False
    verification_timestamp: Optional[str] = None
    message: str = ""
    error_details: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
