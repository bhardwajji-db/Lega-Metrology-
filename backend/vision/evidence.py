from typing import List, Optional, Dict, Any
from models.schemas import EvidenceItem
from vision.schemas import VisionAnalysisResult

class VisionEvidenceAdapter:
    """
    Adapts Vision Analysis detections into standard MetrCheck EvidenceItem instances
    so they render seamlessly on the existing Evidence Viewer.
    """

    @classmethod
    def generate_evidence_items(
        cls,
        vision_res: VisionAnalysisResult,
        image_index: int = 0,
        image_label: str = "Front"
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []

        # 1. Package Boundary Evidence
        if vision_res.package_boundary.detected and vision_res.package_boundary.bbox:
            items.append(EvidenceItem(
                id=f"cv_bound_{image_index}",
                image_index=image_index,
                image_label=image_label,
                text="Physical Packaging Boundary",
                normalized_value="DETECTED",
                bbox=vision_res.package_boundary.bbox,
                geometry_type="WORD_UNION",
                match_method="SEMANTIC_PANEL",
                confidence=vision_res.package_boundary.confidence,
                evidence_status="VERIFIED",
                evidence_type="DIRECT_OCR",
                explanation=f"Detected package boundary (area ratio: {vision_res.package_boundary.area_ratio*100:.1f}%)",
                field_type="PANEL"
            ))

        # 2. Semantic Regions Evidence
        for reg in vision_res.semantic_regions:
            if reg.detected and reg.bbox:
                items.append(EvidenceItem(
                    id=reg.evidence_id or f"cv_reg_{reg.region_type}_{image_index}",
                    image_index=image_index,
                    image_label=image_label,
                    text=f"{reg.region_type.replace('_', ' ').title()} Region",
                    normalized_value=reg.associated_text or "DETECTED",
                    bbox=reg.bbox,
                    geometry_type="WORD_UNION",
                    match_method="SEMANTIC_PANEL",
                    confidence=reg.confidence,
                    evidence_status="VERIFIED",
                    evidence_type="DIRECT_OCR",
                    explanation=f"Detected {reg.region_type.replace('_', ' ')} zone via {reg.detection_method}",
                    field_type="REGION"
                ))

        # 3. Symbols Evidence
        for sym in vision_res.symbols:
            if sym.detected and sym.bbox:
                items.append(EvidenceItem(
                    id=sym.evidence_id or f"cv_sym_{sym.symbol_type}_{image_index}",
                    image_index=image_index,
                    image_label=image_label,
                    text=f"Statutory Mark: {sym.symbol_type}",
                    normalized_value=sym.symbol_type,
                    bbox=sym.bbox,
                    geometry_type="WORD_UNION",
                    match_method="SEMANTIC_PANEL",
                    confidence=sym.confidence,
                    evidence_status="VERIFIED",
                    evidence_type="DIRECT_OCR",
                    explanation=sym.notes or f"Detected {sym.symbol_type} symbol",
                    field_type="FIELD"
                ))

        # 4. Barcode Evidence
        if vision_res.barcode.detected and vision_res.barcode.bbox:
            items.append(EvidenceItem(
                id=f"cv_barcode_{image_index}",
                image_index=image_index,
                image_label=image_label,
                text="1D Barcode Symbology",
                normalized_value=vision_res.barcode.decoded_value or "DETECTED",
                bbox=vision_res.barcode.bbox,
                geometry_type="WORD_UNION",
                match_method="SEMANTIC_PANEL",
                confidence=vision_res.barcode.confidence,
                evidence_status="VERIFIED",
                evidence_type="DIRECT_OCR",
                explanation="1D Barcode localized via high-frequency gradient bars",
                field_type="FIELD"
            ))

        # 5. QR Code Evidence
        if vision_res.qr_code.detected and vision_res.qr_code.bbox:
            items.append(EvidenceItem(
                id=f"cv_qr_{image_index}",
                image_index=image_index,
                image_label=image_label,
                text="QR Code Symbology",
                normalized_value=vision_res.qr_code.decoded_payload or "DETECTED",
                bbox=vision_res.qr_code.bbox,
                geometry_type="WORD_UNION",
                match_method="SEMANTIC_PANEL",
                confidence=vision_res.qr_code.confidence,
                evidence_status="VERIFIED",
                evidence_type="DIRECT_OCR",
                explanation=vision_res.qr_code.warning or "2D QR code detected and safely decoded",
                field_type="FIELD"
            ))

        return items

vision_evidence_adapter = VisionEvidenceAdapter()
