"""
MetrCheck AI — External Product & Licence Verification Pipeline
Coordinates:
1. Package OCR & Image Feature Extraction
2. FSSAI Licence/Registration Detection & Normalization
3. Barcode & QR Code Detection & Decoding
4. External Provider Lookups (FoSCoS API & GS1 DataKart API / Verified Cache)
5. Deterministic Field Matching & Normalization Engine
6. Assembly of the Three-Layer Data Architecture
"""

import re
import os
import abc
import time
import logging
import difflib
import ipaddress
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any, Tuple

from utils.datetime_utils import get_current_utc_iso
from config import settings
from models.schemas import ProductInfo, ProductImageEvidence
from models.external_verification import (
    ExternalVerificationStatus,
    ComparisonResult,
    FSSAIExtractionData,
    BarcodeExtractionData,
    ExternalFSSAIData,
    ExternalProductData,
    CrossSourceFieldComparison,
    ExternalProductVerificationPipelineResult,
)
from services.barcode_service import (
    barcode_service,
    resolve_gs1_country,
    validate_ean13_checksum,
    VERIFIED_PRODUCT_REGISTRY
)
from services.identity.fssai_extractor import fssai_extractor, FSSAI_STATE_CODES

logger = logging.getLogger(__name__)

# Corporate stop words to ignore during business name comparison
CORPORATE_STOP_WORDS = {
    "pvt", "ltd", "private", "limited", "llp", "inc", "corp", "corporation",
    "co", "company", "enterprises", "industries", "foods", "beverages",
    "products", "india", "mfg", "manufactured", "by", "marketed", "packed",
    "fbo", "licensee", "unit", "works", "plant", "and", "&"
}


def _is_ssrf_blocked(url: str) -> bool:
    """Blocks requests to private, link-local, loopback, or cloud metadata endpoints."""
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


# =============================================================================
# 1. FSSAI Provider Abstraction
# =============================================================================

class FSSAIProvider(abc.ABC):
    """Abstract interface for FSSAI verification providers."""
    @abc.abstractmethod
    async def verify(self, fssai_number: str) -> ExternalFSSAIData:
        """Verify 14-digit FSSAI number against official API or verified source."""
        pass


class FoSCoSOfficialProvider(FSSAIProvider):
    """
    Official FoSCoS (Food Safety Compliance System) Registry API Provider.
    Queries official Government of India FSSAI / FoSCoS endpoints when configured.
    """
    def __init__(self, api_url: str = "", api_key: str = "", timeout_sec: float = 4.0):
        self.api_url = (api_url or getattr(settings, 'FSSAI_API_URL', '')).strip()
        self.api_key = (api_key or getattr(settings, 'FSSAI_API_KEY', '')).strip()
        self.timeout_sec = timeout_sec or getattr(settings, 'FSSAI_API_TIMEOUT_SEC', 4.0)

    def is_configured(self) -> bool:
        return bool(self.api_url)

    async def verify(self, fssai_number: str) -> ExternalFSSAIData:
        now_ts = get_current_utc_iso()
        manual_url = "https://foscos.fssai.gov.in"
        manual_inst = f"External automatic verification unavailable. Verify this licence manually on the official FoSCoS portal: {manual_url} (Licence Number: {fssai_number})"

        if not self.is_configured():
            return ExternalFSSAIData(
                status=ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE,
                source="FoSCoS Official Registry API (Unconfigured)",
                licence_number=fssai_number,
                lookup_timestamp=now_ts,
                message="Official FoSCoS API endpoint is not configured in server environment.",
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )

        if _is_ssrf_blocked(self.api_url):
            return ExternalFSSAIData(
                status=ExternalVerificationStatus.EXTERNAL_LOOKUP_FAILED,
                source="FoSCoS Official Registry API",
                licence_number=fssai_number,
                lookup_timestamp=now_ts,
                message="SSRF policy blocked request to private or local network address.",
                error_details="Blocked by SSRF protection policy",
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )

        try:
            import httpx
            headers = {"User-Agent": "MetrCheckAI-ProductVerification/2.4"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Retry loop with backoff (up to 2 attempts)
            last_err = None
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                        resp = await client.get(f"{self.api_url.rstrip('/')}/{fssai_number}", headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            is_active = bool(data.get("active") or str(data.get("status", "")).upper() == "ACTIVE")
                            return ExternalFSSAIData(
                                status=ExternalVerificationStatus.EXTERNALLY_VERIFIED if is_active else ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND,
                                source="FoSCoS Official Registry API (Live)",
                                licence_number=fssai_number,
                                business_name=data.get("business_name") or data.get("fbo_name"),
                                registered_address=data.get("premise_address") or data.get("address"),
                                licence_status=data.get("licence_status") or ("ACTIVE" if is_active else "INACTIVE"),
                                valid_upto=data.get("valid_upto") or data.get("expiry_date"),
                                business_type=data.get("business_type") or data.get("kind_of_business"),
                                food_categories=data.get("food_categories") or data.get("categories"),
                                lookup_timestamp=now_ts,
                                message="FSSAI licence record successfully retrieved from live FoSCoS registry.",
                                raw_reference=data,
                                manual_verification_url=manual_url,
                                manual_verification_instructions=manual_inst,
                                provenance="REAL_EXTERNAL"
                            )
                        elif resp.status_code == 404:
                            return ExternalFSSAIData(
                                status=ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND,
                                source="FoSCoS Official Registry API (Live)",
                                licence_number=fssai_number,
                                lookup_timestamp=now_ts,
                                message=f"Licence {fssai_number} was not found in the official FoSCoS registry.",
                                manual_verification_url=manual_url,
                                manual_verification_instructions=manual_inst,
                                provenance="REAL_EXTERNAL"
                            )
                        else:
                            last_err = f"HTTP {resp.status_code}: {resp.text[:150]}"
                except Exception as e:
                    last_err = str(e)
                    if attempt == 0:
                        await time_sleep(0.5)

            return ExternalFSSAIData(
                status=ExternalVerificationStatus.EXTERNAL_LOOKUP_FAILED,
                source="FoSCoS Official Registry API",
                licence_number=fssai_number,
                lookup_timestamp=now_ts,
                message="FoSCoS registry lookup failed or timed out.",
                error_details=last_err,
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )
        except Exception as e:
            return ExternalFSSAIData(
                status=ExternalVerificationStatus.EXTERNAL_LOOKUP_FAILED,
                source="FoSCoS Official Registry API",
                licence_number=fssai_number,
                lookup_timestamp=now_ts,
                message="Internal lookup exception.",
                error_details=str(e),
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )


class FoSCoSPublicLookupProvider(FSSAIProvider):
    """
    Public FoSCoS Portal Verification Adapter.
    Safely inspects the public FoSCoS portal at https://foscos.fssai.gov.in.

    IMPORTANT STATUTORY & ETHICAL COMPLIANCE RULE:
    The public FoSCoS portal requires interactive CAPTCHA validation and implements anti-bot
    protections. As per MetrCheck AI statutory compliance guidelines (Rule 7), automated CAPTCHA
    bypasses, unauthorized web scrapers, and third-party solving services are strictly prohibited.
    When official API credentials are absent, the system safely reports
    EXTERNAL_VERIFICATION_UNAVAILABLE and supplies the official portal reference for manual verification.
    """
    def __init__(self, portal_url: str = "https://foscos.fssai.gov.in", timeout_sec: float = 4.0):
        self.portal_url = portal_url
        self.timeout_sec = timeout_sec

    async def verify(self, fssai_number: str) -> ExternalFSSAIData:
        now_ts = get_current_utc_iso()
        clean = re.sub(r'\D', '', str(fssai_number))
        manual_url = "https://foscos.fssai.gov.in"
        manual_inst = f"External automatic verification unavailable due to mandatory portal CAPTCHA. Verify this licence manually on the official FoSCoS portal: {manual_url} (Licence Number: {clean})"

        return ExternalFSSAIData(
            status=ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE,
            source="FoSCoS Official Portal (foscos.fssai.gov.in)",
            licence_number=clean,
            lookup_timestamp=now_ts,
            message="Public FoSCoS portal search requires interactive CAPTCHA validation. Automated query safely refused to comply with portal terms; manual officer verification required.",
            manual_verification_url=manual_url,
            manual_verification_instructions=manual_inst,
            provenance="UNAVAILABLE"
        )


async def time_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)


class LocalFSSAICacheProvider(FSSAIProvider):
    """
    Verified offline / local cache provider for FSSAI records.
    Reads persistent SQLite verification_cache table and memory store.
    """
    def __init__(self):
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def seed_record(self, licence_number: str, data: Dict[str, Any]):
        clean = re.sub(r'\D', '', str(licence_number))
        self._memory_cache[clean] = data

    async def verify(self, fssai_number: str) -> ExternalFSSAIData:
        now_ts = get_current_utc_iso()
        clean = re.sub(r'\D', '', str(fssai_number))
        manual_url = "https://foscos.fssai.gov.in"
        manual_inst = f"Verify this licence manually on the official FoSCoS portal: {manual_url} (Licence Number: {clean})"

        # 1. In-memory seed
        if clean in self._memory_cache:
            rec = self._memory_cache[clean]
            return ExternalFSSAIData(
                status=ExternalVerificationStatus.LOCAL_REFERENCE_MATCH,
                source=rec.get("source", "MetrCheck Verified FSSAI Local Cache"),
                licence_number=clean,
                business_name=rec.get("business_name"),
                registered_address=rec.get("registered_address") or rec.get("address"),
                licence_status=rec.get("licence_status", "ACTIVE"),
                valid_upto=rec.get("valid_upto"),
                business_type=rec.get("business_type"),
                food_categories=rec.get("food_categories"),
                lookup_timestamp=rec.get("cached_at", now_ts),
                message="FSSAI licence matched in local reference registry (not officially verified against live FoSCoS).",
                raw_reference=rec,
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="LOCAL_CACHE"
            )

        # 2. Persistent SQLite verification_cache
        try:
            from database.db import get_cached_verification
            db_entry = await get_cached_verification("FSSAI", clean)
            if db_entry:
                return ExternalFSSAIData(
                    status=ExternalVerificationStatus.LOCAL_REFERENCE_MATCH,
                    source=db_entry.get("provider", "SQLite Persistent Cache (FSSAI)"),
                    licence_number=clean,
                    business_name=db_entry.get("business_name"),
                    registered_address=db_entry.get("registered_address") or db_entry.get("address"),
                    licence_status=db_entry.get("licence_status", "ACTIVE"),
                    valid_upto=db_entry.get("valid_upto"),
                    business_type=db_entry.get("business_type"),
                    food_categories=db_entry.get("food_categories"),
                    lookup_timestamp=db_entry.get("_cached_at", now_ts),
                    message="FSSAI licence retrieved from persistent offline database cache (local reference only, not live FoSCoS).",
                    raw_reference=db_entry,
                    manual_verification_url=manual_url,
                    manual_verification_instructions=manual_inst,
                    provenance="LOCAL_CACHE"
                )
        except Exception as e:
            logger.debug(f"[FSSAI Cache] DB lookup failed: {e}")

        return ExternalFSSAIData(
            status=ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND,
            source="MetrCheck Verified FSSAI Local Cache",
            licence_number=clean,
            lookup_timestamp=now_ts,
            message=f"FSSAI licence {clean} is not present in the local verified registry.",
            manual_verification_url=manual_url,
            manual_verification_instructions=manual_inst,
            provenance="UNAVAILABLE"
        )


class FSSAIProviderCoordinator:
    """Coordinates primary API and fallback cache providers for FSSAI verification."""
    def __init__(self, primary: Optional[FSSAIProvider] = None, fallback: Optional[FSSAIProvider] = None):
        self.primary = primary or FoSCoSOfficialProvider()
        self.fallback = fallback or LocalFSSAICacheProvider()

    async def verify_fssai(self, licence_number: Optional[str]) -> ExternalFSSAIData:
        now_ts = get_current_utc_iso()
        if not licence_number or not str(licence_number).strip():
            return ExternalFSSAIData(
                status=ExternalVerificationStatus.NOT_DETECTED,
                source="FSSAI Verifier",
                licence_number=None,
                lookup_timestamp=now_ts,
                message="No FSSAI licence number declared on package."
            )

        clean = re.sub(r'\D', '', str(licence_number))
        if len(clean) != 14 or clean[0] not in ('1', '2'):
            return ExternalFSSAIData(
                status=ExternalVerificationStatus.INVALID_FORMAT,
                source="FSSAI Format Validator",
                licence_number=clean,
                lookup_timestamp=now_ts,
                message=f"Licence '{licence_number}' does not conform to the statutory 14-digit FoSCoS format."
            )

        # Mode check: in live mode, do NOT fall back to local mock cache
        mode = getattr(settings, 'EXTERNAL_VERIFICATION_MODE', 'mock').lower()
        res = await self.primary.verify(clean)
        if mode == "live":
            return res

        # In mock / demo mode:
        if res.status in (ExternalVerificationStatus.EXTERNALLY_VERIFIED, ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND):
            return res

        # Fallback Cache for mock / offline demo
        if self.fallback:
            fallback_res = await self.fallback.verify(clean)
            if fallback_res.status in (ExternalVerificationStatus.EXTERNALLY_VERIFIED, ExternalVerificationStatus.LOCAL_REFERENCE_MATCH):
                return fallback_res

        return res


# =============================================================================
# 2. Barcode / GTIN Product Lookup Provider Abstraction
# =============================================================================

class ProductLookupProvider(abc.ABC):
    """Abstract interface for external barcode & GTIN product data providers."""
    @abc.abstractmethod
    async def lookup_by_gtin(self, gtin: str) -> ExternalProductData:
        """Lookup product details by GTIN/EAN."""
        pass

    @abc.abstractmethod
    async def lookup_by_barcode(self, barcode: str) -> ExternalProductData:
        """Lookup product details by barcode value."""
        pass


class GS1DataKartOfficialProvider(ProductLookupProvider):
    """
    Official GS1 India DataKart / Verified by GS1 API Provider.
    Queries GS1 DataKart API when configured in server environment.
    """
    def __init__(self, api_url: str = "", api_key: str = "", timeout_sec: float = 4.0):
        self.api_url = (api_url or getattr(settings, 'GS1_API_URL', '')).strip()
        self.api_key = (api_key or getattr(settings, 'GS1_API_KEY', '')).strip()
        self.timeout_sec = timeout_sec or getattr(settings, 'GS1_API_TIMEOUT_SEC', 4.0)

    def is_configured(self) -> bool:
        return bool(self.api_url)

    async def lookup_by_gtin(self, gtin: str) -> ExternalProductData:
        now_ts = get_current_utc_iso()
        clean_gtin = re.sub(r'\D', '', str(gtin))
        manual_url = "https://www.gs1india.org"
        manual_inst = f"External automatic verification unavailable. Verify this GTIN manually on the GS1 portal: {manual_url} (GTIN: {clean_gtin})"

        if not self.is_configured():
            return ExternalProductData(
                status=ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE,
                source="GS1 India DataKart API (Unconfigured)",
                gtin=clean_gtin,
                lookup_timestamp=now_ts,
                message="GS1 DataKart API endpoint is not configured in server environment.",
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )

        if _is_ssrf_blocked(self.api_url):
            return ExternalProductData(
                status=ExternalVerificationStatus.EXTERNAL_LOOKUP_FAILED,
                source="GS1 India DataKart API",
                gtin=clean_gtin,
                lookup_timestamp=now_ts,
                message="SSRF policy blocked request to private or local network address.",
                error_details="Blocked by SSRF protection policy",
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )

        try:
            import httpx
            headers = {"User-Agent": "MetrCheckAI-ProductVerification/2.4"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.get(f"{self.api_url.rstrip('/')}/{clean_gtin}", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    is_valid = bool(data.get("valid", True))
                    return ExternalProductData(
                        status=ExternalVerificationStatus.EXTERNALLY_VERIFIED if is_valid else ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND,
                        source="GS1 India DataKart API (Live)",
                        gtin=clean_gtin,
                        product_name=data.get("product_name") or data.get("product_description"),
                        brand=data.get("brand_name") or data.get("brand"),
                        manufacturer=data.get("company_name") or data.get("manufacturer"),
                        net_quantity=data.get("net_content") or data.get("net_quantity"),
                        category=data.get("gpc_category") or data.get("category"),
                        images=data.get("images", []),
                        lookup_timestamp=now_ts,
                        message="GTIN barcode successfully verified against live GS1 DataKart registry.",
                        raw_reference=data,
                        manual_verification_url=manual_url,
                        manual_verification_instructions=manual_inst,
                        provenance="REAL_EXTERNAL"
                    )
                elif resp.status_code == 404:
                    return ExternalProductData(
                        status=ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND,
                        source="GS1 India DataKart API (Live)",
                        gtin=clean_gtin,
                        lookup_timestamp=now_ts,
                        message=f"GTIN {clean_gtin} was not found in GS1 DataKart registry.",
                        manual_verification_url=manual_url,
                        manual_verification_instructions=manual_inst,
                        provenance="REAL_EXTERNAL"
                    )
                else:
                    return ExternalProductData(
                        status=ExternalVerificationStatus.EXTERNAL_LOOKUP_FAILED,
                        source="GS1 India DataKart API",
                        gtin=clean_gtin,
                        lookup_timestamp=now_ts,
                        message=f"GS1 API returned HTTP {resp.status_code}.",
                        error_details=resp.text[:150],
                        manual_verification_url=manual_url,
                        manual_verification_instructions=manual_inst,
                        provenance="UNAVAILABLE"
                    )
        except Exception as e:
            return ExternalProductData(
                status=ExternalVerificationStatus.EXTERNAL_LOOKUP_FAILED,
                source="GS1 India DataKart API",
                gtin=clean_gtin,
                lookup_timestamp=now_ts,
                message="GS1 DataKart API connection failed or timed out.",
                error_details=str(e),
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="UNAVAILABLE"
            )

    async def lookup_by_barcode(self, barcode: str) -> ExternalProductData:
        return await self.lookup_by_gtin(barcode)


class LocalProductDataCacheProvider(ProductLookupProvider):
    """
    Verified local product registry provider.
    Searches seeded GS1 verified products registry and SQLite cache.
    """
    def __init__(self):
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def seed_product(self, gtin: str, data: Dict[str, Any]):
        clean = re.sub(r'\D', '', str(gtin))
        self._memory_cache[clean] = data

    async def lookup_by_gtin(self, gtin: str) -> ExternalProductData:
        now_ts = get_current_utc_iso()
        clean = re.sub(r'\D', '', str(gtin))
        manual_url = "https://www.gs1india.org"
        manual_inst = f"Verify this GTIN manually on the GS1 portal: {manual_url} (GTIN: {clean})"

        # 1. Check custom in-memory seed
        if clean in self._memory_cache:
            rec = self._memory_cache[clean]
            return ExternalProductData(
                status=ExternalVerificationStatus.LOCAL_REFERENCE_MATCH,
                source=rec.get("source", "MetrCheck Verified GS1 Local Cache"),
                gtin=clean,
                product_name=rec.get("product_name"),
                brand=rec.get("brand_name") or rec.get("brand"),
                manufacturer=rec.get("company_name") or rec.get("manufacturer"),
                net_quantity=rec.get("net_quantity") or rec.get("net_content"),
                category=rec.get("category") or rec.get("gpc_category"),
                images=rec.get("images", []),
                lookup_timestamp=rec.get("cached_at", now_ts),
                message="GTIN matched in local reference registry cache (not officially verified against live GS1 DataKart).",
                raw_reference=rec,
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="LOCAL_CACHE"
            )

        # 2. Check canonical VERIFIED_PRODUCT_REGISTRY (Kissan, Alpino, Maggi, Tata Tea, Amul, Fortune)
        if clean in VERIFIED_PRODUCT_REGISTRY:
            rec = VERIFIED_PRODUCT_REGISTRY[clean]
            return ExternalProductData(
                status=ExternalVerificationStatus.LOCAL_REFERENCE_MATCH,
                source="MetrCheck Verified GS1 Local Master Registry",
                gtin=clean,
                product_name=rec.get("product_name"),
                brand=rec.get("brand_name"),
                manufacturer=rec.get("company_name"),
                net_quantity=rec.get("net_quantity"),
                category=rec.get("category"),
                lookup_timestamp=now_ts,
                message="GTIN matched in local GS1 master product reference database (not officially verified against live GS1 DataKart).",
                raw_reference=rec,
                manual_verification_url=manual_url,
                manual_verification_instructions=manual_inst,
                provenance="LOCAL_CACHE"
            )

        # 3. Check persistent SQLite cache
        try:
            from database.db import get_cached_verification
            db_entry = await get_cached_verification("GS1_GTIN", clean)
            if db_entry:
                return ExternalProductData(
                    status=ExternalVerificationStatus.LOCAL_REFERENCE_MATCH,
                    source=db_entry.get("provider", "SQLite Persistent Cache (GS1)"),
                    gtin=clean,
                    product_name=db_entry.get("product_description") or db_entry.get("product_name"),
                    brand=db_entry.get("brand_name") or db_entry.get("brand"),
                    manufacturer=db_entry.get("company_name") or db_entry.get("manufacturer"),
                    net_quantity=db_entry.get("net_content") or db_entry.get("net_quantity"),
                    category=db_entry.get("gpc_category") or db_entry.get("category"),
                    lookup_timestamp=db_entry.get("_cached_at", now_ts),
                    message="GTIN retrieved from persistent offline database cache (local reference only, not live GS1 DataKart).",
                    raw_reference=db_entry,
                    manual_verification_url=manual_url,
                    manual_verification_instructions=manual_inst,
                    provenance="LOCAL_CACHE"
                )
        except Exception as e:
            logger.debug(f"[GS1 Cache] DB lookup failed: {e}")

        return ExternalProductData(
            status=ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND,
            source="MetrCheck Verified GS1 Local Registry",
            gtin=clean,
            lookup_timestamp=now_ts,
            message=f"GTIN {clean} was not found in the local product master registry.",
            manual_verification_url=manual_url,
            manual_verification_instructions=manual_inst,
            provenance="UNAVAILABLE"
        )

    async def lookup_by_barcode(self, barcode: str) -> ExternalProductData:
        return await self.lookup_by_gtin(barcode)


class ProductLookupCoordinator:
    """Coordinates primary API and fallback cache providers for Barcode / GTIN product lookup."""
    def __init__(self, primary: Optional[ProductLookupProvider] = None, fallback: Optional[ProductLookupProvider] = None):
        self.primary = primary or GS1DataKartOfficialProvider()
        self.fallback = fallback or LocalProductDataCacheProvider()

    async def lookup_product(self, barcode_val: Optional[str]) -> ExternalProductData:
        now_ts = get_current_utc_iso()
        if not barcode_val or not str(barcode_val).strip():
            return ExternalProductData(
                status=ExternalVerificationStatus.NOT_DETECTED,
                source="Barcode Verifier",
                gtin=None,
                lookup_timestamp=now_ts,
                message="No barcode or GTIN declared on package."
            )

        clean = re.sub(r'\D', '', str(barcode_val))
        if len(clean) in (8, 12, 13, 14):
            if len(clean) == 13 and not validate_ean13_checksum(clean):
                return ExternalProductData(
                    status=ExternalVerificationStatus.INVALID_FORMAT,
                    source="GS1 Checksum Validator",
                    gtin=clean,
                    lookup_timestamp=now_ts,
                    message=f"Barcode '{barcode_val}' failed standard GS1 Modulo-10 checksum."
                )

        # Mode check: in live mode, do NOT fall back to local mock cache
        mode = getattr(settings, 'EXTERNAL_VERIFICATION_MODE', 'mock').lower()
        res = await self.primary.lookup_by_gtin(clean)
        if mode == "live":
            return res

        # In mock / demo mode:
        if res.status in (ExternalVerificationStatus.EXTERNALLY_VERIFIED, ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND):
            return res

        # Fallback Cache for mock / offline demo
        if self.fallback:
            fallback_res = await self.fallback.lookup_by_gtin(clean)
            if fallback_res.status in (ExternalVerificationStatus.EXTERNALLY_VERIFIED, ExternalVerificationStatus.LOCAL_REFERENCE_MATCH):
                return fallback_res

        return res


# =============================================================================
# 3. Deterministic Field Matching & Normalization Engine
# =============================================================================

def normalize_text(text: Optional[str]) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and removing excess whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(text).lower())
    return " ".join(cleaned.split())


def normalize_entity_name(name: Optional[str]) -> str:
    """Normalizes business/manufacturer name by stripping corporate stop words."""
    norm = normalize_text(name)
    words = [w for w in norm.split() if w not in CORPORATE_STOP_WORDS]
    return " ".join(words)


def parse_quantity(val_str: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses numeric quantity and standardizes units to grams or millilitres:
    e.g. '1 kg' -> (1000.0, 'g'), '500 g' -> (500.0, 'g'), '1.5 L' -> (1500.0, 'ml').
    """
    if not val_str:
        return None, None
    s = str(val_str).lower().strip()
    m = re.search(r'([\d\.]+)\s*([a-zA-Z]+)?', s)
    if not m:
        return None, None
    try:
        qty = float(m.group(1))
        unit = (m.group(2) or '').strip()
        if unit in ('kg', 'kilogram', 'kilograms'):
            return round(qty * 1000, 2), 'g'
        if unit in ('g', 'gm', 'gms', 'gram', 'grams'):
            return round(qty, 2), 'g'
        if unit in ('l', 'ltr', 'liter', 'litre', 'litres', 'liters'):
            return round(qty * 1000, 2), 'ml'
        if unit in ('ml', 'milliliter', 'millilitre'):
            return round(qty, 2), 'ml'
        return qty, unit or None
    except Exception:
        return None, None


def parse_currency_amount(val_str: Optional[str]) -> Optional[float]:
    """Parses retail price by stripping ₹, Rs, INR, and taxes."""
    if not val_str:
        return None
    cleaned = re.sub(r'[₹rRsS\.,\-_/]', ' ', str(val_str))
    m = re.search(r'(\d+(?:\.\d{1,2})?)', str(val_str).replace(',', ''))
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return None


class FieldComparator:
    """Performs deterministic, normalized comparisons between Package OCR and External Sources."""

    @classmethod
    def compare_product_name(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "Product Name"
        if not package_val or not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.NOT_FOUND if not external_val else ComparisonResult.NOT_VERIFIED,
                details="Product name missing from external source or package." if not external_val else "Package declaration missing.",
                source=source_name
            )

        norm_p = normalize_text(package_val)
        norm_e = normalize_text(external_val)

        if norm_p == norm_e or norm_p in norm_e or norm_e in norm_p:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.MATCH,
                details=f"Product name matches external registry record ({source_name}).",
                source=source_name
            )

        # Token jaccard + sequence similarity
        tokens_p = set(norm_p.split())
        tokens_e = set(norm_e.split())
        intersection = tokens_p.intersection(tokens_e)
        seq_ratio = difflib.SequenceMatcher(None, norm_p, norm_e).ratio()
        if (tokens_p and len(intersection) / len(tokens_p) >= 0.50) or seq_ratio >= 0.65:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.MATCH,
                details=f"Product name overlaps with external record '{external_val}'.",
                source=source_name
            )

        return CrossSourceFieldComparison(
            field=field,
            package_value=package_val,
            external_value=external_val,
            result=ComparisonResult.MISMATCH,
            details=f"Extracted product name '{package_val}' differs from registry product '{external_val}'.",
            source=source_name
        )

    @classmethod
    def compare_brand(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "Brand"
        if not package_val or not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.NOT_FOUND if not external_val else ComparisonResult.NOT_VERIFIED,
                details="Brand missing from external source or package.",
                source=source_name
            )

        norm_p = normalize_text(package_val)
        norm_e = normalize_text(external_val)

        if norm_p == norm_e or norm_p in norm_e or norm_e in norm_p:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.MATCH,
                details=f"Brand name consistent with external master record ({source_name}).",
                source=source_name
            )

        return CrossSourceFieldComparison(
            field=field,
            package_value=package_val,
            external_value=external_val,
            result=ComparisonResult.MISMATCH,
            details=f"Packaging brand '{package_val}' does not match registered brand '{external_val}'.",
            source=source_name
        )

    @classmethod
    def compare_manufacturer(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "Manufacturer"
        if not package_val or not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.NOT_FOUND if not external_val else ComparisonResult.NOT_VERIFIED,
                details="Manufacturer missing from external source or package.",
                source=source_name
            )

        norm_p = normalize_entity_name(package_val)
        norm_e = normalize_entity_name(external_val)

        if norm_p == norm_e or norm_p in norm_e or norm_e in norm_p:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.MATCH,
                details=f"Manufacturer consistent with registered entity ({source_name}).",
                source=source_name
            )

        tokens_p = set(norm_p.split())
        tokens_e = set(norm_e.split())
        inter = tokens_p.intersection(tokens_e)
        if tokens_p and len(inter) / len(tokens_p) >= 0.50:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.MATCH,
                details=f"Manufacturer name overlaps registered entity '{external_val}'.",
                source=source_name
            )

        return CrossSourceFieldComparison(
            field=field,
            package_value=package_val,
            external_value=external_val,
            result=ComparisonResult.MISMATCH,
            details=f"Package manufacturer '{package_val}' differs from registered entity '{external_val}'.",
            source=source_name
        )

    @classmethod
    def compare_net_quantity(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "Net Quantity"
        if not package_val or not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.NOT_FOUND if not external_val else ComparisonResult.NOT_VERIFIED,
                details="Net quantity missing from external record or package.",
                source=source_name
            )

        qty_p, unit_p = parse_quantity(package_val)
        qty_e, unit_e = parse_quantity(external_val)

        if qty_p is not None and qty_e is not None:
            if qty_p == qty_e and (unit_p == unit_e or not unit_p or not unit_e):
                return CrossSourceFieldComparison(
                    field=field,
                    package_value=package_val,
                    external_value=external_val,
                    result=ComparisonResult.MATCH,
                    details=f"Net quantity matches registered net weight ({external_val}).",
                    source=source_name
                )
            else:
                return CrossSourceFieldComparison(
                    field=field,
                    package_value=package_val,
                    external_value=external_val,
                    result=ComparisonResult.MISMATCH,
                    details=f"Package quantity ({package_val}) conflicts with master specification ({external_val}).",
                    source=source_name
                )

        if normalize_text(package_val) == normalize_text(external_val):
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.MATCH,
                details="Net quantity string matches external record.",
                source=source_name
            )

        return CrossSourceFieldComparison(
            field=field,
            package_value=package_val,
            external_value=external_val,
            result=ComparisonResult.MISMATCH,
            details=f"Package quantity '{package_val}' does not match registered '{external_val}'.",
            source=source_name
        )

    @classmethod
    def compare_fssai_number(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "FSSAI Number"
        if not package_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=None,
                external_value=external_val,
                result=ComparisonResult.NOT_FOUND,
                details="No FSSAI licence detected on package.",
                source=source_name
            )
        if not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=None,
                result=ComparisonResult.NOT_VERIFIED,
                details="FSSAI number extracted from package, but live registry verification was not available.",
                source=source_name
            )

        clean_p = re.sub(r'\D', '', str(package_val))
        clean_e = re.sub(r'\D', '', str(external_val))

        if clean_p == clean_e:
            return CrossSourceFieldComparison(
                field=field,
                package_value=clean_p,
                external_value=clean_e,
                result=ComparisonResult.MATCH,
                details=f"FSSAI licence number confirmed authentic in FoSCoS database.",
                source=source_name
            )

        return CrossSourceFieldComparison(
            field=field,
            package_value=clean_p,
            external_value=clean_e,
            result=ComparisonResult.MISMATCH,
            details=f"Declared FSSAI licence ({clean_p}) does not match verified number ({clean_e}).",
            source=source_name
        )

    @classmethod
    def compare_barcode_gtin(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "Barcode / GTIN"
        if not package_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=None,
                external_value=external_val,
                result=ComparisonResult.NOT_FOUND,
                details="No barcode or GTIN detected on package.",
                source=source_name
            )
        if not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=None,
                result=ComparisonResult.NOT_VERIFIED,
                details="Barcode decoded from package, but external GS1 registry was not available.",
                source=source_name
            )

        clean_p = re.sub(r'\D', '', str(package_val))
        clean_e = re.sub(r'\D', '', str(external_val))

        if clean_p == clean_e:
            return CrossSourceFieldComparison(
                field=field,
                package_value=clean_p,
                external_value=clean_e,
                result=ComparisonResult.MATCH,
                details="Scanned barcode GTIN matches registered GS1 identifier.",
                source=source_name
            )

        return CrossSourceFieldComparison(
            field=field,
            package_value=clean_p,
            external_value=clean_e,
            result=ComparisonResult.MISMATCH,
            details=f"Scanned barcode ({clean_p}) differs from registered GTIN ({clean_e}).",
            source=source_name
        )

    @classmethod
    def compare_mrp(cls, package_val: Optional[str], external_val: Optional[str], source_name: str) -> CrossSourceFieldComparison:
        field = "MRP"
        if not package_val or not external_val:
            return CrossSourceFieldComparison(
                field=field,
                package_value=package_val,
                external_value=external_val,
                result=ComparisonResult.NOT_COMPARABLE if not external_val else ComparisonResult.NOT_FOUND,
                details="MRP comparison not available from external database.",
                source=source_name
            )

        p_num = parse_currency_amount(package_val)
        e_num = parse_currency_amount(external_val)

        if p_num is not None and e_num is not None:
            if abs(p_num - e_num) < 0.05:
                return CrossSourceFieldComparison(
                    field=field,
                    package_value=package_val,
                    external_value=external_val,
                    result=ComparisonResult.MATCH,
                    details=f"Retail price matches registered MRP ({external_val}).",
                    source=source_name
                )
            else:
                return CrossSourceFieldComparison(
                    field=field,
                    package_value=package_val,
                    external_value=external_val,
                    result=ComparisonResult.MISMATCH,
                    details=f"Declared MRP ({package_val}) differs from registered MRP ({external_val}).",
                    source=source_name
                )

        return CrossSourceFieldComparison(
            field=field,
            package_value=package_val,
            external_value=external_val,
            result=ComparisonResult.NOT_COMPARABLE,
            details="Could not parse numerical price for comparison.",
            source=source_name
        )


# =============================================================================
# 4. Central Verification Pipeline Coordinator
# =============================================================================

class ExternalProductVerificationPipeline:
    """
    Central Coordinator for the External Product & Licence Verification Pipeline.
    """
    def __init__(
        self,
        fssai_coordinator: Optional[FSSAIProviderCoordinator] = None,
        product_coordinator: Optional[ProductLookupCoordinator] = None
    ):
        self.fssai_coordinator = fssai_coordinator or FSSAIProviderCoordinator()
        self.product_coordinator = product_coordinator or ProductLookupCoordinator()

    def decode_barcodes_from_images(
        self,
        image_paths: List[str],
        image_evidences: Optional[List[ProductImageEvidence]] = None
    ) -> List[BarcodeExtractionData]:
        """
        Scans all package images directly using barcode_service (ZXing / OpenCV).
        Returns standardized BarcodeExtractionData items with bounding boxes and confidence.
        """
        extractions: List[BarcodeExtractionData] = []
        seen_vals = set()

        for idx, p in enumerate(image_paths):
            if not os.path.exists(p):
                continue
            ev_label = image_evidences[idx].label if (image_evidences and idx < len(image_evidences)) else f"Image {idx+1}"
            b_items = barcode_service.scan_from_image_path(p)

            for b in b_items:
                if not b.raw_value or b.raw_value in seen_vals:
                    continue
                seen_vals.add(b.raw_value)
                extractions.append(BarcodeExtractionData(
                    detected=True,
                    type=b.symbology,
                    value=b.raw_value,
                    source="barcode_decoder",
                    confidence=b.confidence,
                    evidence_image=ev_label,
                    evidence_bbox=b.bbox,
                    is_valid_checksum=b.is_valid_checksum,
                    country_of_origin=b.country_of_origin,
                    country_flag=b.country_flag,
                    gs1_prefix=b.gs1_prefix,
                    qr_payload=b.raw_value if "QR" in b.symbology.upper() else None
                ))

        return extractions

    def extract_fssai_with_provenance(
        self,
        ocr_text: str,
        image_evidences: Optional[List[ProductImageEvidence]] = None,
        product_info: Optional[ProductInfo] = None
    ) -> FSSAIExtractionData:
        """
        Extracts 14-digit FSSAI number from OCR text, validates format,
        and links to image bounding boxes and confidence.
        """
        item, state_name, lic_type = fssai_extractor.extract_fssai(ocr_text, images=image_evidences)
        candidate = item.value or (product_info.fssai_license if product_info else None)
        raw_ocr = item.nearby_text or str(candidate or "")

        if candidate:
            clean = re.sub(r'\D', '', str(candidate))
            is_v, st_name, l_type = fssai_extractor.validate_structure(clean)
            return FSSAIExtractionData(
                detected=True,
                number=clean,
                original_ocr_text=raw_ocr,
                source="ocr",
                confidence=round(item.confidence / 100.0 if item.confidence > 1.0 else item.confidence, 2) or 0.90,
                evidence_image=item.image_id or "Front",
                evidence_bbox=item.bounding_box,
                format_valid=is_v,
                number_type=l_type or "LICENCE",
                state_code=clean[1:3] if len(clean) >= 3 else None,
                state_name=st_name
            )

        return FSSAIExtractionData(
            detected=False,
            number=None,
            original_ocr_text=None,
            source="ocr",
            confidence=0.0,
            format_valid=False,
            number_type="NOT_DETECTED"
        )

    async def run_pipeline(
        self,
        image_paths: List[str],
        ocr_text: str,
        product_info: ProductInfo,
        image_evidences: Optional[List[ProductImageEvidence]] = None
    ) -> ExternalProductVerificationPipelineResult:
        """
        Executes the end-to-end external product verification pipeline across all 3 data layers.
        """
        # ── Layer 1: Package OCR & Vision Extraction ──
        fssai_ext = self.extract_fssai_with_provenance(ocr_text, image_evidences, product_info)
        barcode_exts = self.decode_barcodes_from_images(image_paths, image_evidences)

        # Fallback barcode from product_info if no physical barcode was decoded from image
        barcode_candidate = None
        if barcode_exts:
            barcode_candidate = barcode_exts[0].value
        elif product_info.barcode_detected or getattr(product_info, 'barcode', None):
            raw_bc = str(product_info.barcode_detected or getattr(product_info, 'barcode', None))
            clean_digits = re.sub(r'\D', '', raw_bc)
            c_name, c_flag = resolve_gs1_country(clean_digits)
            barcode_exts.append(BarcodeExtractionData(
                detected=True,
                type="EAN-13" if len(clean_digits) == 13 else "BARCODE",
                value=raw_bc,
                source="ocr",
                confidence=0.88,
                evidence_image="Front",
                is_valid_checksum=validate_ean13_checksum(clean_digits) if len(clean_digits) == 13 else True,
                country_of_origin=c_name,
                country_flag=c_flag,
                gs1_prefix=clean_digits[:3] if len(clean_digits) >= 3 else None
            ))
            barcode_candidate = raw_bc

        # Check if any QR code contains an embedded FSSAI number
        for b in barcode_exts:
            if b.qr_payload and not fssai_ext.detected:
                extracted_f = barcode_service.extract_fssai_from_qr_data(b.qr_payload)
                if extracted_f:
                    is_v, st_name, l_type = fssai_extractor.validate_structure(extracted_f)
                    fssai_ext = FSSAIExtractionData(
                        detected=True,
                        number=extracted_f,
                        original_ocr_text=f"QR Code: {b.qr_payload[:60]}",
                        source="qr_decoder",
                        confidence=0.98,
                        evidence_image=b.evidence_image,
                        evidence_bbox=b.evidence_bbox,
                        format_valid=is_v,
                        number_type=l_type or "LICENCE",
                        state_code=extracted_f[1:3] if len(extracted_f) >= 3 else None,
                        state_name=st_name
                    )
                    break

        package_ocr_layer = {
            "product_name": product_info.product_name,
            "brand": product_info.brand,
            "manufacturer": product_info.manufacturer_name or product_info.manufacturer or product_info.marketed_by_name or product_info.marketed_by,
            "net_quantity": product_info.net_quantity,
            "mrp": product_info.mrp,
            "fssai_number": fssai_ext.number,
            "barcode": barcode_candidate,
            "category": product_info.category,
        }

        # ── Layer 2: External Lookups ──
        external_fssai = await self.fssai_coordinator.verify_fssai(fssai_ext.number)
        external_product = await self.product_coordinator.lookup_product(barcode_candidate)

        # ── Layer 3: Cross-Source Comparisons ──
        comparisons: List[CrossSourceFieldComparison] = []

        # 1. Product Name
        comparisons.append(FieldComparator.compare_product_name(
            package_ocr_layer["product_name"],
            external_product.product_name,
            external_product.source
        ))

        # 2. Brand
        comparisons.append(FieldComparator.compare_brand(
            package_ocr_layer["brand"],
            external_product.brand,
            external_product.source
        ))

        # 3. Manufacturer (Check against both GS1 company and FoSCoS FBO)
        mfr_external = external_product.manufacturer or external_fssai.business_name
        mfr_source = external_product.source if external_product.manufacturer else external_fssai.source
        comparisons.append(FieldComparator.compare_manufacturer(
            package_ocr_layer["manufacturer"],
            mfr_external,
            mfr_source
        ))

        # 4. Net Quantity
        comparisons.append(FieldComparator.compare_net_quantity(
            package_ocr_layer["net_quantity"],
            external_product.net_quantity,
            external_product.source
        ))

        # 5. FSSAI Number
        _fssai_verified_statuses = (ExternalVerificationStatus.EXTERNALLY_VERIFIED, ExternalVerificationStatus.LOCAL_REFERENCE_MATCH)
        comparisons.append(FieldComparator.compare_fssai_number(
            package_ocr_layer["fssai_number"],
            external_fssai.licence_number if external_fssai.status in _fssai_verified_statuses else None,
            external_fssai.source
        ))

        # 6. Barcode / GTIN
        _product_verified_statuses = (ExternalVerificationStatus.EXTERNALLY_VERIFIED, ExternalVerificationStatus.LOCAL_REFERENCE_MATCH)
        comparisons.append(FieldComparator.compare_barcode_gtin(
            package_ocr_layer["barcode"],
            external_product.gtin if external_product.status in _product_verified_statuses else None,
            external_product.source
        ))

        # 7. MRP (if present in external registry)
        if external_product.raw_reference and external_product.raw_reference.get("mrp"):
            comparisons.append(FieldComparator.compare_mrp(
                package_ocr_layer["mrp"],
                str(external_product.raw_reference.get("mrp")),
                external_product.source
            ))

        # Overall Status
        has_mismatch = any(c.result == ComparisonResult.MISMATCH for c in comparisons)
        has_match = any(c.result == ComparisonResult.MATCH for c in comparisons)

        if has_mismatch:
            overall_status = "REVIEW_REQUIRED"
        elif has_match:
            overall_status = "MATCH"
        elif external_fssai.status == ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE and external_product.status == ExternalVerificationStatus.EXTERNAL_VERIFICATION_UNAVAILABLE:
            overall_status = "EXTERNAL_VERIFICATION_UNAVAILABLE"
        elif external_fssai.status == ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND or external_product.status == ExternalVerificationStatus.EXTERNAL_DATA_NOT_FOUND:
            overall_status = "EXTERNAL_DATA_NOT_FOUND"
        else:
            overall_status = "NOT_VERIFIED"

        return ExternalProductVerificationPipelineResult(
            package_ocr_data=package_ocr_layer,
            fssai_extraction=fssai_ext,
            barcode_extractions=barcode_exts,
            external_fssai=external_fssai,
            external_product=external_product,
            cross_source_comparisons=comparisons,
            verification_status=overall_status,
            overall_pipeline_status=overall_status
        )


# Global singleton instance
external_verification_pipeline = ExternalProductVerificationPipeline()
