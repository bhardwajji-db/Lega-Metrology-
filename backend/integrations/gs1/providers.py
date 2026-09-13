import abc
import asyncio
import logging
from typing import Optional, Dict, Any
from utils.datetime_utils import get_current_utc_iso
from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus

logger = logging.getLogger(__name__)

class BaseGS1Provider(abc.ABC):
    @abc.abstractmethod
    async def verify_gtin(self, gtin: str) -> GS1VerificationRecord:
        """Verify GTIN barcode against registry."""
        pass

class GS1DataKartApiProvider(BaseGS1Provider):
    """
    Official GS1 India DataKart API Provider.
    Queries GS1 DataKart / Verified by GS1 API when configured.
    Handles network timeouts and service downtime gracefully.
    """
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
    """
    Local verified cache provider for GS1 barcodes with explicit provenance.
    """
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
