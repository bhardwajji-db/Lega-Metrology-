from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel

class FSSAIVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_FORMAT = "INVALID_FORMAT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NOT_VERIFIED = "NOT_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class FSSAIProviderType(str, Enum):
    OFFICIAL_FOSCOS_API = "OFFICIAL_FOSCOS_API"
    VERIFIED_LOCAL_CACHE = "VERIFIED_LOCAL_CACHE"
    HYBRID = "HYBRID"

class FSSAIVerificationRecord(BaseModel):
    licence_number: Optional[str] = None
    status: FSSAIVerificationStatus = FSSAIVerificationStatus.NOT_VERIFIED
    provider: str = "FoSCoS Official Registry API / Verified Provider"
    business_name: Optional[str] = None
    licence_type: Optional[str] = None
    valid_upto: Optional[str] = None
    is_live: bool = False
    verification_timestamp: Optional[str] = None
    message: str = ""
    error_details: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
