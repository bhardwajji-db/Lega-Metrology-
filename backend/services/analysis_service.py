import os
import uuid
import time
import logging
from datetime import datetime
from utils.datetime_utils import get_current_utc_iso
from fastapi import UploadFile, HTTPException
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
from integrations.cross_checker import cross_check_engine
from services.calibration_service import calibration_service
from vision.pipeline import vision_pipeline
from services.integrity_service import compute_analysis_integrity_hash
from services.identity.identity_service import identity_service
from services.external_verification_pipeline import external_verification_pipeline
from services.barcode_service import BarcodeItem
from version import SYSTEM_VERSION, OCR_PIPELINE_VERSION, COMPLIANCE_RULESET_VERSION
from claims.engine import claim_engine

logger = logging.getLogger(__name__)

async def analyze_products(
    files: List[UploadFile],
    labels: Optional[List[str]] = None,
    owner_user_id: Optional[str] = None,
    organization_id: Optional[str] = None
) -> AnalysisResponse:
    start_total_time = time.perf_counter()
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

        t_pre0 = time.perf_counter()
        # 1. Save and preprocess image
        await process_and_save_image(file, image_path)

        # 1b. Assess image quality
        from ocr.quality import assess_image_quality
        quality_data = assess_image_quality(image_path)
        t_pre = (time.perf_counter() - t_pre0) * 1000
        logger.info(f"[PERF] {label} image preprocessing: {t_pre:.1f} ms")

        ev = ProductImageEvidence(
            filename=image_filename,
            image_url=f"/api/images/{image_filename}",
            label=label,
            image_quality=quality_data,
            quality_warning=quality_data.get('warning')
        )
        image_evidences.append(ev)
        pending.append((ev, image_path))

    # ── Phase 2 (parallel): OCR all images concurrently ──
    t_ocr_all0 = time.perf_counter()
    import asyncio as _asyncio
    ocr_results = await _asyncio.gather(
        *[ocr_engine.extract(path) for _, path in pending]
    )
    t_ocr_all = (time.perf_counter() - t_ocr_all0) * 1000
    for (ev, _path), ocr_res in zip(pending, ocr_results):
        logger.info(f"[PERF] {ev.label} OCR: {ocr_res.processing_time * 1000:.1f} ms (passes: {ocr_res.ocr_passes})")
    logger.info(f"[PERF] Combined OCR Phase: {t_ocr_all:.1f} ms")

    # ── Phase 3: fill per-image OCR evidence & run Computer Vision Analysis ──
    for idx, ((ev, _path), ocr_res) in enumerate(zip(pending, ocr_results)):
        total_processing_time += ocr_res.processing_time
        all_words.extend(ocr_res.words)
        ev.ocr_text = ocr_res.full_text
        ev.words = ocr_res.words
        ev.word_count = ocr_res.word_count or len(ocr_res.words) or len(ocr_res.full_text.split())
        ev.average_confidence = ocr_res.average_confidence
        ev.preprocessing_variant = ocr_res.preprocessing_variant

        # Run Computer Vision Intelligence Pipeline
        try:
            t_vis0 = time.perf_counter()
            words_dict = [w.model_dump() if hasattr(w, 'model_dump') else w for w in ocr_res.words]
            ev.vision_analysis = vision_pipeline.analyze_image(
                image_path=_path,
                ocr_text=ocr_res.full_text,
                words=words_dict,
                image_index=idx,
                image_label=ev.label
            )
            t_vis = (time.perf_counter() - t_vis0) * 1000
            logger.info(f"[PERF] {ev.label} Computer Vision Analysis: {t_vis:.1f} ms")
        except Exception as e:
            logger.warning(f"[VISION] Failed for image {ev.label}: {e}")

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

    # 5. Extract structured info from combined OCR text with per-image provenance
    t_ext0 = time.perf_counter()
    product_info = llm_extractor.extract(combined_text, images=image_evidences)
    t_ext = (time.perf_counter() - t_ext0) * 1000
    logger.info(f"[PERF] Structured Extraction: {t_ext:.1f} ms")

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
        ocr_passes=ocr_passes_count,
        multilingual=getattr(product_info, 'multilingual', None)
    )
    
    # 6. Compliance check with visual proof localization
    t_comp0 = time.perf_counter()
    comp_result_dict = compliance_engine.check(product_info, ocr_text=combined_text, images=image_evidences, analysis_id=analysis_id)
    compliance_result = ComplianceResult(**comp_result_dict)
    t_comp = (time.perf_counter() - t_comp0) * 1000
    logger.info(f"[PERF] Compliance & Evidence: {t_comp:.1f} ms")
    
    # 6B. Physical Calibration & Rule 12 Font Size Analysis
    t_font0 = time.perf_counter()
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
    t_font = (time.perf_counter() - t_font0) * 1000
    logger.info(f"[PERF] Calibration & Font Size Analysis: {t_font:.1f} ms")
    
    # 6C. Comprehensive 3-Layer External Product & Licence Verification Pipeline
    image_paths_list = [p for _, p in pending]
    pipeline_result = await external_verification_pipeline.run_pipeline(
        image_paths=image_paths_list,
        ocr_text=combined_text,
        product_info=product_info,
        image_evidences=image_evidences
    )

    # Sync barcode and FSSAI from image decoder into product_info if available
    if pipeline_result.barcode_extractions and not product_info.barcode_detected:
        product_info.barcode_detected = pipeline_result.barcode_extractions[0].value
    if pipeline_result.fssai_extraction.detected and not product_info.fssai_license:
        product_info.fssai_license = pipeline_result.fssai_extraction.number

    fssai_verification = await fssai_verifier.verify(product_info.fssai_license)
    barcode_val = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
    gs1_verification = await gs1_verifier.verify(barcode_val)

    # 6D. Cross-Checking & Statutory Consistency Evaluation (Section 13)
    qr_payload_val = None
    for ev in image_evidences:
        if ev.vision_analysis and ev.vision_analysis.qr_code and ev.vision_analysis.qr_code.detected:
            qr_payload_val = ev.vision_analysis.qr_code.decoded_payload
            if qr_payload_val:
                break
    if not qr_payload_val:
        for be in pipeline_result.barcode_extractions:
            if be.qr_payload:
                qr_payload_val = be.qr_payload
                break

    external_verification = cross_check_engine.evaluate_all(
        extracted_data=product_info.model_dump(),
        fssai_record=fssai_verification,
        gs1_record=gs1_verification,
        qr_payload=qr_payload_val,
        barcode_detected=barcode_val,
        offline_mode=False
    )

    primary_filename = image_evidences[0].filename if image_evidences else ""
    primary_image_url = image_evidences[0].image_url if image_evidences else "/placeholder.png"
    created_at = get_current_utc_iso()
    
    # 7. Compute deterministic cryptographic integrity hash (Section 15)
    extracted_dict = product_info.model_dump()
    compliance_dict = compliance_result.model_dump()
    integrity_hash = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_info.product_name or 'Unknown Product',
        score=compliance_result.score,
        status=compliance_result.status,
        extracted_data=extracted_dict,
        compliance_result=compliance_dict
    )

    # Convert pipeline barcode extractions to BarcodeItem instances for identity_service
    b_items_adapted = []
    for be in pipeline_result.barcode_extractions:
        b_items_adapted.append(BarcodeItem(
            raw_value=be.value or "",
            symbology=be.type,
            bbox=be.evidence_bbox,
            confidence=be.confidence,
            is_valid_checksum=be.is_valid_checksum,
            country_of_origin=be.country_of_origin,
            country_flag=be.country_flag,
            gs1_prefix=be.gs1_prefix,
            image_id=be.evidence_image
        ))

    # Extract Product Identity & Verification Provenance with complete image & external data
    prod_identity = identity_service.extract_identity(
        product_info=product_info,
        ocr_text=combined_text,
        images=image_evidences,
        image_paths=image_paths_list,
        barcode_items=b_items_adapted,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification
    )

    # 7C. Misleading Claim Detection Engine
    t_claim0 = time.perf_counter()
    claims_analysis = claim_engine.analyze(
        product_info=product_info,
        ocr_text=combined_text,
        images=image_evidences
    )
    t_claim = (time.perf_counter() - t_claim0) * 1000
    logger.info(f"[PERF] Misleading Claim Detection: {t_claim:.1f} ms (claims: {claims_analysis.claims_detected})")

    # 8. Save to DB
    t_db0 = time.perf_counter()
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': primary_filename,
        'ocr_text': combined_text,
        'extracted_data': extracted_dict,
        'compliance_result': compliance_dict,
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [ev.model_dump() for ev in image_evidences],
        'owner_user_id': owner_user_id or "",
        'organization_id': organization_id or "",
        'integrity_hash': integrity_hash,
        'system_version': SYSTEM_VERSION,
        'ocr_engine_version': OCR_PIPELINE_VERSION,
        'ruleset_version': COMPLIANCE_RULESET_VERSION,
        'product_identity': prod_identity.model_dump(),
        'external_product_verification': pipeline_result.model_dump(),
        'external_verification': external_verification.model_dump() if hasattr(external_verification, 'model_dump') else external_verification,
        'claims_analysis': claims_analysis.model_dump()
    }
    await save_analysis(db_data)
    try:
        from services.review_service import get_or_create_review
        await get_or_create_review(analysis_id)
    except Exception as e:
        logger.warning(f"[REVIEW] Auto-create review failed for analysis {analysis_id}: {e}")
    t_db = (time.perf_counter() - t_db0) * 1000
    logger.info(f"[PERF] DB Save: {t_db:.1f} ms")

    t_total_analysis = (time.perf_counter() - start_total_time) * 1000
    logger.info(f"[PERF] TOTAL Backend Analysis: {t_total_analysis:.1f} ms ({t_total_analysis/1000:.2f} s)")
    
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
        owner_user_id=owner_user_id or "",
        organization_id=organization_id or "",
        multilingual=getattr(product_info, 'multilingual', None),
        vision_analysis=image_evidences[0].vision_analysis if image_evidences else None,
        external_verification=external_verification,
        integrity_hash=integrity_hash,
        system_version=SYSTEM_VERSION,
        ocr_engine_version=OCR_PIPELINE_VERSION,
        ruleset_version=COMPLIANCE_RULESET_VERSION,
        product_identity=prod_identity,
        cross_validation=getattr(prod_identity, 'cross_validation', None),
        external_product_verification=pipeline_result,
        claims_analysis=claims_analysis
    )

async def analyze_product(file: UploadFile) -> AnalysisResponse:
    return await analyze_products([file], ["Front"])


async def analyze_text(
    text: str,
    owner_user_id: Optional[str] = None,
    organization_id: Optional[str] = None
) -> AnalysisResponse:
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
    
    # 4. Font size analysis placeholder for text
    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        ocr_result=ocr_res,
        images=[],
        checks=compliance_result.checks
    )

    # 5. Comprehensive 3-Layer External Verification for text mode
    pipeline_result = await external_verification_pipeline.run_pipeline(
        image_paths=[],
        ocr_text=text,
        product_info=product_info,
        image_evidences=[]
    )

    fssai_match = None
    if product_info.fssai_license:
        fssai_match = await fssai_verifier.verify(product_info.fssai_license)
    fssai_verification = fssai_match

    barcode_val = product_info.barcode_detected or getattr(product_info, 'barcode', None) or (product_info.other_declarations.get('barcode') if product_info.other_declarations else None)
    gs1_match = None
    if barcode_val:
        gs1_match = await gs1_verifier.verify(barcode_val)
    gs1_verification = gs1_match

    external_verification = cross_check_engine.evaluate_all(
        extracted_data=product_info.model_dump(),
        fssai_record=fssai_verification,
        gs1_record=gs1_verification,
        qr_payload=None,
        barcode_detected=barcode_val,
        offline_mode=False
    )

    created_at = get_current_utc_iso()
    extracted_dict = product_info.model_dump()
    compliance_dict = compliance_result.model_dump()

    # Deterministic cryptographic integrity hash
    integrity_hash = compute_analysis_integrity_hash(
        analysis_id=analysis_id,
        created_at=created_at,
        product_name=product_info.product_name or 'Unknown Product',
        score=compliance_result.score,
        status=compliance_result.status,
        extracted_data=extracted_dict,
        compliance_result=compliance_dict
    )

    prod_identity = identity_service.extract_identity(
        product_info=product_info,
        ocr_text=text,
        fssai_verification=fssai_verification,
        gs1_verification=gs1_verification
    )

    # 5B. Misleading Claim Detection Engine for text
    claims_analysis = claim_engine.analyze(
        product_info=product_info,
        ocr_text=text,
        images=[]
    )

    # 6. Save to DB
    db_data = {
        'id': analysis_id,
        'product_name': product_info.product_name or 'Unknown Product',
        'image_filename': "",
        'ocr_text': text,
        'extracted_data': extracted_dict,
        'compliance_result': compliance_dict,
        'score': compliance_result.score,
        'status': compliance_result.status,
        'created_at': created_at,
        'images': [],
        'owner_user_id': owner_user_id or "",
        'organization_id': organization_id or "",
        'integrity_hash': integrity_hash,
        'system_version': SYSTEM_VERSION,
        'ocr_engine_version': OCR_PIPELINE_VERSION,
        'ruleset_version': COMPLIANCE_RULESET_VERSION,
        'product_identity': prod_identity.model_dump(),
        'external_product_verification': pipeline_result.model_dump(),
        'external_verification': external_verification.model_dump() if hasattr(external_verification, 'model_dump') else external_verification,
        'claims_analysis': claims_analysis.model_dump()
    }
    await save_analysis(db_data)
    try:
        from services.review_service import get_or_create_review
        await get_or_create_review(analysis_id)
    except Exception as e:
        logger.warning(f"[REVIEW] Auto-create review failed for analysis {analysis_id}: {e}")
    
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
        owner_user_id=owner_user_id or "",
        organization_id=organization_id or "",
        multilingual=getattr(product_info, 'multilingual', None),
        external_verification=external_verification,
        integrity_hash=integrity_hash,
        system_version=SYSTEM_VERSION,
        ocr_engine_version=OCR_PIPELINE_VERSION,
        ruleset_version=COMPLIANCE_RULESET_VERSION,
        product_identity=prod_identity,
        cross_validation=getattr(prod_identity, 'cross_validation', None),
        external_product_verification=pipeline_result,
        claims_analysis=claims_analysis
    )
