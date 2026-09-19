"""
MetrCheck AI — Barcode & GTIN Integration Package
"""

from models.barcode_product import (
    ProvenanceType,
    FieldState,
    BarcodeLookupStatus,
    ComparisonStatus,
    ProvenanceValue,
    DetectedBarcodeCode,
    ExternalProductMaster,
    ExternalLookupAudit,
    DeterministicFieldComparison,
    BarcodeProductLookupResult,
)
from integrations.barcode.provider import (
    BarcodeProductProvider,
    AuthorizedExternalBarcodeProvider,
    LocalRegistryBarcodeProvider,
    BarcodeProductCoordinator,
    barcode_coordinator,
    map_provider_response_to_master,
    is_ssrf_blocked,
)
from integrations.barcode.comparator import (
    BarcodeOcrComparator,
    barcode_ocr_comparator,
)

__all__ = [
    "ProvenanceType",
    "FieldState",
    "BarcodeLookupStatus",
    "ComparisonStatus",
    "ProvenanceValue",
    "DetectedBarcodeCode",
    "ExternalProductMaster",
    "ExternalLookupAudit",
    "DeterministicFieldComparison",
    "BarcodeProductLookupResult",
    "BarcodeProductProvider",
    "AuthorizedExternalBarcodeProvider",
    "LocalRegistryBarcodeProvider",
    "BarcodeProductCoordinator",
    "barcode_coordinator",
    "map_provider_response_to_master",
    "is_ssrf_blocked",
    "BarcodeOcrComparator",
    "barcode_ocr_comparator",
]
