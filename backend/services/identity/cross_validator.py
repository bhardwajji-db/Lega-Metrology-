"""
MetrCheck AI — Cross-Validation & Conflict Detection Layer
Cross-validates information across multiple independent sources:
1. Label OCR Text
2. 2D QR Code / GS1 Digital Link Payloads
3. 1D Retail Barcode Symbology & Prefix Data
4. Master Product Registry & External Verification Records
Flags conflicts explicitly without guessing or fabricating data.
"""

import re
import logging
from typing import Optional, List, Dict, Any
from services.identity.schemas import (
    ProductIdentity,
    CrossValidationSummary,
    ConflictItem,
    FieldStatus
)

logger = logging.getLogger(__name__)

class IdentityCrossValidator:
    """
    Cross-validation coordinator for Legal Metrology & Food Declarations.
    """

    @classmethod
    def cross_validate(
        cls,
        identity: ProductIdentity,
        fssai_verification: Optional[Any] = None,
        gs1_verification: Optional[Any] = None
    ) -> CrossValidationSummary:
        conflicts: List[ConflictItem] = []
        fssai_cross_check: Dict[str, Any] = {"status": "NOT_CHECKED"}
        barcode_cross_check: Dict[str, Any] = {"status": "NOT_CHECKED"}

        # ── 1. FSSAI Cross-Check: OCR vs QR Code vs External Verification ──
        ocr_fssai = identity.fssai_license_number.value
        qr_fssai: Optional[str] = None
        qr_evidence_box: Optional[List[int]] = None

        for qr in identity.qr_codes:
            if qr.gs1_ai_data and qr.gs1_ai_data.get("fssai_license"):
                qr_fssai = qr.gs1_ai_data["fssai_license"]
                qr_evidence_box = qr.bounding_box
                break
            # Look for 14-digit pattern in raw QR value
            raw_q = str(qr.raw_value or "")
            m = re.search(r'\b(1\d{13}|2\d{13})\b', raw_q)
            if m:
                qr_fssai = m.group(1)
                qr_evidence_box = qr.bounding_box
                break

        if ocr_fssai and qr_fssai:
            if ocr_fssai != qr_fssai:
                conflict = ConflictItem(
                    field_name="FSSAI License Number",
                    source_a="OCR Label Text",
                    value_a=ocr_fssai,
                    source_b="QR Code Payload",
                    value_b=qr_fssai,
                    severity="HIGH",
                    description=f"FSSAI License number on label text ({ocr_fssai}) conflicts with embedded QR code license ({qr_fssai}).",
                    evidence_boxes=[
                        {"source": "OCR", "bbox": identity.fssai_license_number.bounding_box, "value": ocr_fssai},
                        {"source": "QR_CODE", "bbox": qr_evidence_box, "value": qr_fssai}
                    ]
                )
                conflicts.append(conflict)
                identity.fssai_license_number.status = FieldStatus.REVIEW_REQUIRED
                fssai_cross_check = {
                    "status": "CONFLICT_DETECTED",
                    "ocr_value": ocr_fssai,
                    "qr_value": qr_fssai,
                    "details": "Label text and QR code declare different FSSAI license numbers."
                }
            else:
                fssai_cross_check = {
                    "status": "CONSISTENT",
                    "ocr_value": ocr_fssai,
                    "qr_value": qr_fssai,
                    "details": "FSSAI License matches across Label OCR and QR Code payload."
                }

        # ── 2. Net Quantity Cross-Check: Label OCR vs Barcode / QR GS1 Data ──
        ocr_net = identity.net_quantity.value
        barcode_val = identity.barcodes[0].raw_value if identity.barcodes else None

        # Check against GS1 AI (310x) in QR if present
        for qr in identity.qr_codes:
            if qr.gs1_ai_data and qr.gs1_ai_data.get("weight_kg"):
                qr_weight = qr.gs1_ai_data["weight_kg"]
                if ocr_net and qr_weight:
                    norm_label = re.sub(r'\s+', '', ocr_net.lower())
                    norm_qr = re.sub(r'\s+', '', qr_weight.lower())
                    if norm_label != norm_qr:
                        conflicts.append(ConflictItem(
                            field_name="Net Quantity",
                            source_a="OCR Label Text",
                            value_a=ocr_net,
                            source_b="QR GS1 Digital Link",
                            value_b=qr_weight,
                            severity="HIGH",
                            description=f"Net Quantity on label ({ocr_net}) differs from QR GS1 weight declaration ({qr_weight})."
                        ))

        # Check against GS1 external verification or local verified product registry
        gs1_brand = None
        gs1_product = None
        gs1_net = None
        gs1_company = None
        gs1_gtin = None
        gs1_verified = False

        if gs1_verification:
            g_dict = gs1_verification.model_dump() if hasattr(gs1_verification, 'model_dump') else (gs1_verification if isinstance(gs1_verification, dict) else {})
            g_st = getattr(gs1_verification, "status", None) or g_dict.get("status")
            if hasattr(g_st, "value"):
                g_st = g_st.value
            if str(g_st).upper() == "VERIFIED":
                gs1_gtin = getattr(gs1_verification, "gtin", None) or g_dict.get("gtin")
                gs1_brand = getattr(gs1_verification, "brand_name", None) or g_dict.get("brand_name")
                gs1_product = getattr(gs1_verification, "product_description", None) or g_dict.get("product_description")
                gs1_net = getattr(gs1_verification, "net_content", None) or g_dict.get("net_content")
                gs1_company = getattr(gs1_verification, "company_name", None) or g_dict.get("company_name")
                if gs1_brand or gs1_net or gs1_product:
                    gs1_verified = True

        if not gs1_brand and barcode_val and gs1_verification is None:
            from services.barcode_service import VERIFIED_PRODUCT_REGISTRY
            clean_bc = re.sub(r'\D', '', barcode_val)
            reg_entry = VERIFIED_PRODUCT_REGISTRY.get(clean_bc)
            if reg_entry:
                gs1_gtin = clean_bc
                gs1_brand = reg_entry.get("brand_name")
                gs1_product = reg_entry.get("product_name")
                gs1_net = reg_entry.get("net_quantity")
                gs1_company = reg_entry.get("company_name")
                gs1_verified = True

        if gs1_brand or gs1_net:
            clean_bc = gs1_gtin or (re.sub(r'\D', '', barcode_val) if barcode_val else "GTIN")
            if ocr_net and gs1_net:
                norm_label = re.sub(r'\s+', '', ocr_net.lower())
                norm_reg = re.sub(r'\s+', '', gs1_net.lower())
                digits_label = re.search(r'\d+', norm_label)
                digits_reg = re.search(r'\d+', norm_reg)
                if digits_label and digits_reg and digits_label.group(0) != digits_reg.group(0):
                    conflicts.append(ConflictItem(
                        field_name="Net Quantity",
                        source_a="OCR Label Text",
                        value_a=ocr_net,
                        source_b="Barcode Master Record",
                        value_b=gs1_net,
                        severity="HIGH",
                        description=f"Net quantity on physical package ({ocr_net}) does not match registered master weight ({gs1_net}) for GTIN {clean_bc}."
                    ))

            ocr_brand = identity.brand_name.value
            if ocr_brand and gs1_brand:
                if gs1_brand.lower() not in ocr_brand.lower() and ocr_brand.lower() not in gs1_brand.lower():
                    conflicts.append(ConflictItem(
                        field_name="Brand Name",
                        source_a="OCR Label Text",
                        value_a=ocr_brand,
                        source_b="Barcode Master Record",
                        value_b=gs1_brand,
                        severity="MEDIUM",
                        description=f"Packaging brand '{ocr_brand}' does not match brand '{gs1_brand}' registered to barcode {clean_bc}."
                    ))

            barcode_cross_check = {
                "status": "VERIFIED_MATCH" if not any(c.field_name in ("Net Quantity", "Brand Name") for c in conflicts) else "CONFLICT_DETECTED",
                "gtin": clean_bc,
                "registered_product": f"{gs1_brand} - {gs1_net}"
            }

        # Check FSSAI business name vs OCR Manufacturer / Marketer if verified
        fssai_verified = False
        if fssai_verification:
            f_dict = fssai_verification.model_dump() if hasattr(fssai_verification, 'model_dump') else (fssai_verification if isinstance(fssai_verification, dict) else {})
            f_st = getattr(fssai_verification, "status", None) or f_dict.get("status")
            if hasattr(f_st, "value"):
                f_st = f_st.value
            if str(f_st).upper() == "VERIFIED":
                fbo_name = getattr(fssai_verification, "business_name", None) or f_dict.get("business_name")
                if fbo_name:
                    fssai_verified = True
                    mfr_name = identity.manufacturer.value or identity.marketer.value
                    if mfr_name and len(mfr_name) > 4:
                        clean_fbo = re.sub(r'[^a-zA-Z0-9]', '', fbo_name.lower())
                        clean_mfr = re.sub(r'[^a-zA-Z0-9]', '', mfr_name.lower())
                        if clean_fbo not in clean_mfr and clean_mfr not in clean_fbo:
                            words_fbo = set(re.findall(r'\w{4,}', fbo_name.lower()))
                            words_mfr = set(re.findall(r'\w{4,}', mfr_name.lower()))
                            if not words_fbo.intersection(words_mfr):
                                conflicts.append(ConflictItem(
                                    field_name="Manufacturer / Business Name",
                                    source_a="OCR Label Text",
                                    value_a=mfr_name,
                                    source_b="FSSAI FoSCoS Registry",
                                    value_b=fbo_name,
                                    severity="MEDIUM",
                                    description=f"Manufacturer name on label ('{mfr_name}') does not match registered FSSAI business entity ('{fbo_name}')."
                                ))

        # ── 3. Country of Origin Check: Label OCR vs Barcode GS1 Prefix ──
        ocr_country = identity.country_of_origin.value
        if identity.barcodes and ocr_country:
            bc_country = identity.barcodes[0].country_of_origin
            if bc_country and bc_country != "Unknown Jurisdiction" and bc_country != "Restricted Distribution":
                if bc_country.lower() not in ocr_country.lower() and ocr_country.lower() not in bc_country.lower():
                    conflicts.append(ConflictItem(
                        field_name="Country of Origin",
                        source_a="OCR Label Text",
                        value_a=ocr_country,
                        source_b="Barcode GS1 Country Prefix",
                        value_b=bc_country,
                        severity="MEDIUM",
                        description=f"Label declares Country of Origin as '{ocr_country}', but barcode prefix indicates '{bc_country}'."
                    ))

        # ── 4. Explicit Status Determination ──
        # States: MATCH, CONFLICT_DETECTED, REGISTRY_NOT_FOUND, REGISTRY_UNAVAILABLE, NOT_CHECKED
        has_conflicts = len(conflicts) > 0
        if has_conflicts:
            overall_status = "CONFLICT_DETECTED"
            summary_msg = f"Cross-validation identified {len(conflicts)} data conflict(s)."
        elif fssai_verified or gs1_verified:
            overall_status = "PASS"
            summary_msg = "Cross-validation confirmed consistency across all available sources."
        elif (fssai_verification and str(getattr(fssai_verification, 'status', '')).upper() == 'NOT_FOUND') or \
             (gs1_verification and str(getattr(gs1_verification, 'status', '')).upper() == 'NOT_FOUND'):
            overall_status = "REGISTRY_NOT_FOUND"
            summary_msg = "Declared product identifier not found in external statutory database."
        elif not identity.fssai_license_number.value and not identity.barcodes:
            overall_status = "NOT_CHECKED"
            summary_msg = "No external identifiers present to cross-validate."
        else:
            overall_status = "REGISTRY_UNAVAILABLE"
            summary_msg = "External registry comparison could not be performed. No conclusion about registry consistency is made."

        summary = CrossValidationSummary(
            status=overall_status,
            has_conflicts=has_conflicts,
            conflicts=conflicts,
            fssai_cross_check=fssai_cross_check,
            barcode_cross_check=barcode_cross_check,
            summary_message=summary_msg
        )

        identity.cross_validation = summary
        return summary


cross_validator = IdentityCrossValidator()
