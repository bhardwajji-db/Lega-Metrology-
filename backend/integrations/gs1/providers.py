import abc
import asyncio
import logging
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from utils.datetime_utils import get_current_utc_iso
from integrations.gs1.schemas import GS1VerificationRecord, GS1VerificationStatus

logger = logging.getLogger(__name__)

def _is_ssrf_blocked(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname or hostname in ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"):
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            pass
        return False
    except Exception:
        return True

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

        if _is_ssrf_blocked(self.api_url):
            return GS1VerificationRecord(
                gtin=gtin,
                status=GS1VerificationStatus.SERVICE_UNAVAILABLE,
                provider="GS1 India DataKart API (Live)",
                is_live=False,
                verification_timestamp=now_ts,
                message="SSRF Protection Policy blocked request to private or local network address."
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
    Queries in-memory dictionary and persistent SQLite verification_cache table.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def set_cache_record(self, gtin: str, data: Dict[str, Any]):
        self._cache[gtin] = data

    async def verify_gtin(self, gtin: str) -> GS1VerificationRecord:
        now_ts = get_current_utc_iso()

        # 1. Check in-memory cache
        if gtin in self._cache:
            entry = self._cache[gtin]
            return GS1VerificationRecord(
                gtin=gtin,
                status=entry.get("status", GS1VerificationStatus.VERIFIED),
                provider=entry.get("provider", "MetrCheck Verified GS1 Local Cache"),
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

        # 2. Check persistent SQLite cache
        try:
            from database.db import get_cached_verification
            db_entry = await get_cached_verification("GS1_GTIN", gtin)
            if db_entry:
                status_val = db_entry.get("status", GS1VerificationStatus.VERIFIED)
                if isinstance(status_val, str):
                    try:
                        status_val = GS1VerificationStatus(status_val)
                    except ValueError:
                        status_val = GS1VerificationStatus.VERIFIED
                return GS1VerificationRecord(
                    gtin=gtin,
                    status=status_val,
                    provider=db_entry.get("provider", f"SQLite Persistent Cache ({db_entry.get('_cache_source', 'LOCAL')})"),
                    brand_name=db_entry.get("brand_name"),
                    product_description=db_entry.get("product_description"),
                    company_name=db_entry.get("company_name"),
                    gpc_category=db_entry.get("gpc_category"),
                    net_content=db_entry.get("net_content"),
                    country_of_sale=db_entry.get("country_of_sale", "India"),
                    is_live=False,
                    verification_timestamp=db_entry.get("_cached_at", now_ts),
                    message="GTIN barcode retrieved from persistent offline database cache.",
                    raw_payload=db_entry
                )
        except Exception as e:
            logger.debug(f"SQLite cache lookup skipped: {e}")

        return GS1VerificationRecord(
            gtin=gtin,
            status=GS1VerificationStatus.NOT_FOUND,
            provider="MetrCheck Verified GS1 Local Cache",
            is_live=False,
            verification_timestamp=now_ts,
            message="GTIN not present in local verified cache."
        )
