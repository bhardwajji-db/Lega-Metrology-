"""
MetrCheck AI — Intelligent Product Identity & Verification Service
Aggregates OCR extractions, 1D barcodes, 2D QR codes, dedicated FSSAI validation,
image quality diagnostics, and cross-source verification into a unified ProductIdentity.
"""

import os
import re
import cv2
import logging
from typing import Optional, List, Dict, Any, Tuple
from models.schemas import ProductInfo, ProductImageEvidence, OCRWord
from services.identity.schemas import (
    ProductIdentity,
    FieldEvidenceItem,
    FieldStatus,
    QRContentData,
    BarcodeIdentityData,
    DateDeclarations,
    ConsumerCareDeclarations,
    FoodDeclarations,
    OtherDeclarations,
    CrossValidationSummary,
)
from services.identity.qr_decoder import qr_decoder_service, SafeURLValidator
from services.identity.fssai_extractor import fssai_extractor
from services.identity.cross_validator import cross_validator
from services.barcode_service import barcode_service, resolve_gs1_country, validate_ean13_checksum
from ocr.quality import assess_image_quality

logger = logging.getLogger(__name__)


class ProductIdentityService:
    """
    Orchestrates extraction, field provenance normalization, spatial evidence linking,
    and cross-source validation for package inspection.
    """

    @classmethod
    def _find_bbox_for_value(
        cls,
        target_value: Optional[str],
        images: Optional[List[ProductImageEvidence]]
    ) -> Tuple[Optional[List[int]], Optional[str], float]:
        """
        Locates bounding box and source image label for an extracted text string.
        """
        if not target_value or not images:
            return None, None, 0.0

        target_clean = re.sub(r'[^a-zA-Z0-9]', '', str(target_value).lower())
        if not target_clean:
            return None, None, 0.0

        best_bbox = None
        best_img_id = None
        best_conf = 0.0

        for img in images:
            if not img.words:
                continue
            for w in img.words:
                w_clean = re.sub(r'[^a-zA-Z0-9]', '', str(w.text).lower())
                if not w_clean:
                    continue
                if target_clean in w_clean or w_clean in target_clean:
                    best_bbox = w.bbox
                    best_img_id = img.label or img.filename
                    best_conf = float(w.confidence)
                    return best_bbox, best_img_id, best_conf

        return best_bbox, best_img_id, best_conf

    @classmethod
    def _create_field_item(
        cls,
        product_info: Optional[ProductInfo],
        field_key: str,
        attr_name: Optional[str] = None,
        images: Optional[List[ProductImageEvidence]] = None,
        default_unit: Optional[str] = None,
        is_food_field: bool = False,
        is_food_product: bool = True,
        override_val: Optional[str] = None
    ) -> FieldEvidenceItem:
        """
        Standardized factory creating a FieldEvidenceItem with spatial proof.
        """
        if is_food_field and not is_food_product:
            return FieldEvidenceItem(
                value=None,
                normalized_value=None,
                confidence=100.0,
                source="RULES_ENGINE",
                status=FieldStatus.NOT_APPLICABLE,
                explanation=f"{field_key.replace('_', ' ').title()} is not applicable to non-food products."
            )

        val: Optional[str] = override_val
        norm_val: Optional[str] = None
        bbox: Optional[List[int]] = None
        img_id: Optional[str] = None
        conf: float = 0.0
        source: str = "OCR"
        nearby: Optional[str] = None

        # 1. Primary value from product_info attributes
        if not val and product_info:
            if attr_name and hasattr(product_info, attr_name):
                val = getattr(product_info, attr_name)
            elif field_key in (product_info.other_declarations or {}):
                val = product_info.other_declarations.get(field_key)

        # 2. Enrich with field provenance if available
        if product_info and hasattr(product_info, 'field_provenance') and product_info.field_provenance:
            prov = product_info.field_provenance.get(field_key)
            if prov:
                val = val or prov.normalized_value or prov.raw_value
                norm_val = prov.normalized_value or val
                bbox = prov.source_bbox or bbox
                img_id = prov.image_label or img_id
                conf = max(conf, float(prov.confidence or 0.0))
                nearby = prov.source_text or prov.raw_value
                if prov.match_method == "MULTILINGUAL_DICTIONARY":
                    source = "MULTILINGUAL_DICT"

        # Spatial search in images if bbox is still missing
        if val and not bbox and images:
            b, im, c = cls._find_bbox_for_value(str(val), images)
            if b:
                bbox = b
                img_id = im
                conf = max(conf, c)

        if not val or not str(val).strip():
            return FieldEvidenceItem(
                value=None,
                normalized_value=None,
                confidence=0.0,
                source=source,
                bounding_box=None,
                image_id=None,
                status=FieldStatus.NOT_FOUND,
                explanation=f"Declaration for {field_key.replace('_', ' ').title()} not found on package."
            )

        val_str = str(val).strip()
        norm_str = norm_val or val_str
        confidence_val = round(conf, 1) if conf > 0.0 else 85.0

        status = FieldStatus.FOUND if confidence_val >= 60.0 else FieldStatus.LOW_CONFIDENCE

        return FieldEvidenceItem(
            value=val_str,
            normalized_value=norm_str,
            confidence=confidence_val,
            source=source,
            bounding_box=bbox,
            image_id=img_id,
            status=status,
            explanation=f"Extracted {field_key.replace('_', ' ').title()} from label evidence."
        )

    @classmethod
    def extract_identity(
        cls,
        product_info: Optional[ProductInfo] = None,
        ocr_text: str = "",
        images: Optional[List[ProductImageEvidence]] = None,
        image_paths: Optional[List[str]] = None,
        barcode_items: Optional[List[Any]] = None,
        fssai_verification: Optional[Any] = None,
        gs1_verification: Optional[Any] = None
    ) -> ProductIdentity:
        """
        Constructs a complete ProductIdentity object.
        """
        product_info = product_info or ProductInfo()
        images = images or []
        image_paths = image_paths or []
        barcode_items = barcode_items or []

        # ── 1. Image Quality Diagnostics ──
        quality_status = "PASS"
        quality_reasons: List[str] = []

        for ev in images:
            q = ev.image_quality or {}
            issues = q.get("issues", [])
            if issues:
                quality_reasons.extend(issues)
            if not q.get("is_good", True):
                quality_status = "REVIEW_REQUIRED"

        # Also assess image paths if not already scored
        if not quality_reasons and image_paths:
            for p in image_paths:
                if os.path.exists(p):
                    res = assess_image_quality(p)
                    if res.get("issues"):
                        quality_reasons.extend(res["issues"])
                    if not res.get("is_good", True):
                        quality_status = "REVIEW_REQUIRED"

        # Check for minimum dimension requirement (< 300px)
        for ev in images:
            q = ev.image_quality or {}
            res_str = q.get("resolution", "")
            if "x" in res_str:
                try:
                    parts = [int(x) for x in res_str.split("x")]
                    if min(parts) < 300:
                        msg = f"Low resolution ({res_str} < 300px min dimension); statutory text verification unreliable."
                        if msg not in quality_reasons:
                            quality_reasons.append(msg)
                        quality_status = "REVIEW_REQUIRED"
                except Exception:
                    pass

        if quality_reasons:
            quality_status = "REVIEW_REQUIRED"

        # ── 2. QR Code Intelligence ──
        detected_qrs: List[QRContentData] = []
        seen_qr_vals = set()

        # Scan direct from image files with QRCodeIntelligenceDecoder
        for idx, p in enumerate(image_paths):
            if os.path.exists(p):
                label = images[idx].label if idx < len(images) else "Front"
                try:
                    img_mat = cv2.imread(p)
                    if img_mat is not None:
                        qrs = qr_decoder_service.decode_image(img_mat, image_label=label)
                        for qr in qrs:
                            if qr.raw_value not in seen_qr_vals:
                                seen_qr_vals.add(qr.raw_value)
                                detected_qrs.append(qr)
                except Exception as e:
                    logger.debug(f"[Identity] QR decode error on {p}: {e}")

        # Adapt any QR items from barcode_service items
        for bc in barcode_items:
            sym = getattr(bc, "symbology", "").upper()
            raw_v = getattr(bc, "raw_value", "")
            if ("QR" in sym or "DIGITAL_LINK" in sym) and raw_v not in seen_qr_vals:
                seen_qr_vals.add(raw_v)
                c_type, ai_data = qr_decoder_service.classify_content(raw_v)
                is_safe, p_url, host, warn = (True, None, None, None)
                if "URL" in c_type:
                    is_safe, p_url, host, warn = SafeURLValidator.validate_url(raw_v)

                detected_qrs.append(QRContentData(
                    raw_value=raw_v,
                    content_type=c_type,
                    is_safe_url=is_safe,
                    parsed_url=p_url,
                    hostname=host,
                    gs1_ai_data=ai_data,
                    bounding_box=getattr(bc, "bounding_box", None),
                    image_id=getattr(bc, "image_id", "Front"),
                    confidence=0.95,
                    status=FieldStatus.FOUND if is_safe else FieldStatus.REVIEW_REQUIRED,
                    security_warning=warn
                ))

        # ── 3. Barcode Intelligence ──
        detected_barcodes: List[BarcodeIdentityData] = []
        seen_bc_vals = set()

        for bc in barcode_items:
            sym = getattr(bc, "symbology", "").upper()
            raw_v = getattr(bc, "raw_value", "")
            if not raw_v or "QR" in sym:
                continue

            if raw_v not in seen_bc_vals:
                seen_bc_vals.add(raw_v)
                clean_digits = re.sub(r'\D', '', raw_v)
                valid_chk = True
                if len(clean_digits) == 13:
                    valid_chk = validate_ean13_checksum(clean_digits)

                c_name, c_flag = resolve_gs1_country(clean_digits)
                prefix = clean_digits[:3] if len(clean_digits) >= 3 else None

                detected_barcodes.append(BarcodeIdentityData(
                    raw_value=raw_v,
                    symbology=getattr(bc, "symbology", "EAN-13"),
                    is_valid_checksum=valid_chk,
                    country_of_origin=c_name,
                    country_flag=c_flag,
                    gs1_prefix=prefix,
                    bounding_box=getattr(bc, "bounding_box", None),
                    image_id=getattr(bc, "image_id", "Front"),
                    confidence=0.95,
                    status=FieldStatus.FOUND if valid_chk else FieldStatus.REVIEW_REQUIRED
                ))

        # Fallback barcode from product_info if no physical barcode decoded
        if not detected_barcodes:
            fallback_bc = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
            if fallback_bc:
                clean_digits = re.sub(r'\D', '', str(fallback_bc))
                valid_chk = True
                if len(clean_digits) == 13:
                    valid_chk = validate_ean13_checksum(clean_digits)
                c_name, c_flag = resolve_gs1_country(clean_digits)
                prefix = clean_digits[:3] if len(clean_digits) >= 3 else None
                bbox, im_id, conf = cls._find_bbox_for_value(str(fallback_bc), images)
                detected_barcodes.append(BarcodeIdentityData(
                    raw_value=str(fallback_bc),
                    symbology="EAN-13" if len(clean_digits) == 13 else "BARCODE",
                    is_valid_checksum=valid_chk,
                    country_of_origin=c_name,
                    country_flag=c_flag,
                    gs1_prefix=prefix,
                    bounding_box=bbox,
                    image_id=im_id or "Front",
                    confidence=conf or 0.9,
                    status=FieldStatus.FOUND if valid_chk else FieldStatus.REVIEW_REQUIRED
                ))

        # Barcode External Verification & Provenance Mapping
        bc_ext_verified = False
        bc_ver_status = "NOT_VERIFIED"
        bc_provenance = "Extracted from package" if detected_barcodes else "Not found"
        bc_registered_details = None

        if gs1_verification:
            if hasattr(gs1_verification, 'model_dump') and callable(getattr(gs1_verification, 'model_dump', None)):
                dump_res = gs1_verification.model_dump()
                gs1_dict = dump_res if isinstance(dump_res, dict) else {}
            elif isinstance(gs1_verification, dict):
                gs1_dict = gs1_verification
            else:
                gs1_dict = {}

            raw_status = getattr(gs1_verification, "status", None) or gs1_dict.get("status", "NOT_VERIFIED")
            if hasattr(raw_status, "value"):
                raw_status = raw_status.value
            bc_ver_status = str(raw_status).upper()

            if bc_ver_status == "VERIFIED":
                bc_ext_verified = True
                bc_provenance = "Externally verified"
                bc_registered_details = {
                    "gtin": getattr(gs1_verification, "gtin", None) or gs1_dict.get("gtin"),
                    "brand_name": getattr(gs1_verification, "brand_name", None) or gs1_dict.get("brand_name"),
                    "product_description": getattr(gs1_verification, "product_description", None) or gs1_dict.get("product_description"),
                    "company_name": getattr(gs1_verification, "company_name", None) or gs1_dict.get("company_name"),
                    "gpc_category": getattr(gs1_verification, "gpc_category", None) or gs1_dict.get("gpc_category"),
                    "net_content": getattr(gs1_verification, "net_content", None) or gs1_dict.get("net_content"),
                    "country_of_sale": getattr(gs1_verification, "country_of_sale", None) or gs1_dict.get("country_of_sale", "India"),
                    "provider": getattr(gs1_verification, "provider", None) or gs1_dict.get("provider")
                }
                for b_item in detected_barcodes:
                    b_item.external_verified = True
                    b_item.verification_status = "VERIFIED"
                    b_item.provenance_label = "Externally verified"
                    b_item.registered_brand = bc_registered_details.get("brand_name")
                    b_item.registered_product = bc_registered_details.get("product_description")
                    b_item.registered_company = bc_registered_details.get("company_name")
                    b_item.registered_net_quantity = bc_registered_details.get("net_content")
                    b_item.provider = bc_registered_details.get("provider")
            elif bc_ver_status == "NOT_FOUND":
                bc_ext_verified = False
                bc_provenance = "Not found in registry" if detected_barcodes else "Not found"
                for b_item in detected_barcodes:
                    b_item.external_verified = False
                    b_item.verification_status = "NOT_FOUND"
                    b_item.provenance_label = "Not found in registry"
            elif bc_ver_status in ("SERVICE_UNAVAILABLE", "NOT_VERIFIED"):
                bc_ext_verified = False
                bc_provenance = "Verification unavailable" if detected_barcodes else "Not found"
                for b_item in detected_barcodes:
                    b_item.external_verified = False
                    b_item.verification_status = bc_ver_status
                    b_item.provenance_label = "Verification unavailable"

        # ── 4. FSSAI Information Extraction ──
        # Check if canonical FSSAI was already extracted upstream in product_info
        canonical_fssai: Optional[str] = None
        if product_info and product_info.fssai_license:
            clean_p = re.sub(r'\D', '', str(product_info.fssai_license))
            if len(clean_p) == 14:
                canonical_fssai = clean_p

        fssai_item, state_name, lic_type = fssai_extractor.extract_fssai(ocr_text, images=images)

        # Prioritize canonical FSSAI from product_info so multi-license labels don't override the primary declaration
        if canonical_fssai:
            if fssai_item.value != canonical_fssai:
                is_v, st_name, l_type = fssai_extractor.validate_structure(canonical_fssai)
                bbox, img_id, conf = cls._find_bbox_for_value(canonical_fssai, images)
                fssai_item = FieldEvidenceItem(
                    value=canonical_fssai,
                    normalized_value=canonical_fssai,
                    confidence=round(conf or 90.0, 1),
                    source="OCR",
                    bounding_box=bbox,
                    image_id=img_id,
                    status=FieldStatus.FOUND if is_v else FieldStatus.REVIEW_REQUIRED,
                    explanation=f"FSSAI License {canonical_fssai} declared on label."
                )
                state_name = st_name
                lic_type = l_type
        elif fssai_item.status == FieldStatus.NOT_FOUND and product_info and product_info.fssai_license:
            clean_lic = re.sub(r'\D', '', str(product_info.fssai_license))
            if len(clean_lic) == 14:
                is_v, st_name, l_type = fssai_extractor.validate_structure(clean_lic)
                bbox, img_id, conf = cls._find_bbox_for_value(clean_lic, images)
                fssai_item = FieldEvidenceItem(
                    value=clean_lic,
                    normalized_value=clean_lic,
                    confidence=round(conf or 88.0, 1),
                    source="OCR",
                    bounding_box=bbox,
                    image_id=img_id,
                    status=FieldStatus.FOUND if is_v else FieldStatus.REVIEW_REQUIRED,
                    explanation=f"FSSAI License {clean_lic} extracted from label."
                )
                state_name = st_name
                lic_type = l_type

        # Ensure product_info has the same FSSAI number if extracted from text
        if fssai_item.value and product_info and not product_info.fssai_license:
            product_info.fssai_license = fssai_item.value

        # Check external verification & provenance
        fssai_ext_verified = False
        fssai_ver_status = "NOT_VERIFIED"
        fssai_provenance = "Extracted from package" if fssai_item.value else "Not found"
        fssai_details = None

        if fssai_verification:
            if hasattr(fssai_verification, 'model_dump') and callable(getattr(fssai_verification, 'model_dump', None)):
                dump_res = fssai_verification.model_dump()
                fssai_details = dump_res if isinstance(dump_res, dict) else {}
            elif isinstance(fssai_verification, dict):
                fssai_details = fssai_verification
            else:
                fssai_details = {}

            raw_f_status = getattr(fssai_verification, "status", None) or fssai_details.get("status", "")
            if hasattr(raw_f_status, "value"):
                raw_f_status = raw_f_status.value
            fssai_ver_status = str(raw_f_status).upper()

            # ONLY truly verified if status is VERIFIED and contains actual registered business details
            if fssai_ver_status in ("VERIFIED", "ACTIVE") and (getattr(fssai_verification, "business_name", None) or fssai_details.get("business_name")):
                fssai_ext_verified = True
                fssai_provenance = "Externally verified"
                if fssai_item.status == FieldStatus.FOUND:
                    fssai_item.status = FieldStatus.VERIFIED
            elif fssai_ver_status == "NOT_FOUND":
                fssai_ext_verified = False
                fssai_provenance = "Not found in registry" if fssai_item.value else "Not found"
            elif fssai_ver_status in ("FAILED", "INVALID", "EXPIRED", "INVALID_FORMAT"):
                fssai_ext_verified = False
                fssai_provenance = "Verification failed"
                fssai_item.status = FieldStatus.VERIFICATION_FAILED
            else:
                fssai_ext_verified = False
                fssai_ver_status = "SERVICE_UNAVAILABLE" if fssai_ver_status == "SERVICE_UNAVAILABLE" else "NOT_VERIFIED"
                fssai_provenance = "Verification unavailable" if fssai_item.value else "Not found"

        # ── 5. Is Food Determination ──
        is_food = bool(product_info.is_food)
        cat_lower = str(product_info.category or "").lower()
        if not is_food and any(k in cat_lower for k in ("food", "snack", "beverage", "sauce", "ketchup", "dairy", "grain", "cereal", "bakery", "spice", "tea", "coffee")):
            is_food = True
        if fssai_item.value:
            is_food = True

        # Non-food products do not require FSSAI
        if not is_food and fssai_item.status == FieldStatus.NOT_FOUND:
            fssai_item.status = FieldStatus.NOT_APPLICABLE
            fssai_item.explanation = "FSSAI licence declaration is not required for non-food products."

        # ── 6. Assemble Core Identity Fields ──
        f_prod = cls._create_field_item(product_info, "product_name", "product_name", images)
        f_brand = cls._create_field_item(product_info, "brand_name", "brand", images)
        f_variant = cls._create_field_item(product_info, "variant", None, images)
        f_category = cls._create_field_item(product_info, "category", "category", images)

        # Manufacturer / Packer / Importer / Marketer
        f_mfr = cls._create_field_item(product_info, "manufacturer_name", "manufacturer_name", images, override_val=product_info.manufacturer_name or product_info.manufacturer)
        f_packer = cls._create_field_item(product_info, "packer_name", "packer_name", images)
        f_importer = cls._create_field_item(product_info, "importer_name", "importer_name", images)
        f_marketer = cls._create_field_item(product_info, "marketed_by_name", "marketed_by_name", images, override_val=product_info.marketed_by_name or product_info.marketed_by)
        f_addr = cls._create_field_item(product_info, "complete_address", "manufacturer_address", images, override_val=product_info.manufacturer_address or product_info.marketed_by_address)
        f_country = cls._create_field_item(product_info, "country_of_origin", "country_of_origin", images)

        # Legal Metrology Core Declarations
        f_mrp = cls._create_field_item(product_info, "mrp", "mrp", images)
        f_net = cls._create_field_item(product_info, "net_quantity", "net_quantity", images)
        f_unit = cls._create_field_item(product_info, "unit", None, images)
        f_batch = cls._create_field_item(product_info, "batch_number", "batch_number", images)

        # Dates
        f_mfg = cls._create_field_item(product_info, "manufacturing_date", "manufacturing_date", images, override_val=product_info.manufacturing_date or product_info.manufacture_date)
        f_pack = cls._create_field_item(product_info, "packaging_date", "packaging_date", images)
        f_imp = cls._create_field_item(product_info, "import_date", None, images)
        f_bb = cls._create_field_item(product_info, "best_before", "best_before", images)
        f_exp = cls._create_field_item(product_info, "expiry_date", "expiry_date", images)
        f_use = cls._create_field_item(product_info, "use_by_date", "use_by_date", images)

        dates = DateDeclarations(
            date_of_manufacture=f_mfg,
            date_of_packaging=f_pack,
            date_of_import=f_imp,
            best_before=f_bb,
            expiry_date=f_exp,
            use_by_date=f_use
        )

        # Consumer Care
        f_phone = cls._create_field_item(product_info, "consumer_care_phone", "consumer_care_phone", images)
        f_email = cls._create_field_item(product_info, "consumer_care_email", "consumer_care_email", images)
        f_cc_addr = cls._create_field_item(product_info, "consumer_care_address", "consumer_care", images, override_val=product_info.consumer_care)
        f_cc_web = cls._create_field_item(product_info, "consumer_care_website", None, images)

        consumer_care = ConsumerCareDeclarations(
            phone=f_phone,
            email=f_email,
            address=f_cc_addr,
            website=f_cc_web
        )

        # Food Declarations
        f_ing_ev = cls._create_field_item(product_info, "ingredients", "ingredients", images, is_food_field=True, is_food_product=is_food)
        f_alg_ev = cls._create_field_item(product_info, "allergens", "allergen_info", images, is_food_field=True, is_food_product=is_food)
        f_nut_ev = cls._create_field_item(product_info, "nutritional_info", "nutritional_info", images, is_food_field=True, is_food_product=is_food)
        f_veg_ev = cls._create_field_item(product_info, "veg_nonveg_status", "veg_nonveg_status", images, is_food_field=True, is_food_product=is_food)
        f_serv_ev = cls._create_field_item(product_info, "serving_info", None, images, is_food_field=True, is_food_product=is_food)
        f_stor_ev = cls._create_field_item(product_info, "storage_instructions", None, images, is_food_field=True, is_food_product=is_food)

        # Parse ingredient list tokens
        ing_list: List[str] = []
        if is_food and product_info.ingredients:
            raw_ing = re.sub(r'^(ingredients?|contains?)[\s.:\-_/]*', '', product_info.ingredients, flags=re.IGNORECASE)
            ing_list = [i.strip() for i in re.split(r'[,;•\n]', raw_ing) if i.strip()]

        alg_list: List[str] = []
        if is_food and product_info.allergen_info:
            raw_alg = re.sub(r'^(contains?|allergens?|allergy\s+advice)[\s.:\-_/]*', '', product_info.allergen_info, flags=re.IGNORECASE)
            alg_list = [a.strip() for a in re.split(r'[,;•\n]', raw_alg) if a.strip()]

        nut_dict: Dict[str, str] = {}
        if is_food and product_info.nutrition_facts:
            nut_dict = dict(product_info.nutrition_facts)

        food_decls = FoodDeclarations(
            is_food=is_food,
            ingredients=ing_list,
            ingredients_evidence=f_ing_ev,
            allergens=alg_list,
            allergens_evidence=f_alg_ev,
            nutritional_info=nut_dict,
            nutrition_evidence=f_nut_ev,
            veg_nonveg_status=f_veg_ev,
            serving_info=f_serv_ev,
            storage_instructions=f_stor_ev
        )

        # Other Declarations
        f_pcode = cls._create_field_item(product_info, "product_code", None, images)
        f_model = cls._create_field_item(product_info, "model_number", None, images)
        other_decls = OtherDeclarations(
            product_code=f_pcode,
            model_number=f_model,
            certifications=[]
        )

        # Construct ProductIdentity
        identity = ProductIdentity(
            product_name=f_prod,
            brand_name=f_brand,
            product_variant=f_variant,
            product_category=f_category,
            barcodes=detected_barcodes,
            qr_codes=detected_qrs,
            fssai_license_number=fssai_item,
            fssai_state_name=state_name,
            fssai_license_type=lic_type,
            fssai_external_verified=fssai_ext_verified,
            fssai_verification_status=fssai_ver_status,
            fssai_provenance_label=fssai_provenance,
            fssai_verification_details=fssai_details,
            barcode_external_verified=bc_ext_verified,
            barcode_verification_status=bc_ver_status,
            barcode_provenance_label=bc_provenance,
            barcode_registered_details=bc_registered_details,
            manufacturer=f_mfr,
            packer=f_packer,
            importer=f_importer,
            marketer=f_marketer,
            complete_address=f_addr,
            country_of_origin=f_country,
            mrp=f_mrp,
            net_quantity=f_net,
            unit=f_unit,
            batch_number=f_batch,
            dates=dates,
            customer_care=consumer_care,
            food_declarations=food_decls,
            other_declarations=other_decls,
            image_quality_status=quality_status,
            quality_reasons=quality_reasons,
            cross_validation=CrossValidationSummary()
        )

        # ── 7. Cross-Validation Layer ──
        cross_validator.cross_validate(
            identity,
            fssai_verification=fssai_verification,
            gs1_verification=gs1_verification
        )

        return identity


identity_service = ProductIdentityService()
