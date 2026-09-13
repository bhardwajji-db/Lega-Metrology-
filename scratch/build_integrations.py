import os
import pathlib

BASE_DIR = pathlib.Path("backend")

fssai_schemas = """from enum import Enum
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
"""

fssai_providers = """import abc
import asyncio
import logging
from typing import Optional, Dict, Any
from utils.datetime_utils import get_current_utc_iso
from backend.integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus

logger = logging.getLogger(__name__)

class BaseFSSAIProvider(abc.ABC):
    @abc.abstractmethod
    async def verify_licence(self, licence_number: str) -> FSSAIVerificationRecord:
        \"\"\"Verify a 14-digit FSSAI licence number.\"\"\"
        pass

class FoSCoSApiProvider(BaseFSSAIProvider):
    \"\"\"
    Official FoSCoS (Food Safety Compliance System) Registry API Provider.
    Calls official Government of India FSSAI / FoSCoS verification endpoints when configured.
    Handles network timeouts and service downtime gracefully without fabricated records.
    \"\"\"
    def __init__(self, api_url: str = "", api_key: str = "", timeout_sec: float = 3.0):
        self.api_url = (api_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout_sec = timeout_sec

    def is_configured(self) -> bool:
        return bool(self.api_url)

    async def verify_licence(self, licence_number: str) -> FSSAIVerificationRecord:
        now_ts = get_current_utc_iso()
        if not self.is_configured():
            return FSSAIVerificationRecord(
                licence_number=licence_number,
                status=FSSAIVerificationStatus.NOT_VERIFIED,
                provider="FoSCoS Official Registry API (Unconfigured)",
                is_live=False,
                verification_timestamp=now_ts,
                message="Official FoSCoS API endpoint not configured in server environment. Format verified locally."
            )

        try:
            import httpx
            headers = {"User-Agent": "MetrCheckAI-ComplianceEngine/1.0"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.get(f"{self.api_url}/{licence_number}", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return FSSAIVerificationRecord(
                        licence_number=licence_number,
                        status=FSSAIVerificationStatus.VERIFIED if data.get("active") else FSSAIVerificationStatus.NOT_FOUND,
                        provider="FoSCoS Official Registry API (Live)",
                        business_name=data.get("business_name") or data.get("fbo_name"),
                        licence_type=data.get("licence_type") or data.get("kind_of_business"),
                        valid_upto=data.get("valid_upto") or data.get("expiry_date"),
                        is_live=True,
                        verification_timestamp=now_ts,
                        message="FSSAI licence successfully verified against live FoSCoS registry.",
                        raw_payload=data
                    )
                elif resp.status_code == 404:
                    return FSSAIVerificationRecord(
                        licence_number=licence_number,
                        status=FSSAIVerificationStatus.NOT_FOUND,
                        provider="FoSCoS Official Registry API (Live)",
                        is_live=True,
                        verification_timestamp=now_ts,
                        message=f"Licence {licence_number} not found in FoSCoS registry."
                    )
                else:
                    return FSSAIVerificationRecord(
                        licence_number=licence_number,
                        status=FSSAIVerificationStatus.SERVICE_UNAVAILABLE,
                        provider="FoSCoS Official Registry API (Live)",
                        is_live=False,
                        verification_timestamp=now_ts,
                        message=f"FoSCoS API returned HTTP {resp.status_code}.",
                        error_details=resp.text[:200]
                    )
        except Exception as e:
            logger.warning(f"FoSCoS API connection error for licence {licence_number}: {e}")
            return FSSAIVerificationRecord(
                licence_number=licence_number,
                status=FSSAIVerificationStatus.SERVICE_UNAVAILABLE,
                provider="FoSCoS Official Registry API (Live)",
                is_live=False,
                verification_timestamp=now_ts,
                message="Official FoSCoS API service currently unreachable or timed out.",
                error_details=str(e)
            )

class LocalFSSAICacheProvider(BaseFSSAIProvider):
    \"\"\"
    Local verified cache provider for FSSAI licences with explicit provenance.
    \"\"\"
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def set_cache_record(self, licence_number: str, data: Dict[str, Any]):
        self._cache[licence_number] = data

    async def verify_licence(self, licence_number: str) -> FSSAIVerificationRecord:
        now_ts = get_current_utc_iso()
        if licence_number in self._cache:
            entry = self._cache[licence_number]
            return FSSAIVerificationRecord(
                licence_number=licence_number,
                status=entry.get("status", FSSAIVerificationStatus.VERIFIED),
                provider="MetrCheck Verified FSSAI Local Cache",
                business_name=entry.get("business_name"),
                licence_type=entry.get("licence_type"),
                valid_upto=entry.get("valid_upto"),
                is_live=False,
                verification_timestamp=entry.get("cached_at", now_ts),
                message="FSSAI licence matched in local verified cache records.",
                raw_payload=entry
            )
        return FSSAIVerificationRecord(
            licence_number=licence_number,
            status=FSSAIVerificationStatus.NOT_FOUND,
            provider="MetrCheck Verified FSSAI Local Cache",
            is_live=False,
            verification_timestamp=now_ts,
            message="Licence not present in local verified cache."
        )
"""

fssai_verifier = """import re
import logging
from typing import Optional
from utils.datetime_utils import get_current_utc_iso
from backend.config import settings
from backend.integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus
from backend.integrations.fssai.providers import FoSCoSApiProvider, LocalFSSAICacheProvider, BaseFSSAIProvider

logger = logging.getLogger(__name__)

class FSSAILicenceVerifier:
    \"\"\"
    Coordinator for FSSAI 14-digit Licence Verification.
    Validates structural conformity (Rule 14-digit format, starting with 1 or 2)
    and queries configured external/cached providers.
    \"\"\"
    def __init__(self, primary_provider: Optional[BaseFSSAIProvider] = None, fallback_provider: Optional[BaseFSSAIProvider] = None):
        if primary_provider is not None:
            self.primary_provider = primary_provider
        else:
            self.primary_provider = FoSCoSApiProvider(
                api_url=settings.FSSAI_API_URL,
                api_key=settings.FSSAI_API_KEY,
                timeout_sec=settings.FSSAI_API_TIMEOUT_SEC
            )
        self.fallback_provider = fallback_provider or LocalFSSAICacheProvider()

    @staticmethod
    def validate_format(licence_number: str) -> bool:
        \"\"\"
        Validates FSSAI 14-digit format:
        - Exactly 14 digits
        - Digit 1: Licence category (1 = Central/State Licence, 2 = Registration)
        - Digits 2-3: State Code (00-38)
        - Digits 4-5: Year of Registration (e.g. 19, 20, 21, 22, 23, 24, 25, 26)
        \"\"\"
        if not licence_number:
            return False
        clean = re.sub(r'\\D', '', str(licence_number))
        if len(clean) != 14:
            return False
        if clean[0] not in ('1', '2'):
            return False
        return True

    async def verify(self, licence_number: Optional[str]) -> FSSAIVerificationRecord:
        now_ts = get_current_utc_iso()
        if not licence_number or not str(licence_number).strip():
            return FSSAIVerificationRecord(
                licence_number=None,
                status=FSSAIVerificationStatus.NOT_APPLICABLE,
                provider="FSSAI Validator",
                is_live=False,
                verification_timestamp=now_ts,
                message="No FSSAI licence number provided for verification."
            )

        clean_licence = re.sub(r'\\D', '', str(licence_number))
        if not self.validate_format(clean_licence):
            return FSSAIVerificationRecord(
                licence_number=licence_number,
                status=FSSAIVerificationStatus.INVALID_FORMAT,
                provider="FSSAI Validator",
                is_live=False,
                verification_timestamp=now_ts,
                message=f"Licence '{licence_number}' does not conform to the statutory 14-digit FoSCoS format (starting with 1 or 2)."
            )

        # 1. Attempt primary provider (FoSCoS API)
        res = await self.primary_provider.verify_licence(clean_licence)
        if res.status in (FSSAIVerificationStatus.VERIFIED, FSSAIVerificationStatus.NOT_FOUND):
            return res

        # 2. Attempt fallback provider (Local cache)
        if self.fallback_provider and res.status in (FSSAIVerificationStatus.NOT_VERIFIED, FSSAIVerificationStatus.SERVICE_UNAVAILABLE):
            cache_res = await self.fallback_provider.verify_licence(clean_licence)
            if cache_res.status == FSSAIVerificationStatus.VERIFIED:
                return cache_res

        # 3. If still unverified/unavailable, return structural format pass
        if res.status == FSSAIVerificationStatus.NOT_VERIFIED:
            category_name = "Licence" if clean_licence[0] == '1' else "Registration"
            return FSSAIVerificationRecord(
                licence_number=clean_licence,
                status=FSSAIVerificationStatus.NOT_VERIFIED,
                provider="MetrCheck Local FoSCoS Format Validator",
                is_live=False,
                verification_timestamp=now_ts,
                message=f"Statutory 14-digit format valid ({clean_licence[:1]} = {category_name}, State={clean_licence[1:3]}). Live registry check unconfigured."
            )

        return res

# Global instance
fssai_verifier = FSSAILicenceVerifier()
"""

fssai_init = """from backend.integrations.fssai.schemas import FSSAIVerificationStatus, FSSAIVerificationRecord
from backend.integrations.fssai.providers import FoSCoSApiProvider, LocalFSSAICacheProvider, BaseFSSAIProvider
from backend.integrations.fssai.verifier import FSSAILicenceVerifier, fssai_verifier
"""

# GS1 Files
gs1_schemas = """from enum import Enum
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
"""

gs1_providers = """import abc
import asyncio
import logging
from typing import Optional, Dict, Any
from utils.datetime_utils import get_current_utc_iso
from backend.integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus

logger = logging.getLogger(__name__)

class BaseGS1Provider(abc.ABC):
    @abc.abstractmethod
    async def verify_gtin(self, gtin: str) -> GS1VerificationRecord:
        \"\"\"Verify GTIN barcode against registry.\"\"\"
        pass

class GS1DataKartApiProvider(BaseGS1Provider):
    \"\"\"
    Official GS1 India DataKart API Provider.
    Queries GS1 DataKart / Verified by GS1 API when configured.
    Handles network timeouts and service downtime gracefully.
    \"\"\"
    def __init__(self, api_url: str = "", api_key: str = "", timeout_sec: float = 3.0):
        self.api_url = (api_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout_sec = timeout_sec

    def is_configured(self) -> bool:
        return bool(self.api_url)

    async def verify_gtin(self, gtin: str) -> GS1VerificationRecord:
        now_ts = get_current_utc_iso()
        if not self.is_configured():
            return GS1VerificationRecord(
                gtin=gtin,
                status=GS1VerificationStatus.NOT_VERIFIED,
                provider="GS1 India DataKart API (Unconfigured)",
                is_live=False,
                verification_timestamp=now_ts,
                message="Official GS1 India API endpoint not configured in server environment. Checksum verified locally."
            )

        try:
            import httpx
            headers = {"User-Agent": "MetrCheckAI-ComplianceEngine/1.0"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.get(f"{self.api_url}/{gtin}", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return GS1VerificationRecord(
                        gtin=gtin,
                        status=GS1VerificationStatus.VERIFIED if data.get("valid") else GS1VerificationStatus.NOT_FOUND,
                        provider="GS1 India DataKart API (Live)",
                        brand_name=data.get("brand_name"),
                        product_description=data.get("product_description"),
                        company_name=data.get("company_name"),
                        gpc_category=data.get("gpc_category"),
                        net_content=data.get("net_content"),
                        country_of_sale=data.get("country_of_sale", "India"),
                        is_live=True,
                        verification_timestamp=now_ts,
                        message="GTIN barcode successfully verified against GS1 India DataKart registry.",
                        raw_payload=data
                    )
                elif resp.status_code == 404:
                    return GS1VerificationRecord(
                        gtin=gtin,
                        status=GS1VerificationStatus.NOT_FOUND,
                        provider="GS1 India DataKart API (Live)",
                        is_live=True,
                        verification_timestamp=now_ts,
                        message=f"GTIN {gtin} not found in GS1 registry."
                    )
                else:
                    return GS1VerificationRecord(
                        gtin=gtin,
                        status=GS1VerificationStatus.SERVICE_UNAVAILABLE,
                        provider="GS1 India DataKart API (Live)",
                        is_live=False,
                        verification_timestamp=now_ts,
                        message=f"GS1 API returned HTTP {resp.status_code}.",
                        error_details=resp.text[:200]
                    )
        except Exception as e:
            logger.warning(f"GS1 API connection error for GTIN {gtin}: {e}")
            return GS1VerificationRecord(
                gtin=gtin,
                status=GS1VerificationStatus.SERVICE_UNAVAILABLE,
                provider="GS1 India DataKart API (Live)",
                is_live=False,
                verification_timestamp=now_ts,
                message="Official GS1 DataKart API service currently unreachable or timed out.",
                error_details=str(e)
            )

class LocalGS1CacheProvider(BaseGS1Provider):
    \"\"\"
    Local verified cache provider for GS1 barcodes with explicit provenance.
    \"\"\"
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def set_cache_record(self, gtin: str, data: Dict[str, Any]):
        self._cache[gtin] = data

    async def verify_gtin(self, gtin: str) -> GS1VerificationRecord:
        now_ts = get_current_utc_iso()
        if gtin in self._cache:
            entry = self._cache[gtin]
            return GS1VerificationRecord(
                gtin=gtin,
                status=entry.get("status", GS1VerificationStatus.VERIFIED),
                provider="MetrCheck Verified GS1 Local Cache",
                brand_name=entry.get("brand_name"),
                product_description=entry.get("product_description"),
                company_name=entry.get("company_name"),
                gpc_category=entry.get("gpc_category"),
                net_content=entry.get("net_content"),
                country_of_sale=entry.get("country_of_sale", "India"),
                is_live=False,
                verification_timestamp=entry.get("cached_at", now_ts),
                message="GTIN barcode matched in local verified cache records.",
                raw_payload=entry
            )
        return GS1VerificationRecord(
            gtin=gtin,
            status=GS1VerificationStatus.NOT_FOUND,
            provider="MetrCheck Verified GS1 Local Cache",
            is_live=False,
            verification_timestamp=now_ts,
            message="GTIN not present in local verified cache."
        )
"""

gs1_verifier = """import re
import logging
from typing import Optional
from utils.datetime_utils import get_current_utc_iso
from backend.config import settings
from backend.integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus
from backend.integrations.gs1.providers import GS1DataKartApiProvider, LocalGS1CacheProvider, BaseGS1Provider

logger = logging.getLogger(__name__)

class GS1BarcodeVerifier:
    \"\"\"
    Coordinator for GS1 GTIN / Barcode Verification.
    Validates structural conformity (GTIN-8, GTIN-12, GTIN-13, GTIN-14 Modulo-10 checksum)
    and queries configured external/cached providers.
    \"\"\"
    def __init__(self, primary_provider: Optional[BaseGS1Provider] = None, fallback_provider: Optional[BaseGS1Provider] = None):
        if primary_provider is not None:
            self.primary_provider = primary_provider
        else:
            self.primary_provider = GS1DataKartApiProvider(
                api_url=settings.GS1_API_URL,
                api_key=settings.GS1_API_KEY,
                timeout_sec=settings.GS1_API_TIMEOUT_SEC
            )
        self.fallback_provider = fallback_provider or LocalGS1CacheProvider()

    @staticmethod
    def calculate_check_digit(digits_str: str) -> int:
        \"\"\"
        Calculate GS1 standard Modulo-10 check digit for an N-digit prefix.
        Alternating weights (3, 1) starting from the rightmost digit before check digit.
        \"\"\"
        rev = digits_str[::-1]
        total = 0
        for idx, char in enumerate(rev):
            weight = 3 if idx % 2 == 0 else 1
            total += int(char) * weight
        remainder = total % 10
        return 0 if remainder == 0 else (10 - remainder)

    @classmethod
    def validate_gtin_checksum(cls, gtin: str) -> bool:
        \"\"\"
        Validates GTIN-8, GTIN-12, GTIN-13, or GTIN-14 check digit.
        \"\"\"
        clean = re.sub(r'\\D', '', str(gtin))
        if len(clean) not in (8, 12, 13, 14):
            return False
        prefix = clean[:-1]
        expected_check = cls.calculate_check_digit(prefix)
        return int(clean[-1]) == expected_check

    async def verify(self, gtin: Optional[str]) -> GS1VerificationRecord:
        now_ts = get_current_utc_iso()
        if not gtin or not str(gtin).strip():
            return GS1VerificationRecord(
                gtin=None,
                status=GS1VerificationStatus.NOT_APPLICABLE,
                provider="GS1 Barcode Validator",
                is_live=False,
                verification_timestamp=now_ts,
                message="No GTIN barcode provided for verification."
            )

        clean_gtin = re.sub(r'\\D', '', str(gtin))
        if not self.validate_gtin_checksum(clean_gtin):
            return GS1VerificationRecord(
                gtin=gtin,
                status=GS1VerificationStatus.INVALID_FORMAT,
                provider="GS1 Barcode Validator",
                is_live=False,
                verification_timestamp=now_ts,
                message=f"Barcode '{gtin}' does not pass standard GS1 Modulo-10 checksum validation (Length: {len(clean_gtin)} digits)."
            )

        # 1. Attempt primary provider (GS1 DataKart API)
        res = await self.primary_provider.verify_gtin(clean_gtin)
        if res.status in (GS1VerificationStatus.VERIFIED, GS1VerificationStatus.NOT_FOUND):
            return res

        # 2. Attempt fallback provider (Local cache)
        if self.fallback_provider and res.status in (GS1VerificationStatus.NOT_VERIFIED, GS1VerificationStatus.SERVICE_UNAVAILABLE):
            cache_res = await self.fallback_provider.verify_gtin(clean_gtin)
            if cache_res.status == GS1VerificationStatus.VERIFIED:
                return cache_res

        # 3. Return local format & checksum verification
        if res.status == GS1VerificationStatus.NOT_VERIFIED:
            gtin_type = f"GTIN-{len(clean_gtin)}"
            return GS1VerificationRecord(
                gtin=clean_gtin,
                status=GS1VerificationStatus.NOT_VERIFIED,
                provider="MetrCheck Local GS1 Checksum Validator",
                is_live=False,
                verification_timestamp=now_ts,
                message=f"Standard {gtin_type} structure and Modulo-10 checksum validated. Live DataKart registry check unconfigured."
            )

        return res

# Global instance
gs1_verifier = GS1BarcodeVerifier()
"""

gs1_init = """from backend.integrations.gs1.schemas import GS1VerificationStatus, GS1VerificationRecord
from backend.integrations.gs1.providers import GS1DataKartApiProvider, LocalGS1CacheProvider, BaseGS1Provider
from backend.integrations.gs1.verifier import GS1BarcodeVerifier, gs1_verifier
"""

files = {
    "backend/integrations/__init__.py": '\"\"\"External Integrations Package for MetrCheck AI.\"\"\"\\n',
    "backend/integrations/fssai/schemas.py": fssai_schemas,
    "backend/integrations/fssai/providers.py": fssai_providers,
    "backend/integrations/fssai/verifier.py": fssai_verifier,
    "backend/integrations/fssai/__init__.py": fssai_init,
    "backend/integrations/gs1/schemas.py": gs1_schemas,
    "backend/integrations/gs1/providers.py": gs1_providers,
    "backend/integrations/gs1/verifier.py": gs1_verifier,
    "backend/integrations/gs1/__init__.py": gs1_init,
}

for path_str, content in files.items():
    p = pathlib.Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\\n", encoding="utf-8")
    print(f"Created {path_str}")

print("Phase 6 Integrations created successfully.")
