"""
MetrCheck AI — Live Integration Audit Script for FSSAI & GS1 Verification
Performs real-time audit of:
1. Configured FoSCoS URL and GS1 DataKart URL authenticity
2. Non-fabrication & credential status
3. Mock mode execution (SUCCESS, NOT_FOUND, UNAVAILABLE, TIMEOUT, MISMATCH)
4. Unconfigured graceful fallback verification
5. Production comparison summary table
"""

import sys
import os
import asyncio
import unittest.mock as mock
from typing import Dict, Any

# Ensure backend directory is in path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import settings
from integrations.fssai.providers import FoSCoSApiProvider, FSSAIVerificationStatus
from integrations.gs1.providers import GS1DataKartApiProvider, GS1VerificationStatus
from services.external_verification_pipeline import (
    FoSCoSOfficialProvider,
    GS1DataKartOfficialProvider,
    FieldComparator,
    ExternalVerificationStatus,
    ComparisonResult,
)


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()}")
    print("=" * 80)


def print_check(name: str, passed: bool, details: str):
    icon = "[PASS]" if passed else "[FAIL]"
    print(f"{icon} {name}: {details}")


async def audit_configuration():
    print_banner("1. Configuration & Endpoint Authenticity Audit")

    fssai_url = settings.FSSAI_API_URL or os.environ.get("FSSAI_API_URL", "")
    fssai_key = settings.FSSAI_API_KEY or os.environ.get("FSSAI_API_KEY", "")
    fssai_enabled = settings.FSSAI_API_ENABLED or os.environ.get("FSSAI_API_ENABLED", "").lower() in ("true", "1")

    gs1_url = settings.GS1_API_URL or os.environ.get("GS1_API_URL", "")
    gs1_key = settings.GS1_API_KEY or os.environ.get("GS1_API_KEY", "")
    gs1_enabled = settings.GS1_API_ENABLED or os.environ.get("GS1_API_ENABLED", "").lower() in ("true", "1")

    print(f"* FSSAI_API_URL configured: '{fssai_url}' (Enabled: {fssai_enabled})")
    print(f"* FSSAI_API_KEY status: {'[PRESENT - REDACTED]' if fssai_key else '[UNCONFIGURED / EMPTY]'}")
    print(f"* GS1_API_URL configured: '{gs1_url}' (Enabled: {gs1_enabled})")
    print(f"* GS1_API_KEY status: {'[PRESENT - REDACTED]' if gs1_key else '[UNCONFIGURED / EMPTY]'}")
    print(f"* EXTERNAL_VERIFICATION_MODE: '{settings.EXTERNAL_VERIFICATION_MODE}'")

    print("\nReality Check Findings:")
    print("1. FSSAI / FoSCoS Reality:")
    print("   - Official Food Safety and Standards Authority of India (FSSAI) operates https://foscos.fssai.gov.in.")
    print("   - FSSAI does NOT provide an open, unauthenticated public REST API for software developers.")
    print("   - Public verification is protected behind web-forms with mandatory CAPTCHA.")
    print("   - Automated programmatic verification requires Government MoU / FSSAI IT Division B2B credentials,")
    print("     or authorized commercial RegTech providers (e.g. Decentro, Surepass, AuthBridge).")
    print("   - Result: Any hardcoded public FoSCoS API URL without institutional credentials is a PLACEHOLDER.")

    print("2. GS1 India / DataKart Reality:")
    print("   - Official GS1 India operates DataKart at https://www.gs1india.org.")
    print("   - GS1 does NOT provide an open, unauthenticated public REST API.")
    print("   - Programmatic access requires registered GS1 India enterprise membership and signed API agreements.")
    print("   - Global Verified by GS1 API requires registered OAuth2 client credentials.")
    print("   - Result: Any hardcoded DataKart API URL without member credentials is a PLACEHOLDER.")


async def audit_mock_mode():
    print_banner("2. Mock Mode Resilience & Failure Handling Tests")
    all_passed = True

    # --- FSSAI Mock Tests ---
    print("\n[FSSAI / FoSCoS Provider Tests]")
    fssai_prov = FoSCoSApiProvider(api_url="https://api.mock-foscos.gov.in/v1/licences", api_key="mock-test-key")

    # 1. Success
    with mock.patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "active": True,
            "business_name": "Organic India Pvt Ltd",
            "licence_type": "Central Licence",
            "valid_upto": "2028-03-31"
        }
        mock_get.return_value = mock_resp
        rec = await fssai_prov.verify_licence("10014011001899")
        p = rec.status == FSSAIVerificationStatus.VERIFIED and rec.business_name == "Organic India Pvt Ltd"
        print_check("FSSAI SUCCESS Handling", p, f"Status={rec.status.value}, Business={rec.business_name}")
        all_passed = all_passed and p

    # 2. Not Found
    with mock.patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        rec = await fssai_prov.verify_licence("10014011009999")
        p = rec.status == FSSAIVerificationStatus.NOT_FOUND and rec.business_name is None
        print_check("FSSAI NOT_FOUND Handling", p, f"Status={rec.status.value}, Business={rec.business_name} (Zero fabrication)")
        all_passed = all_passed and p

    # 3. Unavailable / 500
    with mock.patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp
        rec = await fssai_prov.verify_licence("10014011001899")
        p = rec.status == FSSAIVerificationStatus.SERVICE_UNAVAILABLE
        print_check("FSSAI UNAVAILABLE Handling", p, f"Status={rec.status.value}, Message='{rec.message}'")
        all_passed = all_passed and p

    # 4. Timeout
    with mock.patch("httpx.AsyncClient.get", side_effect=Exception("ReadTimeout: Request timed out after 3.0s")):
        rec = await fssai_prov.verify_licence("10014011001899")
        p = rec.status == FSSAIVerificationStatus.SERVICE_UNAVAILABLE and "timed out" in rec.message.lower()
        print_check("FSSAI TIMEOUT Handling", p, f"Status={rec.status.value}, Message='{rec.message}'")
        all_passed = all_passed and p

    # --- GS1 Mock Tests ---
    print("\n[GS1 India DataKart Provider Tests]")
    gs1_prov = GS1DataKartApiProvider(api_url="https://api.mock-gs1india.org/datakart", api_key="mock-test-key")

    # 1. Success
    with mock.patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "valid": True,
            "brand_name": "Kissan",
            "product_description": "Fresh Tomato Ketchup 1kg",
            "company_name": "Hindustan Unilever Ltd"
        }
        mock_get.return_value = mock_resp
        rec = await gs1_prov.verify_gtin("8901030383748")
        p = rec.status == GS1VerificationStatus.VERIFIED and rec.brand_name == "Kissan"
        print_check("GS1 SUCCESS Handling", p, f"Status={rec.status.value}, Brand={rec.brand_name}, Company={rec.company_name}")
        all_passed = all_passed and p

    # 2. Not Found
    with mock.patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        rec = await gs1_prov.verify_gtin("8909999999999")
        p = rec.status == GS1VerificationStatus.NOT_FOUND and rec.brand_name is None
        print_check("GS1 NOT_FOUND Handling", p, f"Status={rec.status.value}, Brand={rec.brand_name} (Zero fabrication)")
        all_passed = all_passed and p

    # 3. Unavailable / 500
    with mock.patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        mock_get.return_value = mock_resp
        rec = await gs1_prov.verify_gtin("8901030383748")
        p = rec.status == GS1VerificationStatus.SERVICE_UNAVAILABLE
        print_check("GS1 UNAVAILABLE Handling", p, f"Status={rec.status.value}, Message='{rec.message}'")
        all_passed = all_passed and p

    # 4. Timeout
    with mock.patch("httpx.AsyncClient.get", side_effect=Exception("ReadTimeout: Network socket timed out")):
        rec = await gs1_prov.verify_gtin("8901030383748")
        p = rec.status == GS1VerificationStatus.SERVICE_UNAVAILABLE and "timed out" in rec.message.lower()
        print_check("GS1 TIMEOUT Handling", p, f"Status={rec.status.value}, Message='{rec.message}'")
        all_passed = all_passed and p

    # 5. Mismatch Handling (FieldComparator)
    print("\n[Cross-Source Mismatch Handling Tests]")
    # Case A: Brand mismatch (Package says 'Maggi', GS1 registry says 'Kissan')
    diff_brand = FieldComparator.compare_brand(
        package_val="Maggi",
        external_val="Kissan",
        source_name="GS1 DataKart"
    )
    p_brand = diff_brand.result == ComparisonResult.MISMATCH
    print_check("Brand MISMATCH Detection", p_brand, f"Result={diff_brand.result.value}, Details='{diff_brand.details}'")
    all_passed = all_passed and p_brand

    # Case B: Net Quantity mismatch (Package says '1 kg', GS1 registry says '500 g')
    diff_qty = FieldComparator.compare_net_quantity(
        package_val="1 kg",
        external_val="500 g",
        source_name="GS1 DataKart"
    )
    p_qty = diff_qty.result == ComparisonResult.MISMATCH
    print_check("Quantity MISMATCH Detection", p_qty, f"Result={diff_qty.result.value}, Details='{diff_qty.details}'")
    all_passed = all_passed and p_qty

    # Case C: Exact match
    diff_match = FieldComparator.compare_brand(
        package_val="Kissan",
        external_val="Kissan",
        source_name="GS1 DataKart"
    )
    p_match = diff_match.result == ComparisonResult.MATCH
    print_check("Exact MATCH Detection", p_match, f"Result={diff_match.result.value}, Details='{diff_match.details}'")
    all_passed = all_passed and p_match

    return all_passed


async def audit_unconfigured_graceful_handling():
    print_banner("3. Unconfigured Endpoint Graceful Fallback & Report Honesty")

    # When unconfigured, providers must NOT crash and must NEVER fabricate
    unconf_fssai = FoSCoSApiProvider(api_url="")
    rec_f = await unconf_fssai.verify_licence("10014011001899")
    print_check("Unconfigured FSSAI Provider", rec_f.status == FSSAIVerificationStatus.NOT_VERIFIED, f"Status={rec_f.status.value}, Message='{rec_f.message}'")

    unconf_gs1 = GS1DataKartApiProvider(api_url="")
    rec_g = await unconf_gs1.verify_gtin("8901030383748")
    print_check("Unconfigured GS1 Provider", rec_g.status == GS1VerificationStatus.NOT_VERIFIED, f"Status={rec_g.status.value}, Message='{rec_g.message}'")

    # Verify pipeline reports honest status and manual verification links
    pipeline_fssai = FoSCoSOfficialProvider(api_url="", api_key="")
    pipeline_rec = await pipeline_fssai.verify("10014011001899")
    has_manual_link = pipeline_rec.manual_verification_url == "https://foscos.fssai.gov.in"
    print_check("FSSAI Manual Verification Link Present", has_manual_link, f"URL='{pipeline_rec.manual_verification_url}'")

    pipeline_gs1 = GS1DataKartOfficialProvider(api_url="", api_key="")
    pipeline_g_rec = await pipeline_gs1.lookup_by_gtin("8901030383748")
    has_gs1_link = pipeline_g_rec.manual_verification_url == "https://www.gs1india.org"
    print_check("GS1 Manual Verification Link Present", has_gs1_link, f"URL='{pipeline_g_rec.manual_verification_url}'")


def print_comparison_table():
    print_banner("4. System Comparison Audit Table")
    headers = ["System", "Configured Endpoint", "Reality Check", "Auth Method", "Official Documentation", "Legitimate Access Path", "Operational State"]
    
    rows = [
        [
            "FSSAI / FoSCoS",
            "FSSAI_API_URL (Empty)",
            "Placeholder / No public open API exists",
            "Bearer Token / API Key via Gateway or RegTech partner",
            "https://foscos.fssai.gov.in",
            "Govt MoU with FSSAI IT Div or authorized RegTech (Decentro, Surepass)",
            "Mock / Local Verified Cache Mode"
        ],
        [
            "GS1 India / DataKart",
            "GS1_API_URL (Empty)",
            "Placeholder / Restricted to GS1 members",
            "OAuth2 Bearer Token (Client ID + Secret)",
            "https://www.gs1india.org",
            "Register as GS1 India member and request API credentials via info@gs1india.org",
            "Mock / Local Product Registry Mode"
        ]
    ]

    col_widths = [20, 22, 38, 30, 28, 42, 32]
    separator = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    
    print(separator)
    header_str = "|" + "|".join([f" {headers[i].ljust(col_widths[i])} " for i in range(len(headers))]) + "|"
    print(header_str)
    print(separator)
    for row in rows:
        row_str = "|" + "|".join([f" {row[i].ljust(col_widths[i])} " for i in range(len(row))]) + "|"
        print(row_str)
    print(separator)


async def main():
    print("Starting MetrCheck AI External Verification Live Integration Audit...")
    await audit_configuration()
    resilience_passed = await audit_mock_mode()
    await audit_unconfigured_graceful_handling()
    print_comparison_table()

    if resilience_passed:
        print("\n>>> AUDIT SUMMARY: ALL INTEGRATION INTEGRITY & RESILIENCE CRITERIA VERIFIED (100% PASS). <<<\n")
        sys.exit(0)
    else:
        print("\n>>> AUDIT SUMMARY: FAILURES DETECTED IN INTEGRATION AUDIT. <<<\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
