import re
import logging
from typing import Optional
from utils.datetime_utils import get_current_utc_iso
from config import settings
from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus
from integrations.gs1.providers import GS1DataKartApiProvider, LocalGS1CacheProvider, BaseGS1Provider

logger = logging.getLogger(__name__)

class GS1BarcodeVerifier:
    """
    Coordinator for GS1 GTIN / Barcode Verification.
    Validates structural conformity (GTIN-8, GTIN-12, GTIN-13, GTIN-14 Modulo-10 checksum)
    and queries configured external/cached providers.
    """
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
        """
        Calculate GS1 standard Modulo-10 check digit for an N-digit prefix.
        Alternating weights (3, 1) starting from the rightmost digit before check digit.
        """
        rev = digits_str[::-1]
        total = 0
        for idx, char in enumerate(rev):
            weight = 3 if idx % 2 == 0 else 1
            total += int(char) * weight
        remainder = total % 10
        return 0 if remainder == 0 else (10 - remainder)

    @classmethod
    def validate_gtin_checksum(cls, gtin: str) -> bool:
        """
        Validates GTIN-8, GTIN-12, GTIN-13, or GTIN-14 check digit.
        """
        clean = re.sub(r'\D', '', str(gtin))
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

        clean_gtin = re.sub(r'\D', '', str(gtin))
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
