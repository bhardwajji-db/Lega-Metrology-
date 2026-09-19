"""
MetrCheck AI — Deterministic OCR vs Barcode Product Data Comparison Layer
Implements Section 6 of the statutory Legal Metrology specification:
Compares on-pack OCR declarations against authoritative barcode registry data.
Normalizes case, punctuation, whitespace, units, and corporate suffixes while
preserving original raw values for audit integrity.
"""

import re
import difflib
from typing import Optional, List, Tuple, Dict, Any
from models.barcode_product import (
    ComparisonStatus,
    DeterministicFieldComparison,
    ExternalProductMaster,
    ProvenanceType,
)

# Common corporate / legal entity suffixes to strip during normalization
LEGAL_ENTITY_SUFFIXES = {
    "pvt", "ltd", "private", "limited", "llp", "inc", "corp", "corporation",
    "co", "company", "enterprises", "industries", "foods", "beverages",
    "products", "india", "mfg", "manufactured", "by", "marketed", "packed",
    "fbo", "licensee", "unit", "works", "plant", "and", "&"
}


def normalize_string(val: Optional[str]) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    if not val:
        return ""
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(val).lower())
    return " ".join(cleaned.split())


def normalize_entity_name(name: Optional[str]) -> str:
    """Normalize corporate or brand name by stripping legal company suffixes."""
    norm = normalize_string(name)
    words = [w for w in norm.split() if w not in LEGAL_ENTITY_SUFFIXES]
    return " ".join(words)


def parse_quantity_unit(val_str: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses numeric quantity and normalizes unit to canonical metric form:
    e.g. '1 kg' -> (1000.0, 'g'), '400 g' -> (400.0, 'g'), '1.5 L' -> (1500.0, 'ml').
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
        if unit in ('kg', 'kilogram', 'kilograms', 'kgs'):
            return round(qty * 1000.0, 2), 'g'
        if unit in ('g', 'gm', 'gms', 'gram', 'grams'):
            return round(qty, 2), 'g'
        if unit in ('l', 'ltr', 'liter', 'litre', 'litres', 'liters'):
            return round(qty * 1000.0, 2), 'ml'
        if unit in ('ml', 'milliliter', 'millilitre', 'mls'):
            return round(qty, 2), 'ml'
        return qty, unit or None
    except Exception:
        return None, None


class BarcodeOcrComparator:
    """Performs deterministic comparisons between package OCR data and external product data."""

    @classmethod
    def compare_text_field(
        cls,
        field_name: str,
        ocr_val: Optional[str],
        ext_val: Optional[str],
        source: str,
        provenance: ProvenanceType,
        is_entity: bool = False
    ) -> DeterministicFieldComparison:
        """Compares text with normalization and token overlap."""
        if not ocr_val and not ext_val:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=ext_val,
                status=ComparisonStatus.NOT_PROVIDED,
                details=f"{field_name} not available in package OCR or external database.",
                source=source,
                provenance=provenance
            )

        if not ocr_val:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=None,
                external_value=ext_val,
                status=ComparisonStatus.NOT_PROVIDED,
                details=f"{field_name} present in barcode registry ('{ext_val}') but not detected on package OCR.",
                source=source,
                provenance=provenance
            )

        if not ext_val:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=None,
                status=ComparisonStatus.NOT_PROVIDED,
                details=f"{field_name} declared on package ('{ocr_val}') but not supplied by barcode registry.",
                source=source,
                provenance=provenance
            )

        norm_ocr = normalize_entity_name(ocr_val) if is_entity else normalize_string(ocr_val)
        norm_ext = normalize_entity_name(ext_val) if is_entity else normalize_string(ext_val)

        # 1. Exact normalized match
        if norm_ocr == norm_ext or (norm_ocr and norm_ocr in norm_ext) or (norm_ext and norm_ext in norm_ocr):
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=ext_val,
                status=ComparisonStatus.MATCH,
                details=f"{field_name} matches between package OCR and barcode registry.",
                source=source,
                provenance=provenance
            )

        # 2. Token overlap & Sequence similarity
        toks_ocr = set(norm_ocr.split())
        toks_ext = set(norm_ext.split())
        overlap = toks_ocr.intersection(toks_ext)
        seq_ratio = difflib.SequenceMatcher(None, norm_ocr, norm_ext).ratio()

        if (toks_ocr and len(overlap) / len(toks_ocr) >= 0.5) or seq_ratio >= 0.70:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=ext_val,
                status=ComparisonStatus.MATCH,
                details=f"{field_name} substantially matches registry record ('{ext_val}').",
                source=source,
                provenance=provenance
            )

        return DeterministicFieldComparison(
            field_name=field_name,
            package_ocr_value=ocr_val,
            external_value=ext_val,
            status=ComparisonStatus.MISMATCH,
            details=f"Discrepancy in {field_name}: package declares '{ocr_val}', but barcode database records '{ext_val}'.",
            source=source,
            provenance=provenance
        )

    @classmethod
    def compare_net_quantity(
        cls,
        ocr_val: Optional[str],
        ext_val: Optional[str],
        source: str,
        provenance: ProvenanceType
    ) -> DeterministicFieldComparison:
        """Compares net quantity with unit conversion (e.g. 1 kg == 1000 g)."""
        field_name = "Net Quantity"
        if not ocr_val and not ext_val:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=ext_val,
                status=ComparisonStatus.NOT_PROVIDED,
                details="Net quantity not provided in OCR or barcode database.",
                source=source,
                provenance=provenance
            )

        if not ocr_val or not ext_val:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=ext_val,
                status=ComparisonStatus.NOT_PROVIDED,
                details=f"Net quantity missing from {'external source' if not ext_val else 'package OCR'}.",
                source=source,
                provenance=provenance
            )

        qty_o, unit_o = parse_quantity_unit(ocr_val)
        qty_e, unit_e = parse_quantity_unit(ext_val)

        if qty_o is not None and qty_e is not None:
            if unit_o and unit_e and unit_o == unit_e:
                if abs(qty_o - qty_e) < 0.01:
                    return DeterministicFieldComparison(
                        field_name=field_name,
                        package_ocr_value=ocr_val,
                        external_value=ext_val,
                        status=ComparisonStatus.MATCH,
                        details=f"Net quantity matches exactly ({ocr_val} = {ext_val}).",
                        source=source,
                        provenance=provenance
                    )
            elif qty_o == qty_e:
                return DeterministicFieldComparison(
                    field_name=field_name,
                    package_ocr_value=ocr_val,
                    external_value=ext_val,
                    status=ComparisonStatus.MATCH,
                    details=f"Numeric quantity values match ({qty_o}).",
                    source=source,
                    provenance=provenance
                )

        # Fallback to normalized text comparison
        norm_o = re.sub(r'\s+', '', str(ocr_val).lower())
        norm_e = re.sub(r'\s+', '', str(ext_val).lower())
        if norm_o == norm_e:
            return DeterministicFieldComparison(
                field_name=field_name,
                package_ocr_value=ocr_val,
                external_value=ext_val,
                status=ComparisonStatus.MATCH,
                details=f"Net quantity matches ({ocr_val}).",
                source=source,
                provenance=provenance
            )

        return DeterministicFieldComparison(
            field_name=field_name,
            package_ocr_value=ocr_val,
            external_value=ext_val,
            status=ComparisonStatus.MISMATCH,
            details=f"Net quantity mismatch: package declares '{ocr_val}', but barcode database records '{ext_val}'.",
            source=source,
            provenance=provenance
        )

    @classmethod
    def compare_all(
        cls,
        ocr_data: Dict[str, Any],
        product_master: Optional[ExternalProductMaster]
    ) -> List[DeterministicFieldComparison]:
        """Runs full comparison across all matching fields."""
        comparisons: List[DeterministicFieldComparison] = []
        if not product_master:
            return comparisons

        src = product_master.source
        prov = product_master.provenance

        # 1. Product Name
        comparisons.append(cls.compare_text_field(
            field_name="Product Name",
            ocr_val=ocr_data.get("product_name"),
            ext_val=product_master.product_name,
            source=src,
            provenance=prov,
            is_entity=False
        ))

        # 2. Brand Name
        comparisons.append(cls.compare_text_field(
            field_name="Brand Name",
            ocr_val=ocr_data.get("brand") or ocr_data.get("brand_name"),
            ext_val=product_master.brand,
            source=src,
            provenance=prov,
            is_entity=True
        ))

        # 3. Manufacturer / Company
        comparisons.append(cls.compare_text_field(
            field_name="Manufacturer / Company",
            ocr_val=ocr_data.get("manufacturer") or ocr_data.get("manufacturer_name"),
            ext_val=product_master.manufacturer,
            source=src,
            provenance=prov,
            is_entity=True
        ))

        # 4. Net Quantity
        comparisons.append(cls.compare_net_quantity(
            ocr_val=ocr_data.get("net_quantity"),
            ext_val=product_master.net_quantity,
            source=src,
            provenance=prov
        ))

        # 5. Product Category
        comparisons.append(cls.compare_text_field(
            field_name="Product Category",
            ocr_val=ocr_data.get("category") or ocr_data.get("product_category"),
            ext_val=product_master.category,
            source=src,
            provenance=prov,
            is_entity=False
        ))

        # 6. Package / Variant
        var_ocr = ocr_data.get("variant") or ocr_data.get("product_variant")
        var_ext = (product_master.standard_fields.packaging.variant_flavour.value or
                   product_master.standard_fields.identity.product_variant.value)
        if var_ocr or var_ext:
            comparisons.append(cls.compare_text_field(
                field_name="Package Variant",
                ocr_val=var_ocr,
                ext_val=str(var_ext) if var_ext else None,
                source=src,
                provenance=prov,
                is_entity=False
            ))

        # 7. GTIN / Barcode
        barcode_ocr = ocr_data.get("barcode") or ocr_data.get("barcode_detected")
        if barcode_ocr or product_master.gtin:
            norm_b = re.sub(r'\D', '', str(barcode_ocr or ''))
            norm_g = re.sub(r'\D', '', str(product_master.gtin or ''))
            is_match = (norm_b == norm_g) or (norm_b and norm_g and (norm_b in norm_g or norm_g in norm_b))
            comparisons.append(DeterministicFieldComparison(
                field_name="GTIN / Barcode",
                package_ocr_value=barcode_ocr,
                external_value=product_master.gtin,
                status=ComparisonStatus.MATCH if is_match else ComparisonStatus.MISMATCH,
                details="Scanned barcode matches registered GTIN identifier." if is_match else f"Barcode mismatch ({barcode_ocr} vs {product_master.gtin}).",
                source=src,
                provenance=prov
            ))

        # 8. Product Description
        desc_ocr = ocr_data.get("product_description") or ocr_data.get("description")
        desc_ext = product_master.standard_fields.identity.product_description.value
        if desc_ocr or desc_ext:
            comparisons.append(cls.compare_text_field(
                field_name="Product Description",
                ocr_val=desc_ocr,
                ext_val=str(desc_ext) if desc_ext else None,
                source=src,
                provenance=prov,
                is_entity=False
            ))

        return comparisons


barcode_ocr_comparator = BarcodeOcrComparator()
