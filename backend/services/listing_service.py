import re
import socket
import logging
import ipaddress
import uuid
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser
from datetime import datetime, timezone

import httpx
from models.schemas import ProductInfo, ComplianceResult
from models.listing_schemas import (
    ListingFieldComparisonItem,
    ListingCheckRequest,
    ListingCheckResponse
)
from extraction.extractor import LocalExtractor
from compliance.engine import ComplianceEngine
from compliance.scorer import calculate_score
from database.db import get_analysis

logger = logging.getLogger(__name__)

extractor_instance = LocalExtractor()
compliance_engine_instance = ComplianceEngine()

# SSRF Blacklisted IP networks & cloud metadata endpoints
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),          # Loopback IPv4
    ipaddress.ip_network("10.0.0.0/8"),           # RFC 1918 Private
    ipaddress.ip_network("172.16.0.0/12"),        # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),       # RFC 1918 Private
    ipaddress.ip_network("169.254.0.0/16"),       # Link-Local (includes AWS/GCP metadata 169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),            # Current network
    ipaddress.ip_network("224.0.0.0/4"),          # Multicast
    ipaddress.ip_network("240.0.0.0/4"),          # Reserved
    ipaddress.ip_network("::1/128"),              # Loopback IPv6
    ipaddress.ip_network("fc00::/7"),             # Unique local address IPv6
    ipaddress.ip_network("fe80::/10"),            # Link-local IPv6
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.gcp",
    "instance-data",
    "169.254.169.254"
}


class HTMLTextExtractor(HTMLParser):
    """Lightweight and robust HTML stripper that removes scripts, styles, and tags."""
    def __init__(self):
        super().__init__()
        self.text_parts: List[str] = []
        self.skip_depth = 0
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link', 'noscript', 'svg', 'iframe'}

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self.skip_tags:
            self.skip_depth += 1

    def handle_endtag(self, tag: str):
        if tag.lower() in self.skip_tags and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data: str):
        if self.skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self.text_parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self.text_parts)


def validate_ssrf_safety(target_url: str) -> Tuple[bool, Optional[str]]:
    """
    Validates that a URL does not point to internal, private, loopback, or cloud metadata IP addresses.
    Returns (is_safe, error_reason).
    """
    if not target_url or not isinstance(target_url, str):
        return False, "Empty or invalid URL provided."

    parsed = urlparse(target_url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported URL protocol '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "Could not determine valid hostname from URL."

    hostname_clean = hostname.lower().strip(".")
    if hostname_clean in BLOCKED_HOSTNAMES:
        return False, f"Access to restricted hostname '{hostname}' is blocked."

    # DNS Resolution check
    try:
        addr_infos = socket.getaddrinfo(hostname_clean, None)
        if not addr_infos:
            return False, f"Unable to resolve host '{hostname}'."

        for family, socktype, proto, canonname, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)

            for blocked_net in BLOCKED_IP_NETWORKS:
                if ip_obj in blocked_net:
                    return False, f"Access to private/internal IP address ({ip_str}) is prohibited."

            if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
                return False, f"Target IP address ({ip_str}) is within a non-routable or private range."

    except socket.gaierror:
        return False, f"Hostname '{hostname}' could not be resolved by DNS."
    except Exception as e:
        return False, f"DNS security resolution failed: {e}"

    return True, None


async def fetch_listing_url_content(target_url: str) -> str:
    """
    Fetches web content with strict SSRF checks on both initial request and every redirect.
    """
    is_safe, err = validate_ssrf_safety(target_url)
    if not is_safe:
        raise ValueError(f"SSRF Security Violation: {err}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    current_url = target_url
    max_redirects = 3

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            is_safe, err = validate_ssrf_safety(current_url)
            if not is_safe:
                raise ValueError(f"SSRF Security Violation on redirect: {err}")

            response = await client.get(current_url, headers=headers)
            
            if response.is_redirect:
                loc = response.headers.get("Location")
                if not loc:
                    break
                current_url = urljoin(current_url, loc)
                continue

            response.raise_for_status()
            html_content = response.text
            
            # Extract plain text
            parser = HTMLTextExtractor()
            parser.feed(html_content[:1024 * 1024])  # Cap parsing to first 1MB
            extracted_text = parser.get_text()

            if not extracted_text.strip():
                # Fallback: simple tag stripping regex
                extracted_text = re.sub(r'<[^>]+>', ' ', html_content)
                extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()

            return extracted_text

    raise ValueError("Too many redirects encountered while fetching listing URL.")


def build_listing_text_from_structured(data: Dict[str, Any]) -> str:
    """Builds a formatted product listing text from structured form fields."""
    lines: List[str] = []

    p_name = data.get("productName") or data.get("product_name")
    brand = data.get("brand")
    category = data.get("category")
    net_qty_amt = data.get("netQtyAmount") or data.get("net_quantity")
    net_qty_unit = data.get("netQtyUnit", "g")
    mrp = data.get("mrp")
    usp = data.get("unitSalePrice") or data.get("unit_sale_price")
    batch = data.get("batchNumber") or data.get("batch_number")
    mfg_date = data.get("mfgDate") or data.get("mfg_date") or data.get("manufacturing_date")
    exp_date = data.get("expiryDate") or data.get("expiry_date") or data.get("best_before")
    country = data.get("countryOfOrigin") or data.get("country_of_origin", "India")

    if p_name: lines.append(f"Product Name: {p_name}")
    if brand: lines.append(f"Brand: {brand}")
    if category: lines.append(f"Category: {category}")
    if net_qty_amt:
        qty_str = f"{net_qty_amt} {net_qty_unit}".strip() if net_qty_unit and not str(net_qty_amt).endswith(net_qty_unit) else str(net_qty_amt)
        lines.append(f"Net Quantity: {qty_str}")
    if mrp: lines.append(f"Maximum Retail Price (MRP): Rs. {mrp}")
    if usp: lines.append(f"Unit Sale Price: {usp}")
    if batch: lines.append(f"Batch Number: {batch}")
    if mfg_date: lines.append(f"Date of Manufacture: {mfg_date}")
    if exp_date: lines.append(f"Best Before / Expiry: {exp_date}")
    if country: lines.append(f"Country of Origin: {country}")

    mfg_name = data.get("manufacturerName") or data.get("manufacturer")
    mfg_addr = data.get("manufacturerAddress")
    if mfg_name or mfg_addr:
        lines.append("\nManufactured & Packed by:")
        if mfg_name: lines.append(str(mfg_name))
        if mfg_addr: lines.append(str(mfg_addr))

    care_phone = data.get("consumerCarePhone")
    care_email = data.get("consumerCareEmail")
    if care_phone or care_email:
        lines.append("\nConsumer Care Details:")
        if care_phone: lines.append(f"Helpline: {care_phone}")
        if care_email: lines.append(f"Email: {care_email}")

    fssai = data.get("fssaiLicense") or data.get("fssai_license")
    if fssai: lines.append(f"\nFSSAI License No.: {fssai}")

    ingredients = data.get("ingredients")
    if ingredients:
        lines.append(f"\nIngredients:\n{ingredients}")

    return "\n".join(lines)


def _parse_qty_amount(val: Optional[str]) -> Optional[float]:
    if not val:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)', str(val))
    return float(m.group(1)) if m else None


def _parse_mrp_float(val: Optional[str]) -> Optional[float]:
    if not val:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)', str(val))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def compare_package_vs_listing(
    package_info: ProductInfo,
    listing_info: ProductInfo
) -> Tuple[List[ListingFieldComparisonItem], str, int, int, int]:
    """
    Performs field-by-field cross comparison between physical package data and online listing data.
    Returns (comparisons_list, cross_verdict, match_count, mismatch_count, insufficient_count).
    """
    comparisons: List[ListingFieldComparisonItem] = []
    matches = 0
    mismatches = 0
    insufficient = 0

    # 1. Product Name
    pkg_name = (package_info.product_name or "").strip()
    lst_name = (listing_info.product_name or "").strip()
    if pkg_name and lst_name:
        pkg_tokens = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', pkg_name.lower()))
        lst_tokens = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', lst_name.lower()))
        overlap = pkg_tokens.intersection(lst_tokens)
        if overlap:
            comparisons.append(ListingFieldComparisonItem(
                field="product_name",
                field_label="Product Name",
                status="MATCH",
                package_value=pkg_name,
                listing_value=lst_name,
                explanation="Product title aligns with physical packaging.",
                severity="INFO"
            ))
            matches += 1
        else:
            comparisons.append(ListingFieldComparisonItem(
                field="product_name",
                field_label="Product Name",
                status="MISMATCH",
                package_value=pkg_name,
                listing_value=lst_name,
                explanation="Product title on e-commerce listing differs significantly from physical packaging.",
                severity="HIGH"
            ))
            mismatches += 1
    elif pkg_name and not lst_name:
        comparisons.append(ListingFieldComparisonItem(
            field="product_name",
            field_label="Product Name",
            status="INSUFFICIENT_DATA",
            package_value=pkg_name,
            listing_value=None,
            explanation="Product title missing or unparsed from online listing.",
            severity="MEDIUM"
        ))
        insufficient += 1

    # 2. Net Quantity
    pkg_qty = (package_info.net_quantity or "").strip()
    lst_qty = (listing_info.net_quantity or "").strip()
    if pkg_qty and lst_qty:
        amt_p = _parse_qty_amount(pkg_qty)
        amt_l = _parse_qty_amount(lst_qty)
        if amt_p is not None and amt_l is not None and abs(amt_p - amt_l) < 0.01:
            comparisons.append(ListingFieldComparisonItem(
                field="net_quantity",
                field_label="Net Quantity",
                status="MATCH",
                package_value=pkg_qty,
                listing_value=lst_qty,
                explanation="Declared net quantity exactly matches physical packaging.",
                severity="INFO"
            ))
            matches += 1
        else:
            comparisons.append(ListingFieldComparisonItem(
                field="net_quantity",
                field_label="Net Quantity",
                status="MISMATCH",
                package_value=pkg_qty,
                listing_value=lst_qty,
                explanation=f"Net quantity discrepancy: package declares '{pkg_qty}' but online listing states '{lst_qty}'.",
                severity="CRITICAL"
            ))
            mismatches += 1
    elif pkg_qty and not lst_qty:
        comparisons.append(ListingFieldComparisonItem(
            field="net_quantity",
            field_label="Net Quantity",
            status="INSUFFICIENT_DATA",
            package_value=pkg_qty,
            listing_value=None,
            explanation="Statutory net quantity declaration is missing on the e-commerce listing (Rule 6 violation).",
            severity="HIGH"
        ))
        insufficient += 1

    # 3. Maximum Retail Price (MRP)
    pkg_mrp = (package_info.mrp or "").strip()
    lst_mrp = (listing_info.mrp or "").strip()
    if pkg_mrp and lst_mrp:
        val_p = _parse_mrp_float(pkg_mrp)
        val_l = _parse_mrp_float(lst_mrp)
        if val_p is not None and val_l is not None:
            if abs(val_p - val_l) < 0.01:
                comparisons.append(ListingFieldComparisonItem(
                    field="mrp",
                    field_label="Maximum Retail Price (MRP)",
                    status="MATCH",
                    package_value=pkg_mrp,
                    listing_value=lst_mrp,
                    explanation="MRP declaration is identical across physical package and online listing.",
                    severity="INFO"
                ))
                matches += 1
            elif val_l > val_p:
                comparisons.append(ListingFieldComparisonItem(
                    field="mrp",
                    field_label="Maximum Retail Price (MRP)",
                    status="MISMATCH",
                    package_value=pkg_mrp,
                    listing_value=lst_mrp,
                    explanation=f"Online listing displays higher MRP ({lst_mrp}) than physical package ({pkg_mrp}), violating Section 18 / Rule 18.",
                    severity="CRITICAL"
                ))
                mismatches += 1
            else:
                comparisons.append(ListingFieldComparisonItem(
                    field="mrp",
                    field_label="Maximum Retail Price (MRP)",
                    status="MISMATCH",
                    package_value=pkg_mrp,
                    listing_value=lst_mrp,
                    explanation=f"MRP mismatch: Package states '{pkg_mrp}' while listing states '{lst_mrp}'.",
                    severity="HIGH"
                ))
                mismatches += 1
        else:
            comparisons.append(ListingFieldComparisonItem(
                field="mrp",
                field_label="Maximum Retail Price (MRP)",
                status="MATCH" if pkg_mrp.lower() == lst_mrp.lower() else "MISMATCH",
                package_value=pkg_mrp,
                listing_value=lst_mrp,
                explanation="MRP declaration checked.",
                severity="MEDIUM"
            ))
            if pkg_mrp.lower() == lst_mrp.lower(): matches += 1
            else: mismatches += 1
    elif pkg_mrp and not lst_mrp:
        comparisons.append(ListingFieldComparisonItem(
            field="mrp",
            field_label="Maximum Retail Price (MRP)",
            status="INSUFFICIENT_DATA",
            package_value=pkg_mrp,
            listing_value=None,
            explanation="MRP declaration not explicitly specified on the e-commerce listing.",
            severity="HIGH"
        ))
        insufficient += 1

    # 4. Manufacturer
    pkg_mfg = (package_info.manufacturer or "").strip()
    lst_mfg = (listing_info.manufacturer or "").strip()
    if pkg_mfg and lst_mfg:
        p_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', pkg_mfg.lower()))
        l_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', lst_mfg.lower()))
        common = p_tokens.intersection(l_tokens)
        if len(common) >= 1:
            comparisons.append(ListingFieldComparisonItem(
                field="manufacturer",
                field_label="Manufacturer Details",
                status="MATCH",
                package_value=pkg_mfg,
                listing_value=lst_mfg,
                explanation="Manufacturer name/address matches physical package origin.",
                severity="INFO"
            ))
            matches += 1
        else:
            comparisons.append(ListingFieldComparisonItem(
                field="manufacturer",
                field_label="Manufacturer Details",
                status="MISMATCH",
                package_value=pkg_mfg,
                listing_value=lst_mfg,
                explanation="Manufacturer information differs between physical package and online listing.",
                severity="HIGH"
            ))
            mismatches += 1
    elif pkg_mfg and not lst_mfg:
        comparisons.append(ListingFieldComparisonItem(
            field="manufacturer",
            field_label="Manufacturer Details",
            status="INSUFFICIENT_DATA",
            package_value=pkg_mfg,
            listing_value=None,
            explanation="Manufacturer identity is missing from e-commerce listing.",
            severity="MEDIUM"
        ))
        insufficient += 1

    # 5. FSSAI License Number
    pkg_fssai = (package_info.fssai_license or "").strip()
    lst_fssai = (listing_info.fssai_license or "").strip()
    if pkg_fssai and lst_fssai:
        clean_p = re.sub(r'\D', '', pkg_fssai)
        clean_l = re.sub(r'\D', '', lst_fssai)
        if clean_p == clean_l:
            comparisons.append(ListingFieldComparisonItem(
                field="fssai_license",
                field_label="FSSAI License Number",
                status="MATCH",
                package_value=pkg_fssai,
                listing_value=lst_fssai,
                explanation="FSSAI 14-digit license number verified identical.",
                severity="INFO"
            ))
            matches += 1
        else:
            comparisons.append(ListingFieldComparisonItem(
                field="fssai_license",
                field_label="FSSAI License Number",
                status="MISMATCH",
                package_value=pkg_fssai,
                listing_value=lst_fssai,
                explanation=f"FSSAI license discrepancy: package shows '{pkg_fssai}' while listing shows '{lst_fssai}'.",
                severity="CRITICAL"
            ))
            mismatches += 1
    elif pkg_fssai and not lst_fssai:
        comparisons.append(ListingFieldComparisonItem(
            field="fssai_license",
            field_label="FSSAI License Number",
            status="INSUFFICIENT_DATA",
            package_value=pkg_fssai,
            listing_value=None,
            explanation="FSSAI License is present on physical package but omitted from e-commerce listing.",
            severity="HIGH"
        ))
        insufficient += 1

    # 6. Country of Origin
    pkg_country = (package_info.country_of_origin or "").strip()
    lst_country = (listing_info.country_of_origin or "").strip()
    if pkg_country and lst_country:
        if pkg_country.lower() == lst_country.lower():
            comparisons.append(ListingFieldComparisonItem(
                field="country_of_origin",
                field_label="Country of Origin",
                status="MATCH",
                package_value=pkg_country,
                listing_value=lst_country,
                explanation="Country of origin is consistently declared.",
                severity="INFO"
            ))
            matches += 1
        else:
            comparisons.append(ListingFieldComparisonItem(
                field="country_of_origin",
                field_label="Country of Origin",
                status="MISMATCH",
                package_value=pkg_country,
                listing_value=lst_country,
                explanation=f"Country of origin conflict: '{pkg_country}' vs '{lst_country}'.",
                severity="CRITICAL"
            ))
            mismatches += 1
    elif pkg_country and not lst_country:
        comparisons.append(ListingFieldComparisonItem(
            field="country_of_origin",
            field_label="Country of Origin",
            status="INSUFFICIENT_DATA",
            package_value=pkg_country,
            listing_value=None,
            explanation="Mandatory Country of Origin is missing on online listing (Rule 6(10) / Consumer Protection E-Commerce Rules).",
            severity="HIGH"
        ))
        insufficient += 1

    # Overall cross verdict
    if mismatches > 0:
        verdict = "MISMATCH_DETECTED"
    elif insufficient > 0:
        verdict = "INSUFFICIENT_ONLINE_DATA"
    elif matches > 0:
        verdict = "COMPLIANT_MATCH"
    else:
        verdict = "NO_OVERLAPPING_FIELDS"

    return comparisons, verdict, matches, mismatches, insufficient


async def check_listing_compliance(request: ListingCheckRequest) -> ListingCheckResponse:
    """
    Main orchestration service for Listing Check:
    1. Obtains text from URL (with SSRF protection), raw text, or structured form.
    2. Runs information extraction and deterministic statutory compliance.
    3. Optionally cross-compares against a physical package screening.
    """
    check_id = f"lst-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    listing_text = ""

    # Step 1: Ingest listing data based on mode
    if request.mode == "URL":
        if not request.url:
            raise ValueError("URL is required when mode is 'URL'.")
        listing_text = await fetch_listing_url_content(request.url)
    elif request.mode == "STRUCTURED":
        if not request.structured_data:
            raise ValueError("structured_data is required when mode is 'STRUCTURED'.")
        listing_text = build_listing_text_from_structured(request.structured_data)
    else:
        # RAW_TEXT
        listing_text = (request.raw_text or "").strip()
        if not listing_text:
            raise ValueError("raw_text is required when mode is 'RAW_TEXT'.")

    # Step 2: Extract structured declarations
    extracted_info = extractor_instance.extract(listing_text)

    # Step 3: Run compliance engine
    comp_dict = compliance_engine_instance.check(
        product_info=extracted_info,
        ocr_text=listing_text,
        images=[]
    )

    score_data = calculate_score(
        checks=comp_dict.get("checks", []),
        product_info=extracted_info,
        conflicts=comp_dict.get("conflicts", [])
    )
    final_score = float(score_data.get("final_score", comp_dict.get("score", 0.0)))
    comp_status = comp_dict.get("status", "POTENTIAL NON-COMPLIANCE")

    comp_res = ComplianceResult(
        checks=comp_dict.get("checks", []),
        score=final_score,
        status=comp_status,
        total_rules=comp_dict.get("total_rules", 0),
        passed_rules=comp_dict.get("passed_rules", 0),
        failed_rules=comp_dict.get("failed_rules", 0),
        warning_rules=comp_dict.get("warning_rules", 0),
        needs_review_rules=comp_dict.get("needs_review_rules", 0),
        not_applicable_rules=comp_dict.get("not_applicable_rules", 0),
        issues=comp_dict.get("issues", []),
        recommendations=comp_dict.get("recommendations", [])
    )

    # Step 4: Optional cross-comparison against physical package
    comparison_performed = False
    field_comparisons: List[ListingFieldComparisonItem] = []
    match_count = 0
    mismatch_count = 0
    insufficient_count = 0
    cross_verdict = None
    package_product_name = None

    package_info: Optional[ProductInfo] = None
    if request.package_data:
        try:
            package_info = ProductInfo(**request.package_data)
            package_product_name = package_info.product_name
        except Exception:
            pass
    elif request.package_analysis_id:
        ana = await get_analysis(request.package_analysis_id)
        if ana:
            package_product_name = ana.get("product_name")
            ext = ana.get("extracted_data")
            if isinstance(ext, dict):
                package_info = ProductInfo(**ext)
            elif isinstance(ext, str):
                import json
                try:
                    package_info = ProductInfo(**json.loads(ext))
                except Exception:
                    pass

    if package_info:
        comparison_performed = True
        field_comparisons, cross_verdict, match_count, mismatch_count, insufficient_count = compare_package_vs_listing(
            package_info=package_info,
            listing_info=extracted_info
        )

    return ListingCheckResponse(
        id=check_id,
        source_mode=request.mode,
        source_url=request.url if request.mode == "URL" else None,
        listing_text=listing_text[:5000],  # Preview text
        extracted_info=extracted_info,
        compliance_result=comp_res,
        score=final_score,
        status=comp_status,
        comparison_performed=comparison_performed,
        package_analysis_id=request.package_analysis_id,
        package_product_name=package_product_name,
        field_comparisons=field_comparisons,
        match_count=match_count,
        mismatch_count=mismatch_count,
        insufficient_data_count=insufficient_count,
        cross_verdict=cross_verdict,
        created_at=now_iso
    )
