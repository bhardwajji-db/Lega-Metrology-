"""
MetrCheck AI — Barcode & Live Camera Scanning API Endpoints
Provides real-time frame scanning, barcode/QR detection, and GS1 cross-verification.
"""

import os
import base64
import cv2
import numpy as np
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from pydantic import BaseModel, Field

from services.barcode_service import barcode_service, BarcodeItem, BarcodeVerificationResult, VERIFIED_PRODUCT_REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/barcode", tags=["Barcode & Live Camera Scanner"])

class LiveFrameRequest(BaseModel):
    image_base64: str
    include_text_boxes: bool = True

class LiveDetectionBox(BaseModel):
    label: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]
    type: str  # 'barcode', 'qr', 'declaration', 'panel'
    color: str  # hex color for HUD overlay

class LiveFrameResponse(BaseModel):
    detected: bool
    barcodes: List[BarcodeItem] = Field(default_factory=list)
    hud_boxes: List[LiveDetectionBox] = Field(default_factory=list)
    fps_estimate: float = 0.0
    detected_declarations: Dict[str, str] = Field(default_factory=dict)
    summary: str = ""

class VerifyBarcodeRequest(BaseModel):
    raw_value: str
    symbology: str = "EAN-13"
    brand: Optional[str] = None
    net_quantity: Optional[str] = None
    country_of_origin: Optional[str] = None
    fssai_license: Optional[str] = None
    mrp: Optional[str] = None

def _decode_image_from_bytes_or_base64(raw_bytes: Optional[bytes], b64_str: Optional[str]) -> Optional[np.ndarray]:
    try:
        if raw_bytes:
            nparr = np.frombuffer(raw_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if b64_str:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            data = base64.b64decode(b64_str)
            nparr = np.frombuffer(data, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.debug(f"[Barcode API] Image decode failed: {e}")
    return None

@router.post("/scan", response_model=List[BarcodeItem])
async def scan_barcode_from_upload(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None)
):
    """
    Detect and decode all 1D Barcodes and QR Codes in an uploaded image or base64 frame.
    Automatically enriches decoded barcodes with product master and manufacturer registry data.
    """
    raw_bytes = await file.read() if file else None
    img = _decode_image_from_bytes_or_base64(raw_bytes, image_base64)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image input or format")

    results = barcode_service.detect_and_decode(img)
    # Auto-enrich items with master product data
    for item in results:
        try:
            lookup = await barcode_service.lookup_product_details(item.raw_value)
            if lookup.get("found") and lookup.get("data"):
                pdata = lookup["data"]
                item.registered_data = pdata
                item.product_name = pdata.get("product_name")
                item.brand_name = pdata.get("brand_name")
                item.company_name = pdata.get("company_name")
                item.net_quantity = pdata.get("net_quantity")
                item.category = pdata.get("category")
                item.image_url = pdata.get("image_url")
                if not item.fssai_from_barcode and pdata.get("fssai_license"):
                    item.fssai_from_barcode = pdata.get("fssai_license")
        except Exception:
            pass

    return results

@router.post("/live-frame", response_model=LiveFrameResponse)
async def process_live_camera_frame(req: LiveFrameRequest):
    """
    Real-time lightweight frame analyzer for Live Camera / Webcam Scanner.
    Returns detected barcodes, QR codes, and visual HUD bounding boxes for packaging declarations.
    """
    import time
    t0 = time.perf_counter()

    img = _decode_image_from_bytes_or_base64(None, req.image_base64)
    if img is None:
        raise HTTPException(status_code=400, detail="Failed to decode live camera frame")

    orig_h, orig_w = img.shape[:2]
    max_dim = max(orig_w, orig_h)
    scale = 1.0
    if max_dim > 1080:
        scale = 1080.0 / max_dim
        proc_img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
    else:
        proc_img = img

    h, w = proc_img.shape[:2]
    barcodes = barcode_service.detect_and_decode(proc_img)
    hud_boxes: List[LiveDetectionBox] = []

    # 1. Add Barcode / QR boxes scaled to original dimensions & enrich metadata
    for b in barcodes:
        try:
            lookup = await barcode_service.lookup_product_details(b.raw_value)
            if lookup.get("found") and lookup.get("data"):
                pdata = lookup["data"]
                b.registered_data = pdata
                b.product_name = pdata.get("product_name")
                b.brand_name = pdata.get("brand_name")
                b.company_name = pdata.get("company_name")
                b.net_quantity = pdata.get("net_quantity")
                b.category = pdata.get("category")
                b.image_url = pdata.get("image_url")
                if not b.fssai_from_barcode and pdata.get("fssai_license"):
                    b.fssai_from_barcode = pdata.get("fssai_license")
        except Exception:
            pass

        box = b.bbox or [int(w * 0.25), int(h * 0.6), int(w * 0.75), int(h * 0.85)]
        if scale != 1.0:
            box = [int(box[0] / scale), int(box[1] / scale), int(box[2] / scale), int(box[3] / scale)]
        label_text = f"{b.symbology}: {b.raw_value}"
        if b.brand_name:
            label_text += f" ({b.brand_name})"
        elif b.country_of_origin:
            label_text += f" ({b.country_of_origin})"
        hud_boxes.append(LiveDetectionBox(
            label=label_text,
            confidence=b.confidence,
            bbox=box,
            type="barcode" if "qr" not in b.symbology.lower() else "qr",
            color="#3b82f6" if "qr" not in b.symbology.lower() else "#8b5cf6"  # blue or purple
        ))

    # 2. Fast morphological text-region detector for real-time packaging HUD
    if req.include_text_boxes:
        try:
            gray = cv2.cvtColor(proc_img, cv2.COLOR_BGR2GRAY)
            grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3)))
            contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            candidate_boxes = []
            for c in contours:
                cx, cy, cw, ch = cv2.boundingRect(c)
                if 25 <= cw <= w * 0.85 and 12 <= ch <= h * 0.35 and (cw * ch) > 350:
                    bx1 = int(cx / scale) if scale != 1.0 else cx
                    by1 = int(cy / scale) if scale != 1.0 else cy
                    bx2 = int((cx + cw) / scale) if scale != 1.0 else (cx + cw)
                    by2 = int((cy + ch) / scale) if scale != 1.0 else (cy + ch)
                    candidate_boxes.append([bx1, by1, bx2, by2])

            candidate_boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
            for idx, cbox in enumerate(candidate_boxes[:4]):
                overlap = False
                for bc_box in hud_boxes:
                    ix1 = max(cbox[0], bc_box.bbox[0])
                    iy1 = max(cbox[1], bc_box.bbox[1])
                    ix2 = min(cbox[2], bc_box.bbox[2])
                    iy2 = min(cbox[3], bc_box.bbox[3])
                    if ix2 > ix1 and iy2 > iy1:
                        overlap = True
                        break
                if not overlap:
                    hud_boxes.append(LiveDetectionBox(
                        label=f"Text Declaration #{idx+1}",
                        confidence=0.88,
                        bbox=cbox,
                        type="declaration",
                        color="#10b981"
                    ))
        except Exception as e:
            logger.debug(f"[Live HUD] Text contour error: {e}")

    elapsed_ms = (time.perf_counter() - t0) * 1000
    fps_est = round(1000.0 / max(elapsed_ms, 1.0), 1)

    return LiveFrameResponse(
        detected=bool(barcodes or hud_boxes),
        barcodes=barcodes,
        hud_boxes=hud_boxes,
        fps_estimate=fps_est,
        summary=f"Processed in {elapsed_ms:.1f}ms ({len(barcodes)} barcode(s), {len(hud_boxes)} visual targets localized)"
    )

@router.post("/verify", response_model=BarcodeVerificationResult)
async def verify_barcode_against_product(req: VerifyBarcodeRequest):
    """
    Cross-verify a scanned barcode value against GS1 product master, Open Food Facts, and on-pack declarations.
    """
    clean_code = req.raw_value.strip()
    c, f, p = barcode_service.resolve_country_of_origin(clean_code)
    is_valid = barcode_service.validate_checksum(clean_code) if len(clean_code) in (8, 12, 13, 14) else True

    # Retrieve real product details from local master registry, SQLite cache, or live Open Food Facts
    lookup_res = await barcode_service.lookup_product_details(clean_code)
    reg_data = lookup_res.get("data") if lookup_res.get("found") else None

    item = BarcodeItem(
        raw_value=clean_code,
        symbology=req.symbology,
        confidence=0.98,
        is_valid_checksum=is_valid,
        country_of_origin=c,
        country_flag=f,
        gs1_prefix=p,
        registered_data=reg_data,
        product_name=reg_data.get("product_name") if reg_data else None,
        brand_name=reg_data.get("brand_name") if reg_data else None,
        company_name=reg_data.get("company_name") if reg_data else None,
        net_quantity=reg_data.get("net_quantity") if reg_data else None,
        category=reg_data.get("category") if reg_data else None
    )

    class MockExtracted:
        brand = req.brand
        net_quantity = req.net_quantity
        country_of_origin = req.country_of_origin
        fssai_license = req.fssai_license
        mrp = req.mrp

    result = barcode_service.verify_against_declarations(item, MockExtracted(), reg_data=reg_data)
    return result

@router.get("/lookup/{gtin}")
async def lookup_gtin_master(gtin: str):
    """
    Retrieve product master record for a given GTIN/barcode across local registry, SQLite cache, and live Open Food Facts.
    """
    clean_gtin = "".join(filter(str.isdigit, gtin))
    res = await barcode_service.lookup_product_details(clean_gtin)
    return res

