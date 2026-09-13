import os
import uuid
from datetime import datetime
from utils.datetime_utils import get_current_utc_iso
from fastapi import UploadFile
from config import settings
from ocr.factory import get_ocr_engine
from extraction.llm_extractor import llm_extractor
from compliance.engine import engine as compliance_engine
from compliance.rules.legal_metrology import compute_font_size_and_readability
from database.db import save_analysis
from typing import List, Optional
from models.schemas import AnalysisResponse, OCRResult, ProductInfo, ComplianceResult, ProductImageEvidence
from services.image_service import process_and_save_image
from integrations.fssai.verifier import fssai_verifier
from integrations.gs1.verifier import gs1_verifier
from services.calibration_service import calibration_service

async def analyze_products(files: List[UploadFile], labels: Optional[List[str]] = None, owner_user_id: Optional[str] = None) -> AnalysisResponse:
    analysis_id = str(uuid.uuid4())
    ocr_engine = get_ocr_engine()
    
    default_labels = ["Front", "Back", "Side 1", "Side 2", "Side 3", "Side 4"]
    image_evidences: List[ProductImageEvidence] = []
    all_words = []
    total_processing_time = 0.0

    # ── Phase 1 (fast, sequential): save + quality-assess each image ──
    pending: List[tuple] = []  # (evidence, image_path) to OCR in Phase 2
    for idx, file in enumerate(files):
        label = "Front"
        if labels and idx < len(labels) and labels[idx]:
            label = str(labels[idx]).strip()
        elif idx < len(default_labels):
            label = default_labels[idx]
        else:
            label = f"Image {idx+1}"

        safe_label = label.lower().replace(' ', '_')
        image_filename = f"{analysis_id}_{safe_label}_{file.filename}"
        image_path = os.path.join(settings.UPLOAD_DIR, image_filename)

        # 1. Save and preprocess image
        await process_and_save_image(file, image_path)

        # 1b. Assess image quality
        from ocr.quality import assess_image_quality
        quality_data = assess_image_quality(image_path)

        ev = ProductImageEvidence(
            filename=image_filename,
            image_url=f"/uploads/{image_filename}",
            label=label,
            image_quality=quality_data,
            quality_warning=quality_data.get('warning')
        )
        image_evidences.append(ev)
        pending.append((ev, image_path))

    # ── Phase 2 (parallel): OCR all images concurrently ──
    import asyncio as _asyncio
    ocr_results = await _asyncio.gather(
        *[ocr_engine.extract(path) for _, path in pending]
    )

    # ── Phase 3: fill per-image OCR evidence (order preserved) ──
    for (ev, _path), ocr_res in zip(pending, ocr_results):
        total_processing_time += ocr_res.processing_time
        all_words.extend(ocr_res.words)
        ev.ocr_text = ocr_res.full_text
        ev.words = ocr_res.words
        ev.word_count = ocr_res.word_count or len(ocr_res.words) or len(ocr_res.full_text.split())
        ev.average_confidence = ocr_res.average_confidence
        ev.preprocessing_variant = ocr_res.preprocessing_variant

    # 4. Combine OCR text across all images
    if len(image_evidences) == 1:
        combined_text = image_evidences[0].ocr_text
    else:
        combined_text = "\n\n".join([
            f"=== [{ev.label.upper()} LABEL] ===\n{ev.ocr_text}"
            for ev in image_evidences
        ])
        
    avg_conf = round(sum(ev.average_confidence for ev in image_evidences) / len(image_evidences), 1) if image_evidences else 0.0
    total_words = sum(ev.word_count for ev in image_evidences)
    total_regions = sum(r.regions_processed for r in ocr_results) if ocr_results else 0
    
    # Check overall quality warnings
    quality_warnings = [ev.quality_warning for ev in image_evidences if ev.quality_warning]
    combined_quality_warning = " | ".join(quality_warnings) if quality_warnings else None

    primary_ocr = ocr_results[0] if ocr_results else None
    active_engine_name = primary_ocr.engine if primary_ocr else "PaddleOCR (PP-OCRv4)"
    active_variant = primary_ocr.preprocessing_variant if primary_ocr else "Deep Learning Det + Rec"
    ocr_passes_count = sum(r.ocr_passes for r in ocr_results) if ocr_results else 1

    combined_ocr_result = OCRResult(
        full_text=combined_text,
        words=all_words,
        language="eng",
        processing_time=round(total_processing_time, 2),
        average_confidence=avg_conf,
        word_count=total_words,
        engine=active_engine_name,
        preprocessing_variant=active_variant,
        regions_processed=total_regions,
        ocr_passes=ocr_passes_count
    )
    
    # 5. Extract structured info from combined OCR text with per-image provenance
    product_info = llm_extractor.extract(combined_text, images=image_evidences)
    
    # 6. Compliance check with visual proof localization
    comp_result_dict = compliance_engine.check(product_info, ocr_text=combined_text, images=image_evidences, analysis_id=analysis_id)
    compliance_result = ComplianceResult(**comp_result_dict)
    
    # 6B. Physical Calibration & Rule 12 Font Size Analysis
    primary_img_path = pending[0][1] if pending else None
    calibration_result = None
    if primary_img_path:
        calibration_result = calibration_service.detect_aruco_marker(primary_img_path)

    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        ocr_result=combined_ocr_result,
        images=image_evidences,
        checks=compliance_result.checks,
        calibration_result=calibration_result
    )
    
    # 6C. External Verifications (FSSAI Licence & GS1 Barcode)
    fssai_verification = await fssai_verifier.verify(product_info.fssai_license)
    barcode_val = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
    gs1_verification = await gs1_verifier.verify(barcode_val)

    primary_filename = image_evidences[0].filename if image_evidences else ""
    primary_image_url = image_evidences[0].image_url if image_evidences else "/placeholder.png"
    created_at = get_current_utc_iso()
    
    # 7. Save to DB
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': primary_filename,
        'ocr_text': combined_text,
        'extracted_data': product_info.model_dump(),
        'compliance_result': compliance_result.model_dump(),
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [ev.model_dump() for ev in image_evidences],
        'owner_user_id': owner_user_id or ""
    }
    await save_analysis(db_data)
    
    return AnalysisResponse(
        id=analysis_id,
        product_name=db_data['product_name'],
        image_url=primary_image_url,
        images=image_evidences,
        ocr_result=combined_ocr_result,
        product_info=product_info,
        compliance_result=compliance_result,
        recommendations=compliance_result.recommendations,
        created_at=created_at,
        image_quality_warning=combined_quality_warning,
        font_size_analysis=font_size_analysis,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification,
        calibration_result=calibration_result,
        owner_user_id=owner_user_id or ""
    )

async def analyze_product(file: UploadFile) -> AnalysisResponse:
    return await analyze_products([file], ["Front"])


async def analyze_text(text: str, owner_user_id: Optional[str] = None) -> AnalysisResponse:
    """Analyze raw product listing or label text without images."""
    analysis_id = str(uuid.uuid4())
    
    # 1. Extract structured info from input text
    product_info = llm_extractor.extract(text)
    
    # 2. Compliance check
    comp_result_dict = compliance_engine.check(product_info, ocr_text=text, images=[])
    compliance_result = ComplianceResult(**comp_result_dict)
    
    # 3. Create minimal OCRResult for text input
    ocr_res = OCRResult(
        full_text=text,
        words=[],
        language="eng",
        processing_time=0.0,
        average_confidence=0.0,
        word_count=len(text.split()),
        engine="Product Listing Text Input",
        preprocessing_variant="None",
        regions_processed=0,
        ocr_passes=1
    )
    
    # 4. Font size & readability analysis
    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        ocr_result=ocr_res,
        images=[],
        checks=compliance_result.checks
    )

    # 5. External Verifications
    fssai_verification = await fssai_verifier.verify(product_info.fssai_license)
    barcode_val = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
    gs1_verification = await gs1_verifier.verify(barcode_val)
    
    created_at = get_current_utc_iso()
    
    # 6. Save to DB
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': "",
        'ocr_text': text,
        'extracted_data': product_info.model_dump(),
        'compliance_result': compliance_result.model_dump(),
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [],
        'owner_user_id': owner_user_id or ""
    }
    await save_analysis(db_data)
    
    return AnalysisResponse(
        id=analysis_id,
        product_name=db_data['product_name'],
        image_url="/placeholder.png",
        images=[],
        ocr_result=ocr_res,
        product_info=product_info,
        compliance_result=compliance_result,
        recommendations=compliance_result.recommendations,
        created_at=created_at,
        image_quality_warning=None,
        font_size_analysis=font_size_analysis,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification,
        calibration_result=None,
        owner_user_id=owner_user_id or ""
    )
