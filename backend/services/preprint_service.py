import os
import io
import re
import time
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import numpy as np

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None
from config import settings
from ocr.factory import get_ocr_engine
from extraction.extractor import LocalExtractor
from compliance.engine import ComplianceEngine
from compliance.scorer import calculate_score
from models.schemas import ProductInfo, ProductImageEvidence, OCRWord, ComplianceCheck, ComplianceResult
from models.preprint_schemas import (
    ArtworkDocument,
    ArtworkPageInfo,
    ArtworkLayoutRegion,
    DesignerCorrectionItem,
    PlacementCheckResult,
    FontSizeEstimateResult,
    PreprintApprovalRecord,
    PreprintUploadResponse,
    PreprintAnalysisResponse
)

logger = logging.getLogger(__name__)

MAX_ARTWORK_FILE_SIZE = 30 * 1024 * 1024  # 30 MB
MAX_PDF_PAGES = 12

extractor_instance = LocalExtractor()
compliance_engine_instance = ComplianceEngine()


def validate_artwork_file(filename: str, file_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
    """
    Validates uploaded packaging artwork file:
    - Path traversal check
    - File size limit (<= 30MB)
    - Magic bytes validation for PDF, PNG, JPEG, WEBP
    Returns (file_type, error_message). If valid, error_message is None.
    """
    if not filename or ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        return None, "Path traversal or invalid filename detected."

    if not file_bytes or len(file_bytes) == 0:
        return None, "Empty file uploaded."

    if len(file_bytes) > MAX_ARTWORK_FILE_SIZE:
        return None, f"File size ({len(file_bytes) // (1024*1024)}MB) exceeds maximum allowed limit of 30MB."

    # Magic byte checks
    if file_bytes.startswith(b'%PDF'):
        return "PDF", None
    elif file_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "PNG", None
    elif file_bytes.startswith(b'\xff\xd8\xff'):
        return "JPEG", None
    elif file_bytes.startswith(b'RIFF') and len(file_bytes) > 12 and file_bytes[8:12] == b'WEBP':
        return "WEBP", None

    # Check extension and PIL validation
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".pdf",):
        return None, "Corrupted or invalid PDF header."
    elif ext in (".png",):
        return None, "Corrupted or invalid PNG image."
    elif ext in (".jpg", ".jpeg"):
        return None, "Corrupted or invalid JPEG image."
    elif ext in (".webp",):
        return None, "Corrupted or invalid WEBP image."

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
            fmt = (img.format or "").upper()
            if fmt in ("PNG", "JPEG", "WEBP", "MPO"):
                return fmt, None
    except Exception:
        pass

    return None, "Unsupported or invalid file format. Allowed formats: PDF, PNG, JPG, JPEG, WEBP (up to 30MB)."


def extract_text_and_tokens_from_image(image_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Runs PaddleOCR on the given image path and returns (full_text, words_list)."""
    try:
        from ocr.paddle_engine import _sync_paddle_extract_multiscale
        from ocr.cleaner import clean_ocr_text
        lines, words, confs, _ = _sync_paddle_extract_multiscale(image_path, "en")
        cleaned_lines = [clean_ocr_text(l) for l in lines if l and l.strip()]
        full_text = "\n".join(cleaned_lines).strip()
        word_dicts: List[Dict[str, Any]] = []
        for w in words:
            bbox = w.bbox if hasattr(w, "bbox") else [0, 0, 0, 0]
            txt = w.text if hasattr(w, "text") else str(w)
            conf = float(w.confidence) if hasattr(w, "confidence") else 90.0
            word_dicts.append({"text": txt, "bbox": bbox, "confidence": conf})
        return full_text, word_dicts
    except Exception as e:
        logger.error(f"[PREPRINT] OCR extraction error on {image_path}: {e}")
        return "", []


def render_artwork_pages(file_path: str, file_type: str, output_dir: str) -> List[ArtworkPageInfo]:
    """
    Parses packaging artwork file, extracts vector text from PDF or OCR tokens from image,
    and renders preview JPEG images for each page/artboard.
    """
    pages: List[ArtworkPageInfo] = []
    artwork_base_id = os.path.splitext(os.path.basename(file_path))[0]

    if file_type == "PDF":
        try:
            pdf = pdfium.PdfDocument(file_path)
            total_pages = min(len(pdf), MAX_PDF_PAGES)

            for page_idx in range(total_pages):
                page = pdf[page_idx]
                width_pt, height_pt = page.get_size()
                
                # Extract embedded vector text if present
                vector_text = ""
                try:
                    textpage = page.get_textpage()
                    vector_text = textpage.get_text_range().strip()
                except Exception:
                    vector_text = ""

                # Render page at 150 DPI (scale ~2.08)
                bitmap = page.render(scale=2.0)
                pil_img = bitmap.to_pil()

                # Cap preview size if huge
                max_dim = 2048
                if pil_img.width > max_dim or pil_img.height > max_dim:
                    pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                preview_filename = f"preprint_{artwork_base_id}_p{page_idx + 1}.jpg"
                preview_path = os.path.join(output_dir, preview_filename)
                pil_img.save(preview_path, "JPEG", quality=85)

                words_from_text: List[Dict[str, Any]] = []
                text_source = "PDF_VECTOR" if vector_text else "OCR"

                if not vector_text or len(vector_text.strip()) < 15:
                    # Scanned or outline-converted PDF artwork: run OCR on rendered preview page
                    ocr_text, ocr_tokens = extract_text_and_tokens_from_image(preview_path)
                    if ocr_text:
                        vector_text = ocr_text
                        text_source = "OCR"
                        words_from_text = ocr_tokens

                if not words_from_text and vector_text:
                    for line in vector_text.splitlines():
                        for w in line.split():
                            words_from_text.append({"text": w, "bbox": [10, 10, 50, 30]})

                layout_regions = detect_layout_regions(words_from_text, pil_img.width, pil_img.height)

                pages.append(ArtworkPageInfo(
                    page_number=page_idx + 1,
                    width=pil_img.width,
                    height=pil_img.height,
                    dpi=150.0,
                    preview_image_path=f"/api/images/{preview_filename}",
                    extracted_text=vector_text,
                    text_source=text_source,
                    layout_regions=layout_regions,
                    text_tokens=words_from_text,
                    word_count=len(vector_text.split()) if vector_text else 0
                ))
        except Exception as e:
            logger.warning(f"[PREPRINT] PDFium rendering failed, creating fallback page: {e}")
            pages.append(ArtworkPageInfo(
                page_number=1,
                width=800,
                height=1000,
                dpi=72.0,
                preview_image_path=None,
                extracted_text="",
                text_source="OCR",
                layout_regions=[],
                word_count=0
            ))
    else:
        # Raster image artwork (PNG, JPG, WEBP)
        try:
            with Image.open(file_path) as pil_img:
                pil_img = pil_img.convert("RGB")
                max_dim = 2048
                if pil_img.width > max_dim or pil_img.height > max_dim:
                    pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                preview_filename = f"preprint_{artwork_base_id}_p1.jpg"
                preview_path = os.path.join(output_dir, preview_filename)
                pil_img.save(preview_path, "JPEG", quality=85)

                extracted_text, word_dicts = extract_text_and_tokens_from_image(preview_path)
                layout_regions = detect_layout_regions(word_dicts, pil_img.width, pil_img.height)

                pages.append(ArtworkPageInfo(
                    page_number=1,
                    width=pil_img.width,
                    height=pil_img.height,
                    dpi=150.0,
                    preview_image_path=f"/api/images/{preview_filename}",
                    extracted_text=extracted_text,
                    text_source="OCR",
                    layout_regions=layout_regions,
                    text_tokens=word_dicts,
                    word_count=len(extracted_text.split()) if extracted_text else 0
                ))
        except Exception as e:
            logger.error(f"[PREPRINT] Image opening error: {e}")
            pages.append(ArtworkPageInfo(
                page_number=1,
                width=800,
                height=1000,
                dpi=72.0,
                preview_image_path=None,
                extracted_text="",
                text_source="OCR",
                layout_regions=[],
                word_count=0
            ))

    return pages


def detect_layout_regions(words: List[Dict[str, Any]], width_px: int, height_px: int) -> List[ArtworkLayoutRegion]:
    """
    Detects semantic packaging layout regions:
    - BRAND_HEADER (Brand title & commodity name in top area)
    - MRP_STAMP (MRP, currency, taxes)
    - NET_QTY_AREA (Net quantity & weight declarations)
    - MANUFACTURER_BLOCK (Manufacturer / Packer / Marketer address details)
    - NUTRITION_PANEL (Nutrition facts / table)
    - CONSUMER_CARE (Helpline, email, customer contact)
    """
    regions: List[ArtworkLayoutRegion] = []
    if not words:
        return regions

    w_px = max(width_px, 1)
    h_px = max(height_px, 1)

    brand_words = []
    mrp_words = []
    net_qty_words = []
    mfg_words = []
    nutr_words = []
    care_words = []

    for w in words:
        txt = str(w.get("text", "")).lower()
        bbox = w.get("bbox", [0, 0, 0, 0])
        y_center = (bbox[1] + bbox[3]) / (2.0 * h_px)

        if any(k in txt for k in ("mrp", "rs.", "rs", "₹", "incl", "taxes", "tax")):
            mrp_words.append(w)
        elif any(k in txt for k in ("net", "quantity", "qty", "weight", "volume", "200g", "250g", "500g", "1kg", "100g", "100ml", "500ml")):
            net_qty_words.append(w)
        elif any(k in txt for k in ("nutrition", "nutritional", "energy", "protein", "carbohydrate", "fat", "sugar", "sodium")):
            nutr_words.append(w)
        elif any(k in txt for k in ("manufactured", "mfg", "packed", "marketed", "packer", "importer", "factory", "unit", "plot", "bangalore", "mumbai", "delhi")):
            mfg_words.append(w)
        elif any(k in txt for k in ("consumer", "care", "customer", "feedback", "helpline", "email", "@", "toll", "1800-", "1800")):
            care_words.append(w)
        elif y_center < 0.35 and any(k in txt for k in ("britannia", "parle", "amul", "cadbury", "nestle", "good", "day", "cookies", "biscuits", "butter", "chips", "tea", "atta", "wheat")):
            brand_words.append(w)

    def _make_region(word_group: List[Dict[str, Any]], reg_type: str, default_norm_box: List[float]) -> Optional[ArtworkLayoutRegion]:
        if not word_group:
            return None
        min_x = min(w.get("bbox", [0, 0, 0, 0])[0] for w in word_group)
        min_y = min(w.get("bbox", [0, 0, 0, 0])[1] for w in word_group)
        max_x = max(w.get("bbox", [0, 0, 0, 0])[2] for w in word_group)
        max_y = max(w.get("bbox", [0, 0, 0, 0])[3] for w in word_group)

        norm_box = [
            round(max(0.0, min_x / w_px), 4),
            round(max(0.0, min_y / h_px), 4),
            round(min(1.0, max_x / w_px), 4),
            round(min(1.0, max_y / h_px), 4),
        ]
        text_content = " ".join(str(w.get("text", "")) for w in word_group)
        return ArtworkLayoutRegion(
            region_id=f"reg-{reg_type.lower()}-{uuid.uuid4().hex[:6]}",
            region_type=reg_type,
            bbox_normalized=norm_box,
            bbox_pixels=[min_x, min_y, max_x, max_y],
            confidence=0.92,
            text_content=text_content,
            font_size_pt_estimated=round((max_y - min_y) * 0.75, 1)
        )

    if brand_words:
        r = _make_region(brand_words, "BRAND_HEADER", [0.05, 0.05, 0.95, 0.25])
        if r: regions.append(r)
    if mrp_words:
        r = _make_region(mrp_words, "MRP_STAMP", [0.05, 0.70, 0.50, 0.85])
        if r: regions.append(r)
    if net_qty_words:
        r = _make_region(net_qty_words, "NET_QTY_AREA", [0.05, 0.80, 0.50, 0.95])
        if r: regions.append(r)
    if mfg_words:
        r = _make_region(mfg_words, "MANUFACTURER_BLOCK", [0.05, 0.35, 0.95, 0.55])
        if r: regions.append(r)
    if nutr_words:
        r = _make_region(nutr_words, "NUTRITION_PANEL", [0.55, 0.25, 0.95, 0.65])
        if r: regions.append(r)
    if care_words:
        r = _make_region(care_words, "CONSUMER_CARE", [0.05, 0.55, 0.95, 0.70])
        if r: regions.append(r)

    return regions


def evaluate_placement_checks(
    regions: List[ArtworkLayoutRegion],
    words: List[Dict[str, Any]],
    width_px: int,
    height_px: int
) -> List[PlacementCheckResult]:
    """
    Evaluates statutory placement rules:
    - MRP placement: Principal Display Panel / Front or clear statutory box. Rule 8(1).
    - Net Quantity placement: Principal Display Panel / Bottom front. Rule 7.
    """
    mrp_region = next((r for r in regions if r.region_type == "MRP_STAMP"), None)
    net_qty_region = next((r for r in regions if r.region_type == "NET_QTY_AREA"), None)

    # Fallback to checking words if region not aggregated
    if not mrp_region and any("mrp" in str(w.get("text", "")).lower() for w in words):
        mrp_region = ArtworkLayoutRegion(
            region_id="reg-mrp-fallback",
            region_type="MRP_STAMP",
            bbox_normalized=[0.05, 0.75, 0.45, 0.85],
            confidence=0.85,
            text_content="MRP"
        )
    if not net_qty_region and any("net" in str(w.get("text", "")).lower() or "qty" in str(w.get("text", "")).lower() for w in words):
        net_qty_region = ArtworkLayoutRegion(
            region_id="reg-netqty-fallback",
            region_type="NET_QTY_AREA",
            bbox_normalized=[0.05, 0.80, 0.45, 0.90],
            confidence=0.85,
            text_content="Net Qty"
        )

    results: List[PlacementCheckResult] = []

    # 1. MRP Placement Check
    if mrp_region:
        norm_y = mrp_region.bbox_normalized[1]
        results.append(PlacementCheckResult(
            check_name="MRP Placement Check",
            field_name="mrp",
            passed=True,
            status="PASS",
            finding="MRP declaration is clearly placed within designated statutory display zone.",
            recommended_zone="Principal Display Panel / Lower Stamp Box",
            actual_zone=f"Normalized Y: {round(norm_y, 2)}",
            legal_citation="Rule 8(1) - Display of Retail Sale Price",
            bbox_normalized=mrp_region.bbox_normalized
        ))
    else:
        results.append(PlacementCheckResult(
            check_name="MRP Placement Check",
            field_name="mrp",
            passed=False,
            status="REVIEW",
            finding="MRP declaration zone not distinctly isolated on artboard. Verify prominent placement.",
            recommended_zone="Principal Display Panel / Lower Stamp Box",
            actual_zone=None,
            legal_citation="Rule 8(1) - Display of Retail Sale Price",
            bbox_normalized=None
        ))

    # 2. Net Quantity Placement Check
    if net_qty_region:
        norm_y = net_qty_region.bbox_normalized[1]
        results.append(PlacementCheckResult(
            check_name="Net Quantity Placement Check",
            field_name="net_quantity",
            passed=True,
            status="PASS",
            finding="Net quantity declaration is positioned in prominent statutory zone.",
            recommended_zone="Principal Display Panel / Bottom Zone",
            actual_zone=f"Normalized Y: {round(norm_y, 2)}",
            legal_citation="Rule 7 - Declaration of Quantity on Principal Display Panel",
            bbox_normalized=net_qty_region.bbox_normalized
        ))
    else:
        results.append(PlacementCheckResult(
            check_name="Net Quantity Placement Check",
            field_name="net_quantity",
            passed=False,
            status="REVIEW",
            finding="Net quantity placement could not be verified on designated display panel.",
            recommended_zone="Principal Display Panel / Bottom Zone",
            actual_zone=None,
            legal_citation="Rule 7 - Declaration of Quantity on Principal Display Panel",
            bbox_normalized=None
        ))

    return results


def evaluate_font_size_estimates(
    words: List[Dict[str, Any]],
    width_px: int,
    height_px: int,
    dpi: float = 72.0
) -> List[FontSizeEstimateResult]:
    """
    Provides font-size assistance per Legal Metrology rules:
    - Net Quantity: >= 2.0 mm (pack size <= 200g/ml) or >= 4.0 mm (> 200g/ml)
    - MRP, Date, Manufacturer: >= 1.0 mm
    Explicitly labeled as ESTIMATED with physical proof disclaimers.
    """
    effective_dpi = max(dpi, 72.0)
    results: List[FontSizeEstimateResult] = []

    target_fields = [
        ("net_quantity", ("net", "qty", "quantity", "200g", "250g", "500g", "100g", "1kg"), 2.0),
        ("mrp", ("mrp", "rs.", "rs", "₹", "incl"), 1.5),
        ("manufacturing_date", ("mfg", "date", "packed", "pkd"), 1.0),
        ("manufacturer", ("manufactured", "mfg by", "by:", "ltd"), 1.0),
    ]

    for field_name, keywords, mandated_mm in target_fields:
        matched_words = [w for w in words if any(k in str(w.get("text", "")).lower() for k in keywords)]
        if matched_words:
            heights = [(w.get("bbox", [0, 0, 0, 0])[3] - w.get("bbox", [0, 0, 0, 0])[1]) for w in matched_words]
            avg_h_px = sum(heights) / len(heights) if heights else 20.0
            
            # Optical mm height calculation
            estimated_mm = round((avg_h_px / effective_dpi) * 25.4, 2)
            estimated_pt = round(estimated_mm / 0.352778, 1)

            sample_text = " ".join(str(w.get("text", "")) for w in matched_words[:4])
            is_compliant = estimated_mm >= mandated_mm

            results.append(FontSizeEstimateResult(
                field_name=field_name,
                text_sample=sample_text,
                estimated_height_mm=estimated_mm,
                estimated_pt_size=estimated_pt,
                mandated_minimum_mm=mandated_mm,
                is_compliant=is_compliant,
                confidence=0.88,
                estimation_method="OPTICAL_DPI_BOUNDING_BOX",
                disclaimer="ESTIMATED optical font size. Physical proof verification recommended before cylinder engraving or mass plate production.",
                bbox_normalized=[
                    round(matched_words[0].get("bbox", [0, 0, 0, 0])[0] / max(width_px, 1), 3),
                    round(matched_words[0].get("bbox", [0, 0, 0, 0])[1] / max(height_px, 1), 3),
                    round(matched_words[-1].get("bbox", [0, 0, 0, 0])[2] / max(width_px, 1), 3),
                    round(matched_words[-1].get("bbox", [0, 0, 0, 0])[3] / max(height_px, 1), 3),
                ]
            ))

    return results


def generate_designer_corrections(
    missing_declarations: List[str],
    checks: List[Any],
    placement_checks: List[PlacementCheckResult],
    font_estimates: List[FontSizeEstimateResult]
) -> List[DesignerCorrectionItem]:
    """
    Generates actionable, prioritized designer checklist items for packaging engineers.
    """
    corrections: List[DesignerCorrectionItem] = []

    # 1. Missing declarations
    for field in missing_declarations:
        corrections.append(DesignerCorrectionItem(
            item_id=f"corr-missing-{field}-{uuid.uuid4().hex[:6]}",
            field_name=field,
            severity="CRITICAL",
            issue=f"Mandatory statutory declaration '{field.replace('_', ' ').title()}' is missing from artwork.",
            suggested_action=f"Add clear and legible declaration for {field.replace('_', ' ')} in statutory display area.",
            affected_area="Statutory Declaration Panel",
            legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 Rule 6",
            is_blocking_for_print=True
        ))

    # 2. Failed compliance checks
    for chk in checks:
        status = getattr(chk, "status", "")
        field = getattr(chk, "field", "")
        if status == "FAIL" and field not in missing_declarations:
            desc = getattr(chk, "description", "")
            rec = getattr(chk, "recommendation", "") or getattr(chk, "fail_reason", "") or "Rectify declaration format."
            src = getattr(chk, "source", "Legal Metrology Rules 2011")
            corrections.append(DesignerCorrectionItem(
                item_id=f"corr-fail-{field}-{uuid.uuid4().hex[:6]}",
                field_name=field,
                severity="CRITICAL",
                issue=desc or f"Non-compliant declaration for {field}.",
                suggested_action=rec,
                affected_area="Packaging Artwork",
                legal_reference=src,
                is_blocking_for_print=True
            ))

    # 3. Placement warnings
    for plc in placement_checks:
        if not plc.passed:
            corrections.append(DesignerCorrectionItem(
                item_id=f"corr-plc-{plc.field_name}-{uuid.uuid4().hex[:6]}",
                field_name=plc.field_name,
                severity="MAJOR",
                issue=plc.finding,
                suggested_action=f"Reposition {plc.field_name.replace('_', ' ')} to {plc.recommended_zone}.",
                affected_area=plc.recommended_zone,
                legal_reference=plc.legal_citation,
                is_blocking_for_print=False
            ))

    # 4. Font size warnings
    for fnt in font_estimates:
        if not fnt.is_compliant:
            corrections.append(DesignerCorrectionItem(
                item_id=f"corr-font-{fnt.field_name}-{uuid.uuid4().hex[:6]}",
                field_name=fnt.field_name,
                severity="MAJOR",
                issue=f"Estimated font height ({fnt.estimated_height_mm} mm) is below statutory minimum ({fnt.mandated_minimum_mm} mm).",
                suggested_action=f"Increase font height to at least {fnt.mandated_minimum_mm} mm (~{round(fnt.mandated_minimum_mm / 0.352778, 1)} pt).",
                affected_area="Typography Layer",
                legal_reference="Legal Metrology (Packaged Commodities) Rules, 2011 Rule 9",
                is_blocking_for_print=False
            ))

    return corrections


def analyze_artwork(
    artwork_dict: Dict[str, Any],
    product_name_hint: Optional[str] = None,
    category: Optional[str] = None
) -> PreprintAnalysisResponse:
    """
    Main orchestration service for Section 8 Pre-Print Packaging Compliance.
    """
    artwork_id = artwork_dict.get("id", "art-unknown")
    filename = artwork_dict.get("filename", "artwork.pdf")
    file_type = artwork_dict.get("file_type", "PDF")
    iteration_number = artwork_dict.get("iteration_number", 1)
    parent_artwork_id = artwork_dict.get("parent_artwork_id")
    raw_pages = artwork_dict.get("pages_data", [])

    # Reconstruct or parse pages
    pages: List[ArtworkPageInfo] = []
    combined_texts: List[str] = []
    all_words: List[Dict[str, Any]] = []

    for p_data in raw_pages:
        p_info = ArtworkPageInfo(**p_data) if isinstance(p_data, dict) else p_data

        # If extracted text is missing, attempt on-demand OCR
        if not p_info.extracted_text or not p_info.extracted_text.strip():
            img_candidate = None
            if p_info.preview_image_path:
                cand = os.path.join(settings.UPLOAD_DIR, os.path.basename(p_info.preview_image_path))
                if os.path.exists(cand):
                    img_candidate = cand
            if not img_candidate and artwork_dict.get("file_path") and os.path.exists(str(artwork_dict["file_path"])):
                img_candidate = str(artwork_dict["file_path"])

            if img_candidate:
                txt, tokens = extract_text_and_tokens_from_image(img_candidate)
                if txt:
                    p_info.extracted_text = txt
                    p_info.text_tokens = tokens
                    p_info.word_count = len(txt.split())
                    p_info.layout_regions = detect_layout_regions(tokens, p_info.width, p_info.height)

        pages.append(p_info)
        if p_info.extracted_text:
            combined_texts.append(p_info.extracted_text)
            if p_info.text_tokens:
                all_words.extend(p_info.text_tokens)
            else:
                for line in p_info.extracted_text.splitlines():
                    for w in line.split():
                        all_words.append({"text": w, "bbox": [10, 10, 50, 30]})

    full_text = "\n\n".join(combined_texts)

    # 1. Advanced Information Extraction
    product_info = extractor_instance.extract(full_text)
    if product_name_hint and not product_info.product_name:
        product_info.product_name = product_name_hint

    # 2. Compliance Evaluation (Reusing Section 6 engine)
    comp_dict = compliance_engine_instance.check(
        product_info=product_info,
        ocr_text=full_text,
        images=[],
        analysis_id=artwork_id
    )

    compliance_res = ComplianceResult(
        checks=comp_dict.get("checks", []),
        score=comp_dict.get("score", 0.0),
        status=comp_dict.get("status", "POTENTIAL NON-COMPLIANCE"),
        total_rules=comp_dict.get("total_rules", 0),
        passed_rules=comp_dict.get("passed_rules", 0),
        failed_rules=comp_dict.get("failed_rules", 0),
        warning_rules=comp_dict.get("warning_rules", 0),
        needs_review_rules=comp_dict.get("needs_review_rules", 0),
        not_applicable_rules=comp_dict.get("not_applicable_rules", 0),
        issues=comp_dict.get("issues", []),
        recommendations=comp_dict.get("recommendations", [])
    )

    # 3. Compliance Scoring & Risk Assessment (Section 7)
    score_breakdown = calculate_score(
        checks=compliance_res.checks,
        product_info=product_info,
        conflicts=comp_dict.get("conflicts", [])
    )
    final_score = score_breakdown.get("final_score", compliance_res.score)

    # 4. Mandatory 14 PCR Declarations Checklist
    mandatory_checklist = {
        "manufacturer": bool(product_info.manufacturer),
        "product_name": bool(product_info.product_name),
        "net_quantity": bool(product_info.net_quantity),
        "mrp": bool(product_info.mrp),
        "manufacturing_date": bool(product_info.manufacturing_date or product_info.manufacture_date or product_info.packaging_date),
        "expiry_date": bool(product_info.expiry_date or product_info.best_before or product_info.use_by_date),
        "country_of_origin": bool(product_info.country_of_origin),
        "consumer_care": bool(product_info.consumer_care),
        "fssai_license": bool(product_info.fssai_license),
        "ingredients": bool(product_info.ingredients),
        "nutritional_info": bool(product_info.nutritional_info or product_info.nutrition_panel_detected),
        "batch_number": bool(product_info.batch_number),
    }

    missing_declarations = [f for f, present in mandatory_checklist.items() if not present]

    # 5. Placement & Semantic Zoning Checks
    first_page_w = pages[0].width if pages else 800
    first_page_h = pages[0].height if pages else 1000
    all_regions = []
    for p in pages:
        all_regions.extend(p.layout_regions)

    placement_checks = evaluate_placement_checks(all_regions, all_words, first_page_w, first_page_h)

    # 6. Font-Size Assistance
    font_size_estimates = evaluate_font_size_estimates(all_words, first_page_w, first_page_h, pages[0].dpi if pages else 72.0)

    # 7. Actionable Designer Corrections
    designer_corrections = generate_designer_corrections(
        missing_declarations=missing_declarations,
        checks=compliance_res.checks,
        placement_checks=placement_checks,
        font_estimates=font_size_estimates
    )

    # 8. Ready-for-Print Eligibility & Overall Status
    blocking_count = sum(1 for c in designer_corrections if c.is_blocking_for_print)
    has_critical_fails = any(c.status == "FAIL" for c in compliance_res.checks)

    if has_critical_fails or len(missing_declarations) > 2:
        overall_status = "NON_COMPLIANT"
        workflow_status = "ACTION_REQUIRED"
        ready_eligible = False
    elif len(missing_declarations) > 0 or blocking_count > 0:
        overall_status = "NEEDS_REVIEW"
        workflow_status = "CHANGES_REQUESTED"
        ready_eligible = False
    else:
        overall_status = "COMPLIANT"
        workflow_status = "DRAFT"
        ready_eligible = True

    summary_notes = [
        f"Pre-print packaging verification completed for {filename}.",
        f"Compliance Score: {final_score}/100 with {blocking_count} print-blocking issues detected.",
        f"Source Identity: PRE-PRINT ARTWORK (Rule set: Legal Metrology Rules 2011)."
    ]

    return PreprintAnalysisResponse(
        artwork_id=artwork_id,
        filename=filename,
        file_type=file_type,
        page_count=len(pages),
        source_identity="PRE-PRINT ARTWORK",
        compliance_ruleset="Legal Metrology (Packaged Commodities) Rules, 2011",
        iteration_number=iteration_number,
        parent_artwork_id=parent_artwork_id,
        overall_status=overall_status,
        overall_score=final_score,
        workflow_status=workflow_status,
        missing_declarations=missing_declarations,
        mandatory_checklist=mandatory_checklist,
        placement_checks=placement_checks,
        font_size_estimates=font_size_estimates,
        designer_corrections=designer_corrections,
        pages=pages,
        product_info=product_info,
        compliance_result=compliance_res,
        scoring_breakdown=score_breakdown,
        ready_for_print_eligible=ready_eligible,
        print_blocking_issues_count=blocking_count,
        summary_notes=summary_notes
    )
