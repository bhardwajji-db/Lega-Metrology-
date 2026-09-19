import abc
import asyncio
import logging
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from utils.datetime_utils import get_current_utc_iso
from integrations.fssai.schemas import FSSAIVerificationRecord, FSSAIVerificationStatus

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

class BaseFSSAIProvider(abc.ABC):
    @abc.abstractmethod
    async def verify_licence(self, licence_number: str) -> FSSAIVerificationRecord:
        """Verify a 14-digit FSSAI licence number."""
        pass

class FoSCoSApiProvider(BaseFSSAIProvider):
    """
    Official FoSCoS (Food Safety Compliance System) Registry API Provider.
    Calls official Government of India FSSAI / FoSCoS verification endpoints when configured.
    Handles network timeouts and service downtime gracefully without fabricated records.
    """
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

        if _is_ssrf_blocked(self.api_url):
            return FSSAIVerificationRecord(
                licence_number=licence_number,
                status=FSSAIVerificationStatus.SERVICE_UNAVAILABLE,
                provider="FoSCoS Official Registry API (Live)",
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
    """
    Local verified cache provider for FSSAI licences with explicit provenance.
    Queries in-memory dictionary and persistent SQLite verification_cache table.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def set_cache_record(self, licence_number: str, data: Dict[str, Any]):
        self._cache[licence_number] = data

    async def verify_licence(self, licence_number: str) -> FSSAIVerificationRecord:
        now_ts = get_current_utc_iso()
        
        # 1. Check in-memory cache
        if licence_number in self._cache:
            entry = self._cache[licence_number]
            return FSSAIVerificationRecord(
                licence_number=licence_number,
                status=entry.get("status", FSSAIVerificationStatus.VERIFIED),
                provider=entry.get("provider", "MetrCheck Verified FSSAI Local Cache"),
                business_name=entry.get("business_name"),
                licence_type=entry.get("licence_type"),
                valid_upto=entry.get("valid_upto"),
                is_live=False,
                verification_timestamp=entry.get("cached_at", now_ts),
                message="FSSAI licence matched in local verified cache records.",
                raw_payload=entry
            )
            
        # 2. Check persistent SQLite cache
        try:
            from database.db import get_cached_verification
            db_entry = await get_cached_verification("FSSAI", licence_number)
            if db_entry:
                status_val = db_entry.get("status", FSSAIVerificationStatus.VERIFIED)
                if isinstance(status_val, str):
                    try:
                        status_val = FSSAIVerificationStatus(status_val)
                    except ValueError:
                        status_val = FSSAIVerificationStatus.VERIFIED
                return FSSAIVerificationRecord(
                    licence_number=licence_number,
                    status=status_val,
                    provider=db_entry.get("provider", f"SQLite Persistent Cache ({db_entry.get('_cache_source', 'LOCAL')})"),
                    business_name=db_entry.get("business_name"),
                    licence_type=db_entry.get("licence_type"),
                    valid_upto=db_entry.get("valid_upto"),
                    is_live=False,
                    verification_timestamp=db_entry.get("_cached_at", now_ts),
                    message="FSSAI licence retrieved from persistent offline database cache.",
                    raw_payload=db_entry
                )
        except Exception as e:
            logger.debug(f"SQLite cache lookup skipped: {e}")

        return FSSAIVerificationRecord(
            licence_number=licence_number,
            status=FSSAIVerificationStatus.NOT_FOUND,
            provider="MetrCheck Verified FSSAI Local Cache",
            is_live=False,
            verification_timestamp=now_ts,
            message="Licence not present in local verified cache."
        )
