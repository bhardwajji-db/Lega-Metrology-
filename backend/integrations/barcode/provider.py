"""
MetrCheck AI — Barcode & GTIN External Product Lookup Provider System
Implements:
1. BarcodeProductProvider abstraction
2. AuthorizedExternalBarcodeProvider (GS1 DataKart / official legitimate API)
3. LocalRegistryBarcodeProvider (verified offline reference cache)
4. BarcodeProductCoordinator (manages routing, security, fallback, and provenance)
5. Comprehensive dynamic field mapping & unknown attributes preservation
6. SSRF defense, timeout protection, response-size bounds, and credential privacy
"""

import abc
import os
import re
import json
import logging
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List, Tuple
from utils.datetime_utils import get_current_utc_iso
from config import settings
from services.gtin_validator import gtin_validator
from services.barcode_service import VERIFIED_PRODUCT_REGISTRY
from models.barcode_product import (
    ProvenanceType,
    FieldState,
    BarcodeLookupStatus,
    ProvenanceValue,
    ExternalProductMaster,
    ExternalLookupAudit,
    StandardProductFields,
    ProductIdentityFields,
    ManufacturerCompanyFields,
    PackagingFields,
    ClassificationFields,
    AttributeFields,
    MediaFields,
    DatesStatusFields,
    RegulatoryIdentifierFields,
)

logger = logging.getLogger(__name__)

# Maximum response size limit to prevent memory exhaustion / DoS attacks (5 MB)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


def is_ssrf_blocked(url: str) -> bool:
    """
    Validates target URL against SSRF threats.
    Blocks private IPs (RFC 1918), loopback, link-local, broadcast, and cloud metadata IPs.
    """
    if not url:
        return True
    try:
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            return True

        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return True

        # Deny known local/metadata hostnames
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "metadata.google.internal"):
            return True

        # Deny resolved or direct IP if in private/restricted ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return True
        except ValueError:
            # It is a domain name — check if it points to localhost-like names
            if hostname.endswith(".localhost") or hostname.endswith(".local") or hostname.endswith(".internal"):
                return True

        return False
    except Exception:
        return True


def redact_sensitive_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Redacts authentication keys from log/audit headers."""
    sanitized = {}
    for k, v in headers.items():
        if any(secret in k.lower() for secret in ("auth", "key", "token", "secret", "password")):
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = v
    return sanitized


class BarcodeProductProvider(abc.ABC):
    """Abstract interface for legitimate Barcode/GTIN product data providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @abc.abstractmethod
    async def lookup_gtin(self, gtin: str) -> ExternalProductMaster:
        """Fetch product record by GTIN."""
        pass


class AuthorizedExternalBarcodeProvider(BarcodeProductProvider):
    """
    Authorized external product data provider (e.g. GS1 India DataKart / Verified by GS1 API).
    Configured strictly through environment variables:
    BARCODE_LOOKUP_ENABLED, BARCODE_LOOKUP_URL, BARCODE_LOOKUP_API_KEY, BARCODE_LOOKUP_TIMEOUT_SEC.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_sec: Optional[float] = None,
        provider_name: str = "GS1 India DataKart Official API"
    ):
        self._provider_name = provider_name
        self.api_url = (api_url or getattr(settings, 'active_barcode_lookup_url', '')).strip()
        self.api_key = (api_key or getattr(settings, 'active_barcode_lookup_api_key', '')).strip()
        self.timeout_sec = timeout_sec or getattr(settings, 'barcode_lookup_timeout_sec', 10.0)

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def is_configured(self) -> bool:
        return bool(self.api_url)

    async def lookup_gtin(self, gtin: str) -> ExternalProductMaster:
        now_ts = get_current_utc_iso()
        clean_gtin = re.sub(r'\D', '', str(gtin))

        # Check if unconfigured
        if not self.is_configured():
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.EXTERNAL_VERIFICATION_UNAVAILABLE,
                source=f"{self.provider_name} (Unconfigured)",
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_ts,
                message="External barcode lookup provider URL is not configured in server environment.",
                audit=ExternalLookupAudit(
                    provider_name=self.provider_name,
                    request_timestamp=now_ts,
                    gtin_queried=clean_gtin,
                    response_timestamp=now_ts,
                    provenance=ProvenanceType.UNAVAILABLE,
                    success=False,
                    error_message="Provider unconfigured"
                )
            )

        # Check Modulo-10 checksum before querying external provider
        if not gtin_validator.validate_modulo10(clean_gtin):
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.INVALID_GTIN,
                source=self.provider_name,
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_ts,
                message=f"GTIN '{clean_gtin}' failed GS1 Modulo-10 check digit verification. External query aborted.",
                audit=ExternalLookupAudit(
                    provider_name=self.provider_name,
                    request_timestamp=now_ts,
                    gtin_queried=clean_gtin,
                    response_timestamp=now_ts,
                    provenance=ProvenanceType.UNAVAILABLE,
                    success=False,
                    error_message="Invalid GTIN Modulo-10 checksum"
                )
            )

        # SSRF Check
        if is_ssrf_blocked(self.api_url):
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_FAILED,
                source=self.provider_name,
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_ts,
                message="SSRF Protection Policy blocked request to restricted address.",
                audit=ExternalLookupAudit(
                    provider_name=self.provider_name,
                    request_timestamp=now_ts,
                    gtin_queried=clean_gtin,
                    response_timestamp=now_ts,
                    provenance=ProvenanceType.UNAVAILABLE,
                    success=False,
                    error_message="SSRF protection blocked request"
                )
            )

        # Dispatch HTTP request to legitimate provider
        try:
            import httpx
            headers = {
                "User-Agent": "MetrCheckAI-ProductVerification/3.0",
                "Accept": "application/json"
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            endpoint = f"{self.api_url.rstrip('/')}/{clean_gtin}"
            req_ts = get_current_utc_iso()

            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.get(endpoint, headers=headers)
                resp_ts = get_current_utc_iso()

                # Response size safeguard
                if len(resp.content) > MAX_RESPONSE_BYTES:
                    return ExternalProductMaster(
                        gtin=clean_gtin,
                        lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_FAILED,
                        source=self.provider_name,
                        provenance=ProvenanceType.UNAVAILABLE,
                        lookup_timestamp=resp_ts,
                        message="Provider response exceeded safety payload threshold (5MB limit).",
                        audit=ExternalLookupAudit(
                            provider_name=self.provider_name,
                            request_timestamp=req_ts,
                            gtin_queried=clean_gtin,
                            response_timestamp=resp_ts,
                            http_status=resp.status_code,
                            provenance=ProvenanceType.UNAVAILABLE,
                            success=False,
                            error_message="Response payload too large"
                        )
                    )

                if resp.status_code == 200:
                    try:
                        raw_data = resp.json()
                    except Exception as json_err:
                        return ExternalProductMaster(
                            gtin=clean_gtin,
                            lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_FAILED,
                            source=self.provider_name,
                            provenance=ProvenanceType.UNAVAILABLE,
                            lookup_timestamp=resp_ts,
                            message=f"Failed to parse JSON from provider: {json_err}",
                            audit=ExternalLookupAudit(
                                provider_name=self.provider_name,
                                request_timestamp=req_ts,
                                gtin_queried=clean_gtin,
                                response_timestamp=resp_ts,
                                http_status=200,
                                provenance=ProvenanceType.UNAVAILABLE,
                                success=False,
                                error_message="Invalid JSON response"
                            )
                        )

                    # Dynamic mapping of all returned fields
                    master = map_provider_response_to_master(
                        raw_data=raw_data,
                        gtin=clean_gtin,
                        provider_name=self.provider_name,
                        provenance=ProvenanceType.REAL_EXTERNAL,
                        lookup_timestamp=resp_ts
                    )

                    # Audit trail
                    master.audit = ExternalLookupAudit(
                        provider_name=self.provider_name,
                        request_timestamp=req_ts,
                        gtin_queried=clean_gtin,
                        response_timestamp=resp_ts,
                        http_status=200,
                        provider_response_id=str(raw_data.get("id") or raw_data.get("response_id") or ""),
                        normalized_fields={
                            "product_name": master.product_name,
                            "brand": master.brand,
                            "manufacturer": master.manufacturer,
                            "net_quantity": master.net_quantity,
                            "category": master.category
                        },
                        raw_response=raw_data,
                        provenance=ProvenanceType.REAL_EXTERNAL,
                        api_version=str(raw_data.get("version") or raw_data.get("api_version") or "1.0"),
                        success=True
                    )
                    return master

                elif resp.status_code == 404:
                    return ExternalProductMaster(
                        gtin=clean_gtin,
                        lookup_status=BarcodeLookupStatus.PRODUCT_NOT_FOUND,
                        source=self.provider_name,
                        provenance=ProvenanceType.REAL_EXTERNAL,
                        lookup_timestamp=resp_ts,
                        message=f"GTIN {clean_gtin} was not found in {self.provider_name}.",
                        audit=ExternalLookupAudit(
                            provider_name=self.provider_name,
                            request_timestamp=req_ts,
                            gtin_queried=clean_gtin,
                            response_timestamp=resp_ts,
                            http_status=404,
                            provenance=ProvenanceType.REAL_EXTERNAL,
                            success=False,
                            error_message="Product not found (HTTP 404)"
                        )
                    )

                elif resp.status_code in (401, 403):
                    return ExternalProductMaster(
                        gtin=clean_gtin,
                        lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_FAILED,
                        source=self.provider_name,
                        provenance=ProvenanceType.UNAVAILABLE,
                        lookup_timestamp=resp_ts,
                        message="Provider API authentication failed. Verify configured API credentials.",
                        audit=ExternalLookupAudit(
                            provider_name=self.provider_name,
                            request_timestamp=req_ts,
                            gtin_queried=clean_gtin,
                            response_timestamp=resp_ts,
                            http_status=resp.status_code,
                            provenance=ProvenanceType.UNAVAILABLE,
                            success=False,
                            error_message=f"Authentication failure (HTTP {resp.status_code})"
                        )
                    )

                else:
                    return ExternalProductMaster(
                        gtin=clean_gtin,
                        lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_UNAVAILABLE,
                        source=self.provider_name,
                        provenance=ProvenanceType.UNAVAILABLE,
                        lookup_timestamp=resp_ts,
                        message=f"Provider returned HTTP {resp.status_code}.",
                        audit=ExternalLookupAudit(
                            provider_name=self.provider_name,
                            request_timestamp=req_ts,
                            gtin_queried=clean_gtin,
                            response_timestamp=resp_ts,
                            http_status=resp.status_code,
                            provenance=ProvenanceType.UNAVAILABLE,
                            success=False,
                            error_message=f"Provider error HTTP {resp.status_code}"
                        )
                    )

        except httpx.TimeoutException as te:
            now_err = get_current_utc_iso()
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_UNAVAILABLE,
                source=self.provider_name,
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_err,
                message=f"Connection to external provider timed out after {self.timeout_sec}s.",
                audit=ExternalLookupAudit(
                    provider_name=self.provider_name,
                    request_timestamp=now_ts,
                    gtin_queried=clean_gtin,
                    response_timestamp=now_err,
                    provenance=ProvenanceType.UNAVAILABLE,
                    success=False,
                    error_message=f"Timeout: {te}"
                )
            )
        except Exception as e:
            now_err = get_current_utc_iso()
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.EXTERNAL_LOOKUP_UNAVAILABLE,
                source=self.provider_name,
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_err,
                message=f"External provider communication failed: {e}",
                audit=ExternalLookupAudit(
                    provider_name=self.provider_name,
                    request_timestamp=now_ts,
                    gtin_queried=clean_gtin,
                    response_timestamp=now_err,
                    provenance=ProvenanceType.UNAVAILABLE,
                    success=False,
                    error_message=str(e)
                )
            )


class LocalRegistryBarcodeProvider(BarcodeProductProvider):
    """
    Local Verified Reference Registry Provider (seeded verified cache & SQLite cache).
    CRITICAL STATUTORY AUDIT RULE:
    This provider MUST NEVER assign provenance=REAL_EXTERNAL or status=EXTERNALLY_VERIFIED!
    It explicitly labels records as LOCAL_CACHE / LOCAL_REFERENCE_MATCH.
    """

    def __init__(self, provider_name: str = "MetrCheck Verified Local Registry"):
        self._provider_name = provider_name
        self._custom_seed: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def seed_product(self, gtin: str, data: Dict[str, Any]):
        clean = re.sub(r'\D', '', str(gtin))
        self._custom_seed[clean] = data

    async def lookup_gtin(self, gtin: str) -> ExternalProductMaster:
        now_ts = get_current_utc_iso()
        clean_gtin = re.sub(r'\D', '', str(gtin))

        # Check Modulo-10 checksum
        if not gtin_validator.validate_modulo10(clean_gtin):
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.INVALID_GTIN,
                source=self.provider_name,
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_ts,
                message=f"GTIN '{clean_gtin}' failed GS1 Modulo-10 check digit verification."
            )

        # 1. Custom in-memory seed
        if clean_gtin in self._custom_seed:
            raw_rec = self._custom_seed[clean_gtin]
            master = map_provider_response_to_master(
                raw_data=raw_rec,
                gtin=clean_gtin,
                provider_name=self.provider_name,
                provenance=ProvenanceType.LOCAL_CACHE,
                lookup_timestamp=now_ts
            )
            master.lookup_status = BarcodeLookupStatus.LOCAL_REFERENCE_MATCH
            master.message = "GTIN matched in local reference registry (not live external verification)."
            master.audit = ExternalLookupAudit(
                provider_name=self.provider_name,
                request_timestamp=now_ts,
                gtin_queried=clean_gtin,
                response_timestamp=now_ts,
                provenance=ProvenanceType.LOCAL_CACHE,
                success=True
            )
            return master

        # 2. Canonical VERIFIED_PRODUCT_REGISTRY
        if clean_gtin in VERIFIED_PRODUCT_REGISTRY:
            raw_rec = VERIFIED_PRODUCT_REGISTRY[clean_gtin]
            master = map_provider_response_to_master(
                raw_data=raw_rec,
                gtin=clean_gtin,
                provider_name=self.provider_name,
                provenance=ProvenanceType.LOCAL_CACHE,
                lookup_timestamp=now_ts
            )
            master.lookup_status = BarcodeLookupStatus.LOCAL_REFERENCE_MATCH
            master.message = "GTIN matched in local master product registry (not live external verification)."
            master.audit = ExternalLookupAudit(
                provider_name=self.provider_name,
                request_timestamp=now_ts,
                gtin_queried=clean_gtin,
                response_timestamp=now_ts,
                provenance=ProvenanceType.LOCAL_CACHE,
                success=True
            )
            return master

        # 3. SQLite persistent verification_cache
        try:
            from database.db import get_cached_verification
            db_entry = await get_cached_verification("GS1_GTIN", clean_gtin)
            if db_entry:
                master = map_provider_response_to_master(
                    raw_data=db_entry,
                    gtin=clean_gtin,
                    provider_name="SQLite Persistent Cache",
                    provenance=ProvenanceType.LOCAL_CACHE,
                    lookup_timestamp=now_ts
                )
                master.lookup_status = BarcodeLookupStatus.LOCAL_REFERENCE_MATCH
                master.message = "GTIN retrieved from persistent offline SQLite database cache."
                master.audit = ExternalLookupAudit(
                    provider_name="SQLite Persistent Cache",
                    request_timestamp=now_ts,
                    gtin_queried=clean_gtin,
                    response_timestamp=now_ts,
                    provenance=ProvenanceType.LOCAL_CACHE,
                    success=True
                )
                return master
        except Exception as e:
            logger.debug(f"[Local Registry] SQLite cache check failed: {e}")

        # Not found in local registry
        return ExternalProductMaster(
            gtin=clean_gtin,
            lookup_status=BarcodeLookupStatus.PRODUCT_NOT_FOUND,
            source=self.provider_name,
            provenance=ProvenanceType.LOCAL_CACHE,
            lookup_timestamp=now_ts,
            message=f"GTIN {clean_gtin} was not found in local verified registry.",
            audit=ExternalLookupAudit(
                provider_name=self.provider_name,
                request_timestamp=now_ts,
                gtin_queried=clean_gtin,
                response_timestamp=now_ts,
                provenance=ProvenanceType.LOCAL_CACHE,
                success=False,
                error_message="Not found in local cache"
            )
        )


# =============================================================================
# Field Mapping & Dynamic Unknown Field Preservation
# =============================================================================

def _extract_field(
    raw: Dict[str, Any],
    candidate_keys: List[str],
    source: str,
    provenance: ProvenanceType
) -> Tuple[ProvenanceValue, Optional[str]]:
    """
    Extracts value matching candidate keys, returning (ProvenanceValue, matched_key).
    """
    for key in candidate_keys:
        if key in raw and raw[key] is not None:
            val = raw[key]
            # Normalize strings
            str_val = str(val).strip() if isinstance(val, (str, int, float)) else val
            if str_val != "":
                return ProvenanceValue(
                    value=str_val,
                    source=source,
                    provenance=provenance,
                    state=FieldState.AVAILABLE,
                    raw_key=key
                ), key
    return ProvenanceValue(
        value=None,
        source=source,
        provenance=provenance,
        state=FieldState.NOT_PROVIDED,
        raw_key=None
    ), None


def map_provider_response_to_master(
    raw_data: Dict[str, Any],
    gtin: str,
    provider_name: str,
    provenance: ProvenanceType,
    lookup_timestamp: str
) -> ExternalProductMaster:
    """
    Dynamically maps any incoming provider JSON response into standard categories,
    while capturing ALL additional or unmapped fields in `provider_attributes`.
    """
    consumed_keys = set()
    std = StandardProductFields()

    # 1. Product Identity
    identity_map = [
        ("product_name", ["product_name", "product_description", "description", "title", "name"]),
        ("product_description", ["product_description", "description", "details", "long_description"]),
        ("brand_name", ["brand_name", "brand", "brandName"]),
        ("sub_brand", ["sub_brand", "subBrand", "sub_brand_name"]),
        ("product_category", ["product_category", "category", "category_name", "gpc_category"]),
        ("product_type", ["product_type", "type"]),
        ("product_family", ["product_family", "family"]),
        ("product_variant", ["product_variant", "variant", "flavor", "flavour"]),
        ("model_number", ["model_number", "model", "model_no"]),
        ("sku", ["sku", "sku_code", "item_code"]),
        ("gtin", ["gtin", "gtin_code", "ean", "upc", "barcode"]),
        ("upc", ["upc", "upc_a", "upca"]),
        ("ean", ["ean", "ean13", "ean_13"]),
    ]
    for field_name, candidates in identity_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.identity, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 2. Manufacturer / Company
    mfr_map = [
        ("manufacturer_name", ["manufacturer_name", "manufacturer", "company_name", "company", "mfg_by"]),
        ("manufacturer_legal_name", ["manufacturer_legal_name", "legal_name", "fbo_name"]),
        ("manufacturer_address", ["manufacturer_address", "address", "company_address", "premise_address"]),
        ("manufacturer_country", ["manufacturer_country", "country_of_origin", "country", "origin"]),
        ("brand_owner", ["brand_owner", "brandOwner", "owner"]),
        ("brand_owner_address", ["brand_owner_address", "brandOwnerAddress"]),
        ("packer", ["packer", "packed_by", "packer_name"]),
        ("importer", ["importer", "imported_by", "importer_name"]),
        ("distributor", ["distributor", "marketed_by", "distributor_name"]),
        ("company_identifiers", ["company_identifiers", "cin", "gstin", "pan", "company_id"]),
        ("company_contact", ["company_contact", "contact", "email", "phone", "website"]),
    ]
    for field_name, candidates in mfr_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.manufacturer, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 3. Packaging
    packaging_map = [
        ("package_type", ["package_type", "packaging_type", "pack_type"]),
        ("package_size", ["package_size", "pack_size", "size"]),
        ("net_quantity", ["net_quantity", "net_content", "net_weight", "net_volume", "quantity"]),
        ("quantity_value", ["quantity_value", "net_weight_value", "content_value"]),
        ("quantity_unit", ["quantity_unit", "net_weight_unit", "unit"]),
        ("pack_count", ["pack_count", "pack_size_count", "count", "number_of_units"]),
        ("number_of_units", ["number_of_units", "unit_count", "units"]),
        ("variant_flavour", ["variant_flavour", "flavor", "flavour", "variant"]),
        ("size_weight_volume", ["size_weight_volume", "gross_weight", "total_volume"]),
        ("packaging_dimensions", ["packaging_dimensions", "dimensions", "height_width_depth"]),
    ]
    for field_name, candidates in packaging_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.packaging, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 4. Classification
    class_map = [
        ("category", ["category", "gpc_category", "segment", "class"]),
        ("subcategory", ["subcategory", "sub_category", "subCategory"]),
        ("product_group", ["product_group", "group"]),
        ("industry_codes", ["industry_codes", "hs_code", "hsn_code"]),
        ("unspsc", ["unspsc", "unspsc_code"]),
        ("gpc_code", ["gpc_code", "gpc", "brick_code"]),
    ]
    for field_name, candidates in class_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.classification, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 5. Attributes
    attr_map = [
        ("material", ["material", "materials"]),
        ("colour", ["colour", "color"]),
        ("size", ["size", "item_size"]),
        ("flavour", ["flavour", "flavor"]),
        ("ingredients", ["ingredients", "ingredient_list", "contents"]),
        ("product_features", ["product_features", "features", "highlights"]),
        ("technical_specifications", ["technical_specifications", "specifications", "specs"]),
        ("consumer_attributes", ["consumer_attributes", "consumer_info"]),
    ]
    for field_name, candidates in attr_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.attributes, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 6. Media / Images
    media_map = [
        ("product_image_url", ["product_image_url", "image_url", "image", "main_image"]),
        ("additional_images", ["additional_images", "images", "gallery"]),
        ("front_image", ["front_image", "front_image_url"]),
        ("back_image", ["back_image", "back_image_url"]),
        ("package_image", ["package_image", "packaging_image"]),
        ("thumbnail", ["thumbnail", "thumbnail_url", "thumb"]),
    ]
    for field_name, candidates in media_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.media, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 7. Dates / Status
    dates_map = [
        ("creation_date", ["creation_date", "created_at", "date_created"]),
        ("update_date", ["update_date", "updated_at", "last_updated"]),
        ("launch_date", ["launch_date", "release_date"]),
        ("product_status", ["product_status", "status"]),
        ("active_status", ["active_status", "is_active", "active"]),
    ]
    for field_name, candidates in dates_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.dates, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # 8. Regulatory / Identifiers
    reg_map = [
        ("gtin", ["gtin", "gtin_code"]),
        ("gln", ["gln", "global_location_number"]),
        ("gpc_code", ["gpc_code", "gpc"]),
        ("gs1_company_info", ["gs1_company_info", "gs1_prefix_licensee"]),
        ("other_identifiers", ["other_identifiers", "barcodes"]),
    ]
    for field_name, candidates in reg_map:
        prov_val, matched_key = _extract_field(raw_data, candidates, provider_name, provenance)
        setattr(std.regulatory, field_name, prov_val)
        if matched_key:
            consumed_keys.add(matched_key)

    # Ensure GTIN itself is recorded if not present in raw
    if not std.identity.gtin.value:
        std.identity.gtin = ProvenanceValue(
            value=gtin,
            source=provider_name,
            provenance=provenance,
            state=FieldState.AVAILABLE,
            raw_key="gtin"
        )

    # 9. Separate FSSAI from barcode provider if legitimately supplied
    fssai_val, fssai_key = _extract_field(raw_data, ["fssai_license", "fssai", "fssai_number"], provider_name, provenance)
    if fssai_key:
        consumed_keys.add(fssai_key)

    # 10. Preserve ANY unknown / extra fields dynamically in provider_attributes
    provider_attributes: Dict[str, ProvenanceValue] = {}
    for key, val in raw_data.items():
        if key not in consumed_keys:
            str_val = str(val).strip() if isinstance(val, (str, int, float, bool)) else val
            provider_attributes[key] = ProvenanceValue(
                value=str_val,
                source=provider_name,
                provenance=provenance,
                state=FieldState.AVAILABLE if str_val is not None else FieldState.NOT_PROVIDED,
                raw_key=key
            )

    # Determine completeness status
    core_values = [
        std.identity.product_name.value,
        std.identity.brand_name.value,
        std.manufacturer.manufacturer_name.value,
        std.packaging.net_quantity.value,
    ]
    filled_count = sum(1 for v in core_values if v is not None)
    if provenance == ProvenanceType.REAL_EXTERNAL:
        if filled_count >= 3:
            st = BarcodeLookupStatus.EXTERNALLY_VERIFIED
        elif filled_count > 0 or provider_attributes:
            st = BarcodeLookupStatus.PARTIAL_PRODUCT_RECORD
        else:
            st = BarcodeLookupStatus.EXTERNALLY_VERIFIED
    else:
        st = BarcodeLookupStatus.LOCAL_REFERENCE_MATCH

    msg = f"Product master successfully retrieved from {provider_name}."

    return ExternalProductMaster(
        gtin=gtin,
        lookup_status=st,
        source=provider_name,
        provenance=provenance,
        lookup_timestamp=lookup_timestamp,
        message=msg,
        standard_fields=std,
        provider_attributes=provider_attributes,
        raw_response=raw_data,
        fssai_from_provider=fssai_val if fssai_val.value else None
    )


# =============================================================================
# Barcode Product Coordinator
# =============================================================================

class BarcodeProductCoordinator:
    """
    Coordinates primary live external provider and fallback local cache provider.
    Enforces mode boundaries (live vs mock) and validates check digits.
    """

    def __init__(
        self,
        external_provider: Optional[BarcodeProductProvider] = None,
        local_provider: Optional[BarcodeProductProvider] = None
    ):
        self.external_provider = external_provider or AuthorizedExternalBarcodeProvider()
        self.local_provider = local_provider or LocalRegistryBarcodeProvider()

    async def lookup_product(self, barcode_value: Optional[str]) -> ExternalProductMaster:
        now_ts = get_current_utc_iso()

        if not barcode_value or not str(barcode_value).strip():
            return ExternalProductMaster(
                gtin="",
                lookup_status=BarcodeLookupStatus.NOT_DETECTED,
                source="Barcode Processor",
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_ts,
                message="No barcode or GTIN value provided."
            )

        clean_gtin = re.sub(r'\D', '', str(barcode_value))

        # 1. Modulo-10 check digit verification
        if len(clean_gtin) in (8, 12, 13, 14):
            if not gtin_validator.validate_modulo10(clean_gtin):
                return ExternalProductMaster(
                    gtin=clean_gtin,
                    lookup_status=BarcodeLookupStatus.INVALID_GTIN,
                    source="GS1 Checksum Validator",
                    provenance=ProvenanceType.UNAVAILABLE,
                    lookup_timestamp=now_ts,
                    message=f"Barcode '{barcode_value}' failed GS1 Modulo-10 checksum validation. External query not sent."
                )

        # 2. Check if external provider is enabled and configured
        mode = getattr(settings, 'EXTERNAL_VERIFICATION_MODE', 'mock').lower()
        is_ext_enabled = getattr(settings, 'is_barcode_lookup_enabled', False)
        is_ext_configured = bool(getattr(settings, 'active_barcode_lookup_url', ''))

        # If external provider is configured and enabled, call it
        if is_ext_enabled and is_ext_configured:
            res = await self.external_provider.lookup_gtin(clean_gtin)
            # In live mode, always return external result
            if mode == "live" or res.lookup_status in (
                BarcodeLookupStatus.EXTERNALLY_VERIFIED,
                BarcodeLookupStatus.PARTIAL_PRODUCT_RECORD,
                BarcodeLookupStatus.PRODUCT_NOT_FOUND,
                BarcodeLookupStatus.INVALID_GTIN
            ):
                return res

        # If live mode and external lookup is unconfigured or failed:
        if mode == "live":
            return ExternalProductMaster(
                gtin=clean_gtin,
                lookup_status=BarcodeLookupStatus.EXTERNAL_VERIFICATION_UNAVAILABLE,
                source="Authorized External Provider (Unconfigured)",
                provenance=ProvenanceType.UNAVAILABLE,
                lookup_timestamp=now_ts,
                message="Live external verification required by environment mode, but external provider is unconfigured or unreachable."
            )

        # In mock / demo mode: fall back to local registry
        fallback_res = await self.local_provider.lookup_gtin(clean_gtin)
        return fallback_res


barcode_coordinator = BarcodeProductCoordinator()
