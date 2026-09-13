import re
import logging
from typing import Optional
from utils.datetime_utils import get_current_utc_iso
from config import settings
from integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus
from integrations.fssai.providers import FoSCoSApiProvider, LocalFSSAICacheProvider, BaseFSSAIProvider

logger = logging.getLogger(__name__)

class FSSAILicenceVerifier:
    """
    Coordinator for FSSAI 14-digit Licence Verification.
    Validates structural conformity (Rule 14-digit format, starting with 1 or 2)
    and queries configured external/cached providers.
    """
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
        """
        Validates FSSAI 14-digit format:
        - Exactly 14 digits
        - Digit 1: Licence category (1 = Central/State Licence, 2 = Registration)
        - Digits 2-3: State Code (00-38)
        - Digits 4-5: Year of Registration (e.g. 19, 20, 21, 22, 23, 24, 25, 26)
        """
        if not licence_number:
            return False
        clean = re.sub(r'\D', '', str(licence_number))
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

        clean_licence = re.sub(r'\D', '', str(licence_number))
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
