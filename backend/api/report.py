"""
MetrCheck AI — Report API Endpoint (Phase 5C & 5D)

Returns a professional PDF report for a given analysis ID.
Consumes the existing analysis result — does NOT recalculate anything.
Supports both real analyses from SQLite and instant demo fixtures.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from database.db import get_analysis
from services.report_service import generate_pdf_report
from models.schemas import (
    AnalysisResponse, ComplianceResult, ComplianceCheck, ProductInfo, OCRResult,
    ProductImageEvidence,
)
import json
import io
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
router = APIRouter()


@router.get("/report/{id}")
async def get_report(id: str):
    """Generate and return a professional PDF compliance report for the given analysis."""
    data = await get_analysis(id)
    
    # ── Demo fallback if not in database yet ──
    if not data and (id.startswith("demo-") or id in ("1", "2", "3")):
        from api.demo import get_demo_case
        case_id = "1"
        if id in ("1", "2", "3"):
            case_id = id
        elif id.startswith("demo-"):
            parts = id.split("-")
            if len(parts) >= 2 and parts[1] in ("1", "2", "3"):
                case_id = parts[1]
        try:
            demo_analysis = await get_demo_case(case_id)
            pdf_bytes = generate_pdf_report(demo_analysis)
            filename = f"metrcheck-report-{id}.pdf"
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"'
                }
            )
        except Exception:
            pass

    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # ── Build images list (same logic as history.py) ──
    images_list = []
    if 'images' in data and data['images']:
        try:
            images_list = json.loads(data['images'])
        except Exception:
            images_list = []

    if not images_list:
        images_list = [{
            "filename": data['image_filename'],
            "image_url": f"/uploads/{data['image_filename']}",
            "label": "Front",
            "ocr_text": data['ocr_text'] or '',
            "word_count": len(data['ocr_text'].split()) if data['ocr_text'] else 0
        }]

    # ── Build compliance result with recommendations ──
    comp_dict = json.loads(data['compliance_result'])
    if 'recommendations' not in comp_dict or not comp_dict['recommendations']:
        from compliance.recommendations import generate_recommendations
        checks = [ComplianceCheck(**c) for c in comp_dict.get('checks', [])]
        comp_dict['recommendations'] = [r.model_dump() for r in generate_recommendations(checks)]

    compliance_res = ComplianceResult(**comp_dict)

    # ── Build full AnalysisResponse ──
    analysis = AnalysisResponse(
        id=data['id'],
        product_name=data['product_name'],
        image_url=f"/uploads/{data['image_filename']}",
        images=images_list,
        ocr_result={
            "full_text": data['ocr_text'] or '',
            "words": [],
            "language": "eng",
            "processing_time": 0.0
        },
        product_info=json.loads(data['extracted_data']),
        compliance_result=compliance_res,
        recommendations=compliance_res.recommendations,
        created_at=data['created_at']
    )

    # ── Generate PDF ──
    pdf_bytes = generate_pdf_report(analysis)

    # ── Return as downloadable PDF ──
    filename = f"metrcheck-report-{id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


async def _get_full_analysis_object(id: str) -> AnalysisResponse:
    """Helper to load or construct the AnalysisResponse for an ID."""
    data = await get_analysis(id)
    if not data and (id.startswith("demo-") or id in ("1", "2", "3")):
        from api.demo import get_demo_case
        clean_id = id.replace("demo-", "") if id.startswith("demo-") else id
        try:
            demo_resp = await get_demo_case(clean_id)
            return demo_resp
        except Exception:
            pass
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    images_list = []
    if 'images' in data and data['images']:
        try:
            raw_imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
            images_list = [ProductImageEvidence(**im) for im in raw_imgs]
        except Exception:
            images_list = []

    if not images_list:
        images_list = [
            ProductImageEvidence(
                filename=data.get('image_filename', 'placeholder.png'),
                image_url=f"/uploads/{data.get('image_filename', 'placeholder.png')}",
                label='Front',
                ocr_text=data.get('ocr_text', '')
            )
        ]

    comp_dict = json.loads(data['compliance_result'])
    if 'recommendations' not in comp_dict or not comp_dict['recommendations']:
        from compliance.recommendations import generate_recommendations
        checks = [ComplianceCheck(**c) for c in comp_dict.get('checks', [])]
        comp_dict['recommendations'] = [r.model_dump() for r in generate_recommendations(checks)]

    compliance_res = ComplianceResult(**comp_dict)
    product_info = ProductInfo(**json.loads(data['extracted_data']))
    
    from compliance.rules.legal_metrology import compute_font_size_and_readability
    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        images=images_list,
        checks=compliance_res.checks
    )

    return AnalysisResponse(
        id=data['id'],
        product_name=data['product_name'],
        image_url=f"/uploads/{data['image_filename']}",
        images=images_list,
        ocr_result=OCRResult(
            full_text=data['ocr_text'] or '',
            words=[],
            language="eng",
            processing_time=0.0
        ),
        product_info=product_info,
        compliance_result=compliance_res,
        recommendations=compliance_res.recommendations,
        created_at=data['created_at'],
        font_size_analysis=font_size_analysis
    )


@router.get("/report/{id}/csv")
async def get_report_csv(id: str):
    """Generate and return an editable CSV spreadsheet report for the given analysis."""
    analysis = await _get_full_analysis_object(id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header Metadata
    writer.writerow(["METRCHECK AI — STATUTORY COMPLIANCE INSPECTION REPORT"])
    writer.writerow(["Inspection ID", analysis.id])
    writer.writerow(["Product Name", analysis.product_name])
    writer.writerow(["Inspection Timestamp", analysis.created_at])
    writer.writerow(["Overall Compliance Score", f"{analysis.compliance_result.score} / 100"])
    writer.writerow(["Overall Status", analysis.compliance_result.status])
    writer.writerow(["Passed Rules", analysis.compliance_result.passed_rules])
    writer.writerow(["Failed Rules", analysis.compliance_result.failed_rules])
    writer.writerow(["Warning Rules", analysis.compliance_result.warning_rules])
    writer.writerow(["Review Required Rules", analysis.compliance_result.needs_review_rules])
    writer.writerow([])
    
    # Rule 12 Font Size & Readability
    if analysis.font_size_analysis:
        writer.writerow(["RULE 12 FONT SIZE & READABILITY ASSESSMENT"])
        writer.writerow(["Readability Score", f"{analysis.font_size_analysis.readability_score} / 100 ({analysis.font_size_analysis.readability_tier})"])
        writer.writerow(["Estimated Net Qty Font Height", f"{analysis.font_size_analysis.net_quantity_font_height_mm} mm"])
        writer.writerow(["Statutory Minimum Required", f"{analysis.font_size_analysis.min_required_font_height_mm} mm"])
        writer.writerow(["Rule 12 Compliance Verdict", analysis.font_size_analysis.rule_12_verdict])
        writer.writerow([])
        
    # Detailed Rule Checks
    writer.writerow(["RULE-BY-RULE COMPLIANCE CHECKLIST"])
    writer.writerow([
        "Rule ID", "Domain", "Field Label", "Status", "Detected Value",
        "Statutory Source", "Statutory Reference", "Reason / Finding", "Confidence (%)"
    ])
    
    for c in analysis.compliance_result.checks:
        writer.writerow([
            c.rule_id,
            c.domain,
            c.field_label,
            c.status,
            c.detected_value or "NOT DETECTED",
            c.source_name or "Legal Metrology Rules 2011",
            c.source_reference or "",
            c.reason or c.explanation or "",
            f"{c.confidence:.1f}" if c.confidence else "N/A"
        ])
        
    writer.writerow([])
    # Recommendations
    if analysis.recommendations:
        writer.writerow(["RECOMMENDED CORRECTIVE ACTIONS & REMEDIATION"])
        writer.writerow(["Rule ID", "Priority", "Title", "Issue Description", "Statutory Action Step", "Legal Citation"])
        for r in analysis.recommendations:
            writer.writerow([
                r.rule_id,
                r.priority,
                r.title,
                r.issue,
                r.recommended_action,
                f"{r.source_name or ''} {r.source_reference or ''}".strip()
            ])
            
    csv_content = output.getvalue()
    filename = f"metrcheck-inspection-{id}.csv"
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/report/{id}/json")
async def get_report_json(id: str):
    """Return the complete inspection record in JSON format for automated ingestion."""
    analysis = await _get_full_analysis_object(id)
    json_str = analysis.model_dump_json(indent=2)
    filename = f"metrcheck-inspection-{id}.json"
    return StreamingResponse(
        io.BytesIO(json_str.encode('utf-8')),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/report/{id}/xlsx")
async def get_report_xlsx(id: str):
    """Generate and return an editable, professional multi-sheet Excel (.xlsx) compliance inspection report."""
    analysis = await _get_full_analysis_object(id)

    wb = Workbook()

    # ── Styles & Palette ──
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill_dark = PatternFill(fill_type="solid", start_color="1E293B", end_color="1E293B")
    title_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    title_fill = PatternFill(fill_type="solid", start_color="312E81", end_color="312E81")
    section_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    section_fill = PatternFill(fill_type="solid", start_color="1E293B", end_color="1E293B")

    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=11)
    label_fill = PatternFill(fill_type="solid", start_color="F8FAFC", end_color="F8FAFC")

    thin_side = Side(style="thin", color="CBD5E1")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    align_left = Alignment(horizontal="left", vertical="center")
    align_center = Alignment(horizontal="center", vertical="center")
    align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # Status cell conditional styling
    status_styles = {
        "PASS": (Font(name="Calibri", size=11, bold=True, color="065F46"), PatternFill(fill_type="solid", start_color="D1FAE5", end_color="D1FAE5")),
        "COMPLIANT": (Font(name="Calibri", size=11, bold=True, color="065F46"), PatternFill(fill_type="solid", start_color="D1FAE5", end_color="D1FAE5")),
        "FAIL": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "NON_COMPLIANT": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "VIOLATION": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "WARNING": (Font(name="Calibri", size=11, bold=True, color="92400E"), PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")),
        "CAUTION": (Font(name="Calibri", size=11, bold=True, color="92400E"), PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")),
        "NEEDS_REVIEW": (Font(name="Calibri", size=11, bold=True, color="9A3412"), PatternFill(fill_type="solid", start_color="FFEDD5", end_color="FFEDD5")),
        "REVIEW": (Font(name="Calibri", size=11, bold=True, color="9A3412"), PatternFill(fill_type="solid", start_color="FFEDD5", end_color="FFEDD5")),
        "NOT_APPLICABLE": (Font(name="Calibri", size=11, bold=True, color="475569"), PatternFill(fill_type="solid", start_color="F1F5F9", end_color="F1F5F9")),
    }

    priority_styles = {
        "HIGH": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "MEDIUM": (Font(name="Calibri", size=11, bold=True, color="92400E"), PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")),
        "LOW": (Font(name="Calibri", size=11, bold=True, color="1E40AF"), PatternFill(fill_type="solid", start_color="DBEAFE", end_color="DBEAFE")),
        "INFO": (Font(name="Calibri", size=11, bold=True, color="1E40AF"), PatternFill(fill_type="solid", start_color="DBEAFE", end_color="DBEAFE")),
    }

    # ══════════════════════════════════════════════════════════════════
    # SHEET 1: Summary
    # ══════════════════════════════════════════════════════════════════
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.views.sheetView[0].showGridLines = True

    # Merged title row
    ws_summary.merge_cells("A1:B1")
    title_cell = ws_summary["A1"]
    title_cell.value = "METRCHECK AI — STATUTORY COMPLIANCE INSPECTION REPORT"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = align_center
    ws_summary.row_dimensions[1].height = 36
    ws_summary["A1"].border = thin_border
    ws_summary["B1"].border = thin_border

    summary_data = [
        ("Inspection ID", analysis.id),
        ("Product Name", analysis.product_name),
        ("Inspection Timestamp", analysis.created_at),
        ("Overall Compliance Score", f"{analysis.compliance_result.score} / 100"),
        ("Overall Status", analysis.compliance_result.status),
        ("Passed Rules", analysis.compliance_result.passed_rules),
        ("Failed Rules", analysis.compliance_result.failed_rules),
        ("Warning Rules", analysis.compliance_result.warning_rules),
        ("Review Required Rules", analysis.compliance_result.needs_review_rules),
        ("Not Applicable Rules", analysis.compliance_result.not_applicable_rules),
    ]

    for idx, (lbl, val) in enumerate(summary_data, start=2):
        row_num = idx
        ws_summary.row_dimensions[row_num].height = 22
        cell_a = ws_summary.cell(row=row_num, column=1, value=lbl)
        cell_b = ws_summary.cell(row=row_num, column=2, value=val)

        cell_a.font = bold_font
        cell_a.fill = label_fill
        cell_a.alignment = align_left
        cell_a.border = thin_border

        cell_b.font = regular_font
        cell_b.alignment = align_left
        cell_b.border = thin_border

        if lbl == "Overall Status" and str(val).upper() in status_styles:
            s_font, s_fill = status_styles[str(val).upper()]
            cell_b.font = s_font
            cell_b.fill = s_fill

    # ══════════════════════════════════════════════════════════════════
    # SHEET 2: Font Size (Rule 12) (only if font_size_analysis present)
    # ══════════════════════════════════════════════════════════════════
    if analysis.font_size_analysis:
        ws_font = wb.create_sheet(title="Font Size (Rule 12)")
        ws_font.views.sheetView[0].showGridLines = True

        ws_font.merge_cells("A1:B1")
        font_title_cell = ws_font["A1"]
        font_title_cell.value = "RULE 12 FONT SIZE & READABILITY ASSESSMENT"
        font_title_cell.font = section_font
        font_title_cell.fill = section_fill
        font_title_cell.alignment = align_center
        ws_font.row_dimensions[1].height = 32
        ws_font["A1"].border = thin_border
        ws_font["B1"].border = thin_border

        net_qty_mm = (
            f"{analysis.font_size_analysis.net_quantity_font_height_mm} mm"
            if analysis.font_size_analysis.net_quantity_font_height_mm is not None
            else "N/A"
        )
        min_req_mm = (
            f"{analysis.font_size_analysis.min_required_font_height_mm} mm"
            if analysis.font_size_analysis.min_required_font_height_mm is not None
            else "N/A"
        )
        readability_score_val = (
            f"{analysis.font_size_analysis.readability_score} / 100 ({analysis.font_size_analysis.readability_tier})"
        )

        font_data = [
            ("Readability Score", readability_score_val),
            ("Readability Tier", analysis.font_size_analysis.readability_tier or "N/A"),
            ("Estimated Net Qty Font Height", net_qty_mm),
            ("Statutory Minimum Required", min_req_mm),
            ("Rule 12 Compliance Verdict", analysis.font_size_analysis.rule_12_verdict or "N/A"),
            ("Assessment Details", analysis.font_size_analysis.details or "N/A"),
        ]

        for idx, (lbl, val) in enumerate(font_data, start=2):
            row_num = idx
            ws_font.row_dimensions[row_num].height = 24
            cell_a = ws_font.cell(row=row_num, column=1, value=lbl)
            cell_b = ws_font.cell(row=row_num, column=2, value=val)

            cell_a.font = bold_font
            cell_a.fill = label_fill
            cell_a.alignment = align_left
            cell_a.border = thin_border

            cell_b.font = regular_font
            cell_b.alignment = align_left
            cell_b.border = thin_border

            if lbl == "Readability Tier":
                tier_upper = str(val).upper()
                if tier_upper in ("EXCELLENT", "GOOD"):
                    cell_b.font = Font(name="Calibri", size=11, bold=True, color="065F46")
                    cell_b.fill = PatternFill(fill_type="solid", start_color="D1FAE5", end_color="D1FAE5")
                elif tier_upper in ("MODERATE", "WARNING"):
                    cell_b.font = Font(name="Calibri", size=11, bold=True, color="92400E")
                    cell_b.fill = PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")
                elif tier_upper in ("POOR", "FAIL"):
                    cell_b.font = Font(name="Calibri", size=11, bold=True, color="991B1B")
                    cell_b.fill = PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")

    # ══════════════════════════════════════════════════════════════════
    # SHEET 3: Rule-by-Rule Checklist
    # ══════════════════════════════════════════════════════════════════
    ws_checks = wb.create_sheet(title="Rule-by-Rule Checklist")
    ws_checks.views.sheetView[0].showGridLines = True
    ws_checks.freeze_panes = "A2"

    check_headers = [
        "Rule ID", "Domain", "Field Label", "Status", "Detected Value",
        "Statutory Source", "Statutory Reference", "Reason / Finding", "Confidence (%)"
    ]
    ws_checks.row_dimensions[1].height = 26
    for col_idx, h_text in enumerate(check_headers, start=1):
        c = ws_checks.cell(row=1, column=col_idx, value=h_text)
        c.font = header_font
        c.fill = header_fill_dark
        c.alignment = align_center
        c.border = thin_border

    checks = analysis.compliance_result.checks if analysis.compliance_result else []
    for row_idx, check in enumerate(checks, start=2):
        ws_checks.row_dimensions[row_idx].height = 22
        conf_str = f"{check.confidence:.1f}" if check.confidence is not None else "N/A"
        row_values = [
            check.rule_id,
            check.domain,
            check.field_label,
            check.status,
            check.detected_value or "NOT DETECTED",
            check.source_name or "Legal Metrology Rules 2011",
            check.source_reference or "",
            check.reason or check.explanation or "",
            conf_str,
        ]
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws_checks.cell(row=row_idx, column=col_idx, value=val)
            cell.font = regular_font
            cell.alignment = align_wrap if col_idx in (5, 8) else align_left
            cell.border = thin_border

            # Status column (Col 4)
            if col_idx == 4:
                st_upper = str(val).upper()
                if st_upper in status_styles:
                    s_font, s_fill = status_styles[st_upper]
                    cell.font = s_font
                    cell.fill = s_fill
                    cell.alignment = align_center

            # Confidence column (Col 9)
            if col_idx == 9:
                cell.alignment = align_center

    # ══════════════════════════════════════════════════════════════════
    # SHEET 4: Recommendations
    # ══════════════════════════════════════════════════════════════════
    recs = analysis.recommendations or []
    if recs:
        ws_recs = wb.create_sheet(title="Recommendations")
        ws_recs.views.sheetView[0].showGridLines = True
        ws_recs.freeze_panes = "A2"

        rec_headers = ["Rule ID", "Priority", "Title", "Issue Description", "Statutory Action Step", "Legal Citation"]
        ws_recs.row_dimensions[1].height = 26
        for col_idx, h_text in enumerate(rec_headers, start=1):
            c = ws_recs.cell(row=1, column=col_idx, value=h_text)
            c.font = header_font
            c.fill = header_fill_dark
            c.alignment = align_center
            c.border = thin_border

        for row_idx, r in enumerate(recs, start=2):
            ws_recs.row_dimensions[row_idx].height = 24
            legal_cite = f"{r.source_name or ''} {r.source_reference or ''}".strip()
            row_values = [
                r.rule_id,
                r.priority,
                r.title,
                r.issue,
                r.recommended_action,
                legal_cite,
            ]
            for col_idx, val in enumerate(row_values, start=1):
                cell = ws_recs.cell(row=row_idx, column=col_idx, value=val)
                cell.font = regular_font
                cell.alignment = align_wrap if col_idx in (3, 4, 5) else align_left
                cell.border = thin_border

                # Priority column (Col 2)
                if col_idx == 2:
                    p_upper = str(val).upper()
                    if p_upper in priority_styles:
                        p_font, p_fill = priority_styles[p_upper]
                        cell.font = p_font
                        cell.fill = p_fill
                        cell.alignment = align_center

    # ══════════════════════════════════════════════════════════════════
    # Auto-adjust column widths for all sheets
    # ══════════════════════════════════════════════════════════════════
    for sheet in wb.worksheets:
        for col in sheet.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for cell in col:
                if cell.value is not None:
                    if cell.row == 1 and sheet.title in ("Summary", "Font Size (Rule 12)"):
                        continue
                    val_str = str(cell.value)
                    lines = val_str.split("\n")
                    line_len = max(len(l) for l in lines) if lines else len(val_str)
                    if line_len > max_len:
                        max_len = line_len
            min_w = 16 if sheet.title in ("Summary", "Font Size (Rule 12)") else 12
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, min_w), 60)

    # ══════════════════════════════════════════════════════════════════
    # Save & Return StreamingResponse
    # ══════════════════════════════════════════════════════════════════
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    filename = f"metrcheck-inspection-{id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
